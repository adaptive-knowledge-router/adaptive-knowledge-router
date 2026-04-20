"""
Retrieval-only Eval: Baseline (dense-only RAG) vs AKR System
No synthesizer — judges raw retrieval output directly.

KG strategies  (entity_lookup, relation_filter, multi_hop):
    System   → router → correct KG endpoint → raw structured results
    Baseline → dense RAG → raw text chunks
    Judge    → Groq LLM scores both against KG ground truth (1-5)

RAG strategies (sparse, dense, hybrid):
    System   → router → correct RAG endpoint → retrieved paper_ids
    Baseline → dense RAG → retrieved paper_ids
    Judge    → Hit@5: is the correct paper_id in top-5 results? (0 or 1)

Usage:
    python eval/run_eval_retrieval.py                  # 17 per class (102 total)
    python eval/run_eval_retrieval.py --per-class 5    # 30 total
"""

import argparse
import asyncio
import json
import os
import random
import re
import time
from collections import defaultdict
from pathlib import Path

import httpx
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

ROUTER_URL = "http://localhost:8001"
KG_URL     = "http://localhost:8000"
RAG_URL    = "http://localhost:8002"
TOP_K      = 5
TIMEOUT    = 60.0

GROQ_MODEL    = "llama-3.3-70b-versatile"
KG_STRATEGIES = {"entity_lookup", "relation_filter", "multi_hop"}
RAG_STRATEGIES = {"sparse", "dense", "hybrid"}
LABELS = ["entity_lookup", "relation_filter", "multi_hop", "sparse", "dense", "hybrid"]

_PAPER_ID_RE = re.compile(r"\b\d{4}\.\d{4,5}\b")
_DOI_RE      = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")

_groq = Groq(api_key=os.environ["GROQ_API_KEY"])


# ── Formatters ────────────────────────────────────────────────────────────────

def fmt_kg_results(results: list) -> str:
    """Format raw KG results into a readable text block for the judge."""
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results[:20], 1):
        if isinstance(r, str):
            lines.append(f"[{i}] {r}")
            continue
        parts = []
        for field in ("author_name", "co_author", "related_author", "title", "authors", "paper_id", "categories"):
            v = r.get(field)
            if not v:
                continue
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v)
            parts.append(str(v).strip()[:120])
        lines.append(f"[{i}] " + " | ".join(parts))
    return "\n".join(lines)


def fmt_rag_results(results: list) -> str:
    """Format raw RAG results for the judge (includes all metadata fields)."""
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results[:TOP_K], 1):
        title   = r.get("title", "")
        authors = r.get("authors", "")
        if isinstance(authors, list):
            authors = ", ".join(str(a) for a in authors)
        cats    = r.get("categories", "")
        if isinstance(cats, list):
            cats = ", ".join(str(c) for c in cats)
        text    = r.get("text", r.get("abstract", ""))[:150]
        pid     = r.get("paper_id", "")
        lines.append(f"[{i}] {title} (id:{pid})\n    authors: {authors}\n    categories: {cats}\n    {text}")
    return "\n".join(lines)


def paper_ids_from_rag(results: list) -> list[str]:
    """Extract paper_ids from RAG results."""
    ids = []
    for r in results:
        pid = r.get("paper_id", "")
        if pid:
            ids.append(pid)
    return ids


# ── HTTP calls ────────────────────────────────────────────────────────────────

async def get_strategy(client: httpx.AsyncClient, query: str) -> str:
    """Call the router to get predicted strategy (with deterministic override)."""
    if _PAPER_ID_RE.search(query) or _DOI_RE.search(query):
        return "entity_lookup"
    try:
        r = await client.post(f"{ROUTER_URL}/router/predict",
                              json={"query": query}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("strategy", "dense")
    except Exception:
        return "dense"


async def call_kg(client: httpx.AsyncClient, strategy: str, question: str) -> tuple[list, float]:
    path_map = {
        "entity_lookup": "/kg/query/entity",
        "relation_filter": "/kg/query/relation",
        "multi_hop": "/kg/query/multi_hop",
    }
    t0 = time.perf_counter()
    try:
        r = await client.get(f"{KG_URL}{path_map[strategy]}",
                             params={"question": question}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        # fallback to dense RAG if KG returns nothing
        if not results:
            return await call_rag(client, "dense", question)
        return results, round((time.perf_counter() - t0) * 1000, 1)
    except Exception as e:
        return [], round((time.perf_counter() - t0) * 1000, 1)


async def call_rag(client: httpx.AsyncClient, strategy: str, query: str) -> tuple[list, float]:
    path_map = {"sparse": "/rag/sparse", "dense": "/rag/dense", "hybrid": "/rag/hybrid"}
    t0 = time.perf_counter()
    try:
        r = await client.get(f"{RAG_URL}{path_map[strategy]}",
                             params={"query": query, "top_k": TOP_K}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            return [], round((time.perf_counter() - t0) * 1000, 1)
        latency = data.get("latency_ms", round((time.perf_counter() - t0) * 1000, 1))
        return data.get("results", []), latency
    except Exception:
        return [], round((time.perf_counter() - t0) * 1000, 1)


# ── Run system / baseline ─────────────────────────────────────────────────────

async def run_system(query: str) -> tuple[str, list, float]:
    """Route query → call correct backend → return (strategy, raw_results, total_ms)."""
    t0 = time.perf_counter()
    async with httpx.AsyncClient() as client:
        strategy = await get_strategy(client, query)
        if strategy in KG_STRATEGIES:
            results, _ = await call_kg(client, strategy, query)
        else:
            results, _ = await call_rag(client, strategy, query)
    total_ms = round((time.perf_counter() - t0) * 1000, 1)
    return strategy, results, total_ms


async def run_baseline(query: str) -> tuple[list, float]:
    """Always dense RAG — return (raw_results, ms)."""
    async with httpx.AsyncClient() as client:
        results, ms = await call_rag(client, "dense", query)
    return results, ms


# ── Judges ────────────────────────────────────────────────────────────────────

def judge_kg_retrieval(query: str, sys_results: str, base_results: str,
                       ground_truth: str) -> tuple[int, int, str]:
    """LLM judge: score raw retrieval output against KG ground truth."""
    prompt = f"""\
You are evaluating retrieval quality for a knowledge graph question.
Ground Truth (verified answer):
{ground_truth}

Score each result set on how well it contains the ground truth entities.
5 = ground truth entities clearly present
4 = most entities present, minor gaps
3 = some entities present but incomplete
2 = on-topic but wrong entities
1 = missing or completely wrong

Question: {query}

Result Set A (Baseline - dense RAG):
{base_results[:800]}

Result Set B (System - KG retrieval):
{sys_results[:800]}

Reply ONLY with JSON: {{"score_a":<1-5>,"score_b":<1-5>,"reason":"<one sentence>"}}"""
    try:
        raw = _groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=100,
        ).choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].removeprefix("json").strip()
        d = json.loads(raw)
        a = max(1, min(5, int(d.get("score_a", 3))))
        b = max(1, min(5, int(d.get("score_b", 3))))
        return a, b, str(d.get("reason", ""))
    except Exception as exc:
        return 3, 3, f"(judge error: {exc})"


def hit_at_k(paper_id: str, results: list, k: int = 5) -> int:
    """1 if paper_id is in top-k results, else 0."""
    ids = paper_ids_from_rag(results)
    return int(paper_id in ids[:k])


def judge_rag_retrieval(query: str, sys_results: str, base_results: str) -> tuple[int, int, str]:
    """LLM judge: score raw RAG retrieved text on relevance to the question."""
    prompt = f"""\
You are evaluating retrieval quality for a research question-answering system.
Score each result set on how well the retrieved text contains information to answer the question.

5 = retrieved text directly and fully answers the question
4 = retrieved text mostly answers the question with minor gaps
3 = retrieved text is relevant but only partially answers the question
2 = retrieved text is on-topic but does not answer the specific question
1 = retrieved text is irrelevant or missing

Question: {query}

Result Set A (Baseline - dense RAG):
{base_results[:800]}

Result Set B (System - adaptive RAG):
{sys_results[:800]}

Reply ONLY with JSON: {{"score_a":<1-5>,"score_b":<1-5>,"reason":"<one sentence>"}}"""
    try:
        raw = _groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=100,
        ).choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].removeprefix("json").strip()
        d = json.loads(raw)
        a = max(1, min(5, int(d.get("score_a", 3))))
        b = max(1, min(5, int(d.get("score_b", 3))))
        return a, b, str(d.get("reason", ""))
    except Exception as exc:
        return 3, 3, f"(judge error: {exc})"



def load_dataset(path: str, per_class: int, kg_gts: dict | None = None) -> list[dict]:
    by_class: dict[str, list] = defaultdict(list)
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            by_class[d["strategy"]].append(d)
    random.seed(42)
    samples = []
    for label in LABELS:
        pool = by_class.get(label, [])
        if label in KG_STRATEGIES and kg_gts:
            # For KG strategies, prefer queries that have a ground truth
            with_gt    = [d for d in pool if d["query"] in kg_gts]
            without_gt = [d for d in pool if d["query"] not in kg_gts]
            chosen = with_gt[:per_class]
            if len(chosen) < per_class:
                chosen += random.sample(without_gt, min(per_class - len(chosen), len(without_gt)))
        else:
            chosen = random.sample(pool, min(per_class, len(pool)))
        samples.extend(chosen)
    random.shuffle(samples)
    return samples


def load_kg_ground_truths(path: str) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return {q: v["ground_truth"] for q, v in data.items() if v.get("has_data")}



async def evaluate(args: argparse.Namespace) -> None:
    kg_ground_truths = load_kg_ground_truths(args.ground_truths)
    print(f"Loaded {len(kg_ground_truths)} KG ground truths")

    samples = load_dataset(args.dataset, args.per_class, kg_gts=kg_ground_truths)

    # Drop KG queries without ground truth
    filtered = []
    for s in samples:
        if s["strategy"] in KG_STRATEGIES and s["query"] not in kg_ground_truths:
            print(f"  SKIP (no ground truth): {s['query'][:60]}…")
            continue
        filtered.append(s)
    samples = filtered
    print(f"{len(samples)} queries ({args.per_class} per class)\n")

    results = []
    for i, s in enumerate(samples, 1):
        query    = s["query"]
        gt_strat = s["strategy"]
        paper_id = s.get("paper_id", "")

        print(f"[{i:3d}/{len(samples)}] {gt_strat:<16} | {query[:65]}…")

        # Run both in parallel
        (sys_strat, sys_raw, sys_ms), (base_raw, base_ms) = await asyncio.gather(
            run_system(query),
            run_baseline(query),
        )

        routed_correctly = sys_strat == gt_strat

        if gt_strat in KG_STRATEGIES:
            # KG: LLM judge raw results vs ground truth
            gt      = kg_ground_truths[query]
            sys_fmt  = fmt_kg_results(sys_raw)
            base_fmt = fmt_rag_results(base_raw)
            base_score, sys_score, reason = judge_kg_retrieval(query, sys_fmt, base_fmt, gt)
            sys_metric  = f"judge={sys_score}"
            base_metric = f"judge={base_score}"
        else:
            # RAG: LLM judge on retrieved text relevance + Hit@5 as reference
            sys_fmt  = fmt_rag_results(sys_raw)
            base_fmt = fmt_rag_results(base_raw)
            base_score, sys_score, reason = judge_rag_retrieval(query, sys_fmt, base_fmt)
            sys_hit  = hit_at_k(paper_id, sys_raw,  k=TOP_K)
            base_hit = hit_at_k(paper_id, base_raw, k=TOP_K)
            sys_metric  = f"judge={sys_score} hit@{TOP_K}={sys_hit}"
            base_metric = f"judge={base_score} hit@{TOP_K}={base_hit}"

        print(f"           base={base_ms:6.0f}ms {base_metric} | "
              f"sys={sys_ms:6.0f}ms {sys_metric} → {sys_strat}"
              f"{'' if routed_correctly else ' !'}")

        results.append({
            "index": i,
            "query": query,
            "paper_id": paper_id,
            "ground_truth_strategy": gt_strat,
            "system_strategy": sys_strat,
            "routed_correctly": routed_correctly,
            "baseline": {"latency_ms": base_ms, "score": base_score},
            "system":   {"latency_ms": sys_ms,  "score": sys_score},
            "judge_reason": reason,
        })

    n = len(results)
    def avg(fn): return sum(fn(r) for r in results) / n if n else 0

    base_lat  = avg(lambda r: r["baseline"]["latency_ms"])
    sys_lat   = avg(lambda r: r["system"]["latency_ms"])
    route_acc = avg(lambda r: r["routed_correctly"])

    by_gt: dict[str, list] = defaultdict(list)
    for r in results:
        by_gt[r["ground_truth_strategy"]].append(r)

    per_class = {}
    for label in LABELS:
        rows = by_gt.get(label, [])
        if not rows:
            continue
        m = len(rows)
        per_class[label] = {
            "n": m,
            "metric": "judge(1-5)",
            "base_score": round(sum(r["baseline"]["score"] for r in rows) / m, 3),
            "sys_score":  round(sum(r["system"]["score"]   for r in rows) / m, 3),
            "base_ms":    round(sum(r["baseline"]["latency_ms"] for r in rows) / m, 1),
            "sys_ms":     round(sum(r["system"]["latency_ms"]   for r in rows) / m, 1),
            "route_pct":  round(sum(r["routed_correctly"]       for r in rows) / m, 3),
        }

    summary = {
        "n": n,
        "routing_accuracy": round(route_acc, 3),
        "baseline": {"avg_latency_ms": round(base_lat, 1)},
        "system":   {"avg_latency_ms": round(sys_lat, 1)},
        "speedup_x": round(base_lat / sys_lat, 2) if sys_lat else 0,
        "per_class": per_class,
    }

    sep = "=" * 65
    print(f"\n{sep}\nRETRIEVAL-ONLY RESULTS (no synthesizer)\n{sep}")
    print(f"  Queries          : {n}")
    print(f"  Routing accuracy : {route_acc*100:.1f}%")
    print(f"  Speedup          : {summary['speedup_x']:.1f}x  "
          f"(base={base_lat:,.0f}ms  sys={sys_lat:,.0f}ms)")

    print(f"\n  {'Class':<18} {'N':>3}  {'Metric':<12}  "
          f"{'Base':>6} {'Sys':>6}  {'Bms':>7} {'Sms':>7}  {'Route%':>7}")
    print(f"  {'-'*70}")
    for label in LABELS:
        pc = per_class.get(label)
        if not pc:
            continue
        win = "▲" if pc["sys_score"] > pc["base_score"] else ("▼" if pc["sys_score"] < pc["base_score"] else "=")
        print(f"  {label:<18} {pc['n']:>3}  {pc['metric']:<12}  "
              f"{pc['base_score']:>6.3f} {pc['sys_score']:>6.3f}{win}  "
              f"{pc['base_ms']:>7.0f} {pc['sys_ms']:>7.0f}  {pc['route_pct']*100:>6.1f}%")

    out = Path(__file__).parent
    (out / "retrieval_results.json").write_text(json.dumps(results, indent=2))
    (out / "retrieval_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n  Saved retrieval_results.json + retrieval_summary.json\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset",       default="router-service/filtered_queries.jsonl")
    p.add_argument("--per-class",     type=int, default=17)
    p.add_argument("--ground-truths", default="eval/kg_ground_truths.json")
    asyncio.run(evaluate(p.parse_args()))


if __name__ == "__main__":
    main()
