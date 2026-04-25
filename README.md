# Adaptive Knowledge Router

A microservice system that intelligently routes natural language queries to the most appropriate retrieval strategy — either a **Knowledge Graph (KG)** or **Retrieval-Augmented Generation (RAG)** — using a fine-tuned DeBERTa-v3 classifier.

---

## System Architecture

```
  ┌─────────────────────────────┐
  │       Natural Language      │
  │           Query             │
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │        Orchestrator         │  :8003
  └──────────────┬──────────────┘
                 │  classify
                 ▼
  ┌─────────────────────────────┐
  │       Router Service        │  :8001  DeBERTa-v3-base
  └─────────┬─────────┬─────────┘
            │         │
      KG strategy   RAG strategy
            │         │
            ▼         ▼
  ┌──────────────┐  ┌──────────────┐
  │  KG Service  │  │ RAG Service  │  :8000 / :8002
  │              │  │              │
  │entity_lookup │  │   sparse     │
  │relation_filter  │   dense      │
  │  multi_hop   │  │   hybrid     │
  └──────┬───────┘  └──────┬───────┘
         │                 │
         ▼                 ▼
  ┌──────────────┐  ┌──────────────┐
  │    Neo4j     │  │ FAISS + BM25 │
  │   :7687      │  │    Index     │
  └──────────────┘  └──────────────┘
            │         │
            └────┬────┘
                 │  results
                 ▼
  ┌─────────────────────────────┐
  │      Answer Synthesis       │  qwen2.5:1.5b · Ollama
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │          Response           │
  │  strategy · answer · results│
  └─────────────────────────────┘
```

---

## Services

### Router Service (`:8001`)
Fine-tuned **DeBERTa-v3-base** sequence classifier that maps a natural language query to one of 6 retrieval strategies.

**Training:**
- Dataset: `router-service/arxiv_queries.jsonl` — 12,000 labelled queries (2,000 per strategy) generated from ~20k arXiv papers
- Model: `microsoft/deberta-v3-base` fine-tuned with HuggingFace `Trainer`
- Split: 90/10 stratified train/val, 15 epochs, early stopping (patience=2), lr=2e-5
- Output: saved to `router-service/router_model/`

**Inference:** `POST /router/predict` → returns `strategy`, `confidence`, and per-class `probabilities`

---

### KG Service (`:8000`)
Structured retrieval over a **Neo4j graph** containing Paper, Author, and Category nodes built from ~20k arXiv papers.

**Parameter extraction — two-stage pipeline:**

| Strategy | Extraction method |
|---|---|
| `entity_lookup` | **Regex only** — reliable pattern matching for paper titles, author names, paper IDs, DOIs. No LLM call, lowest latency. |
| `relation_filter` | **Regex first** — extracts author name, title, category via regex. Falls back to **qwen2.5:3b via Ollama** only if regex finds nothing. |
| `multi_hop` | **Regex first** — same as above. LLM used only when regex cannot extract entities. |

The LLM (qwen2.5:3b) receives strategy-specific few-shot prompts and returns structured JSON (title, author_name, category_name, mode). Regex patterns cover 15+ query phrasings for titles and author names.

**Cypher query strategies:**

| Strategy | What it does |
|---|---|
| `entity_lookup` | Matches a Paper node by title (fuzzy) or Author node by name → returns metadata |
| `relation_filter` | Traverses 1-hop relations: author→papers, paper→authors, paper→categories, category→papers, papers by same author filtered to a category |
| `multi_hop` | 2–4 hop traversals: co-authors of X who publish in category Y, papers by co-authors of paper X in category Y, related authors via shared categories |

**Endpoints:** `GET /kg/query/entity`, `GET /kg/query/relation`, `GET /kg/query/multi_hop`

---

### RAG Service (`:8002`)
Text retrieval over ~20k arXiv papers (title, authors, categories, abstract) using three strategies:

| Strategy | Method | Model |
|---|---|---|
| `sparse` | BM25 keyword search (rank-bm25) | — |
| `dense` | Semantic vector search over FAISS index | `BAAI/bge-small-en-v1.5` embeddings |
| `hybrid` | BM25 top-10 + dense top-10 → merge → cross-encoder rerank | `cross-encoder/ms-marco-MiniLM-L-6-v2` |

**Endpoints:** `GET /rag/sparse`, `GET /rag/dense`, `GET /rag/hybrid` (all accept `query` and `top_k`)

---

### Orchestrator (`:8003`)
Coordinates the full pipeline: calls the router → dispatches to KG or RAG → synthesizes a natural language answer via **qwen2.5:1.5b** (Ollama).

**Dispatch behaviour:**
- **Deterministic override:** queries containing a paper ID (e.g. `1706.03762`) or DOI are always routed to `entity_lookup`, regardless of router prediction
- **Confidence threshold:** router confidence below `0.4` is treated as uncertain
- **KG → RAG fallback:** if a KG strategy (`entity_lookup`, `relation_filter`, `multi_hop`) returns 0 results, the orchestrator automatically falls back to RAG `hybrid` retrieval
- **Retry logic:** KG and RAG clients retry up to **2 times** on transient failures (502/503/504, connection errors, timeouts)

**Answer synthesis:**
- Synthesis model (`qwen2.5:1.5b`) is separate from KG entity extraction model (`qwen2.5:3b`)
- Queries are classified into one of 5 modes before synthesis: `exact_lookup`, `list_query`, `open_explanation`, `compare_query`, `fallback`
- **Fast path (no LLM):** KG strategies with `exact_lookup` or `list_query` modes extract answers directly from structured fields — no LLM call
- **LLM path:** open-ended, comparison, and fallback modes build a compact evidence block and call `qwen2.5:1.5b`
- **LRU cache:** synthesized answers are cached in-memory (128 entries) keyed by `(query, strategy, num_results)` — cache hits skip synthesis entirely
- Raw `results` are always preserved in the response; synthesis is a post-retrieval step
- If synthesis fails, `synthesized_answer` is `null` but raw results are still returned

**Web UI:** available at `GET http://localhost:8003/` — a browser interface for submitting queries

**Configuration:** all settings are overridable via `ORCH_*` environment variables or a `.env` file

| Setting | Default | Env var |
|---|---|---|
| Router URL | `http://router-service:8001` | `ORCH_ROUTER_URL` |
| KG URL | `http://kg-service:8000` | `ORCH_KG_URL` |
| RAG URL | `http://rag-service:8002` | `ORCH_RAG_URL` |
| Ollama URL | `http://ollama:11434` | `ORCH_OLLAMA_URL` |
| Answer model | `qwen2.5:1.5b` | `ORCH_ANSWER_MODEL` |
| Default top_k | `5` | `ORCH_DEFAULT_TOP_K` |
| Max retries | `2` | `ORCH_MAX_RETRIES` |
| Request timeout | `120s` | `ORCH_REQUEST_TIMEOUT` |
| Ollama timeout | `240s` | `ORCH_OLLAMA_TIMEOUT` |
| Confidence threshold | `0.4` | `ORCH_CONFIDENCE_THRESHOLD` |
| Cache size | `128` | `ORCH_CACHE_SIZE` |

---

## Routing Logic

| Strategy | Service | Query type |
|---|---|---|
| `entity_lookup` | KG | "Who are the authors of paper X?" / "Show paper 1706.03762" |
| `relation_filter` | KG | "What other papers in cs.AI are written by the authors of X?" |
| `multi_hop` | KG | "Which co-authors of X have also published in cs.LG?" |
| `sparse` | RAG | Keyword-heavy factual questions about paper content |
| `dense` | RAG | Semantic/conceptual questions about methods or contributions |
| `hybrid` | RAG | Complex questions requiring both keyword and semantic matching |

---

## Design Decisions

- **Separation of concerns:** Each service is an independent Docker container (KG, RAG, Router, Orchestrator) orchestrated via Docker Compose. Components can be developed, scaled, or replaced independently — e.g. swapping the router model or upgrading the RAG index without redeploying the full stack.
- **Regex-first extraction:** For `relation_filter` and `multi_hop`, parameter extraction tries regex patterns first (author names, paper titles, category codes). `qwen2.5:3b` is called only when regex finds nothing, avoiding LLM latency on common query patterns.
- **No LLM for `entity_lookup`:** Entity lookups use regex exclusively — no LLM call at all — making this the lowest-latency KG path and fully deterministic.
- **Smart re-routing inside KG service:** Each NL query endpoint (`/kg/query/entity`, `/kg/query/relation`, `/kg/query/multi_hop`) detects actual query intent at runtime and redirects to the correct handler. For example, the entity endpoint recognises "who wrote X?" patterns and re-routes to `relation_filter`; the relation endpoint detects multi-hop patterns and re-routes to multi-hop. This gracefully tolerates occasional router misclassifications.
- **Dual LLM roles:** `qwen2.5:3b` handles KG parameter extraction (entity and mode extraction from natural language); `qwen2.5:1.5b` handles answer synthesis in the Orchestrator. These are separate Ollama models with separate prompts and timeout settings.

---

## Evaluation Results

Retrieval-only evaluation (no synthesizer) — **AKR system vs dense-RAG baseline** across 59 queries (~10 per strategy). Judged by Groq `llama-3.3-70b-versatile` on a 1–5 scale. System latency includes full end-to-end router overhead (CPU inference ~300ms).

| Strategy | N | Base Score | Sys Score | Δ | Base Latency | Sys Latency | Route Accuracy |
|---|---|---|---|---|---|---|---|
| entity_lookup | 10 | 5.0 | 4.9 | ≈ tie | 105ms | 374ms | 100% |
| relation_filter | 10 | 1.2 | **5.0** | **+3.8** | 107ms | 361ms | 90% |
| multi_hop | 9 | 2.4 | **4.8** | **+2.3** | 148ms | 388ms | 100% |
| sparse | 10 | 2.6 | 2.9 | +0.3 | 128ms | 453ms | 100% |
| dense | 10 | 2.9 | 2.9 | = | 115ms | 423ms | 90% |
| hybrid | 10 | 2.6 | 3.4 | +0.8 | 124ms | 997ms | 80% |

**Overall routing accuracy: 93.2%**

**Key findings:**
- `relation_filter` and `multi_hop` — dense-RAG baseline **completely fails** (1.2–2.4/5); AKR retrieves structured graph results that RAG cannot produce
- `entity_lookup` — both systems perform equally; KG is faster on GPU (CPU router overhead dominates on CPU)
- `dense` / `sparse` — comparable quality; AKR adds no degradation
- `hybrid` — modest quality gain (+0.8) at high latency cost; bottleneck is the cross-encoder reranker, not the router
- Router adds ~300ms on CPU; on GPU this reduces to ~5–10ms, restoring the latency advantage for all KG strategies

**Eval setup:**
- Baseline: always calls `dense` RAG directly (no routing)
- System: router classifies query → calls correct KG or RAG endpoint
- KG judge: LLM scores raw KG results (author names / paper titles) against manually verified ground truths
- RAG judge: LLM scores retrieved abstract relevance (1–5) + Hit@5 on source paper
- Ground truths: `eval/kg_ground_truths.json` (30 manually verified: 10 per KG strategy)
- Run: `python eval/run_eval_retrieval.py --dataset router-service/filtered_queries.jsonl --per-class 10`

---

## Quick Start

```bash
# Start all services (first run builds images and loads data — may take several minutes)
docker compose up -d --build

# Check stack readiness
python verify_stack.py --wait 120

# Send a query through the orchestrator
curl -X POST http://localhost:8003/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What papers has Carlos Gershenson written?"}'
```

### Health endpoints

| Service | Endpoint | Notes |
|---|---|---|
| Router | `GET :8001/health` | `model_loaded` confirms DeBERTa is ready |
| KG | `GET :8000/kg/health` | Verifies Neo4j connectivity |
| RAG | `GET :8002/health` | `bm25_ready`, `dense_ready`, `hybrid_ready` fields |
| Orchestrator | `GET :8003/health` | Process up |
| Orchestrator | `GET :8003/readiness` | Pings router, KG, RAG, and Ollama — returns `degraded` if any are unreachable |

### First-run vs subsequent starts

| Step | First run | Subsequent |
|---|---|---|
| Ollama model pull (qwen2.5:3b) | ~1 min download | Skipped (volume) |
| Ollama model pull (qwen2.5:1.5b) | ~1 min download | Skipped (volume) |
| Neo4j data load (~20k papers) | ~40 min | Skipped (volume) |
| FAISS index build | ~45–60 min (CPU) | Skipped (volume) |
| HuggingFace model download | ~1 min | Cached in image |

> **Tip:** The RAG service has the longest cold-start. Use
> `docker compose logs -f rag-service` to watch FAISS indexing progress.

---

## Branch Structure

```
main
├── kg-service       # KG service + Neo4j integration + entity extraction
├── rag-service      # RAG service + FAISS indexes + BM25 + hybrid reranker
├── router-service   # DeBERTa router + training pipeline
└── orchestrator     # Orchestration + answer synthesis
```