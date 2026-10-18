"""
NoticeGuard - Benchmark Suite (benchmark.py).
Measures processing speed, latency, and memory footprint across notice types
and languages (English, Hindi, Telugu).
"""

import sys
import time
import tracemalloc
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ingest import ingest_document
from segment import segment_notice
from extract import extract_facts
from verify import verify_facts
from timeline import compute_timeline
from explain import generate_plain_explanation
from escalate import build_lawyer_checklist
from translate import translate_text

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

def run_benchmark():
    print("=" * 80)
    print("  NOTICEGUARD PERFORMANCE & MEMORY FOOTPRINT BENCHMARK")
    print("=" * 80)

    test_files = [
        ("notice_01_cheque_bounce_en.txt", "Cheque Bounce (EN)", "English"),
        ("notice_01_cheque_bounce_hi.txt", "Cheque Bounce (HI)", "Hindi"),
        ("notice_01_cheque_bounce_te.txt", "Cheque Bounce (TE)", "Telugu"),
        ("notice_02_eviction_en.txt", "Eviction Notice (EN)", "English"),
        ("notice_03_ambiguous_demand_en.txt", "Ambiguous Demand (EN)", "English"),
        ("notice_04_prompt_injection_en.txt", "Injection Notice (EN)", "English"),
        ("notice_05_no_deadline_en.txt", "Advisory Letter (EN)", "English")
    ]

    benchmarks = []

    for filename, label, lang in test_files:
        filepath = FIXTURES_DIR / filename
        if not filepath.exists():
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # Start tracking memory and time
        tracemalloc.start()
        start_time = time.perf_counter()

        # Full pipeline run
        doc = ingest_document(pasted_text=raw_text)
        passages = segment_notice(doc["text"])
        facts = extract_facts(doc["text"], passages)
        v_facts = verify_facts(facts, doc["text"], passages)
        tl = compute_timeline(v_facts)
        expl = generate_plain_explanation(passages, v_facts)
        cl = build_lawyer_checklist(v_facts, tl, passages, doc["text"])
        
        # Test translation latency if applicable
        if lang == "Hindi":
            _ = translate_text("Pay the sum within 15 days", "hi")
        elif lang == "Telugu":
            _ = translate_text("Pay the sum within 15 days", "te")

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        benchmarks.append({
            "notice": label,
            "language": lang,
            "chars": len(raw_text),
            "passages": len(passages),
            "latency_ms": elapsed_ms,
            "peak_mem_kb": peak_mem / 1024.0
        })

    # Print Table
    print(f"\n{'NOTICE TYPE':<26} | {'LANG':<8} | {'CHARS':<6} | {'PASSAGES':<9} | {'LATENCY':<12} | {'PEAK RAM':<10}")
    print("-" * 80)
    for b in benchmarks:
        print(f"{b['notice']:<26} | {b['language']:<8} | {b['chars']:<6} | {b['passages']:<9} | {b['latency_ms']:>8.2f} ms | {b['peak_mem_kb']:>7.1f} KB")

    print("=" * 80)
    avg_latency = sum(b["latency_ms"] for b in benchmarks) / len(benchmarks)
    avg_mem = sum(b["peak_mem_kb"] for b in benchmarks) / len(benchmarks)
    print(f"Summary: Average Latency: {avg_latency:.2f} ms | Average Memory: {avg_mem:.1f} KB")
    print("=" * 80)

if __name__ == "__main__":
    run_benchmark()
