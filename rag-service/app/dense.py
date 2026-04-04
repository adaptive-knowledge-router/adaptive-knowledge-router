import json
import pickle
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer


class DenseRetriever:
    def __init__(
        self,
        data_path="data/processed/papers_processed.jsonl",
        index_dir="indexes/faiss",
        model_name="BAAI/bge-large-en",
        max_docs=None
    ):
        self.data_path = Path(data_path)
        self.index_dir = Path(index_dir)
        self.index_path = self.index_dir / "papers.index"
        self.metadata_path = self.index_dir / "papers.pkl"

        self.model_name = model_name
        self.max_docs = max_docs

        self.model = SentenceTransformer(self.model_name)

        self.papers = []
        self.documents = []
        self.index = None

        self.index_dir.mkdir(parents=True, exist_ok=True)

        self._load_data()

        if self.max_docs is None and self.index_path.exists() and self.metadata_path.exists():
            self._load_index()
        else:
            self._build_and_save_index()

    def _load_data(self):
        with self.data_path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if self.max_docs is not None and i >= self.max_docs:
                    break
                row = json.loads(line)
                self.papers.append(row)

        self.documents = [paper["full_text_for_rag"] for paper in self.papers]

    def _build_and_save_index(self):
        if not self.documents:
            raise ValueError("No documents loaded for dense index.")

        embeddings = self.model.encode(
            self.documents,
            batch_size=8,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        embeddings = embeddings.astype("float32")
        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings)

        if self.max_docs is None:
            faiss.write_index(self.index, str(self.index_path))
            with self.metadata_path.open("wb") as f:
                pickle.dump(self.papers, f)

    def _load_index(self):
        self.index = faiss.read_index(str(self.index_path))

        with self.metadata_path.open("rb") as f:
            self.papers = pickle.load(f)

        self.documents = [paper["full_text_for_rag"] for paper in self.papers]

    def search(self, query: str, top_k: int = 5):
        query = query.strip()
        if not query:
            return []

        top_k = max(1, min(top_k, len(self.papers)))

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")

        scores, indices = self.index.search(query_embedding, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue

            paper = self.papers[idx]
            results.append({
                "paper_id": paper["paper_id"],
                "title": paper["title"],
                "authors": paper["authors"],
                "categories": paper["categories"],
                "abstract": paper["abstract"],
                "score": float(score)
            })

        return results