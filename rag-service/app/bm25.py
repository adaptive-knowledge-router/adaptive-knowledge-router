import json
import re
from pathlib import Path
from rank_bm25 import BM25Okapi


def simple_tokenize(text: str):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


class BM25Retriever:
    def __init__(self, data_path="data/processed/papers_processed.jsonl"):
        self.data_path = Path(data_path)
        self.papers = []
        self.documents = []
        self.tokenized_docs = []
        self.bm25 = None

        self._load_data()
        self._build_index()

    def _load_data(self):
        with self.data_path.open("r", encoding="utf-8") as f:
            for line in f:
                self.papers.append(json.loads(line))

        self.documents = [p["full_text_for_rag"] for p in self.papers]

    def _build_index(self):
        if not self.documents:
            raise ValueError("No documents loaded for BM25 index.")

        self.tokenized_docs = [simple_tokenize(doc) for doc in self.documents]
        self.bm25 = BM25Okapi(self.tokenized_docs)

    def search(self, query: str, top_k: int = 5):
        query = query.strip()
        if not query:
            return []

        top_k = max(1, min(top_k, len(self.papers)))

        tokenized_query = simple_tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:top_k]

        results = []
        for i in ranked_indices:
            paper = self.papers[i]
            results.append({
                "paper_id": paper["paper_id"],
                "title": paper["title"],
                "authors": paper["authors"],
                "categories": paper["categories"],
                "abstract": paper["abstract"],
                "score": float(scores[i])
            })

        return results