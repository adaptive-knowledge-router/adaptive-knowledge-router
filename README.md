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
| Orchestrator | 8003 | FastAPI |
| Neo4j | 7474 / 7687 | Graph database |
| Ollama | 11434 | Local LLM for entity extraction |

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
# Create network
docker network create akr-net

# Start all services
docker compose up -d

# Pull Ollama model (first time only)
docker exec ollama ollama pull qwen2.5:3b
```
