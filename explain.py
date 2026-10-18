"""
NoticeGuard - Plain-Language Explanation Module.
Produces calm, non-intimidating explanations for each key legal passage.
Every item is strictly tagged with:
- STATED: Verbatim, verified fact stated in the notice.
- INTERPRETATION: Contextual meaning in plain language (not legal advice).
- UNKNOWN: Vital facts the notice omits or fails to address.
"""

import re
from typing import List, Dict, Any, Optional
from segment import normalize_unicode_nfc
from extract import is_ollama_available, query_local_ollama, extract_json_from_llm_response, DEFAULT_MODEL
from guardrails import sanitize_output_verdicts

EXPLAIN_SYSTEM_PROMPT = """You are NoticeGuard's calm legal interpreter.
Your role is to explain legal notice passages in calm, reassuring, plain English for a student or freelancer.
CRITICAL RULES:
1. Label every point strictly as "STATED", "INTERPRETATION", or "UNKNOWN".
2. STATED points must directly reflect what is written.
3. INTERPRETATION points explain what it means in simple terms.
4. UNKNOWN points highlight crucial details that the notice fails to state.
5. NEVER say "you are guilty" or "this notice is illegal". No legal verdicts.
6. Return JSON only.

SCHEMA:
[
  {
    "passage_id": "P1",
    "quote": "verbatim text from passage",
    "stated": "calm plain-language summary of what is directly stated",
    "interpretation": "plain meaning of the clause without fear-mongering",
    "unknown": "what the passage leaves unsaid or does not clarify"
  }
]
"""

def generate_plain_explanation(
    passages: List[Dict[str, Any]],
    verified_facts: Dict[str, Any],
    base_url: str = "http://127.0.0.1:11434",
    model: str = DEFAULT_MODEL,
    force_mock: bool = False
) -> List[Dict[str, Any]]:
    """
    Generates plain-language breakdowns for document passages.
    Uses local Gemma when available; falls back to deterministic rule-based generator
    if Ollama is offline or force_mock is True.
    """
    if not force_mock and is_ollama_available(base_url) and len(passages) > 0:
        # Prepare condensed passages text
        passages_text = "\n\n".join([f"[{p['id']}]: {p['text']}" for p in passages[:8]])
        prompt = f"Explain these legal notice passages for a regular person:\n\n{passages_text}\n\nReturn JSON array only."
        
        response = query_local_ollama(
            prompt=prompt,
            system_prompt=EXPLAIN_SYSTEM_PROMPT,
            model=model,
            base_url=base_url
        )
        
        parsed = extract_json_from_llm_response(response) if response else None
        if parsed and isinstance(parsed, list):
            # Sanitize verdicts from model output
            for item in parsed:
                item["stated"] = sanitize_output_verdicts(item.get("stated", ""))
                item["interpretation"] = sanitize_output_verdicts(item.get("interpretation", ""))
                item["unknown"] = sanitize_output_verdicts(item.get("unknown", ""))
            return parsed

    # Deterministic fallback generator
    explanations = []
    for p in passages:
        p_text = p.get("text", "")
        p_id = p.get("id", "")
        
        stated_text = ""
        interp_text = ""
        unknown_text = ""
        
        p_lower = p_text.lower()
        
        if "under instructions from" in p_lower or "on behalf of" in p_lower or "advocate" in p_lower:
            stated_text = "The sender's advocate states that they are authorized to send this formal notice on behalf of their client."
            interp_text = "This identifies who is making the claim and who their legal representative is."
            unknown_text = "The notice does not prove whether the advocate holds an executed power of attorney or vakalatnama."
        elif "sum of" in p_lower or "rs." in p_lower or "₹" in p_lower or "amount" in p_lower or "balance" in p_lower:
            stated_text = "The sender states that a specific financial balance or debt is outstanding and demands its payment."
            interp_text = "The sender is asserting an unpaid monetary balance. A claim in a notice is not a court judgment."
            unknown_text = "The notice does not provide an itemized audit, ledger statement, or invoices verifying how this exact figure was calculated."
        elif "vacate" in p_lower or "premises" in p_lower or "tenancy" in p_lower or "possession" in p_lower:
            stated_text = "The notice demands that you vacate the premises and hand over physical possession."
            interp_text = "The landlord is issuing a termination warning. Under Indian tenancy law, formal eviction requires due process of law."
            unknown_text = "The notice does not account for the security deposit balance or formal move-out inspection details."
        elif "dishonour" in p_lower or "138" in p_lower or "cheque" in p_lower:
            stated_text = "The sender asserts that a cheque issued by you was returned unpaid by the bank."
            interp_text = "This refers to statutory proceedings under the Negotiable Instruments Act. A 15-day notice period is required by law."
            unknown_text = "The notice does not specify whether the bank memo was received within the statutory 30-day window."
        elif "failing which" in p_lower or "legal proceedings" in p_lower or "court" in p_lower or "police" in p_lower:
            stated_text = "The sender states that if demands are not fulfilled, they intend to institute legal proceedings."
            interp_text = "This is standard legal demand language. It indicates intent to file a suit, not an active court summons or police warrant."
            unknown_text = "The notice does not provide a court case number or summons (none has been filed yet)."
        else:
            first_sentence = p_text.split('.')[0].strip()
            stated_text = f"The notice states: '{first_sentence}'"
            interp_text = "This clause outlines the factual narrative from the sender's viewpoint."
            unknown_text = "The document does not state your side of the dispute or previous correspondence."

        explanations.append({
            "passage_id": p_id,
            "quote": p_text[:200] + ("..." if len(p_text) > 200 else ""),
            "stated": sanitize_output_verdicts(stated_text),
            "interpretation": sanitize_output_verdicts(interp_text),
            "unknown": sanitize_output_verdicts(unknown_text)
        })

    return explanations
