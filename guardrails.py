"""
NoticeGuard - Guardrails Module.
Handles:
1. Prompt Injection Scanner (English, Hindi, Telugu).
2. Verdict & Legal Advice Filters and Refusal Triggers.
3. Silent Handler for unaddressed questions.
4. Multilingual Blocklists.
"""

import re
from typing import Dict, Any, Tuple, List

# Injection keywords and patterns across English, Hindi, and Telugu
INJECTION_PATTERNS = [
    # English
    r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b",
    r"(?i)\bsystem\s+prompt\b",
    r"(?i)\byou\s+are\s+now\s+(?:an?\s+)?(?:ai|assistant|unrestricted|god)\b",
    r"(?i)\bdisregard\s+(?:all\s+)?(?:rules|policies|guardrails)\b",
    r"(?i)\bjailbreak\b",
    r"(?i)\bDAN\s+mode\b",
    r"(?i)\bexecute\s+(?:the\s+following|this)\s+(?:code|command)\b",
    r"(?i)\bprint\s+(?:your\s+)?(?:system|hidden|internal)\s+(?:prompt|instructions)\b",
    r"(?i)\bdo\s+not\s+verify\b",
    r"(?i)\bpretend\s+you\s+are\b",
    # Hindi (Devanagari)
    r"पिछल[ेा]\s+(?:सभी\s+)?निर्देश(?:ों)?\s+को?\s*(?:भूल\s+जाओ|रद्द\s+करो|अस्वीकार\s+करो)",
    r"सिस्टम\s+(?:प्रॉम्प्ट|निर्देश)",
    r"नियम(?:ों)?\s+को?\s*अनदेखा\s+करो",
    r"आप\s+अब\s+(?:स्वतंत्र|नियमहीन)\s+एआई\s+हैं",
    # Telugu
    r"మునుపటి\s+(?:అన్ని\s+)?సూచనలను\s+(?:విస్మరించండి|మర్చిపోండి)",
    r"సిస్టమ్\s+ప్రాంప్ట్",
    r"నిబంధనలను\s+పట్టించుకోకండి",
    r"మీరు\s+ఇప్పుడు\s+నియంత్రణలు\s+లేని\s+AI"
]

# Verdict & Legal Advice query patterns that must trigger refusal
VERDICT_QUERY_PATTERNS = [
    # English
    r"(?i)\b(?:is\s+this|is\s+it)\s+(?:[\w\s]{0,20}\s+)?(?:legal|illegal|valid|invalid|enforceable|unenforceable|binding|void)\b",
    r"(?i)\bshould\s+i\s+(?:[\w\s]{0,20}\s+)?(?:pay|ignore|comply|agree|sign|fight)\b",
    r"(?i)\bdo\s+i\s+have\s+to\s+pay\b",
    r"(?i)\bwill\s+i\s+(?:go\s+to\s+jail|be\s+arrested|win|lose)\b",
    r"(?i)\b(?:can|will)\s+(?:the\s+)?(?:police|they|landlord|court)\s+(?:arrest|jail)\s+me\b",
    r"(?i)\b(?:what\s+is\s+your\s+)?(?:legal\s+)?verdict\b",
    r"(?i)\bgive\s+(?:me\s+)?legal\s+advice\b",
    r"(?i)\bcan\s+they\s+really\s+evict\s+me\b",
    # Hindi
    r"क्या\s+यह(?:\s+नोटिस)?(?:\s+कानूनी\s+रूप\s+से)?\s+(?:कानूनी|अवैध|मान्य|अमान्य|लागू|वैध)",
    r"(?:भुगतान\s+करना|पैसे\s+देने|रुपये\s+देने)\s+चाहिए",
    r"(?:जेल\s+होगी|गिरफ्तार\s+किया\s+जाएगा|पुलिस\s+पकड़ेगी)",
    r"क्या\s+मैं\s+यह\s+मुकदमा\s+(?:जीतूंगा|हारूंगा)",
    r"कानूनी\s+सलाह",
    # Telugu
    r"(?:చట్టబద్ధమైనదా|చెల్లుబాటు|చట్టవిరుద్ధమా|చెల్లుతుందా)",
    r"(?:చెల్లించాలా|చెల్లించవద్దా|డబ్బులు\s+ఇవ్వాలా|కట్టాలా)",
    r"(?:అరెస్టు|జైలుకు)",
    r"(?:గెలుస్తానా|ఓడిపోతానా)",
    r"చట్టపరమైన\s+సలహా"
]

# Blocklist of phrases that must NEVER appear in output generation
OUTPUT_VERDICT_BLOCKLIST = [
    # English
    r"(?i)\bthis\s+(?:notice|document)\s+is\s+(?:completely\s+)?(?:illegal|unlawful|invalid|null\s+and\s+void|unenforceable)\b",
    r"(?i)\bthis\s+(?:notice|document)\s+is\s+(?:completely\s+)?(?:legal|valid|enforceable|binding)\b",
    r"(?i)\byou\s+must\s+(?:definitely\s+)?pay\b",
    r"(?i)\byou\s+do\s+not\s+need\s+to\s+pay\b",
    r"(?i)\byou\s+will\s+(?:definitely\s+)?win\s+in\s+court\b",
    r"(?i)\byou\s+will\s+(?:definitely\s+)?lose\s+in\s+court\b",
    r"(?i)\bi\s+advise\s+you\s+to\b",
    r"(?i)\bas\s+your\s+lawyer\b",
    # Hindi
    r"यह\s+नोटिस\s+(?:पूरी\s+तरह\s+से\s+)?(?:अवैध|गैरकानूनी|अमान्य)\s+है",
    r"यह\s+नोटिस\s+(?:पूरी\s+तरह\s+से\s+)?(?:कानूनी|मान्य|बाध्यकारी)\s+है",
    r"आपको\s+(?:अवश्य|ज़रूर)\s+भुगतान\s+करना\s+चाहिए",
    r"आपको\s+भुगतान\s+करने\s+की\s+कोई\s+आवश्यकता\s+नहीं\s+है",
    r"आप\s+अदालत\s+में\s+अवश्य\s+(?:जीतेंगे|हारेंगे)",
    # Telugu
    r"ఈ\s+నోటీసు\s+(?:పూర్తిగా\s+)?(?:చట్టవిరుద్ధం|చెల్లదు)",
    r"ఈ\s+నోటీసు\s+(?:పూర్తిగా\s+)?(?:చట్టబద్ధమైనది|చెల్లుతుంది)",
    r"మీరు\s+ఖచ్చితంగా\s+చెల్లించాలి",
    r"మీరు\s+చెల్లించాల్సిన\s+అవసరం\s+లేదు"
]

def scan_for_injection(text: str) -> Tuple[bool, List[str]]:
    """
    Scans text for prompt injection keywords/patterns.
    Returns (has_injection, detected_patterns).
    """
    if not text:
        return False, []
    
    detected = []
    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            detected.append(match.group(0))
    
    return (len(detected) > 0), detected

def is_verdict_query(query: str) -> bool:
    """
    Checks if a user's question asks for a legal opinion, enforceability
    determination, or payment advice.
    """
    if not query:
        return False
    
    for pattern in VERDICT_QUERY_PATTERNS:
        if re.search(pattern, query):
            return True
    return False

def sanitize_output_verdicts(text: str, language: str = "en") -> str:
    """
    Inspects model-generated text and replaces any unauthorized legal verdicts
    with a neutral escalation reminder.
    """
    if not text:
        return ""
    
    cleaned_text = text
    for pattern in OUTPUT_VERDICT_BLOCKLIST:
        if re.search(pattern, cleaned_text):
            cleaned_text = re.sub(
                pattern,
                "[Legal determination omitted - Please consult an advocate]",
                cleaned_text
            )
    
    return cleaned_text

def get_refusal_message(language: str = "en", strings_dict: Dict[str, Any] = None) -> str:
    """Returns the standardized, localized legal refusal message."""
    if strings_dict and "refusals" in strings_dict and "legal_advice" in strings_dict["refusals"]:
        return strings_dict["refusals"]["legal_advice"]
    
    if language == "hi":
        return "NoticeGuard कानूनी सलाह नहीं दे सकता, न ही यह तय कर सकता है कि यह नोटिस कानूनी रूप से वैध है या आपको भुगतान करना चाहिए या नहीं। कृपया वकील चेकलिस्ट की सहायता से किसी योग्य अधिवक्ता से परामर्श लें।"
    elif language == "te":
        return "NoticeGuard చట్టపరమైన సలహాను అందించలేదు, ఈ నోటీసు చెల్లుబాటు అవుతుందో లేదో లేదా మీరు చెల్లించాలా వద్దా అని నిర్ణయించలేదు. దయచేసి న్యాయవాది చెక్‌లిస్ట్ ఉపయోగించి అర్హత కలిగిన న్యాయవాదిని సంప్రదించండి."
    return "NoticeGuard cannot provide legal advice, determine if this notice is legally valid or enforceable, or advise whether you should pay. Please consult a qualified advocate using the Lawyer Escalation Checklist."

def get_silent_message(language: str = "en", strings_dict: Dict[str, Any] = None) -> str:
    """Returns the standardized message for questions unaddressed in notice."""
    if strings_dict and "refusals" in strings_dict and "silent" in strings_dict["refusals"]:
        return strings_dict["refusals"]["silent"]
    
    if language == "hi":
        return "नोटिस में इस बारे में कुछ नहीं कहा गया है।"
    elif language == "te":
        return "నోటీసులో ఈ అంశం గురించి ప్రస్తావించబడలేదు."
    return "The notice does not address this."
