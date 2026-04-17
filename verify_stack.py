#!/usr/bin/env python3
"""
Adaptive Knowledge Router – Stack Verification Script.

Checks whether each service is healthy, models are loaded,
and indexes are ready. Run from the project root:

    python verify_stack.py            # default localhost ports
    python verify_stack.py --wait 90  # poll until ready or timeout

Exit codes:
    0  all services healthy
    1  one or more services not ready
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

SERVICES = {
    "router": {"url": "http://localhost:8001/health", "ready_key": "model_loaded"},
    "kg": {"url": "http://localhost:8000/kg/health", "ready_key": None},
    "rag": {"url": "http://localhost:8002/health", "ready_key": None},
    "orchestrator": {"url": "http://localhost:8003/health", "ready_key": None},
}

# Optional deep check — orchestrator readiness (pings downstream services)
READINESS_URL = "http://localhost:8003/readiness"

# Cold-start reference
WARM_UP_NOTES = {
    "router": "Model loads in ~2-5 s (local safetensors).",
    "kg": "Fast once Neo4j is healthy. First NL query downloads the Ollama model (~1 min on first run).",
    "rag": "Slowest service. First start builds FAISS index from scratch (5-15 min). Subsequent starts reuse the persisted index volume (<30 s).",
    "orchestrator": "Starts instantly, but waits for downstream services.",
}


def _probe(url: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """GET a URL and return parsed JSON, or None on any failure."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except Exception:
        return None


def _status_line(name: str, data: Optional[Dict[str, Any]], ready_key: Optional[str]) -> Tuple[str, bool]:
    """Return a human-readable status and a boolean healthy flag."""
    if data is None:
        return "UNREACHABLE", False

    status = str(data.get("status", "unknown"))
    if ready_key and not bool(data.get(ready_key, False)):
        return "LOADING", False

    return status.upper(), status == "ok"


def check_all(verbose: bool = False) -> bool:
    """Probe every service once. Returns True when all are healthy."""
    all_ok = True

    for name, cfg in SERVICES.items():
        data = _probe(cfg["url"])
        label, ok = _status_line(name, data, cfg["ready_key"])
        mark = "✓" if ok else "✗"
        extra = ""
        if verbose and data is not None:
            extra = "  " + json.dumps(data)
        print(f"  {mark} {name:14s} {label}{extra}")
        if not ok:
            all_ok = False

    # Deep check through orchestrator /readiness
    readiness = _probe(READINESS_URL)
    if readiness is not None:
        r_status = str(readiness.get("status", "unknown")).upper()
        mark = "✓" if r_status == "OK" else "✗"
        svcs = readiness.get("services", {})
        detail = ", ".join(f"{k}={v}" for k, v in svcs.items())
        print(f"  {mark} {'readiness':14s} {r_status}  ({detail})")
        if r_status != "OK":
            all_ok = False
    else:
        print(f"  ✗ {'readiness':14s} UNREACHABLE (orchestrator down)")
        all_ok = False

    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the AKR stack.")
    parser.add_argument(
        "--wait",
        type=int,
        default=0,
        metavar="SEC",
        help="Poll until all services are ready or SEC seconds elapse.",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    deadline = time.monotonic() + args.wait if args.wait > 0 else 0

    print("─── AKR Stack Verification ───\n")

    attempt = 0
    while True:
        attempt += 1
        if attempt > 1:
            print(f"\n  … retry #{attempt}")

        ok = check_all(verbose=args.verbose)

        if ok:
            print("\n  All services healthy ✓")
            sys.exit(0)

        if deadline and time.monotonic() < deadline:
            remaining = int(deadline - time.monotonic())
            print(f"\n  Not ready yet — retrying (≤{remaining}s left) …")
            time.sleep(5)
            continue

        break

    print("\n  ⚠  Some services are not ready.")
    print("\n─── Cold-Start Reference ───\n")
    for name, note in WARM_UP_NOTES.items():
        print(f"  {name:14s}  {note}")
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()