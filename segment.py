"""
NoticeGuard - Text Segmentation and Normalization Module.
Handles Unicode NFC normalization, Devanagari/Telugu digit normalization,
and passage segmentation (P1, P2, ...).
"""

import re
import unicodedata
from typing import List, Dict, Any

# Mapping Devanagari and Telugu numerals to standard ASCII digits
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

TELUGU_DIGITS = {
    '౦': '0', '౧': '1', '౨': '2', '౩': '3', '౪': '4',
    '౫': '5', '౬': '6', '౭': '7', '౮': '8', '౯': '9'
}

def normalize_unicode_nfc(text: str) -> str:
    """Normalize text using Unicode NFC form."""
    if not text:
        return ""
    return unicodedata.normalize('NFC', text)

def normalize_digits(text: str) -> str:
    """
    Convert Indic digits (Devanagari, Telugu) to standard ASCII 0-9.
    Runs before every numerical and date verification check.
    """
    if not text:
        return ""
    result = []
    for ch in text:
        if ch in DEVANAGARI_DIGITS:
            result.append(DEVANAGARI_DIGITS[ch])
        elif ch in TELUGU_DIGITS:
            result.append(TELUGU_DIGITS[ch])
        else:
            result.append(ch)
    return "".join(result)

def clean_and_normalize(text: str) -> str:
    """Combines NFC normalization and whitespace cleanup."""
    if not text:
        return ""
    # Normalize Unicode to NFC
    norm_text = normalize_unicode_nfc(text)
    # Replace non-standard whitespace / carriage returns
    norm_text = norm_text.replace('\r\n', '\n').replace('\r', '\n')
    # Strip excessive trailing whitespace per line
    lines = [l.strip() for l in norm_text.split('\n')]
    return '\n'.join(lines)

def segment_notice(text: str) -> List[Dict[str, Any]]:
    """
    Segments document into numbered passages (P1, P2, P3...) based on
    paragraphs, clause numbering (1., 2., a., etc.), and double newlines.
    Returns list of passage objects with id, text, normalized_digits_text.
    """
    normalized_doc = clean_and_normalize(text)
    if not normalized_doc.strip():
        return []

    # First, split by double newlines or significant line breaks
    raw_blocks = re.split(r'\n\s*\n+', normalized_doc)
    passages = []
    passage_counter = 1

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        
        # Check if block contains multiple numbered legal clauses like:
        # "1. That my client... \n 2. That you failed..."
        clause_splits = re.split(r'(?=\n(?:\d+[\.\)]|[a-zA-Z][\.\)]|\([0-9a-zA-Z]\))\s+)', '\n' + block)
        
        for clause in clause_splits:
            clause = clause.strip()
            if not clause:
                continue
            
            p_id = f"P{passage_counter}"
            passages.append({
                "id": p_id,
                "text": clause,
                "nfc_text": normalize_unicode_nfc(clause),
                "ascii_digits_text": normalize_digits(clause),
                "length": len(clause)
            })
            passage_counter += 1

    return passages

def get_passage_by_id(passages: List[Dict[str, Any]], passage_id: str) -> Dict[str, Any]:
    """Retrieve a specific passage by its identifier (e.g., 'P1')."""
    for p in passages:
        if p["id"].upper() == passage_id.upper():
            return p
    return {}
