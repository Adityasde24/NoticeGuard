"""
NoticeGuard - Gemma Extraction Module.
Connects locally to Ollama (127.0.0.1:11434) to run narrow structured extraction
passes with schema validation and 1 retry.
Includes an intelligent deterministic fallback parser when Ollama is offline.
"""

import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from segment import normalize_unicode_nfc, normalize_digits

# Default Ollama local endpoint
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma2:latest"
FALLBACK_MODEL = "gemma:2b"

def is_ollama_available(base_url: str = DEFAULT_OLLAMA_URL) -> bool:
    """Checks if local Ollama daemon is reachable on 127.0.0.1."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "NoticeGuard/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def query_local_ollama(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
    temperature: float = 0.1,
    timeout: int = 40
) -> Optional[str]:
    """
    Sends a local HTTP POST request to Ollama on 127.0.0.1 without any external network calls.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": temperature
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            return res_json.get("response", "").strip()
    except Exception as e:
        # Fallback to secondary model if first fails
        if model != FALLBACK_MODEL:
            try:
                payload["model"] = FALLBACK_MODEL
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{base_url}/api/generate",
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    res_json = json.loads(response.read().decode("utf-8"))
                    return res_json.get("response", "").strip()
            except Exception:
                pass
        return None

def extract_json_from_llm_response(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extracts JSON object from LLM response (handling markdown fences)."""
    if not text:
        return None
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
    
    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        # Try finding outermost { ... }
        match = re.search(r'(\{[\s\S]*\})', cleaned)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None

def deterministic_fallback_extraction(text: str, passages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    High-precision deterministic rule-based extractor for legal notices.
    Used when Ollama is offline or for rapid offline testing.
    Extracts sender, recipient, demand, amounts, deadlines, and consequences.
    """
    norm_text = normalize_unicode_nfc(text)
    ascii_text = normalize_digits(norm_text)
    
    facts = {
        "sender": "Unknown Sender",
        "sender_quote": "",
        "recipient": "Unknown Recipient",
        "recipient_quote": "",
        "demand": "Payment or compliance demanded",
        "demand_quote": "",
        "amount": None,
        "amount_quote": "",
        "deadline_raw": "None specified",
        "deadline_quote": "",
        "relative_days": None,
        "is_ambiguous": False,
        "consequence": "Legal proceedings in court of law",
        "consequence_quote": "",
        "urgency": "MEDIUM"
    }

    # 1. Recipient extraction (To / To: / Shri / Mr. / Ms. / Tenant)
    to_match = re.search(r"(?i)\bTo,?\s*\n+([^\n,]{3,60})", norm_text)
    if to_match:
        facts["recipient"] = to_match.group(1).strip()
        facts["recipient_quote"] = to_match.group(0).strip()
    else:
        # Check Hindi / Telugu recipient patterns
        hi_to = re.search(r"(?:प्रति|सेवा\s*में),?\s*\n+([^\n,]{3,60})", norm_text)
        if hi_to:
            facts["recipient"] = hi_to.group(1).strip()
            facts["recipient_quote"] = hi_to.group(0).strip()

    # 2. Sender / Advocate extraction (Under instructions from / on behalf of / Advocate)
    sender_match = re.search(r"(?i)(?:under\s+instructions\s+from|on\s+behalf\s+of\s+my\s+client,?\s*)([^\n,\.]{3,70})", norm_text)
    if sender_match:
        facts["sender"] = sender_match.group(1).strip()
        facts["sender_quote"] = sender_match.group(0).strip()
    else:
        adv_match = re.search(r"(?i)([A-Z][a-zA-Z\.\s]{2,40}),?\s*Advocate", norm_text)
        if adv_match:
            facts["sender"] = f"{adv_match.group(1).strip()} (Advocate)"
            facts["sender_quote"] = adv_match.group(0).strip()

    # 3. Amount extraction (e.g. Rs. 45,000 / ₹1,20,000 / 50000/-)
    amt_match = re.search(r"(?:Rs\.?|INR|₹|रु\.?)\s*([\d,]+(?:\.\d{2})?)\b|-?/?\s*([\d,]+)\s*(?:/-\s*|rupees)", ascii_text, re.IGNORECASE)
    if amt_match:
        amt_str = amt_match.group(1) or amt_match.group(2)
        clean_amt = re.sub(r'[^\d]', '', amt_str)
        if clean_amt:
            facts["amount"] = int(clean_amt)
            # Find the corresponding original quote
            orig_match = re.search(r"(?:Rs\.?|INR|₹|रु\.?)\s*[\d,]+(?:\.\d{2})?(?:/-)?", norm_text, re.IGNORECASE)
            if orig_match:
                facts["amount_quote"] = orig_match.group(0)

    # 4. Deadline extraction
    from timeline import parse_relative_deadline, is_ambiguous_deadline
    
    # Check relative days
    rel_match = re.search(r"(?i)\b(?:within|period\s+of)\s+(\d+)\s+days?\b", ascii_text)
    if rel_match:
        facts["relative_days"] = int(rel_match.group(1))
        facts["deadline_raw"] = f"Within {rel_match.group(1)} days of receipt"
        facts["deadline_quote"] = rel_match.group(0)
    else:
        # Check Hindi relative days
        hi_days = re.search(r"(\d+)\s+दिनों?\s+के\s+(?:भीतर|अंदर)", ascii_text)
        if hi_days:
            facts["relative_days"] = int(hi_days.group(1))
            facts["deadline_raw"] = f"{hi_days.group(1)} दिनों के भीतर"
            facts["deadline_quote"] = hi_days.group(0)
        else:
            # Check Telugu relative days
            te_days = re.search(r"(\d+)\s+రోజుల్(?:లోగా|లో)", ascii_text)
            if te_days:
                facts["relative_days"] = int(te_days.group(1))
                facts["deadline_raw"] = f"{te_days.group(1)} రోజుల్లోగా"
                facts["deadline_quote"] = te_days.group(0)

    if not facts["deadline_quote"]:
        if is_ambiguous_deadline(norm_text):
            facts["is_ambiguous"] = True
            facts["deadline_raw"] = "Immediately / Forthwith"
            for amb in ["forthwith", "immediately", "without any delay", "तत्काल", "तुरंत", "వెంటనే"]:
                if amb.lower() in norm_text.lower():
                    facts["deadline_quote"] = amb
                    break

    # 5. Demand & Consequence extraction
    # Look for demand clauses (call upon you / demand / pay / vacate)
    demand_regex = r"(?i)(?:hereby\s+call\s+upon\s+you\s+to|demand\s+that\s+you|pay\s+the\s+sum\s+of|vacate\s+and\s+hand\s+over)[^\.\n]+"
    d_m = re.search(demand_regex, norm_text)
    if d_m:
        facts["demand"] = d_m.group(0).strip()
        facts["demand_quote"] = d_m.group(0).strip()

    # Look for consequences (failing which / will initiate legal proceedings / Section 138 / police)
    cons_regex = r"(?i)(?:failing\s+which|in\s+default\s+whereof|otherwise)[^\.\n]+(?:legal\s+proceedings|civil|criminal|court|action)[^\.\n]*"
    c_m = re.search(cons_regex, norm_text)
    if c_m:
        facts["consequence"] = c_m.group(0).strip()
        facts["consequence_quote"] = c_m.group(0).strip()

    # Urgency setting
    if facts.get("relative_days") and facts["relative_days"] <= 7:
        facts["urgency"] = "HIGH"
    elif facts.get("relative_days") and facts["relative_days"] <= 15:
        facts["urgency"] = "MEDIUM"
    elif facts.get("is_ambiguous"):
        facts["urgency"] = "HIGH"

    return facts

EXTRACTION_SYSTEM_PROMPT = """You are a specialized legal document triage assistant for NoticeGuard.
Your job is to extract factual entities from legal notices into a strict JSON schema.
RULES:
1. Always return ONLY valid JSON.
2. For EVERY extracted fact, include the EXACT verbatim quote from the text.
3. Do NOT invent or extrapolate facts. If not stated, use null or "Unknown".
4. Do NOT provide legal advice or verdicts.

SCHEMA:
{
  "sender": string,
  "sender_quote": string,
  "recipient": string,
  "recipient_quote": string,
  "demand": string,
  "demand_quote": string,
  "amount": number or null,
  "amount_quote": string,
  "deadline_raw": string,
  "deadline_quote": string,
  "relative_days": number or null,
  "is_ambiguous": boolean,
  "consequence": string,
  "consequence_quote": string,
  "urgency": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
}
"""

def extract_facts(
    text: str,
    passages: List[Dict[str, Any]],
    base_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL
) -> Dict[str, Any]:
    """
    Main extraction function.
    Attempts local Gemma via Ollama with 1 retry on invalid schema.
    Falls back gracefully to high-precision deterministic extractor if Ollama is not available.
    """
    if is_ollama_available(base_url):
        prompt = f"Extract factual entities from this legal notice:\n\n\"\"\"\n{text[:4000]}\n\"\"\"\n\nReturn strict JSON schema only."
        
        response = query_local_ollama(
            prompt=prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            model=model,
            base_url=base_url
        )
        
        parsed = extract_json_from_llm_response(response) if response else None
        
        # 1 Retry if JSON invalid
        if not parsed and response:
            retry_prompt = f"Your previous response was not valid JSON. Please return ONLY valid JSON conforming to the schema for this text:\n\n{text[:3000]}"
            retry_resp = query_local_ollama(
                prompt=retry_prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                model=model,
                base_url=base_url
            )
            parsed = extract_json_from_llm_response(retry_resp) if retry_resp else None

        if parsed and isinstance(parsed, dict) and "sender" in parsed:
            return parsed

    # Deterministic fallback
    return deterministic_fallback_extraction(text, passages)
