"""
NoticeGuard - Streamlit Local-First Web Application.
Private Legal Document Triage Agent for India.
Gemma explains, code verifies. Zero cloud calls, 127.0.0.1 localhost only.
"""
import re
import os
import json
import yaml
from datetime import date, datetime
import streamlit as st

# Import NoticeGuard local modules
from ingest import ingest_document, wipe_temp_directory, IngestError
from segment import segment_notice, normalize_unicode_nfc, normalize_digits
from guardrails import (
    scan_for_injection,
    is_verdict_query,
    get_refusal_message,
    get_silent_message,
    sanitize_output_verdicts
)
from extract import extract_facts, is_ollama_available, query_local_ollama
from verify import verify_facts, verify_quote
from timeline import compute_timeline
from explain import generate_plain_explanation
from escalate import build_lawyer_checklist
from translate import translate_text, MACHINE_TRANSLATION_NOTICES

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
config = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

# Load localized strings
I18N_DIR = os.path.join(os.path.dirname(__file__), "i18n")
def load_i18n(lang: str) -> dict:
    path = os.path.join(I18N_DIR, f"{lang}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Load legal glossary
GLOSSARY_PATH = os.path.join(os.path.dirname(__file__), "glossary.json")
glossary_data = {}
if os.path.exists(GLOSSARY_PATH):
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        glossary_data = json.load(f)

# Sample notices for 1-click testing
SAMPLE_NOTICES = {
    "Select a sample notice...": "",
    "Sample 1: Section 138 Cheque Bounce Demand Notice (English)": """LEGAL NOTICE (UNDER SECTION 138 NEGOTIABLE INSTRUMENTS ACT)
Date: 12th October 2026
To,
Mr. Rahul Sharma,
Flat 402, Sunshine Apartments, Indiranagar, Bengaluru - 560038

Under instructions from and on behalf of my client, M/s Apex Tech Solutions Pvt Ltd, having its registered office at Koramangala, Bengaluru, I hereby serve upon you this formal statutory legal notice:

1. That you had issued Cheque No. 440219 dated 15th September 2026 for a sum of Rs. 75,000/- (Rupees Seventy Five Thousand only) drawn on HDFC Bank in discharge of your outstanding contractual dues.

2. That upon presentation by my client through their banker ICICI Bank, the said cheque was returned unpaid and dishonoured with the Cheque Return Memo stating 'FUNDS INSUFFICIENT' on 28th September 2026.

3. That you have deliberately failed to maintain sufficient balance in your bank account to honour the said commitment.

4. I therefore hereby call upon you to pay the sum of Rs. 75,000/- to my client within a period of 15 days of the receipt of this legal notice.

5. Failing which, my client will be constrained to initiate criminal proceedings against you under Section 138 of the Negotiable Instruments Act, 1881, and initiate civil suit for recovery at your sole risk, cost, and consequences.

Advocate Priya Ramanathan, High Court of Karnataka""",

    "Sample 2: Tenancy Termination and Eviction Notice (English)": """NOTICE TO QUIT AND VACATE PREMISES
Date: 05th October 2026
To,
Ms. Ananya Roy,
Tenant, House No. 12B, Green Glen Layout, Bellandur, Bengaluru

From:
K. V. Subbarao (Landlord),
Represented by Advocate S. Deshmukh

Madam,
Under instructions from my client Sri K. V. Subbarao, landlord of residential premises House No. 12B:

1. That the 11-month lease agreement executed on 1st November 2025 has expired and my client does not wish to renew the tenancy.

2. That you are currently in arrears of rent for the past two months amounting to Rs. 44,000/- (Rupees Forty Four Thousand only).

3. My client hereby terminates your month-to-month tenancy under Section 106 of the Transfer of Property Act and demands that you vacate and hand over vacant physical possession of the said premises and pay the sum of Rs. 44,000/- within 15 days of receipt of this notice.

4. If you fail to vacate the premises within the stipulated 15 days, my client shall institute eviction proceedings before the competent Civil Court and claim mesne profits of Rs. 2,000/- per day for unauthorized occupation.

Advocate S. Deshmukh, Civil Court""",

    "Sample 3: Freelance Recovery Notice with Ambiguous Deadline": """FORMAL PAYMENT DEMAND NOTICE
Date: 10th October 2026
To,
NextGen Media Agency,
Cyber City, Gurugram

Dear Sir/Madam,
I am writing on behalf of freelance designer Vikram Malhotra regarding unpaid milestone invoices #204 and #205.

1. That the design deliverables for your client branding were completed and approved in writing on 14th August 2026.

2. That the outstanding invoice balance of Rs. 1,20,000/- remains unpaid despite repeated email reminders.

3. We hereby call upon you to settle the outstanding dues immediately and forthwith without any further delay.

4. In default whereof, our client will initiate legal proceedings for recovery of debt along with 18% commercial interest per annum and damages.

Vikram Malhotra (via Legal Counsel)"""
}

# Streamlit Page Setup
st.set_page_config(
    page_title="NoticeGuard - Private Legal Document Triage",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .reportview-container {
        background: #0F172A;
        color: #F8FAFC;
    }
    .badge-privacy {
        background: linear-gradient(135deg, #10B981, #059669);
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 12px;
    }
    .disclaimer-box {
        background-color: #1E293B;
        border-left: 4px solid #EAB308;
        padding: 12px 16px;
        border-radius: 6px;
        font-size: 0.85rem;
        color: #CBD5E1;
        margin-bottom: 16px;
    }
    .fact-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 12px;
    }
    .quote-box {
        background-color: #0F172A;
        border-left: 3px solid #38BDF8;
        padding: 8px 12px;
        font-style: italic;
        font-size: 0.88rem;
        color: #94A3B8;
        margin-top: 6px;
        border-radius: 0 4px 4px 0;
    }
    .status-stated {
        color: #38BDF8;
        font-weight: 700;
    }
    .status-interpretation {
        color: #F59E0B;
        font-weight: 700;
    }
    .status-unknown {
        color: #94A3B8;
        font-weight: 700;
    }
    .status-unverified {
        color: #EF4444;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if "lang" not in st.session_state:
    st.session_state.lang = "en"
if "doc_data" not in st.session_state:
    st.session_state.doc_data = None
if "receipt_date" not in st.session_state:
    st.session_state.receipt_date = date.today()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def wipe_all_session():
    st.session_state.doc_data = None
    st.session_state.chat_history = []
    st.session_state.receipt_date = date.today()
    wipe_temp_directory()
    st.toast("Session wiped completely. All in-memory document data erased.", icon="🧹")

# Sidebar
with st.sidebar:
    st.title("🛡️ NoticeGuard")
    st.markdown('<div class="badge-privacy">🔒 100% Local-First | 0 Cloud Calls</div>', unsafe_allow_html=True)
    
    # Language Selector
    lang_choice = st.selectbox(
        "Language / भाषा / భాష",
        options=["en", "hi", "te"],
        format_func=lambda x: {"en": "English", "hi": "हिंदी (Hindi)", "te": "తెలుగు (Telugu)"}[x],
        index=["en", "hi", "te"].index(st.session_state.lang)
    )
    if lang_choice != st.session_state.lang:
        st.session_state.lang = lang_choice
        st.rerun()

    i18n = load_i18n(st.session_state.lang)

    st.markdown("---")
    
    # Receipt date picker for relative deadlines
    st.session_state.receipt_date = st.date_input(
        i18n.get("ui", {}).get("receipt_date_label", "Notice Receipt Date:"),
        value=st.session_state.receipt_date
    )

    st.markdown("---")
    
    # Ollama status check
    ollama_ok = is_ollama_available(config.get("ollama", {}).get("base_url", "http://127.0.0.1:11434"))
    if ollama_ok:
        st.success(f"● Local Gemma Active ({config.get('ollama', {}).get('model', 'gemma2')})")
    else:
        st.info("● Deterministic Verifier Active (Offline Mode)")

    st.markdown("---")
    
    if st.button("🗑️ " + i18n.get("ui", {}).get("wipe_session", "Wipe Session"), use_container_width=True, type="secondary"):
        wipe_all_session()
        st.rerun()

    st.markdown("---")
    st.markdown("### 📚 Legal Terms Guide")
    with st.expander("Explore Indian Legal Terms"):
        for term_key, term_info in glossary_data.items():
            st.markdown(f"**{term_info['term']}**")
            st.caption(term_info['plain_meaning'])

# Main Header
i18n = load_i18n(st.session_state.lang)
st.title(i18n.get("app_title", "NoticeGuard - Local Legal Document Triage"))
st.caption(i18n.get("app_tagline", "Private, local triage for legal notices. Gemma explains, code verifies."))

# Disclaimer Box
st.markdown(f"""
<div class="disclaimer-box">
    <strong>⚖️ {i18n.get("disclaimer", "")}</strong>
</div>
""", unsafe_allow_html=True)

# Document Input Section (if no document processed)
if st.session_state.doc_data is None:
    st.markdown("### 📥 " + i18n.get("ui", {}).get("upload_title", "Input Legal Notice"))
    
    # Sample notice loader
    selected_sample = st.selectbox("💡 Try a sample notice immediately:", list(SAMPLE_NOTICES.keys()))
    default_text = SAMPLE_NOTICES[selected_sample] if selected_sample else ""
    
    col1, col2 = st.tabs(["📄 Upload File (PDF/TXT)", "✍️ Paste Notice Text"])
    
    input_text = ""
    file_bytes = None
    file_name = None

    with col1:
        uploaded_file = st.file_uploader(
            i18n.get("ui", {}).get("upload_help", "Upload a PDF or TXT notice:"),
            type=["pdf", "txt"]
        )
        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            file_name = uploaded_file.name

    with col2:
        pasted_input = st.text_area(
            "Notice Content",
            value=default_text,
            height=260,
            placeholder=i18n.get("ui", {}).get("paste_placeholder", "Paste legal notice text here...")
        )
        if pasted_input.strip():
            input_text = pasted_input.strip()

    if st.button("🚀 Analyze Notice Securely", type="primary"):
        if not file_bytes and not input_text:
            st.error("Please upload a file or paste notice text.")
        else:
            with st.spinner("Analyzing notice locally on your laptop..."):
                try:
                    # 1. Ingest
                    ingest_res = ingest_document(file_bytes=file_bytes, file_name=file_name, pasted_text=input_text)
                    raw_text = ingest_res["text"]

                    # 2. Injection Scan
                    has_injection, detected_patterns = scan_for_injection(raw_text)
                    if has_injection:
                        st.warning(f"⚠️ Security Notice: Detected prompt injection phrases: {', '.join(detected_patterns)}. They have been neutralized.")

                    # 3. Segment into numbered passages (P1, P2...)
                    passages = segment_notice(raw_text)

                    # 4. Gemma Extraction
                    raw_facts = extract_facts(raw_text, passages)

                    # 5. Deterministic Code Verification (Quotes, Amounts, Dates)
                    verified_facts = verify_facts(raw_facts, raw_text, passages)

                    # 6. Timeline Computation
                    timeline_res = compute_timeline(verified_facts, receipt_date=st.session_state.receipt_date)

                    # 7. Plain-Language Paraphrases (STATED, INTERPRETATION, UNKNOWN)
                    explanations = generate_plain_explanation(passages, verified_facts)

                    # 8. Lawyer Escalation Checklist
                    checklist = build_lawyer_checklist(verified_facts, timeline_res, passages, raw_text)

                    st.session_state.doc_data = {
                        "raw_text": raw_text,
                        "passages": passages,
                        "verified_facts": verified_facts,
                        "timeline": timeline_res,
                        "explanations": explanations,
                        "checklist": checklist,
                        "has_injection": has_injection
                    }
                    st.rerun()

                except IngestError as e:
                    st.error(f"Error loading document: {str(e)}")
                except Exception as e:
                    st.error(f"An unexpected error occurred during processing: {str(e)}")

# Display Analysis Dashboard
if st.session_state.doc_data is not None:
    doc = st.session_state.doc_data
    facts = doc["verified_facts"]
    timeline = doc["timeline"]
    passages = doc["passages"]
    explanations = doc["explanations"]
    checklist = doc["checklist"]
    current_lang = st.session_state.lang

    # Re-evaluate timeline in case receipt date was updated in sidebar
    timeline = compute_timeline(facts, receipt_date=st.session_state.receipt_date)

    # Translation Banner if in Hindi or Telugu
    if current_lang != "en":
        st.info(f"🌐 {MACHINE_TRANSLATION_NOTICES.get(current_lang)}")

    # Main Tabs
    ui_strings = i18n.get("ui", {})
    t1, t2, t3, t4, t5 = st.tabs([
        f"📋 {ui_strings.get('tab_facts', 'Key Facts')}",
        f"⏳ {ui_strings.get('tab_timeline', 'Timeline')}",
        f"🔍 {ui_strings.get('tab_explain', 'Plain-Language View')}",
        f"⚖️ {ui_strings.get('tab_checklist', 'Lawyer Checklist')}",
        f"💬 {ui_strings.get('tab_qa', 'Ask a Question')}"
    ])

    # 1. TAB: KEY FACTS
    with t1:
        st.subheader("📋 Notice Core Facts")
        
        # Urgency Banner
        urgency = timeline.get("urgency_level", "MEDIUM")

        urg_color = {"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "blue", "LOW": "green"}.get(urgency, "blue")
        st.markdown(f"**{ui_strings.get('urgency_badge', 'Urgency Level')}:** :{urg_color}[**{urgency}**]")
        st.markdown(f"**Notice Type:** {checklist['notice_type']}")
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"**{ui_strings.get('sender', 'Sender')}:**")
            st.write(facts['sender']['value'])
            if facts['sender']['quote']:
                st.markdown(f"<div class='quote-box'>Verified from {facts['sender']['passage_id'] or 'Document'}: \"{facts['sender']['quote']}\"</div>", unsafe_allow_html=True)
            
            st.markdown(f"**{ui_strings.get('recipient', 'Recipient')}:**")
            st.write(facts['recipient']['value'])
            if facts['recipient']['quote']:
                st.markdown(f"<div class='quote-box'>Verified from {facts['recipient']['passage_id'] or 'Document'}: \"{facts['recipient']['quote']}\"</div>", unsafe_allow_html=True)

            st.markdown(f"**{ui_strings.get('amount', 'Total Amount Claimed')}:**")
            st.markdown(f"### {facts['amount']['value']}")
            if facts['amount']['quote']:
                st.markdown(f"<div class='quote-box'>Verified Quote: \"{facts['amount']['quote']}\"</div>", unsafe_allow_html=True)

        with colB:
            st.markdown(f"**{ui_strings.get('demand', 'Core Demand')}:**")
            st.write(facts['demand']['value'])
            if facts['demand']['quote']:
                st.markdown(f"<div class='quote-box'>Verified from {facts['demand']['passage_id'] or 'Document'}: \"{facts['demand']['quote']}\"</div>", unsafe_allow_html=True)

            st.markdown(f"**{ui_strings.get('deadline', 'Next Deadline')}:**")
            st.write(timeline.get('computed_deadline'))
            if facts['deadline']['quote']:
                st.markdown(f"<div class='quote-box'>Stated in Notice: \"{facts['deadline']['quote']}\"</div>", unsafe_allow_html=True)

            st.markdown(f"**{ui_strings.get('consequence', 'Stated Consequence')}:**")
            st.write(facts['consequence']['value'])
            if facts['consequence']['quote']:
                st.markdown(f"<div class='quote-box'>Verified Quote: \"{facts['consequence']['quote']}\"</div>", unsafe_allow_html=True)

    # 2. TAB: TIMELINE
    with t2:
        st.subheader("⏳ Action & Deadline Milestones")
        st.caption("Deadlines are deterministically calculated based on your receipt date and statutory rules.")

        if timeline.get("is_ambiguous"):
            st.warning("⚠️ Ambiguous Deadline Detected: The notice demands action 'immediately' or 'forthwith' without specifying exact calendar days.")

        for ev in timeline["events"]:
            with st.container():
                st.markdown(f"#### 📅 {ev['event']} — **{ev['date']}**")
                st.write(ev['description'])
                if ev.get("days_remaining") is not None:
                    if ev["days_remaining"] < 0:
                        st.error(f"Deadline passed {abs(ev['days_remaining'])} days ago!")
                    elif ev["days_remaining"] == 0:
                        st.error("Deadline is TODAY!")
                    else:
                        st.info(f"⏳ **{ev['days_remaining']} days remaining** from today.")
                st.divider()

    # 3. TAB: PLAIN-LANGUAGE VIEW
    with t3:
        st.subheader("🔍 Calm Plain-Language Passage Analysis")
        st.caption("Each passage shows what the notice explicitly states, what it means calmly, and what it leaves unsaid.")

        for item in explanations:
            p_id = item.get("passage_id", "")
            with st.expander(f"Passage {p_id} Analysis", expanded=True):
                # Verbatim Quote (NEVER translated, per spec)
                st.markdown(f"**Exact Original Quote ({p_id}):**")
                st.markdown(f"<div class='quote-box'>\"{item.get('quote')}\"</div>", unsafe_allow_html=True)
                
                # Translations if requested
                stated_text = item.get("stated", "")
                interp_text = item.get("interpretation", "")
                unknown_text = item.get("unknown", "")

                if current_lang != "en":
                    stated_text = translate_text(stated_text, current_lang)["text"]
                    interp_text = translate_text(interp_text, current_lang)["text"]
                    unknown_text = translate_text(unknown_text, current_lang)["text"]

                st.markdown(f"<span class='status-stated'>● {i18n.get('labels', {}).get('stated', 'STATED')}:</span> {stated_text}", unsafe_allow_html=True)
                st.markdown(f"<span class='status-interpretation'>● {i18n.get('labels', {}).get('interpretation', 'INTERPRETATION')}:</span> {interp_text}", unsafe_allow_html=True)
                st.markdown(f"<span class='status-unknown'>● {i18n.get('labels', {}).get('unknown', 'UNKNOWN')}:</span> {unknown_text}", unsafe_allow_html=True)

    # 4. TAB: LAWYER CHECKLIST
    with t4:
        st.subheader("⚖️ Lawyer Escalation & Preparation Checklist")
        st.caption("NoticeGuard prepares you for a consultation with an advocate. It does not replace one.")
        
        # Triage line
        st.info(f"📌 **{checklist['triage_line']}**")

        st.markdown(f"#### ❓ {ui_strings.get('lawyer_questions', 'Passage-Specific Questions for Your Advocate')}")
        for q in checklist["questions"]:
            if current_lang != "en":
                q = translate_text(q, current_lang)["text"]
            st.markdown(f"- [ ] {q}")

        st.markdown(f"#### 📁 {ui_strings.get('lawyer_docs', 'Documents to Gather & Bring')}")
        for doc_item in checklist["documents_to_bring"]:
            if current_lang != "en":
                doc_item = translate_text(doc_item, current_lang)["text"]
            st.markdown(f"- [ ] {doc_item}")

        st.markdown(f"#### ⚠️ {ui_strings.get('lawyer_warnings', 'Jurisdiction & Procedural Warnings')}")
        for w in checklist["jurisdiction_warnings"]:
            if current_lang != "en":
                w = translate_text(w, current_lang)["text"]
            st.warning(w)

    # 5. TAB: ASK A QUESTION (Strict Grounding & Refusals)
    with t5:
        st.subheader("💬 Ask a Question About This Notice")
        st.caption("Answers are strictly grounded in verified notice text. Legal advice and enforceability verdicts are refused.")

        user_query = st.text_input(
            "Your Question:",
            placeholder=ui_strings.get("ask_placeholder", "e.g. 'What is the amount demanded?' or 'By when must I respond?'")
        )

        if st.button("Submit Question", type="primary"):
            if not user_query.strip():
                st.warning("Please type a question.")
            else:
                q = user_query.strip()
                
                # Check 1: Injection scan on user query
                is_inj, _ = scan_for_injection(q)
                if is_inj:
                    st.error("Query contains disallowed override instructions.")
                
                # Check 2: Verdict refusal trigger ("Is this legal?", "Should I pay?", etc.)
                elif is_verdict_query(q):
                    refusal = get_refusal_message(current_lang, i18n)
                    st.warning(f"🚫 {refusal}")
                    st.session_state.chat_history.append((q, refusal, "refusal"))

                else:
                    # Check 3: Answer from document or trigger silent handler
                    answer = None
                    matched_passage = None
                    
                    # Search passages for keywords
                    q_lower = q.lower()
                    relevant_passages = []
                    for p in passages:
                        p_low = p["text"].lower()
                        # Simple keyword overlap
                        tokens = [t for t in re.findall(r'\w+', q_lower) if len(t) > 3]
                        overlap = sum(1 for t in tokens if t in p_low)
                        if overlap > 0:
                            relevant_passages.append((overlap, p))
                    
                    relevant_passages.sort(key=lambda x: x[0], reverse=True)
                    
                    if relevant_passages:
                        best_p = relevant_passages[0][1]
                        matched_passage = best_p["id"]
                        
                        # Generate answer with Gemma or direct quote extraction
                        if is_ollama_available():
                            qa_prompt = f"Answer this question strictly using only the text below. If the text does not contain the answer, say 'NOT_ADDRESSED'.\n\nText:\n{best_p['text']}\n\nQuestion: {q}"
                            raw_ans = query_local_ollama(prompt=qa_prompt)
                            if raw_ans and "NOT_ADDRESSED" not in raw_ans:
                                answer = sanitize_output_verdicts(raw_ans)
                        
                        if not answer:
                            # Deterministic extraction
                            answer = f"According to passage {best_p['id']}: \"{best_p['text'][:250]}...\""
                    
                    if not answer or "not address" in answer.lower():
                        answer = get_silent_message(current_lang, i18n)
                        st.info(f"ℹ️ {answer}")
                        st.session_state.chat_history.append((q, answer, "silent"))
                    else:
                        st.success(answer)
                        if matched_passage:
                            st.caption(f"Grounded in verified passage: {matched_passage}")
                        st.session_state.chat_history.append((q, answer, "grounded"))

        # Display history
        if st.session_state.chat_history:
            st.markdown("---")
            st.markdown("##### Previous Questions:")
            for prev_q, prev_a, kind in reversed(st.session_state.chat_history[-5:]):
                st.markdown(f"**Q:** {prev_q}")
                st.markdown(f"**A:** {prev_a}")
                st.divider()
