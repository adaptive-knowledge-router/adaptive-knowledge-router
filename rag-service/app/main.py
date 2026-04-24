from time import perf_counter

from fastapi import FastAPI, Query

from app.bm25 import BM25Retriever
from app.dense import DenseRetriever
from app.hybrid import HybridRetriever

app = FastAPI(title="RAG Service", version="1.0.0")

# Using bge-small-en-v1.5 (smaller, faster). Upgrade to BAAI/bge-large-en for higher accuracy.

bm25_retriever = BM25Retriever()

dense_retriever = DenseRetriever(
    model_name="BAAI/bge-small-en-v1.5",
    max_docs=None
)

hybrid_retriever = HybridRetriever(
    bm25_retriever=bm25_retriever,
    dense_retriever=dense_retriever,
    bm25_top_k=10,
    dense_top_k=10,
    reranker_model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
)


@app.get("/")
def root():
    return {
        "message": "RAG service is running",
        "model": "BAAI/bge-small-en-v1.5",
        "reranker": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "available_endpoints": [
            "/rag/sparse",
            "/rag/dense",
            "/rag/hybrid"
        ]
    }


@app.get("/health")
def health():
    bm25_ready = (
        bm25_retriever is not None
        and hasattr(bm25_retriever, "documents")
        and len(bm25_retriever.documents) > 0
    )
    dense_ready = dense_retriever is not None and dense_retriever.index is not None
    hybrid_ready = hybrid_retriever is not None
    checks = {
        "bm25_ready": bm25_ready,
        "dense_ready": dense_ready,
        "hybrid_ready": hybrid_ready,
    }
    all_ready = all(checks.values())
    return {"status": "ok" if all_ready else "loading", **checks}


@app.get("/rag/sparse")
def rag_sparse(
    query: str = Query(..., description="User query"),
    top_k: int = Query(5, ge=1, le=20)
):
    start = perf_counter()
    try:
        results = bm25_retriever.search(query, top_k=top_k)
        latency_ms = (perf_counter() - start) * 1000

        return {
            "strategy": "sparse",
            "query": query,
            "top_k": top_k,
            "latency_ms": round(latency_ms, 2),
            "results": results
        }
    except Exception as e:
        return {
            "strategy": "sparse",
            "query": query,
            "top_k": top_k,
            "latency_ms": None,
            "results": [],
            "error": str(e)
        }


@app.get("/rag/dense")
def rag_dense(
    query: str = Query(..., description="User query"),
    top_k: int = Query(5, ge=1, le=20)
):
    start = perf_counter()
    try:
        results = dense_retriever.search(query, top_k=top_k)
        latency_ms = (perf_counter() - start) * 1000

        return {
            "strategy": "dense",
            "query": query,
            "top_k": top_k,
            "latency_ms": round(latency_ms, 2),
            "results": results
        }
    except Exception as e:
        return {
            "strategy": "dense",
            "query": query,
            "top_k": top_k,
            "latency_ms": None,
            "results": [],
            "error": str(e)
        }


@app.get("/rag/hybrid")
def rag_hybrid(
    query: str = Query(..., description="User query"),
    top_k: int = Query(5, ge=1, le=20)
):
    start = perf_counter()
    try:
        results = hybrid_retriever.search(query, top_k=top_k)
        latency_ms = (perf_counter() - start) * 1000

        return {
            "strategy": "hybrid",
            "query": query,
            "top_k": top_k,
            "latency_ms": round(latency_ms, 2),
            "results": results
        }
    except Exception as e:
        return {
            "strategy": "hybrid",
            "query": query,
            "top_k": top_k,
            "latency_ms": None,
            "results": [],
            "error": str(e)
        }