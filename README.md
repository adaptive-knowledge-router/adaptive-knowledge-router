# Adaptive Knowledge Router

A microservice system that intelligently routes natural language queries to the most appropriate retrieval strategy — either a **Knowledge Graph (KG)** or **Retrieval-Augmented Generation (RAG)** — using a fine-tuned DeBERTa classifier.

---

## System Architecture

```
                        ┌─────────────────────────────────────────────────┐
                        │                   User Query                    │
                        └─────────────────────┬───────────────────────────┘
                                              │
                                              ▼
                        ┌─────────────────────────────────────────────────┐
                        │             Orchestrator (FastAPI)              │
                        │                  :8003                          │
                        └──────────┬──────────────────────┬──────────────┘
                                   │                      │
                                   ▼                      │
                        ┌──────────────────────┐          │
                        │   Router Service     │          │
                        │   DeBERTa-v3-base    │          │
                        │      :8001           │          │
                        └──────────┬───────────┘          │
                                   │                      │
                         predicts strategy                │
                                   │                      │
              ┌────────────────────┼──────────────────────┘
              │                    │
     KG strategies          RAG strategies
              │                    │
    ┌─────────▼──────────┐  ┌──────▼──────────────────────┐
    │    KG Service      │  │       RAG Service           │
    │    FastAPI         │  │       FastAPI               │
    │    :8000           │  │       :8002                 │
    │                    │  │                             │
    │ ┌────────────────┐ │  │ ┌─────────────────────────┐ │
    │ │ entity_lookup  │ │  │ │ sparse  (BM25)          │ │
    │ │ relation_filter│ │  │ │ dense   (FAISS + bge)   │ │
    │ │ multi_hop      │ │  │ │ hybrid  (BM25 + dense   │ │
    │ └────────────────┘ │  │ │          + reranker)    │ │
    │                    │  │ └─────────────────────────┘ │
    └─────────┬──────────┘  └──────────────────────────── ┘
              │
    ┌─────────▼──────────┐  ┌──────────────────────────── ┐
    │   Neo4j :7687      │  │   papers_processed.jsonl    │
    │   (Graph DB)       │  │   FAISS index               │
    └────────────────────┘  └─────────────────────────────┘
              │
    ┌─────────▼──────────┐
    │  Ollama :11434     │
    │  qwen2.5:3b        │
    │  (entity extract)  │
    │  qwen2.5:1.5b       │
    │  (answer synthesis) │
    └────────────────────┘
```

---

## Routing Logic

The router classifies each query into one of **6 strategies**:

| Strategy | Service | Description |
|---|---|---|
| `entity_lookup` | KG | Fetch a specific paper or author node |
| `relation_filter` | KG | Filter papers by author or category |
| `multi_hop` | KG | Traverse 2+ relationships (co-authors → categories) |
| `sparse` | RAG | BM25 keyword search over abstracts |
| `dense` | RAG | Semantic vector search via FAISS |
| `hybrid` | RAG | BM25 + dense + cross-encoder reranking |

---

## Services

| Service | Port | Tech |
|---|---|---|
| KG Service | 8000 | FastAPI + Neo4j + Ollama (qwen2.5:3b) |
| Router Service | 8001 | FastAPI + DeBERTa-v3-base (fine-tuned) |
| RAG Service | 8002 | FastAPI + FAISS + SentenceTransformers |
| Orchestrator | 8003 | FastAPI + Ollama (qwen2.5:1.5b for synthesis) |
| Neo4j | 7474 / 7687 | Graph database |
| Ollama | 11434 | Local LLM: `qwen2.5:3b` (KG entity extraction), `qwen2.5:1.5b` (answer synthesis) |

---

## Answer Synthesis

After the router dispatches the query and results are retrieved from KG or RAG, the orchestrator calls the **Ollama LLM** to produce a concise, evidence-grounded answer.

The synthesis model (`qwen2.5:1.5b` by default) is **separate** from the KG entity-extraction model (`qwen2.5:3b`). This lets you choose a model optimised for natural-language answers without affecting KG extraction quality. On first start the orchestrator's entrypoint pulls the synthesis model automatically.

- **Raw results are preserved** — the `results` array in the response is unchanged.
- `synthesized_answer` and `synthesis_metadata` appear **before** `results` in the JSON response.
- `synthesis_metadata` reports the model name, synthesis latency, result count, and an `error` field (null on success).
- The LLM is instructed to answer **only from the retrieved evidence**. If evidence is insufficient it will say so explicitly.
- If the LLM call fails, `synthesized_answer` is `null` but `synthesis_metadata` is still returned with a descriptive `error` string. Raw results are never affected.
- No model retraining is involved; this is a pure post-retrieval step.

**Response example (success):**

```json
{
  "query": "What papers has Carlos Gershenson written?",
  "strategy": "relation_filter",
  "confidence": 0.92,
  "synthesized_answer": "Carlos Gershenson has authored papers including ...",
  "synthesis_metadata": {
    "model": "qwen2.5:1.5b",
    "synthesis_latency_ms": 1234.56,
    "used_results_count": 5,
    "error": null
  },
  "results": [ ... ],
  "latency_ms": 345.12,
  "source": "kg"
}
```

**Response example (synthesis failure — raw results still returned):**

```json
{
  "query": "...",
  "strategy": "hybrid",
  "confidence": 0.87,
  "synthesized_answer": null,
  "synthesis_metadata": {
    "model": "qwen2.5:1.5b",
    "synthesis_latency_ms": 0.0,
    "used_results_count": 5,
    "error": "ConnectError: failed to connect to Ollama"
  },
  "results": [ ... ],
  "latency_ms": 210.0,
  "source": "rag"
}
```

**Configuration (env vars):**

| Variable | Default | Description |
|---|---|---|
| `ORCH_OLLAMA_URL` | `http://ollama:11434` | Ollama service URL |
| `ORCH_ANSWER_MODEL` | `qwen2.5:1.5b` | Model for answer synthesis (separate from KG) |
| `ORCH_OLLAMA_TIMEOUT` | `60.0` | Timeout in seconds |

**Verification:**

```bash
python verify_synthesis.py             # immediate check
python verify_synthesis.py --wait 120  # poll until ready
```

---

## Evaluation Baseline

The router is evaluated against an **All KG + Hybrid** baseline:
- Baseline runs `entity_lookup`, `relation_filter`, `multi_hop`, and `hybrid` for every query (4 calls), scores each, picks the best
- Router makes **1 call** to the predicted strategy

**Claim: Router ≈ Baseline in quality at 4x lower latency**

See `orchestrator/EVALUATION_NOTES.md` for full evaluation setup.

---

## Branch Structure

```
main
├── kg-service       # Person 1 — KG service + Neo4j integration
├── rag-service      # Person 2 — RAG service + FAISS indexes
├── router-service   # Person 3 — DeBERTa router + training
└── orchestrator     # Person 4 — Orchestration + evaluation
```

---

## Quick Start

```bash
# Start all services (first run builds images and loads data — may take several minutes)
docker compose up -d --build

# Quick stack check (requires Python 3; no extra deps)
python verify_stack.py

# Or poll until everything is ready (up to 120 s)
python verify_stack.py --wait 120

# Send a query through the orchestrator
curl -X POST http://localhost:8003/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What papers has Carlos Gershenson written?"}'
```

### Health & readiness endpoints

| Service | Liveness | Readiness / detail |
|---|---|---|
| Router | `GET :8001/health` | `model_loaded` field confirms DeBERTa is ready |
| KG | `GET :8000/kg/health` | Verifies Neo4j connectivity |
| RAG | `GET :8002/health` | `bm25_ready`, `dense_ready`, `hybrid_ready` fields |
| Orchestrator | `GET :8003/health` | Process up |
| Orchestrator | `GET :8003/readiness` | Pings router, KG, RAG, and Ollama |

### First-run vs subsequent starts

| Step | First run | Subsequent |
|---|---|---|
| Ollama model pull (qwen2.5:3b) | ~1 min download | Skipped (volume) |
| Ollama model pull (qwen2.5:1.5b) | ~1 min download | Skipped (volume) |
| Neo4j data load (~20k papers) | ~2 min | Skipped (volume) |
| FAISS index build | ~45-60 min (CPU) | Skipped (volume) |
| HuggingFace model download | ~1 min | Cached in image |

> **Tip:** The RAG service has the longest cold-start. Use
> `docker compose logs -f rag-service` to watch FAISS indexing progress.
> All other services are usually ready within 30 s.
