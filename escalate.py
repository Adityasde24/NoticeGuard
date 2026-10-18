"""
NoticeGuard - Lawyer Escalation Module.
Prepares a structured consultation brief for an advocate:
1. Triage summary line.
2. Passage-specific targeted questions for the lawyer.
3. Documents to gather and bring to consultation.
4. Territorial jurisdiction and statutory limitation warnings.
"""

from typing import Dict, Any, List

def build_lawyer_checklist(
    facts: Dict[str, Any],
    timeline: Dict[str, Any],
    passages: List[Dict[str, Any]],
    raw_text: str
) -> Dict[str, Any]:
    """
    Builds a thorough, actionable checklist for consulting a lawyer based on notice type.
    """
    text_lower = raw_text.lower()
    
    # 1. Determine notice type and triage priority
    urgency = timeline.get("urgency_level", "MEDIUM")
    relative_days = timeline.get("relative_days")
    days_remaining = timeline.get("days_remaining")
    
    notice_type = "General Legal Demand"
    if "138" in text_lower or "negotiable instruments" in text_lower or "cheque" in text_lower or "dishonour" in text_lower:
        notice_type = "Section 138 (Cheque Bounce) Statutory Notice"
        triage_priority = "HIGH / STATUTORY"
    elif "vacate" in text_lower or "tenant" in text_lower or "landlord" in text_lower or "premises" in text_lower or "rent" in text_lower:
        notice_type = "Tenancy Termination / Eviction Notice"
        triage_priority = "HIGH" if (relative_days and relative_days <= 15) else "MEDIUM"
    elif "employment" in text_lower or "bond" in text_lower or "resignation" in text_lower or "training cost" in text_lower:
        notice_type = "Employment Bond / Termination Demand"
        triage_priority = "MEDIUM"
    elif "freelance" in text_lower or "invoice" in text_lower or "service agreement" in text_lower:
        notice_type = "Commercial Contract / Service Fee Recovery"
        triage_priority = "MEDIUM"
    else:
        triage_priority = urgency

    triage_line = f"Triage Priority: {triage_priority} | Category: {notice_type} | Time to Deadline: {days_remaining if days_remaining is not None else 'Ambiguous/Unstated'} days"

    # 2. Passage-specific questions for lawyer
    questions = []
    
    if "138" in text_lower or "cheque" in text_lower:
        questions.extend([
            "Did the complainant send this statutory demand within 30 days of receiving the Cheque Return Memo from the bank?",
            "Was the cheque presented within its 3-month validity period?",
            "Was the cheque issued for a legally enforceable debt/liability or merely as a security cheque?",
            "Should we issue a formal reply notice within the 15-day statutory window denying liability?"
        ])
    elif "vacate" in text_lower or "rent" in text_lower or "tenancy" in text_lower:
        questions.extend([
            "Does our rental agreement prescribe a 30-day notice period that supersedes the period demanded in this notice?",
            "Under the applicable State Rent Control legislation, what grounds for eviction are legally recognized for this property?",
            "Can the landlord initiate eviction without first settling or adjusting the security deposit balance?",
            "What is the defense against any claim for 'mesne profits' or unauthorized occupation damages?"
        ])
    elif "bond" in text_lower or "employment" in text_lower:
        questions.extend([
            "Is the employment / training bond clause void under Section 27 of the Indian Contract Act (restraint of trade)?",
            "Has the former employer proven actual, genuine expense incurred on specialized training, or is this an unenforceable penalty?",
            "Should we respond demanding settlement of pending salary, relieving letter, and experience certificate?"
        ])
    else:
        questions.extend([
            "Does the underlying claim comply with the 3-year statutory limitation period under the Limitation Act, 1963?",
            "Should a formal reply notice be served through an advocate denying the factual allegations?",
            "Is there an arbitration clause or mediation requirement in the agreement before any court proceedings can be instituted?",
            "What are our counter-claims or damages against the sender for breach of contract?"
        ])

    # 3. Documents to gather and bring to consultation
    documents = [
        "Original or printed legal notice along with the registered post / speed post envelope showing the tracking number and postmark delivery date.",
        "Underlying signed agreement, lease deed, service contract, offer letter, or purchase order (with all amendments).",
        "Bank account statements, receipts, and payment records showing all transfers, payments, or security deposits made.",
        "Complete trail of written communications (emails, SMS, WhatsApp messages, previous letters) between you and the sender.",
        "Your government-issued ID (Aadhaar / PAN / Passport) for signing a Vakalatnama or formal reply affidavit."
    ]

    if "cheque" in text_lower:
        documents.append("Bank passbook / statement reflecting cheque presentation date and return memo copy if in your possession.")
    if "rent" in text_lower or "vacate" in text_lower:
        documents.append("Rent payment receipts, utility bill payments, and photos/videos of the property condition upon move-in.")

    # 4. Jurisdiction & Limitation warnings
    warnings = [
        "Jurisdiction Check: Verify whether the courts of the city named in the notice have territorial and subject-matter jurisdiction over where the property is located or where the agreement was signed.",
        "Proof of Receipt: Keep the postal delivery stamp or electronic tracking report safely. In Indian courts, statutory limitation clocks run strictly from the proven date of receipt, not the date written on the letter.",
        "Limitation Act Warning: Under the Indian Limitation Act (1963), ordinary monetary claims for debt or damages must generally be filed within 3 years from the date the cause of action arose.",
        "Do Not Ignore: Ignoring a formal legal notice can lead to an ex-parte suit or criminal complaint. Always seek an advocate's help to draft a structured reply within the notice window."
    ]

    return {
        "triage_line": triage_line,
        "notice_type": notice_type,
        "triage_priority": triage_priority,
        "questions": questions,
        "documents_to_bring": documents,
        "jurisdiction_warnings": warnings
    }
