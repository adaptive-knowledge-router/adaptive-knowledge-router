# Router Model — Dataset, Training & Results

Model: `microsoft/deberta-v3-base`
Task: 6-class query classification
Classes: `entity_lookup`, `relation_filter`, `multi_hop`, `sparse`, `dense`, `hybrid`

---

## Dataset Generation

### Source
20,000 arxiv papers from `kg-service/data/processed/arxiv_subset.jsonl` 

### Process
Each paper was processed by `gen_queries.py` using **Llama 3.3-70B** (via Groq API)
to generate exactly **2 queries per paper**:

- **1 factual query** — answerable from structured metadata (title, authors, categories). Assigned one of 3 KG strategies: `entity_lookup`, `relation_filter`, or `multi_hop`.
- **1 semantic query** — requires reading and understanding the abstract. Assigned one of 3 RAG strategies: `sparse`, `dense`, or `hybrid`.

The KG and RAG strategy for each paper was **randomly sampled** so the dataset is
balanced across all 6 classes.

Total dataset: **6,000 papers × 2 queries = 12,000 labeled examples**
Output: `arxiv_queries.jsonl`

---

## Prompt Engineering

### System Prompt

```
You are a dataset curator for a research retrieval system.
Generate realistic user queries for academic papers.
Respond with valid JSON only — no explanation, no markdown, no extra text.
```

### User Prompt (per paper)

```
You will generate exactly 2 queries for the research paper below.

QUERY TYPE DEFINITIONS

FACTUAL
  Answerable using only structured metadata (authors, title, categories, journal).
  Must NOT require reading the abstract.
  Strategy: {kg_strategy}
    - entity_lookup   : ask about a single specific entity. e.g. "Who are the authors of paper X?"
    - relation_filter : ask about papers filtered by an attribute. e.g. "What papers by author X are in category cs.LG?"
    - multi_hop : requires traversing 2+ relationships, but must still be anchored
              to this specific paper. e.g. "Which co-authors of this paper have
              also published in category stat.ML?"

SEMANTIC
  Requires reading and understanding the abstract.
  Cannot be answered from metadata alone.
  Strategy: {rag_strategy}
    - sparse  : use specific technical terms or exact phrases from the abstract.
    - dense   : ask about a specific concept, mechanism, or finding — not just "what problem does this paper solve?"
    - hybrid  : mix of specific terms and conceptual understanding.

PAPER
ID         : {paper_id}
Title      : {title}
Authors    : {authors}
Categories : {categories}
Journal    : {journal}

Abstract:
{abstract}

Generate exactly 2 queries: one FACTUAL using the {kg_strategy} strategy, one SEMANTIC using the {rag_strategy} strategy.
- Write queries as a real user would ask them (natural language).
- Each query must be specific to this paper, not generic.
- Always refer to the paper by its title.

Respond ONLY with a JSON array:
[
  {"query": "...", "type": "factual",  "kg_strategy": "{kg_strategy}"},
  {"query": "...", "type": "semantic", "rag_strategy": "{rag_strategy}"}
]
```

### Key Prompt Design Decisions

- **Strategy injected into prompt** — the LLM is told which strategy to generate for,
  not asked to decide. This ensures a balanced dataset (each class gets equal coverage).
- **Strict JSON-only output** — system prompt forbids markdown/explanation to simplify parsing.
- **"Must NOT require reading the abstract"** for factual — prevents leakage between KG and RAG query types.
- **"Each query must be specific to this paper"** — prevents generic queries like "What papers exist in cs.AI?" that don't reflect real user intent.
- **Temperature 0.7** — enough variation to generate diverse phrasings without losing structure.

### Output Validation
Each LLM response was validated in `call_llama()`:
- Exactly 2 queries returned
- Query 1 has `type=factual` and a valid `kg_strategy`
- Query 2 has `type=semantic` and a valid `rag_strategy`
- Failed papers are skipped with a warning (not retried)

---

## Training Setup

| Parameter | Value |
|---|---|
| Base model | `microsoft/deberta-v3-base` |
| Max sequence length | 128 tokens |
| Batch size | 64 |
| Epochs | 15 (early stopping) |
| Early stopping patience | 2 |
| Optimizer | AdamW |
| Split | 90% train / 10% val (stratified) |

---

## Results by Configuration

| Run | LR   | Batch Size | Max Len | Weight Decay | Best Val Accuracy | Best Epoch | Stopped At | Note |
|-----|------|------------|---------|--------------|-------------------|------------|------------|------|
| 1   | 2e-5 | 64         | 128     | 0.02         | **92.17%**        | 4          | epoch 6    | stratified split ⭐ |
| 2   | 1e-5 | 64         | 128     | 0.02         | 91.92%            | 4          | epoch 6    | stratified split |
| 3   | 3e-5 | 64         | 128     | 0.02         | 91.75%            | 4          | epoch 6    | stratified split |
| 4   | 4e-5 | 64         | 128     | 0.02         | 91.08%            | 1          | epoch 3    | stratified split |
| 5   | 3e-5 | 64         | 128     | 0.01         | 91.75%            | 4          | epoch 6    | stratified split |
| 6   | 3e-5 | 64         | 128     | 0.05         | 91.67%            | 3          | epoch 5    | stratified split |


**Best config:  LR=2e-5, WD=0.02, stratified split → 92.17% val accuracy**

---

## Epoch-level Detail

### Run 1 — LR=2e-5, WD=0.02
| Epoch | Train Loss | Val Loss | Val Accuracy |
|-------|-----------|----------|--------------|
| 1     | 0.2935    | 0.2795   | 88.92%       |
| 2     | 0.2296    | 0.2172   | **91.58%**   |
| 3     | 0.2281    | 0.2386   | 90.83%       |
| 4     | 0.1269    | 0.2246   | 91.58%       |

### Run 2 — LR=1e-5, WD=0.02
| Epoch | Train Loss | Val Loss | Val Accuracy |
|-------|-----------|----------|--------------|
| 1     | 0.4138    | 0.3645   | 85.50%       |
| 2     | 0.2718    | 0.2525   | 90.17%       |
| 3     | 0.2371    | 0.2419   | 91.00%       |
| 4     | 0.1683    | 0.2180   | **91.92%**   |
| 5     | 0.1794    | 0.3152   | 88.83%       |
| 6     | 0.1447    | 0.2945   | 90.67%       |

### Run 3 — LR=3e-5, WD=0.02
| Epoch | Train Loss | Val Loss | Val Accuracy |
|-------|-----------|----------|--------------|
| 1     | 0.2839    | 0.2657   | 89.25%       |
| 2     | 0.2372    | 0.2274   | 91.33%       |
| 3     | 0.2124    | 0.2322   | 91.50%       |
| 4     | 0.1252    | 0.2375   | **91.75%**   |
| 5     | 0.0937    | 0.3695   | 90.50%       |
| 6     | 0.0759    | 0.3758   | 91.17%       |

### Run 4 — LR=4e-5, WD=0.02
| Epoch | Train Loss | Val Loss | Val Accuracy |
|-------|-----------|----------|--------------|
| 1     | 0.2674    | 0.2531   | **91.08%**   |
| 2     | 0.2416    | 0.2229   | 91.00%       |
| 3     | 0.2068    | 0.2391   | 90.83%       |

### Run 5 — LR=3e-5, WD=0.01
| Epoch | Train Loss | Val Loss | Val Accuracy |
|-------|-----------|----------|--------------|
| 1     | 0.2699    | 0.2732   | 89.42%       |
| 2     | 0.2466    | 0.2394   | 90.42%       |
| 3     | 0.1855    | 0.2356   | 90.75%       |
| 4     | 0.1255    | 0.2440   | **91.75%**   |
| 5     | 0.1146    | 0.3254   | 91.08%       |
| 6     | 0.0632    | 0.3473   | 91.17%       |

### Run 6 — LR=3e-5, WD=0.05
| Epoch | Train Loss | Val Loss | Val Accuracy |
|-------|-----------|----------|--------------|
| 1     | 0.2838    | 0.2663   | 89.17%       |
| 2     | 0.2381    | 0.2270   | 91.33%       |
| 3     | 0.2117    | 0.2320   | **91.67%**   |
| 4     | 0.1243    | 0.2438   | 91.67%       |
| 5     | 0.0985    | 0.3722   | 90.00%       |

### Run 7 — LR=2e-5, WD=0.02
| Epoch | Train Loss | Val Loss | Val Accuracy |
|-------|-----------|----------|--------------|
| 1     | 0.4090    | 0.3744   | 83.50%       |
| 2     | 0.2625    | 0.2589   | 88.75%       |
| 3     | 0.2285    | 0.2355   | 90.75%       |
| 4     | 0.1653    | 0.2142   | **92.17%**   |
| 5     | 0.1656    | 0.3274   | 88.42%       |
| 6     | 0.1314    | 0.2606   | 91.42%       |


## Model Weights

sumanth-velagala/akr-router-model