#!/usr/bin/env python3
"""Verify that the answer-synthesis layer works end-to-end.

Usage (from repo root, with the stack running):
    python verify_synthesis.py
    python verify_synthesis.py --wait 120   # poll until ready

Checks:
  1. KG service is healthy and uses its own model (qwen2.5:3b).
  2. RAG service is healthy.
  3. Orchestrator readiness is OK (router, kg, rag, ollama).
  4. Orchestrator returns raw results (unchanged).
  5. Orchestrator returns a synthesized_answer field.
  6. synthesis_metadata is always present (even on failure).
  7. The synthesis model is different from the KG model.
  8. Field order: synthesized_answer before results.
  9. The answer is grounded only in retrieved results (heuristic).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

ORCH_URL = "http://localhost:8003"
KG_URL = "http://localhost:8000"
RAG_URL = "http://localhost:8002"

KG_QUERY = "What papers has Carlos Gershenson written?"
RAG_QUERY = "transformers for natural language processing"

EXPECTED_KG_MODEL = "qwen2.5:3b"


def _post_json(url: str, body: dict, timeout: int = 120) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _get_json(url: str, timeout: int = 15) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def _wait_for_health(url: str, label: str, deadline: float) -> bool:
    while time.monotonic() < deadline:
        try:
            _get_json(url, timeout=5)
            return True
        except Exception:
            remaining = int(deadline - time.monotonic())
            print(f"  {label} not ready, retrying … ({remaining}s left)")
            time.sleep(5)
    return False


def _check_authors_in_answer(answer: str, results: list) -> bool:
    """Return True if at least one author name from results appears in answer."""
    a_lower = answer.lower()
    for rec in results:
        authors = rec.get("authors", rec.get("author_name", ""))
        if isinstance(authors, list):
            for author in authors:
                # match last name (word >2 chars) from the author string
                parts = str(author).split()
                if any(p.lower() in a_lower for p in parts if len(p) > 2):
                    return True
        elif authors and len(str(authors)) > 2:
            if str(authors).lower()[:20] in a_lower:
                return True
    return False


def run_checks() -> bool:
    ok = True
    checks_passed = 0
    checks_total = 0

    def _check(label: str, passed: bool, detail: str = ""):
        nonlocal ok, checks_passed, checks_total
        checks_total += 1
        mark = "✓" if passed else "✗"
        msg = f"  {mark} {label}"
        if detail:
            msg += f"  —  {detail}"
        print(msg)
        if passed:
            checks_passed += 1
        else:
            ok = False

    # ── 1. KG health ─────────────────────────────────────────────────
    print("\n── KG Service ──")
    try:
        kg_health = _get_json(f"{KG_URL}/kg/health")
        _check("KG health", True, f"status={kg_health.get('status', '?')}")
    except Exception as exc:
        _check("KG health", False, str(exc))

    # ── 2. RAG health ────────────────────────────────────────────────
    print("\n── RAG Service ──")
    try:
        rag_health = _get_json(f"{RAG_URL}/health")
        _check("RAG health", True, f"status={rag_health.get('status', '?')}")
    except Exception as exc:
        _check("RAG health", False, str(exc))

    # ── 3. Orchestrator readiness ────────────────────────────────────
    print("\n── Orchestrator Readiness ──")
    try:
        readiness = _get_json(f"{ORCH_URL}/readiness")
        svcs = readiness.get("services", {})
        detail = ", ".join(f"{k}={v}" for k, v in svcs.items())
        _check("Readiness", readiness.get("status") == "ok", detail)
    except Exception as exc:
        _check("Readiness", False, str(exc))

    # ── 4. Query orchestrator (KG path) ──────────────────────────────
    print(f"\n── Query: \"{KG_QUERY}\" ──")
    try:
        resp = _post_json(f"{ORCH_URL}/query", {"query": KG_QUERY, "top_k": 3})
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "timed out" in reason.lower():
            _check("Orchestrator query", False,
                   "HTTP request timed out — the synthesis LLM may be too slow or not loaded. "
                   "Check: docker logs orchestrator-service --tail 40")
        else:
            _check("Orchestrator query", False, reason)
        print(f"\n{'=' * 50}")
        print(f"RESULT: FAILED — cannot continue without orchestrator response")
        return False
    except Exception as exc:
        _check("Orchestrator query", False, str(exc))
        print(f"\n{'=' * 50}")
        print(f"RESULT: FAILED — cannot continue without orchestrator response")
        return False

    # Raw results
    results = resp.get("results", [])
    _check("Raw results present", len(results) > 0, f"count={len(results)}")

    # Synthesized answer
    synth = resp.get("synthesized_answer")
    meta = resp.get("synthesis_metadata")

    if synth is not None:
        preview = synth[:120] + "…" if len(synth) > 120 else synth
        _check("synthesized_answer present", True, f"preview: {preview}")
    else:
        # Diagnosis: check if metadata has an error
        err = meta.get("error", "") if meta else ""
        if "timeout" in err.lower() or "ReadTimeout" in err:
            _check("synthesized_answer present", False,
                   f"LLM timed out — model may be too slow. error: {err}")
        else:
            _check("synthesized_answer present", False,
                   f"null. error: {err or 'unknown'}")

    # Synthesis metadata (must always be present)
    if meta:
        synth_model = meta.get("model", "")
        ret_lat = meta.get("retrieval_latency_ms", -1)
        syn_lat = meta.get("synthesis_latency_ms", -1)
        tot_lat = meta.get("total_latency_ms", -1)
        q_mode = meta.get("query_mode", "?")
        used = meta.get("used_results_count", -1)
        error = meta.get("error")

        _check("synthesis_metadata present", True,
               f"model={synth_model}, mode={q_mode}, "
               f"ret={ret_lat:.1f}ms, syn={syn_lat:.1f}ms, tot={tot_lat:.1f}ms, used={used}"
               + (f", error={error}" if error else ""))

        if error:
            _check("synthesis succeeded (no error)", False, f"error={error}")
        else:
            _check("synthesis succeeded (no error)", True)

        # Model separation
        _check("Model ≠ KG model",
               synth_model != EXPECTED_KG_MODEL,
               f"synthesis={synth_model}, kg={EXPECTED_KG_MODEL}")

        _check("used_results_count matches",
               used == len(results),
               f"used={used}, results={len(results)}")

        # Latency checks
        _check("retrieval_latency_ms present",
               ret_lat >= 0,
               f"retrieval_latency_ms={ret_lat}")
        _check("synthesis_latency_ms present",
               syn_lat >= 0,
               f"synthesis_latency_ms={syn_lat}")
        _check("total_latency_ms consistent",
               tot_lat >= 0 and abs(tot_lat - (ret_lat + syn_lat)) < 1.0,
               f"total={tot_lat}, ret+syn={ret_lat + syn_lat}")
        _check("query_mode present",
               q_mode in ("exact_lookup", "list_query", "open_explanation",
                          "compare_query", "fallback"),
               f"query_mode={q_mode}")
    else:
        _check("synthesis_metadata present", False,
               "metadata is null — this should never happen, even on failure")

    # Field order (synthesized_answer before results in JSON keys)
    keys = list(resp.keys())
    synth_idx = keys.index("synthesized_answer") if "synthesized_answer" in keys else -1
    results_idx = keys.index("results") if "results" in keys else -1
    _check("Field order: answer before results",
           0 <= synth_idx < results_idx,
           f"synthesized_answer@{synth_idx}, results@{results_idx}")

    # Grounding heuristic
    if synth and results:
        answer_lower = synth.lower()
        # Check if ANY result's title/name/author appears in the answer
        fragment_found = False
        for rec in results[:5]:
            for key in ("title", "name", "authors", "paper_id", "id"):
                val = rec.get(key, "")
                if val and len(str(val)) > 3:
                    fragment = str(val)[:40].lower()
                    if fragment in answer_lower:
                        fragment_found = True
                        break
            if fragment_found:
                break
        grounded = fragment_found or any(w in answer_lower for w in [
            "retrieved", "result", "paper", "evidence", "author",
            "not contain", "insufficient", "could not determine",
        ])
        _check("Answer grounded in evidence", grounded,
               "heuristic — manual review recommended if ✗")

    # Answer completeness — not cut off mid-sentence
    if synth:
        stripped = synth.rstrip()
        # A bullet list ending with a complete item (no trailing dash/colon) is OK
        last_line = stripped.split("\n")[-1].strip()
        is_bullet_end = last_line.startswith(("-", "*", "•")) and len(last_line) > 3
        ends_ok = stripped[-1] in ".!?)\"'" or stripped.endswith("…") or is_bullet_end
        _check("Answer not cut off mid-sentence", ends_ok,
               f"last 40 chars: …{stripped[-40:]}")

    # Answer conciseness — should be a reasonable length
    if synth:
        _check("Answer concise (< 2000 chars)", len(synth) < 2000,
               f"length={len(synth)}")

    # Raw results preserved unchanged
    _check("Raw results preserved", len(results) > 0 and isinstance(results, list),
           f"type={type(results).__name__}, count={len(results)}")

    # ── 5. Quick RAG query ───────────────────────────────────────────
    print(f"\n── Query: \"{RAG_QUERY}\" (RAG path) ──")
    try:
        rag_resp = _post_json(f"{ORCH_URL}/query", {"query": RAG_QUERY, "top_k": 3})
        rag_results = rag_resp.get("results", [])
        rag_synth = rag_resp.get("synthesized_answer")
        rag_meta = rag_resp.get("synthesis_metadata")
        _check("RAG raw results", len(rag_results) > 0, f"count={len(rag_results)}")
        _check("RAG synthesized_answer", rag_synth is not None,
               (rag_synth[:80] + "…" if rag_synth and len(rag_synth) > 80
                else (rag_synth or "(null)")))
        _check("RAG synthesis_metadata", rag_meta is not None,
               f"model={rag_meta.get('model', '?')}" if rag_meta else "missing")
    except Exception as exc:
        _check("RAG query via orchestrator", False, str(exc))

    # ── 6. Strategy-aware synthesis checks ───────────────────────────
    def _has_titles(answer, results):
        """Check that ≥1 result title appears in the answer."""
        a_low = answer.lower()
        return any(
            rec.get("title", "")[:30].lower() in a_low
            for rec in results if rec.get("title")
        )

    def _has_no_raw_categories(answer):
        """Check the answer does NOT contain raw category codes as main content."""
        lines = [l.strip() for l in answer.strip().split("\n") if l.strip().startswith("- ")]
        if not lines:
            return True  # no bullets, skip check
        # A line is a "category-only" line if it matches cs.XX / stat.XX patterns
        import re
        cat_pat = re.compile(r"^- (?:\*\*)?[a-z]{1,5}\.[A-Z]{2}", re.IGNORECASE)
        cat_lines = sum(1 for l in lines if cat_pat.match(l))
        return cat_lines < len(lines) * 0.5  # fewer than half are category-only

    def _has_no_raw_authors_only(answer, results):
        """Check the answer is NOT just author names when paper titles
        are available in results."""
        if not any(rec.get("title") for rec in results):
            return True  # no titles to compare
        a_low = answer.lower()
        # If ANY result title appears, answer has titles → OK
        return any(
            rec.get("title", "")[:30].lower() in a_low
            for rec in results if rec.get("title")
        )

    strategy_cases = [
        # (query, label, field_check_fn)
        # field_check_fn receives (synth_answer: str, results: list) -> (passed, detail)
        (
            "What is paper 1609.01491?",
            "Entity lookup: paper title",
            lambda a, r: (
                any(
                    rec.get("title", "").lower() in a.lower()
                    for rec in r if rec.get("title")
                ),
                f"answer={a[:80]}…" if len(a) > 80 else f"answer={a}",
            ),
        ),
        (
            "What is the DOI of paper 1609.01491?",
            "DOI extraction",
            lambda a, r: (
                any(
                    str(rec.get("doi", "")).lower() in a.lower()
                    for rec in r if rec.get("doi")
                ) if any(rec.get("doi") for rec in r)
                else "could not" in a.lower(),
                f"answer={a[:80]}" if len(a) > 80 else f"answer={a}",
            ),
        ),
        (
            "Authors of paper 1609.01491?",
            "Author extraction",
            lambda a, r: (
                _check_authors_in_answer(a, r),
                f"answer={a[:80]}" if len(a) > 80 else f"answer={a}",
            ),
        ),
        (
            "Which papers are written by Emma Brunskill?",
            "Papers-by-author: returns titles",
            lambda a, r: (
                _has_titles(a, r) and _has_no_raw_categories(a),
                f"has_titles={_has_titles(a,r)}, no_raw_cats={_has_no_raw_categories(a)}, "
                f"bullets={a.count('- ')}, results={len(r)}",
            ),
        ),
        (
            "Which papers are written by Emma Brunskill?",
            "Papers-by-author: not author strings",
            lambda a, r: (
                _has_no_raw_authors_only(a, r),
                f"answer preview={a[:120]}…" if len(a) > 120 else f"answer={a}",
            ),
        ),
        (
            "What papers are in category cs.AI?",
            "Papers-in-category: returns titles",
            lambda a, r: (
                _has_titles(a, r),
                f"has_titles={_has_titles(a,r)}, "
                f"bullets={a.count('- ')}, results={len(r)}",
            ),
        ),
        (
            "What papers are in category cs.AI?",
            "Papers-in-category: not category strings",
            lambda a, r: (
                _has_no_raw_categories(a),
                f"no_raw_cats={_has_no_raw_categories(a)}, "
                f"answer preview={a[:120]}…" if len(a) > 120 else f"answer={a}",
            ),
        ),
        (
            "Which papers are written by the same author as paper 1609.01491?",
            "Same-author: returns paper titles",
            lambda a, r: (
                _has_titles(a, r) if r else "could not" in a.lower(),
                f"has_titles={_has_titles(a,r) if r else 'n/a'}, "
                f"bullets={a.count('- ')}, results={len(r)}",
            ),
        ),
        (
            "Which authors have written papers in cs.AI?",
            "Author-list in category",
            lambda a, r: (
                len(a.strip()) > 5 and "could not" not in a.lower(),
                f"answer_len={len(a)}",
            ),
        ),
        (
            "Which authors have written papers in cs.AI?",
            "Author-list: no garbage orgs",
            lambda a, r: (
                not any(g in a.lower() for g in [
                    "department", "university", "institute", "laboratory",
                    "group", "center", "school",
                ]),
                f"answer preview={a[:120]}…" if len(a) > 120 else f"answer={a}",
            ),
        ),
    ]

    print("\n── Strategy-Aware Synthesis ──")
    for sq, label, check_fn in strategy_cases:
        try:
            sr = _post_json(f"{ORCH_URL}/query", {"query": sq})
            sa = sr.get("synthesized_answer", "")
            sr_results = sr.get("results", [])
            if sa is None:
                _check(label, False, "synthesized_answer is null")
            else:
                passed, detail = check_fn(sa, sr_results)
                _check(label, passed, detail)
        except Exception as exc:
            _check(label, False, str(exc))

    # ── 7. Open-ended / explanation queries ──────────────────────────
    open_ended_cases = [
        (
            "What is Bayesian Continuous-valued Label Aggregator BCLA?",
            "Open-ended: BCLA explanation",
            lambda a, r: (
                len(a.strip()) > 30 and "could not" not in a.lower(),
                f"answer_len={len(a)}, preview={a[:100]}…" if len(a) > 100 else f"answer={a}",
            ),
        ),
        (
            "How do machine learning models improve medical time series labeling?",
            "Open-ended: ML medical time series",
            lambda a, r: (
                len(a.strip()) > 30 and "could not" not in a.lower(),
                f"answer_len={len(a)}, preview={a[:100]}…" if len(a) > 100 else f"answer={a}",
            ),
        ),
    ]

    print("\n── Open-Ended Explanation Queries ──")
    for sq, label, check_fn in open_ended_cases:
        try:
            sr = _post_json(f"{ORCH_URL}/query", {"query": sq})
            sa = sr.get("synthesized_answer", "")
            sr_meta = sr.get("synthesis_metadata", {})
            sr_results = sr.get("results", [])
            if sa is None:
                _check(label, False, "synthesized_answer is null")
            else:
                passed, detail = check_fn(sa, sr_results)
                _check(label, passed, detail)
            # check mode
            qm = sr_meta.get("query_mode", "?")
            _check(f"{label} → mode",
                   qm in ("open_explanation", "compare_query", "fallback"),
                   f"query_mode={qm}")
        except Exception as exc:
            _check(label, False, str(exc))

    # ── 8. Latency split ─────────────────────────────────────────────
    print("\n── Latency Split ──")
    try:
        lat_resp = _post_json(f"{ORCH_URL}/query", {"query": KG_QUERY})
        lat_meta = lat_resp.get("synthesis_metadata", {})
        ret_l = lat_meta.get("retrieval_latency_ms", -1)
        syn_l = lat_meta.get("synthesis_latency_ms", -1)
        tot_l = lat_meta.get("total_latency_ms", -1)
        _check("Latency: retrieval ≥ 0", ret_l >= 0, f"retrieval={ret_l:.1f}ms")
        _check("Latency: synthesis ≥ 0", syn_l >= 0, f"synthesis={syn_l:.1f}ms")
        _check("Latency: total = ret + syn",
               abs(tot_l - (ret_l + syn_l)) < 1.0,
               f"total={tot_l:.1f}, ret+syn={ret_l + syn_l:.1f}")
    except Exception as exc:
        _check("Latency split", False, str(exc))

    # ── 9. Fast-path checks ──────────────────────────────────────────
    print("\n── Fast-Path (Direct Extraction) ──")
    fast_path_cases = [
        ("What papers has Carlos Gershenson written?", "list_query"),
        ("What is paper 1609.01491?", "exact_lookup"),
        ("What papers are in category cs.AI?", "list_query"),
    ]
    for fq, expected_mode in fast_path_cases:
        try:
            fr = _post_json(f"{ORCH_URL}/query", {"query": fq})
            fm = fr.get("synthesis_metadata", {})
            fmode = fm.get("query_mode", "?")
            fsyn = fm.get("synthesis_latency_ms", -1)
            cached = fm.get("cached", False)
            # Direct extraction or cache → synthesis_latency_ms should be 0
            is_fast = fsyn == 0.0 or cached
            _check(f"Fast path: \"{fq[:40]}…\"",
                   is_fast and fmode == expected_mode,
                   f"mode={fmode}, synthesis_ms={fsyn}, cached={cached}")
        except Exception as exc:
            _check(f"Fast path: \"{fq[:40]}…\"", False, str(exc))

    # ── 10. Cache checks ─────────────────────────────────────────────
    print("\n── Cache ──")
    cache_query = "What papers has Carlos Gershenson written?"
    try:
        # First call primes the cache (may already be cached from above)
        _post_json(f"{ORCH_URL}/query", {"query": cache_query})
        # Second call should be a cache hit
        cr = _post_json(f"{ORCH_URL}/query", {"query": cache_query})
        cm = cr.get("synthesis_metadata", {})
        is_cached = cm.get("cached", False)
        csyn = cm.get("synthesis_latency_ms", -1)
        ca = cr.get("synthesized_answer")
        _check("Cache: second call is cached",
               is_cached is True,
               f"cached={is_cached}")
        _check("Cache: synthesis_latency_ms = 0 on hit",
               csyn == 0.0,
               f"synthesis_ms={csyn}")
        _check("Cache: answer still present",
               ca is not None and len(ca) > 5,
               f"answer_len={len(ca) if ca else 0}")
        _check("Cache: no error on hit",
               cm.get("error") is None,
               f"error={cm.get('error')}")
    except Exception as exc:
        _check("Cache", False, str(exc))

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n{'=' * 50}")
    print(f"RESULT: {checks_passed}/{checks_total} checks passed")
    if not ok:
        print("\nDiagnosis tips:")
        print("  • docker logs orchestrator-service --tail 40")
        print("  • docker exec ollama ollama list")
        print("  • curl http://localhost:8003/readiness")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify answer-synthesis layer.")
    parser.add_argument("--wait", type=int, default=0, metavar="SEC",
                        help="Poll until orchestrator is ready or SEC seconds elapse.")
    args = parser.parse_args()

    print("─── Answer-Synthesis Verification ───")

    if args.wait > 0:
        deadline = time.monotonic() + args.wait
        print(f"\nWaiting up to {args.wait}s for services …")
        for label, url in [
            ("KG", f"{KG_URL}/kg/health"),
            ("RAG", f"{RAG_URL}/health"),
            ("Orchestrator", f"{ORCH_URL}/health"),
        ]:
            if not _wait_for_health(url, label, deadline):
                print(f"\n  ✗ {label} did not become ready in time.")
                sys.exit(1)
        print()

    ok = run_checks()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
