"""
NoticeGuard - Privacy & Network Isolation Verification Test (privacy_test.py).
Ensures that processing legal notices generates ZERO outbound network calls.
Audits all socket connections to prove strictly local-first processing on 127.0.0.1.
"""

import sys
import socket
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Track all attempted socket connections
monitored_connections = []
original_connect = socket.socket.connect

def monitored_socket_connect(self, address):
    host, port = address[0], address[1]
    monitored_connections.append({"host": host, "port": port})
    # Only allow 127.0.0.1 / localhost
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise PermissionError(f"PRIVACY VIOLATION DETECTED: Attempted non-local network call to {host}:{port}")
    return original_connect(self, address)

# Intercept all socket connections
socket.socket.connect = monitored_socket_connect

def run_privacy_audit():
    print("=" * 70)
    print("  NOTICEGUARD ZERO-NETWORK LEAKAGE PRIVACY AUDIT")
    print("=" * 70)
    
    from ingest import ingest_document
    from segment import segment_notice
    from extract import extract_facts
    from verify import verify_facts
    from timeline import compute_timeline
    from explain import generate_plain_explanation
    from escalate import build_lawyer_checklist
    from translate import translate_text

    test_file = PROJECT_ROOT / "tests" / "fixtures" / "notice_01_cheque_bounce_en.txt"
    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()

    print("\n[+] Ingesting document...")
    ingest_res = ingest_document(pasted_text=content)

    print("[+] Segmenting into numbered passages...")
    passages = segment_notice(ingest_res["text"])

    print("[+] Extracting facts locally...")
    facts = extract_facts(ingest_res["text"], passages)

    print("[+] Verifying quotes, amounts, and deadlines in code...")
    v_facts = verify_facts(facts, ingest_res["text"], passages)

    print("[+] Computing timeline and deadlines...")
    tl = compute_timeline(v_facts)

    print("[+] Generating plain-language breakdowns...")
    expl = generate_plain_explanation(passages, v_facts)

    print("[+] Building lawyer consultation brief...")
    cl = build_lawyer_checklist(v_facts, tl, passages, ingest_res["text"])

    print("[+] Testing Hindi and Telugu local translations...")
    _ = translate_text("Pay the sum of Rs. 75,000 within 15 days", "hi")
    _ = translate_text("Pay the sum of Rs. 75,000 within 15 days", "te")

    print("\n" + "-" * 70)
    print(f"Total socket connections attempted: {len(monitored_connections)}")
    
    external_calls = [c for c in monitored_connections if c["host"] not in ("127.0.0.1", "localhost", "::1")]
    local_calls = [c for c in monitored_connections if c["host"] in ("127.0.0.1", "localhost", "::1")]
    
    print(f"Local loopback calls (127.0.0.1 / Ollama): {len(local_calls)}")
    print(f"External internet calls: {len(external_calls)}")
    print("-" * 70)

    if len(external_calls) == 0:
        print("[PASS] PRIVACY AUDIT PASSED: ZERO EXTERNAL CONNECTIONS MADE!")
        print("       All processing occurred 100% locally on the device (127.0.0.1).")
        print("=" * 70)
        return True
    else:
        print("[FAIL] PRIVACY AUDIT FAILED: Non-local connections were attempted:")
        for c in external_calls:
            print(f"   - {c['host']}:{c['port']}")
        print("=" * 70)
        return False

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    passed = run_privacy_audit()
    sys.exit(0 if passed else 1)
