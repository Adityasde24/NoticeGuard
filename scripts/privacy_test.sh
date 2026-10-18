#!/usr/bin/env bash
# NoticeGuard - Offline & Network Privacy Verification Script
# Verifies zero outbound network packets during notice analysis.

set -e

echo "========================================================================"
echo "  NOTICEGUARD PRIVACY TEST: OFFLINE NETWORK AUDIT"
echo "========================================================================"

# Run the Python privacy audit
python3 scripts/privacy_test.py || python scripts/privacy_test.py

echo ""
echo "NoticeGuard successfully completed all processing without external network calls."
