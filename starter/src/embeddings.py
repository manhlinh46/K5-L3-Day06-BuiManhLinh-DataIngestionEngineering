"""Local embedding adapter using Sentence Transformers."""

from typing import Protocol

from sentence_transformers import SentenceTransformer


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, question: str) -> list[float]:
        ...


class MyEmbedder:
    def __init__(self, model_name: str) -> None:
        expected_model = "sentence-transformers/all-MiniLM-L6-v2"

        if model_name != expected_model:
            raise ValueError(f"This adapter requires {expected_model}")

        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device="cpu")
        self.dimensions = self.model.get_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors = self.model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        )

        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        vector = self.model.encode(
            question,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        return vector.tolist()