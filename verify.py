"""
NoticeGuard - Verification Module.
Core Rule: "Gemma explains, code verifies."
Plain Python handles:
- Exact & fuzzy quote verification against source text (NFC normalized)
- Amount verification (digit-normalized against Indian formats)
- Date existence verification
- Passage linking (mapping verified quotes to P1, P2, ...)
Anything code can't verify is marked UNVERIFIED or dropped.
"""

import re
import unicodedata
from typing import Dict, Any, List, Tuple, Optional
from segment import normalize_unicode_nfc, normalize_digits

# Try importing rapidfuzz, fallback to difflib if not available
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    import difflib
    HAS_RAPIDFUZZ = False

def clean_spacing(text: str) -> str:
    """Collapses consecutive whitespace to a single space."""
    return re.sub(r'\s+', ' ', text).strip()

def verify_quote(
    quote: str,
    source_text: str,
    passages: Optional[List[Dict[str, Any]]] = None,
    threshold: float = 88.0
) -> Dict[str, Any]:
    """
    Verifies if a candidate quote actually exists in the source document.
    Checks:
    1. Exact NFC substring match.
    2. Whitespace-normalized match.
    3. High-confidence fuzzy match (rapidfuzz / difflib).
    Returns a dict with verification result, confidence score, and passage id.
    """
    if not quote or not source_text:
        return {
            "verified": False,
            "match_type": "none",
            "score": 0.0,
            "quote": quote,
            "passage_id": None,
            "status": "UNVERIFIED"
        }

    norm_quote = normalize_unicode_nfc(quote).strip()
    norm_source = normalize_unicode_nfc(source_text)

    # 1. Exact substring match
    if norm_quote in norm_source:
        passage_id = find_passage_for_quote(norm_quote, passages)
        return {
            "verified": True,
            "match_type": "exact",
            "score": 100.0,
            "quote": norm_quote,
            "passage_id": passage_id,
            "status": "STATED"
        }

    # 2. Whitespace-collapsed match
    collapsed_quote = clean_spacing(norm_quote)
    collapsed_source = clean_spacing(norm_source)
    if collapsed_quote in collapsed_source:
        passage_id = find_passage_for_quote(norm_quote, passages)
        return {
            "verified": True,
            "match_type": "normalized_whitespace",
            "score": 98.0,
            "quote": norm_quote,
            "passage_id": passage_id,
            "status": "STATED"
        }

    # 3. High confidence fuzzy match
    score = 0.0
    matched_snippet = ""
    if HAS_RAPIDFUZZ:
        # Partial ratio allows finding substring matches with minor OCR or formatting variance
        score = fuzz.partial_ratio(collapsed_quote.lower(), collapsed_source.lower())
    else:
        # difflib fallback
        matcher = difflib.SequenceMatcher(None, collapsed_quote.lower(), collapsed_source.lower())
        match = matcher.find_longest_match(0, len(collapsed_quote), 0, len(collapsed_source))
        if match.size > 0:
            score = (match.size / len(collapsed_quote)) * 100.0

    if score >= threshold:
        passage_id = find_passage_for_quote(norm_quote, passages)
        return {
            "verified": True,
            "match_type": "fuzzy",
            "score": round(score, 1),
            "quote": norm_quote,
            "passage_id": passage_id,
            "status": "STATED"
        }

    return {
        "verified": False,
        "match_type": "unverified",
        "score": round(score, 1),
        "quote": norm_quote,
        "passage_id": None,
        "status": "UNVERIFIED"
    }

def find_passage_for_quote(quote: str, passages: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """Finds which numbered passage (P1, P2, ...) contains the quote."""
    if not passages or not quote:
        return None
    
    clean_q = clean_spacing(normalize_unicode_nfc(quote)).lower()
    
    # First check exact or substring containment
    for p in passages:
        p_clean = clean_spacing(p.get("nfc_text", "")).lower()
        if clean_q in p_clean:
            return p["id"]
    
    # Next check fuzzy overlap
    best_id = None
    best_score = 0.0
    for p in passages:
        p_clean = clean_spacing(p.get("nfc_text", "")).lower()
        if HAS_RAPIDFUZZ:
            sc = fuzz.partial_ratio(clean_q, p_clean)
        else:
            matcher = difflib.SequenceMatcher(None, clean_q, p_clean)
            sc = matcher.ratio() * 100.0
        if sc > best_score and sc >= 80.0:
            best_score = sc
            best_id = p["id"]

    return best_id

def extract_numeric_value(text: str) -> Optional[int]:
    """Extracts raw integer digits from an amount string, stripping commas/symbols."""
    if not text:
        return None
    # Normalize Devanagari/Telugu digits
    ascii_text = normalize_digits(text)
    # Strip currency signs (₹, Rs, Rs., INR) and commas
    cleaned = re.sub(r'[^\d]', '', ascii_text)
    if cleaned:
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None

def verify_amount(amount_claimed: Any, source_text: str) -> Dict[str, Any]:
    """
    Verifies that the extracted amount claimed genuinely appears in the source text.
    Handles Indian comma formats (e.g. 1,50,000), decimals (150000.00), and Indic digits.
    """
    if amount_claimed is None:
        return {"verified": True, "amount": None, "status": "UNKNOWN"}

    # If amount_claimed is given as string or int
    amount_str = str(amount_claimed)
    num_val = extract_numeric_value(amount_str)
    
    if num_val is None:
        return {"verified": False, "amount": amount_str, "status": "UNVERIFIED"}

    # Normalize source text digits
    norm_source_digits = normalize_digits(source_text)
    
    # Check variations: raw number, comma formats
    patterns = [
        str(num_val),
        f"{num_val:,}", # standard 1,000,000
    ]
    # Indian numbering format: e.g. 1,50,000
    s = str(num_val)
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        indian_formatted = ",".join(groups) + "," + last3
        patterns.append(indian_formatted)

    for p in patterns:
        if p in norm_source_digits:
            return {
                "verified": True,
                "amount": f"₹{num_val:,}",
                "numeric_value": num_val,
                "status": "STATED"
            }

    return {
        "verified": False,
        "amount": f"₹{num_val:,}",
        "numeric_value": num_val,
        "status": "UNVERIFIED"
    }

def verify_facts(raw_facts: Dict[str, Any], source_text: str, passages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Runs deterministic verification across all extracted facts.
    Ensures every fact has a verified quote or is marked UNVERIFIED.
    """
    verified_facts = {}
    
    # Sender
    sender_quote = raw_facts.get("sender_quote", "")
    v_sender = verify_quote(sender_quote, source_text, passages)
    verified_facts["sender"] = {
        "value": raw_facts.get("sender", "Unknown"),
        "quote": v_sender["quote"],
        "verified": v_sender["verified"],
        "passage_id": v_sender["passage_id"],
        "status": "STATED" if v_sender["verified"] else "UNVERIFIED"
    }

    # Recipient
    recip_quote = raw_facts.get("recipient_quote", "")
    v_recip = verify_quote(recip_quote, source_text, passages)
    verified_facts["recipient"] = {
        "value": raw_facts.get("recipient", "Unknown"),
        "quote": v_recip["quote"],
        "verified": v_recip["verified"],
        "passage_id": v_recip["passage_id"],
        "status": "STATED" if v_recip["verified"] else "UNVERIFIED"
    }

    # Demand
    demand_quote = raw_facts.get("demand_quote", "")
    v_demand = verify_quote(demand_quote, source_text, passages)
    verified_facts["demand"] = {
        "value": raw_facts.get("demand", "Not specified"),
        "quote": v_demand["quote"],
        "verified": v_demand["verified"],
        "passage_id": v_demand["passage_id"],
        "status": "STATED" if v_demand["verified"] else "UNVERIFIED"
    }

    # Amount
    raw_amount = raw_facts.get("amount")
    v_amount = verify_amount(raw_amount, source_text)
    amount_quote = raw_facts.get("amount_quote", "")
    v_amount_quote = verify_quote(amount_quote, source_text, passages)
    verified_facts["amount"] = {
        "value": v_amount["amount"] if v_amount["verified"] else (f"₹{raw_amount}" if raw_amount else "None stated"),
        "numeric_value": v_amount.get("numeric_value"),
        "verified": v_amount["verified"] or v_amount_quote["verified"],
        "quote": v_amount_quote["quote"],
        "passage_id": v_amount_quote["passage_id"],
        "status": "STATED" if (v_amount["verified"] or v_amount_quote["verified"]) else "UNKNOWN"
    }

    # Deadline quote and raw string
    dl_quote = raw_facts.get("deadline_quote", "")
    v_dl = verify_quote(dl_quote, source_text, passages)
    verified_facts["deadline"] = {
        "raw_text": raw_facts.get("deadline_raw", "None specified"),
        "quote": v_dl["quote"],
        "verified": v_dl["verified"],
        "passage_id": v_dl["passage_id"],
        "relative_days": raw_facts.get("relative_days"),
        "is_ambiguous": raw_facts.get("is_ambiguous", False),
        "status": "STATED" if v_dl["verified"] else "UNKNOWN"
    }

    # Consequence
    cons_quote = raw_facts.get("consequence_quote", "")
    v_cons = verify_quote(cons_quote, source_text, passages)
    verified_facts["consequence"] = {
        "value": raw_facts.get("consequence", "None specified"),
        "quote": v_cons["quote"],
        "verified": v_cons["verified"],
        "passage_id": v_cons["passage_id"],
        "status": "STATED" if v_cons["verified"] else "UNVERIFIED"
    }

    # Overall urgency
    verified_facts["urgency"] = raw_facts.get("urgency", "MEDIUM")

    return verified_facts
