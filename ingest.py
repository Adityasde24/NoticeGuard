"""
NoticeGuard - Ingestion Module.
Handles loading legal notices from PDF, TXT files, or pasted raw text.
Enforces local security: isolates temporary files and wipes them cleanly on demand.
"""

import os
import shutil
import tempfile
from typing import Optional, Tuple, Dict, Any

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit

class IngestError(Exception):
    """Custom exception for user-friendly ingestion errors."""
    pass

def get_temp_directory() -> str:
    """Returns the dedicated local temporary directory for NoticeGuard."""
    temp_dir = os.path.join(tempfile.gettempdir(), "noticeguard_isolated_temp")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def wipe_temp_directory() -> None:
    """Securely clears and deletes all temporary files created during processing."""
    temp_dir = get_temp_directory()
    if os.path.exists(temp_dir):
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception:
                pass

def extract_text_from_pdf(pdf_path_or_bytes: Any) -> str:
    """
    Extracts text from PDF using PyMuPDF (fitz) with safe fallback.
    Provides friendly errors for password protection or scanned images without text.
    """
    try:
        import pymupdf as fitz  # PyMuPDF
    except ImportError:
        raise IngestError("PyMuPDF (fitz) is not installed. Please install it with 'pip install pymupdf'.")

    try:
        if isinstance(pdf_path_or_bytes, (bytes, bytearray)):
            doc = fitz.open(stream=pdf_path_or_bytes, filetype="pdf")
        elif isinstance(pdf_path_or_bytes, str):
            if not os.path.exists(pdf_path_or_bytes):
                raise IngestError(f"File not found: {pdf_path_or_bytes}")
            doc = fitz.open(pdf_path_or_bytes)
        else:
            raise IngestError("Unsupported input type for PDF extraction.")

        if doc.is_encrypted:
            raise IngestError("The provided PDF is encrypted or password-protected. Please provide an unlocked document.")

        full_text = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text:
                full_text.append(text)

        doc.close()

        extracted = "\n\n".join(full_text).strip()
        if not extracted:
            raise IngestError("The PDF appears to be a scanned image or empty. NoticeGuard currently requires text-based PDFs.")
        
        return extracted
    except IngestError:
        raise
    except Exception as e:
        raise IngestError(f"Failed to process PDF: {str(e)}")

def ingest_document(
    file_bytes: Optional[bytes] = None,
    file_name: Optional[str] = None,
    pasted_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified ingestion entry point. Accepts uploaded file bytes or pasted string.
    Returns metadata dict: { 'source': ..., 'text': ..., 'char_count': ..., 'format': ... }
    """
    if pasted_text and pasted_text.strip():
        text = pasted_text.strip()
        return {
            "source": "pasted_text",
            "format": "text",
            "text": text,
            "char_count": len(text)
        }

    if file_bytes is not None and file_name:
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise IngestError("File size exceeds 50MB limit. Please upload a shorter notice.")

        ext = os.path.splitext(file_name)[1].lower()
        if ext == ".pdf":
            text = extract_text_from_pdf(file_bytes)
            return {
                "source": file_name,
                "format": "pdf",
                "text": text,
                "char_count": len(text)
            }
        elif ext in [".txt", ".text"]:
            if b"\x00" in file_bytes:
                raise IngestError("Corrupted or binary file detected. Please provide a valid plain text document.")
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raise IngestError("Unable to decode text file. Ensure it is UTF-8 encoded.")
            
            text = text.strip()
            if not text:
                raise IngestError("The uploaded text file is empty.")
            
            return {
                "source": file_name,
                "format": "txt",
                "text": text,
                "char_count": len(text)
            }
        else:
            raise IngestError(f"Unsupported file format '{ext}'. Please upload a PDF or TXT file.")

    raise IngestError("No document provided. Please upload a file or paste notice text.")

# Pre-Triage Legal Document Validation Patterns (EN / HI / TE)
LEGAL_NOTICE_PATTERNS = [
    # English Primary Legal Markers
    r"(?i)\b(?:legal\s+)?notice\b",
    r"(?i)\bdemand\s+(?:notice|letter|note)\b",
    r"(?i)\b(?:call\s+upon\s+you|hereby\s+(?:demand|notify|terminate|serve|call))\b",
    r"(?i)\b(?:section\s+\d+|u/s\s+\d+|clause\s+\d+)\b",
    r"(?i)\b(?:negotiable\s+instruments|transfer\s+of\s+property|limitation\s+act|arbitration\s+(?:and\s+conciliation)?\s+act)\b",
    r"(?i)\b(?:cheque\s+(?:no|dishonou?r|bounce)|return\s+memo|insufficient\s+funds)\b",
    r"(?i)\b(?:tenan(?:t|cy)|landlord|vacate\s+(?:and\s+hand\s+over|the\s+premises)|arrears\s+of\s+rent|mesne\s+profits)\b",
    r"(?i)\b(?:advocate|counsel|high\s+court|civil\s+court|district\s+court|legal\s+proceedings)\b",
    r"(?i)\b(?:under\s+instructions\s+from|on\s+behalf\s+of\s+my\s+client)\b",
    r"(?i)\b(?:breach\s+of\s+(?:contract|agreement|terms)|termination\s+(?:notice|letter)|employment\s+bond)\b",
    r"(?i)\b(?:outstanding\s+dues|unpaid\s+(?:invoices?|balance|salary)|recover(?:y)?\s+of\s+(?:debt|money))\b",
    r"(?i)\b(?:without\s+prejudice|failing\s+which|in\s+default\s+whereof|cause\s+of\s+action)\b",
    r"(?i)\b(?:cure\s+period|rectify\s+(?:the\s+)?default|cease\s+and\s+desist)\b",
    # Hindi Legal Markers
    r"(?:कानूनी\s+)?नोटिस",
    r"(?:मांग\s+पत्र|वैधानिक\s+नोटिस)",
    r"(?:अधिवक्ता|वकील|मुवक्किल|न्यायालय|अदालत|धारा\s+\d+)",
    r"(?:चेक\s+बाउंस|अनादरण|अपर्याप्त\s+राशि)",
    r"(?:किरायेदार|मकान\s+मालिक|परिसर\s+खाली|बकाया\s+किराया)",
    r"(?:कानूनी\s+कार्रवाई|हर्जाना|वसूली)",
    # Telugu Legal Markers
    r"(?:చట్టపరమైన\s+)?నోటీసు",
    r"(?:డిమాండ్\s+నోటీసు|చట్టబద్ధమైన\s+నోటీసు)",
    r"(?:న్యాయవాది|క్లయింట్|కోర్టు|సెక్షన్\s+\d+)",
    r"(?:చెక్\s+బౌన్స్|అనాదరణ)",
    r"(?:అద్దెదారు|యజమాని|ఖాళీ\s+చేయడం|బకాయిలు)",
    r"(?:చట్టపరమైన\s+చర్యలు|నష్టపరిహారం)"
]

def validate_is_legal_notice(text: str) -> Tuple[bool, str]:
    """
    Deterministic Pre-Triage Document Validator.
    Verifies that the uploaded/pasted text is a legitimate legal notice,
    statutory demand, or termination letter before invoking any LLM or triage pipeline.
    Rejects recipes, homework, code, or arbitrary non-legal texts.
    Returns (is_valid, reason_or_message).
    """
    if not text or len(text.strip()) < 40:
        return False, "The input document is too short (< 40 characters) to be an actionable legal notice."

    import re
    cleaned = text.strip()
    matched_markers = []
    for pattern in LEGAL_NOTICE_PATTERNS:
        match = re.search(pattern, cleaned)
        if match:
            matched_markers.append(match.group(0))

    if len(matched_markers) == 0:
        return False, "The uploaded file or text does not appear to be a legal notice, contract, or formal demand letter. Please upload a valid legal notice or termination document to run triage."

    # For longer texts (> 200 chars), require at least 2 distinct legal markers to avoid false positives on random text
    if len(cleaned) > 200 and len(matched_markers) < 2:
        return False, "The uploaded file or text does not appear to be a legal notice, contract, or formal demand letter. Please upload a valid legal notice or termination document to run triage."

    return True, f"Valid legal notice detected ({len(matched_markers)} legal markers identified)."
