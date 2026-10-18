"""
NoticeGuard - Silent & Missing Clause Detection Engine.
Explicitly identifies critical legal protections, rights, and procedural terms
that are ABSENT / SILENT in the document (PS2 Requirement).
"""

import re
from typing import Dict, Any, List, Optional
from segment import normalize_unicode_nfc
from verify import find_passage_for_quote

# Patterns used to detect presence of key legal protections
PROTECTION_PATTERNS = {
    "cure_period": {
        "name": "Cure / Rectification Period",
        "description": "A formal window allowing the recipient to remedy the alleged default before litigation.",
        "regex": r"(?i)\b(?:cure\s+period|opportunity\s+to\s+cure|rectify\s+(?:the\s+)?(?:breach|default)|grace\s+period|remedy\s+(?:the\s+)?defect)\b",
        "missing_significance": "Notice does NOT provide an express cure period or grace window to remedy the alleged default before threatening litigation.",
        "advocate_action": "Ask your advocate if the underlying contract or governing law guarantees a mandatory cure period before termination or suit."
    },
    "dispute_resolution": {
        "name": "Dispute Resolution & Arbitration Clause",
        "description": "Pre-litigation conciliation, mediation, or arbitration mechanism to resolve disputes without court.",
        "regex": r"(?i)\b(?:arbitrat(?:ion|or)|mediat(?:ion|or)|amicable\s+settlement|conciliation|dispute\s+resolution\s+clause)\b",
        "missing_significance": "Notice is SILENT regarding contractual arbitration or pre-litigation mediation procedures.",
        "advocate_action": "Verify if your underlying contract contains an arbitration clause (under Section 8 of the Arbitration Act) which bars direct court filing."
    },
    "statutory_notice_period": {
        "name": "Statutory Notice Period Specification",
        "description": "Explicit reference to mandatory statutory periods (e.g., 15 days under Section 138 NI Act or Transfer of Property Act).",
        "regex": r"(?i)\b(?:15\s+days|30\s+days|section\s+138|section\s+106|statutory\s+period|notice\s+period\s+of)\b",
        "missing_significance": "Notice does NOT cite a statutory notice period under applicable legislation.",
        "advocate_action": "Have your advocate verify whether the timeframe given complies with mandatory statutory minimums in your state."
    },
    "itemized_accounting": {
        "name": "Itemized Accounting & Ledger Breakdown",
        "description": "Documented ledger, monthly breakdown, interest computation, or invoices explaining the demanded amount.",
        "regex": r"(?i)\b(?:itemized|statement\s+of\s+accounts?|annexure|ledger\s+(?:copy|statement)|invoice\s+no|breakup\s+of|calculation\s+sheet)\b",
        "missing_significance": "Notice claims a lump sum WITHOUT attaching or specifying an itemized financial ledger or interest breakdown.",
        "advocate_action": "Instruct your advocate to demand a certified statement of accounts and itemized invoice breakdown in your formal reply."
    },
    "remittance_details": {
        "name": "Payment Method & Remittance Details",
        "description": "Specific bank account number, IFSC code, UPI ID, or designated payment recipient coordinates.",
        "regex": r"(?i)\b(?:account\s+no|a/c\s+no|ifsc|bank\s+details|rtgs|neft|payee\s+name|demand\s+draft\s+in\s+favo(?:u)?r)\b",
        "missing_significance": "Notice is SILENT on designated payment coordinates (no bank account number or remittance details provided).",
        "advocate_action": "Do not transfer money to unverified personal accounts; confirm official client bank details in writing through counsel."
    },
    "authorization_vakalatnama": {
        "name": "Proof of Authority / Power of Attorney",
        "description": "Reference to an executed Power of Attorney or Vakalatnama authorizing the advocate to demand on client's behalf.",
        "regex": r"(?i)\b(?:power\s+of\s+attorney|poa|vakalatnama|letter\s+of\s+authority|duly\s+authorized\s+attorney)\b",
        "missing_significance": "Notice does NOT reference an executed Power of Attorney or formal letter of authority verifying advocate's instructions.",
        "advocate_action": "Ask whether you should request proof of legal authority/Vakalatnama before disclosing substantive defenses."
    },
    "governing_jurisdiction": {
        "name": "Designated Court Jurisdiction",
        "description": "Explicit naming of the city or courts possessing territorial and subject-matter jurisdiction.",
        "regex": r"(?i)\b(?:jurisdiction\s+of\s+the\s+courts?|courts?\s+at\s+[a-zA-Z]+|exclusive\s+jurisdiction|subject\s+to\s+[a-zA-Z]+\s+jurisdiction)\b",
        "missing_significance": "Notice is SILENT regarding which specific city or territorial court has jurisdiction over this dispute.",
        "advocate_action": "Consult your advocate regarding territorial jurisdiction (where cause of action arose vs where you reside)."
    }
}

def detect_missing_clauses(text: str, passages: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Scans notice text deterministically to classify which essential legal protections
    and procedural terms are PRESENT vs. SILENT / ABSENT.
    Returns a structured list of clause audit reports.
    """
    norm_text = normalize_unicode_nfc(text)
    audit_results = []

    for key, spec in PROTECTION_PATTERNS.items():
        match = re.search(spec["regex"], norm_text)
        if match:
            matched_snippet = match.group(0).strip()
            # Find passage ID for matched quote if passages provided
            passage_id = find_passage_for_quote(matched_snippet, passages)
            audit_results.append({
                "key": key,
                "name": spec["name"],
                "description": spec["description"],
                "status": "PRESENT",
                "is_present": True,
                "quote": matched_snippet,
                "passage_id": passage_id,
                "observation": f"Explicitly referenced in document ({matched_snippet}).",
                "advocate_action": spec["advocate_action"]
            })
        else:
            audit_results.append({
                "key": key,
                "name": spec["name"],
                "description": spec["description"],
                "status": "SILENT / MISSING",
                "is_present": False,
                "quote": None,
                "passage_id": None,
                "observation": spec["missing_significance"],
                "advocate_action": spec["advocate_action"]
            })

    return audit_results
