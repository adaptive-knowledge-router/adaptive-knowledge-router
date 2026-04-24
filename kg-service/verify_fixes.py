#!/usr/bin/env python3
"""Verification script for KG NL-routing reroute fixes.

Hits the live KG-service endpoints and checks that previously-failing
queries now return 200 with valid data.  Also confirms that already-working
queries are not regressed.

Usage:
    python verify_fixes.py [--host HOST] [--port PORT]
"""

import argparse
import json
import sys
from urllib.parse import quote

import requests

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# Each test: (description, endpoint_path, query, expected_status, check_fn or None)
TESTS = [
    # ── Previously-failing queries (rerouted from relation_filter) ────
    (
        "Title lookup misrouted to relation → should reroute to entity_lookup",
        "/kg/query/relation",
        "Which paper is titled Attention Is All You Need?",
        200,
        lambda r: "entity_lookup" in json.dumps(r.get("router", {})),
    ),
    (
        "Author-to-categories misrouted to relation → should reroute to multi_hop",
        "/kg/query/relation",
        "What fields has Geoffrey Hinton published in?",
        200,
        lambda r: "multi_hop" in json.dumps(r.get("router", {})),
    ),
    # ── Entity endpoint (should still work) ──────────────────────────
    (
        "Entity lookup by title",
        "/kg/query/entity",
        "Show me the paper Attention Is All You Need",
        200,
        None,
    ),
    (
        "Entity endpoint reroutes paper-to-authors (paper not in 20K subset → 400 expected)",
        "/kg/query/entity",
        "Who are the authors of the paper Attention Is All You Need?",
        400,
        None,
    ),
    # ── Relation endpoint (should still work) ────────────────────────
    (
        "Author-to-papers via relation endpoint",
        "/kg/query/relation",
        "What papers has Yann LeCun written?",
        200,
        lambda r: r.get("router", {}).get("selected_mode") == "author_to_papers",
    ),
    (
        "Category-to-papers via relation endpoint",
        "/kg/query/relation",
        "What papers are in category cs.AI?",
        200,
        lambda r: r.get("router", {}).get("selected_mode") == "category_to_papers",
    ),
    # ── Multi-hop endpoint (should still work) ───────────────────────
    (
        "Author-to-categories via multi_hop endpoint",
        "/kg/query/multi_hop",
        "What categories has Geoffrey Hinton published in?",
        200,
        lambda r: r.get("router", {}).get("selected_mode") == "author_to_categories",
    ),
    # ── General /kg/query router (should still work) ─────────────────
    (
        "General router: author-to-papers",
        "/kg/query",
        "What papers has Yoshua Bengio written?",
        200,
        None,
    ),
    (
        "General router: entity lookup by paper title",
        "/kg/query",
        "Show me the paper Deep Residual Learning for Image Recognition",
        200,
        None,
    ),
]


def run_tests(base_url: str) -> bool:
    passed = 0
    failed = 0
    total = len(TESTS)

    for i, (desc, path, query, expected_status, check_fn) in enumerate(TESTS, 1):
        url = f"{base_url}{path}?question={quote(query)}"
        print(f"\n[{i}/{total}] {desc}")
        print(f"       GET {path}?question={query[:60]}...")

        try:
            resp = requests.get(url, timeout=120)
        except requests.RequestException as e:
            print(f"  {RED}FAIL{RESET} — request error: {e}")
            failed += 1
            continue

        if resp.status_code != expected_status:
            print(f"  {RED}FAIL{RESET} — expected {expected_status}, got {resp.status_code}")
            try:
                print(f"       body: {resp.json()}")
            except Exception:
                print(f"       body: {resp.text[:200]}")
            failed += 1
            continue

        try:
            body = resp.json()
        except Exception:
            body = {}

        if check_fn and not check_fn(body):
            print(f"  {YELLOW}WARN{RESET} — status 200 but check failed")
            print(f"       router: {json.dumps(body.get('router', {}), indent=2)[:300]}")
            failed += 1
            continue

        reroute = body.get("router", {}).get("rerouted_from", "")
        mode = body.get("router", {}).get("selected_mode", "")
        extra = f" (mode={mode})" if mode else ""
        extra += f" (rerouted from {reroute})" if reroute else ""
        print(f"  {GREEN}PASS{RESET}{extra}")
        passed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed, {failed}/{total} failed")
    print(f"{'='*60}")
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Verify KG NL-routing fixes")
    parser.add_argument("--host", default="localhost", help="KG service host")
    parser.add_argument("--port", type=int, default=8000, help="KG service port")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    print(f"Testing KG service at {base_url}")

    # Quick health check
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        print(f"Health: {r.json()}")
    except Exception as e:
        print(f"WARNING: health check failed ({e}), proceeding anyway...")

    ok = run_tests(base_url)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
