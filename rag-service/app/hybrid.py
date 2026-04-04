from sentence_transformers import CrossEncoder

from app.bm25 import BM25Retriever
from app.dense import DenseRetriever


class HybridRetriever:
    def __init__(
        self,
        bm25_top_k=10,
        dense_top_k=10,
        reranker_model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        dense_model_name="BAAI/bge-small-en-v1.5",
        max_docs=None,
    ):
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k

        self.bm25 = BM25Retriever()
        self.dense = DenseRetriever(
            model_name=dense_model_name,
            max_docs=max_docs
        )

        self.reranker = CrossEncoder(reranker_model_name)

    def _merge_results(self, bm25_results, dense_results):
        merged = {}

        for item in bm25_results + dense_results:
            paper_id = item["paper_id"]
            if paper_id not in merged:
                merged[paper_id] = item

        return list(merged.values())

    def _rerank_candidates(self, query, candidates, top_k=5):
        if not candidates:
            return []

        pairs = [
            [query, f"{c['title']} {c['abstract']}"]
            for c in candidates
        ]

        scores = self.reranker.predict(pairs)

        rescored = []
        for c, score in zip(candidates, scores):
            item = c.copy()
            item["score"] = float(score)
            rescored.append(item)

        rescored.sort(key=lambda x: x["score"], reverse=True)
        return rescored[:top_k]

    def search(self, query: str, top_k: int = 5):
        query = query.strip()
        if not query:
            return []

        top_k = max(1, top_k)

        bm25_results = self.bm25.search(query, top_k=self.bm25_top_k)
        dense_results = self.dense.search(query, top_k=self.dense_top_k)

        merged_candidates = self._merge_results(bm25_results, dense_results)

        final_results = self._rerank_candidates(
            query=query,
            candidates=merged_candidates,
            top_k=top_k
        )

        return final_results