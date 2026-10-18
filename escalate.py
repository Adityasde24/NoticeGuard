"""
NoticeGuard - Lawyer Escalation Module.
Prepares a structured consultation brief for an advocate:
1. Triage summary line.
2. Passage-specific targeted questions for the lawyer.
3. Documents to gather and bring to consultation.
4. Territorial jurisdiction and statutory limitation warnings.

Design notes:
- Notice type is decided ONCE by classify_notice_type() and every later
  section branches on that result (no duplicated substring checks).
- All keyword checks use word boundaries, so "different" or "current"
  never count as the word "rent".
- Questions that come from the notice are tied to passage IDs.
- Generic legal background is labelled as general information that is NOT
  taken from the notice, and is worded as "may"/"generally", never as a verdict.
"""

import re
from typing import Dict, Any, List

CHEQUE = "Section 138 (Cheque Bounce) Statutory Notice"
TENANCY = "Tenancy Termination / Eviction Notice"
EMPLOYMENT = "Employment Bond / Termination Demand"
COMMERCIAL = "Commercial Contract / Service Fee Recovery"
PAYMENT = "Payment Demand / Recovery Notice"
GENERAL = "General Legal Demand"

# Order matters: the first match wins.
NOTICE_TYPES = [
    (CHEQUE, r"\b(?:138|negotiable\s+instruments|cheque|dishonou?r(?:ed)?)\b"),
    (TENANCY, r"\b(?:vacate|tenant|tenancy|landlord|premises|rent|eviction)\b"),
    (EMPLOYMENT, r"\b(?:employment|bond|resignation|training\s+cost)\b"),
    (COMMERCIAL, r"\b(?:freelance|invoice|invoices|service\s+agreement|services\s+rendered)\b"),
    (PAYMENT, r"\b(?:pay\s+the\s+sum|(?:call\s+upon\s+you\s+to|demand\s+that\s+you)\s+pay|outstanding|dues|owe)\b"),
]


def classify_notice_type(text: str) -> str:
    """Returns one notice-type label using whole-word matching (English keywords only)."""
    if not text:
        return GENERAL
    for label, pattern in NOTICE_TYPES:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return GENERAL


def _short(text: Any, limit: int = 140) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _passage_questions(facts: Dict[str, Any]) -> List[str]:
    """Questions tied to specific passages, built only from verified facts."""
    qs: List[str] = []

    amt = facts.get("amount", {}) or {}
    if amt.get("numeric_value") and amt.get("passage_id"):
        qs.append(
            f"Passage {amt['passage_id']} claims {amt.get('value')}. "
            "What records should the sender provide to show how this figure was calculated, "
            "and do I have any grounds to dispute it?"
        )

    dl = facts.get("deadline", {}) or {}
    if dl.get("passage_id"):
        if dl.get("is_ambiguous"):
            qs.append(
                f"Passage {dl['passage_id']} uses vague timing (\"{_short(dl.get('quote'), 60)}\"). "
                "How should an unclear deadline like this be treated, and how quickly should I reply?"
            )
        else:
            qs.append(
                f"Passage {dl['passage_id']} sets the deadline as \"{_short(dl.get('raw_text'), 60)}\". "
                "From which date does this period count in my case, and can more time be requested?"
            )

    cons = facts.get("consequence", {}) or {}
    if cons.get("passage_id"):
        qs.append(
            f"Passage {cons['passage_id']} states: \"{_short(cons.get('value'))}\". "
            "Is this a warning of a possible future step, or has any legal step already started?"
        )

    dem = facts.get("demand", {}) or {}
    if dem.get("passage_id"):
        qs.append(
            f"Passage {dem['passage_id']} demands: \"{_short(dem.get('value'))}\". "
            "Which parts of this demand, if any, should I respond to in writing, and how?"
        )
    return qs


TYPE_QUESTIONS: Dict[str, List[str]] = {
    CHEQUE: [
        "Was this demand sent within the period allowed after the cheque return memo was received?",
        "Was the cheque presented within its validity period?",
        "Was the cheque issued for a debt that is legally due, or as a security cheque? Does that matter here?",
        "Should a formal written reply be sent within the notice period, and what should it say?",
    ],
    TENANCY: [
        "Does my rental agreement set a notice period that differs from the period in this notice?",
        "Which grounds for eviction apply under the rent laws of my state?",
        "How should my security deposit be handled before any eviction step?",
        "How should I respond to any claim for damages or mesne profits for staying on?",
    ],
    EMPLOYMENT: [
        "Is the bond or training-cost clause in my contract enforceable in my situation?",
        "Can the employer show actual training expense, or is the amount a fixed penalty?",
        "Should my reply also ask for pending salary, a relieving letter and an experience certificate?",
    ],
    COMMERCIAL: [
        "Does my contract or invoice terms say how and when payment disputes must be raised?",
        "Is there an arbitration or mediation clause that must be followed before court?",
        "What proof of delivery or acceptance of work should I gather before replying?",
    ],
    PAYMENT: [
        "Is the claimed amount supported by an agreement, invoice or account statement?",
        "Is the claim still within the time limit for bringing it?",
        "Should a formal reply be sent through an advocate, and what should it address?",
    ],
    GENERAL: [
        "What is this notice based on, and what documents support the claim?",
        "Is the claim still within the time limit for bringing it?",
        "Is there an arbitration or mediation clause that applies before any court step?",
        "Should a formal reply be sent through an advocate, and by when?",
    ],
}

BASE_DOCUMENTS = [
    "The original notice, plus the envelope or tracking record showing the date you received it.",
    "Any signed agreement, lease, contract, offer letter or purchase order, with amendments.",
    "Bank statements, receipts and payment records for the matter.",
    "Your messages with the sender (emails, SMS, WhatsApp, earlier letters).",
    "A government photo ID (for example Aadhaar, PAN or passport) if you decide to appoint an advocate.",
]

EXTRA_DOCUMENTS: Dict[str, str] = {
    CHEQUE: "Your bank statement showing when the cheque was presented, and the cheque return memo if you have it.",
    TENANCY: "Rent receipts, utility bill payments, and photos or videos of the property's condition at move-in.",
    EMPLOYMENT: "Your offer letter, bond or training agreement, salary slips and resignation correspondence.",
    COMMERCIAL: "Invoices, approvals or acceptance of the work, and any emails about payment.",
}

GENERAL_INFO_PREFIX = "General information (not taken from your notice): "

WARNINGS = [
    "Jurisdiction: the court that can hear a dispute may depend on where the property is, where the agreement was signed, or where the parties live. Ask an advocate which court applies.",
    "Proof of receipt: keep the postal stamp or tracking record. Time limits often count from the date you actually received the notice, not the date written on it. An advocate can confirm for your case.",
    "Time limits: ordinary money claims generally have a limitation period (commonly three years under the Limitation Act, 1963), but exceptions exist. Ask an advocate how it applies here.",
    "Replying: not responding to a legal notice can sometimes lead to the sender taking further legal steps. Consider speaking to an advocate about a written reply within the notice period.",
]


def build_lawyer_checklist(
    facts: Dict[str, Any],
    timeline: Dict[str, Any],
    passages: List[Dict[str, Any]],
    raw_text: str,
) -> Dict[str, Any]:
    """Builds the lawyer-consultation checklist for the detected notice type."""
    notice_type = classify_notice_type(raw_text or "")

    urgency = timeline.get("urgency_level", "MEDIUM")
    relative_days = timeline.get("relative_days")
    days_remaining = timeline.get("days_remaining")

    if notice_type == CHEQUE:
        triage_priority = "HIGH / STATUTORY"
    elif notice_type == TENANCY:
        triage_priority = "HIGH" if (relative_days is not None and relative_days <= 15) else "MEDIUM"
    elif notice_type in (EMPLOYMENT, COMMERCIAL):
        triage_priority = "MEDIUM"
    else:
        triage_priority = urgency

    if days_remaining is not None:
        time_text = f"{days_remaining} days"
    elif timeline.get("is_ambiguous"):
        time_text = "Unclear (vague wording in notice)"
    else:
        time_text = "Not stated in notice"

    triage_line = (
        f"Triage Priority: {triage_priority} | Category: {notice_type} | "
        f"Time to Deadline: {time_text}"
    )

    # Questions: passage-tied first (from this notice), then type-specific background.
    questions = _passage_questions(facts) + TYPE_QUESTIONS.get(notice_type, TYPE_QUESTIONS[GENERAL])

    documents = list(BASE_DOCUMENTS)
    if notice_type in EXTRA_DOCUMENTS:
        documents.append(EXTRA_DOCUMENTS[notice_type])

    warnings = [GENERAL_INFO_PREFIX + w for w in WARNINGS]

    return {
        "triage_line": triage_line,
        "notice_type": notice_type,
        "triage_priority": triage_priority,
        "questions": questions,
        "documents_to_bring": documents,
        "jurisdiction_warnings": warnings,
    }
