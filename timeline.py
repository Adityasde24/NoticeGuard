"""
NoticeGuard - Timeline & Deadline Engine.
Handles deterministic date calculations, relative deadline computation
(e.g., 'within 15 days of receipt'), and ambiguity detection.
"""

import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from segment import normalize_digits

# Patterns for relative duration in English, Hindi, and Telugu
RELATIVE_DAYS_PATTERNS = [
    # English: "within 15 days", "15 days from receipt", "period of 7 days"
    (r"(?i)\b(?:within|period\s+of|time\s+of)\s+(\d+)\s+days?\b", 1),
    (r"(?i)\b(\d+)\s+days?\s+(?:from|after|of)\b", 1),
    (r"(?i)\b(?:within|period\s+of)\s+(\d+)\s+weeks?\b", 7),
    (r"(?i)\b(?:within|period\s+of)\s+(\d+)\s+months?\b", 30),
    (r"(?i)\b(?:within)\s+(\d+)\s+hours?\b", 1/24),
    # Hindi: "15 दिनों के भीतर", "7 दिन के अंदर"
    (r"(\d+)\s+दिनों?\s+के\s+(?:भीतर|अंदर)", 1),
    (r"(\d+)\s+सप्ताह\s+के\s+(?:भीतर|अंदर)", 7),
    (r"(\d+)\s+महीने?\s+के\s+(?:भीतर|अंदर)", 30),
    # Telugu: "15 రోజుల్లోగా", "7 రోజుల్లో"
    (r"(\d+)\s+రోజుల్(?:లోగా|లో)", 1),
    (r"(\d+)\s+వారాల్(?:లోగా|లో)", 7)
]

# Ambiguous deadline phrases that do not offer a clear calendar computation
AMBIGUOUS_PATTERNS = [
    # English
    r"(?i)\bforthwith\b",
    r"(?i)\bimmediately\b",
    r"(?i)\bat\s+the\s+earliest\b",
    r"(?i)\bwithout\s+(?:any\s+)?delay\b",
    r"(?i)\breasonable\s+time\b",
    r"(?i)\bas\s+soon\s+as\s+possible\b",
    r"(?i)\bpromptly\b",
    # Hindi
    r"तत्काल",
    r"तुरंत",
    r"यथाशीघ्र",
    r"बिना\s+किसी\s+देरी\s+के",
    r"उचित\s+समय",
    # Telugu
    r"వెంటనే",
    r"ఆలస్యం\s+లేకుండా",
    r"వీలైనంత\s+త్వరగా",
    r"సహేతుకమైన\s+సమయంలో"
]

def parse_relative_deadline(text: str) -> Optional[int]:
    """
    Extracts the number of relative days stated in a notice.
    Normalizes Indic digits first.
    """
    if not text:
        return None
    
    clean_text = normalize_digits(text)
    for pattern, multiplier in RELATIVE_DAYS_PATTERNS:
        match = re.search(pattern, clean_text)
        if match:
            try:
                num = int(match.group(1))
                return max(1, int(num * multiplier))
            except ValueError:
                pass
    return None

def is_ambiguous_deadline(text: str) -> bool:
    """Detects whether deadline phrasing is legally ambiguous/vague."""
    if not text:
        return False
    for pat in AMBIGUOUS_PATTERNS:
        if re.search(pat, text):
            return True
    return False

def compute_timeline(
    facts: Dict[str, Any],
    receipt_date: Optional[date] = None,
    notice_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Builds a structured, chronological timeline from notice facts.
    Computes absolute calendar deadlines from relative timeframes.
    """
    today = date.today()
    if receipt_date is None:
        receipt_date = today

    deadline_info = facts.get("deadline", {})
    raw_deadline_text = deadline_info.get("raw_text", "")
    deadline_quote = deadline_info.get("quote", "")
    relative_days = deadline_info.get("relative_days")

    # If relative_days not pre-extracted, parse from text
    if relative_days is None:
        relative_days = parse_relative_deadline(raw_deadline_text) or parse_relative_deadline(deadline_quote)

    ambiguous = is_ambiguous_deadline(raw_deadline_text) or is_ambiguous_deadline(deadline_quote)

    events: List[Dict[str, Any]] = []

    # 1. Notice Date (if available)
    if notice_date:
        events.append({
            "event": "Notice Issuance Date",
            "date": notice_date.strftime("%d %b %Y"),
            "date_obj": notice_date,
            "type": "notice_date",
            "description": "Date stated on the legal notice document."
        })

    # 2. Receipt Date
    events.append({
        "event": "Notice Receipt Date",
        "date": receipt_date.strftime("%d %b %Y"),
        "date_obj": receipt_date,
        "type": "receipt_date",
        "description": "Date you received the notice (statutory clock starts here)."
    })

    # 3. Calculated Deadline
    computed_deadline_date = None
    days_remaining = None

    if relative_days is not None:
        computed_deadline_date = receipt_date + timedelta(days=relative_days)
        days_remaining = (computed_deadline_date - today).days

        events.append({
            "event": f"Response / Payment Deadline ({relative_days} Days)",
            "date": computed_deadline_date.strftime("%d %b %Y"),
            "date_obj": computed_deadline_date,
            "type": "deadline",
            "days_remaining": days_remaining,
            "is_relative": True,
            "relative_days": relative_days,
            "description": f"Calculated as {relative_days} calendar days from receipt date."
        })
    elif ambiguous:
        events.append({
            "event": "Ambiguous / Immediate Demand",
            "date": "Immediate / Ambiguous",
            "date_obj": receipt_date,
            "type": "ambiguous_deadline",
            "days_remaining": 0,
            "is_relative": False,
            "is_ambiguous": True,
            "description": "Notice demands action 'forthwith' or 'immediately' without a clear statutory calendar span."
        })
    else:
        # Check if an explicit calendar date was given in the notice
        events.append({
            "event": "Action Deadline",
            "date": raw_deadline_text or "Unspecified",
            "date_obj": None,
            "type": "unspecified_deadline",
            "days_remaining": None,
            "description": raw_deadline_text or "No specific deadline date found in notice."
        })

    # Determine urgency level based on days remaining
    urgency_level = "MEDIUM"
    if days_remaining is not None:
        if days_remaining <= 3:
            urgency_level = "CRITICAL"
        elif days_remaining <= 7:
            urgency_level = "HIGH"
        elif days_remaining <= 15:
            urgency_level = "MEDIUM"
        else:
            urgency_level = "LOW"
    elif ambiguous:
        urgency_level = "HIGH"

    return {
        "events": events,
        "receipt_date": receipt_date.strftime("%d %b %Y"),
        "computed_deadline": computed_deadline_date.strftime("%d %b %Y") if computed_deadline_date else "Ambiguous / Not specified",
        "days_remaining": days_remaining,
        "is_ambiguous": ambiguous,
        "relative_days": relative_days,
        "urgency_level": urgency_level
    }
