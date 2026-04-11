# Orchestrator Evaluation Notes

## Baseline vs Router Approach Comparison

The router service classifies each query into one of 6 strategies:
- KG: `entity_lookup`, `relation_filter`, `multi_hop`
- RAG: `sparse`, `dense`, `hybrid`

To evaluate our approach against a baseline, use the following scoring formula.

---

## Scoring Formula

```python
ALPHA = 0.3   # weight for speed
BETA  = 0.7   # weight for quality

speed   = min(1.0 / (latency_seconds * 10.0), 1.0)
quality = llm_judge_score   # float between 0.0 and 1.0

score = ALPHA * speed + BETA * quality
```

**latency_seconds**: wall-clock time for the strategy endpoint to respond
**quality**: scored by an LLM judge (e.g. Llama 3.3-70B via Groq) — prompt the judge with the query and retrieved results, ask for a float 0.0-1.0

---

## Evaluation Flow

For each test query, compare one baseline against our router approach.

**Recommended baseline: All KG + Hybrid.**

### Baseline 1 — Random Strategy
- Randomly pick one of 6 strategies each time
- Easiest to implement, weakest comparison

### Baseline 2 — Always Hybrid RAG
- Always call `GET /rag/hybrid?query=...`
- Common single-strategy baseline in retrieval papers

### Baseline 3 — All KG + Hybrid (recommended)
- Run all 3 KG strategies + hybrid RAG for every query (4 calls total)
- Score each result, pick the best
- Rationale: covers all structured (KG) retrieval paths and the strongest RAG strategy
- More realistic than Oracle (6 calls) — a practitioner might reasonably do this
- Shows our router matches this quality with only 1 call and 4x less latency cost
- Implementation: call entity_lookup, relation_filter, multi_hop, hybrid → score each → pick best

### Baseline 4 — Oracle
- Run all 6 strategies for every query, pick the best
- Represents the absolute upper bound
- 6x more expensive than our router

### Our Approach — Router predicted strategy
- Call `POST /router/predict` → get predicted strategy
- Call that single endpoint (KG or RAG)
- Measure latency, judge quality, compute score

---

## Key Result to Show

| Approach | Avg Score | Latency | API Calls |
|----------|-----------|---------|-----------|
| Random | lowest | varies | 1 |
| Always Hybrid | medium | slow (hybrid is heavy) | 1 |
| **All KG + Hybrid (baseline)** | **high** | slow (4 calls) | 4 |
| **Our Router** | **high** | **fast** | **1** |
| Oracle | highest | very slow | 6 |

The main claim: **Router ≈ All KG + Hybrid baseline in quality, but 4x faster**
because the router picks the single best strategy upfront instead of running all KG
strategies plus hybrid. Factual queries (entity_lookup, relation_filter, multi_hop)
are answered faster and more accurately by KG than by RAG hybrid.

---

## KG Endpoints (called after router predicts a KG strategy)

| Strategy | Endpoint |
|----------|----------|
| `entity_lookup` | `GET http://kg-service:8000/kg/query/entity?question=...` |
| `relation_filter` | `GET http://kg-service:8000/kg/query/relation?question=...` |
| `multi_hop` | `GET http://kg-service:8000/kg/query/multi_hop?question=...` |

All KG endpoints accept `question=` (natural language) and return:
```json
{
  "strategy": "...",
  "count": N,
  "results": [...],
  "total_count": N
}
```

## RAG Endpoints (called after router predicts a RAG strategy)

| Strategy | Endpoint |
|----------|----------|
| `sparse` | `GET http://rag-service:8002/rag/sparse?query=...` |
| `dense` | `GET http://rag-service:8002/rag/dense?query=...` |
| `hybrid` | `GET http://rag-service:8002/rag/hybrid?query=...` |

All RAG endpoints return:
```json
{
  "strategy": "...",
  "latency_ms": N,
  "results": [...]
}
```

Note: RAG returns `latency_ms` directly — divide by 1000 for seconds.
KG does not return latency — use wall-clock time.

---

## LLM Judge Prompt

```python
JUDGE_SYSTEM = (
    "You are an answer quality evaluator for a research paper retrieval system. "
    "The system retrieves results using one of 6 strategies: "
    "KG strategies: entity_lookup, relation_filter, multi_hop. "
    "RAG strategies: sparse, dense, hybrid. "
    "Score how accurately and completely the retrieved results address the question. "
    "Respond with a single float between 0.0 and 1.0 — nothing else."
)

user_message = f"Question: {query}\n\nRetrieved results: {json.dumps(results[:3])}\n\nScore:"
```

---

## Test Set Size

**Recommended: 300 papers** sampled randomly from arxiv_queries_verified.jsonl

- 6 strategy classes → ~50 samples per class — statistically solid
- Oracle baseline: 300 × 6 strategies × judge = ~1800 Groq API calls — manageable
- 500 papers works too but doubles the API cost with marginal statistical benefit
- Ensure balanced sampling: ~50 per strategy class (entity_lookup, relation_filter,
  multi_hop, sparse, dense, hybrid) to avoid skewed results

```python
import json, random
from collections import defaultdict

records = [json.loads(l) for l in open("arxiv_queries_verified.jsonl")]
per_class = defaultdict(list)
for r in records:
    for q in r["queries"]:
        strategy = q.get("kg_strategy") or q.get("rag_strategy")
        per_class[strategy].append((r, q))

# Sample 50 per class
test_set = []
for strategy, items in per_class.items():
    test_set.extend(random.sample(items, min(50, len(items))))
```

---

## Reporting Results

Report per-strategy and overall averages:

| Strategy | Avg Speed | Avg Quality | Avg Score | Count |
|----------|-----------|-------------|-----------|-------|
| entity_lookup | ... | ... | ... | ... |
| relation_filter | ... | ... | ... | ... |
| multi_hop | ... | ... | ... | ... |
| sparse | ... | ... | ... | ... |
| dense | ... | ... | ... | ... |
| hybrid | ... | ... | ... | ... |
| **Baseline (All KG + Hybrid)** | ... | ... | ... | all |
| **Our Router** | ... | ... | ... | all |

The key metric is: **Router score ≈ Baseline score, but Router latency = Baseline latency / 4**
