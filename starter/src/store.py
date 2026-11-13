"""TODO: store and search vectors using PostgreSQL + pgvector."""
from typing import Any
from .models import Chunk
import psycopg
from pgvector.psycopg import register_vector


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        """TODO: retain connection settings; validate model dimensions."""
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than 0")

        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self):
        connection = psycopg.connect(self.database_url)
        register_vector(connection)
        return connection

    def create_schema(self) -> None:
        """TODO: create table with vector column and source/page/filter metadata."""
        with self._connect() as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")

            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    strategy TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}',
                    embedding vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_metadata
                ON chunks USING GIN (metadata)
                """
            )


    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """TODO: validate lengths/dimensions and write stable IDs without duplicates.

        When re-ingesting changed source documents, remove obsolete chunks too.
        """
        if len(chunks) != len(vectors):
            raise ValueError("Number of chunks and vectors must match")

        if not strategy:
            raise ValueError("strategy must not be empty")

        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Expected {self.dimensions} dimensions, "
                    f"got {len(vector)}"
                )

        if not chunks:
            return

        with self._connect() as connection:
            # Remove previous chunks for this strategy and document.
            document_ids = list(
                {chunk.document_id for chunk in chunks}
            )

            connection.execute(
                """
                DELETE FROM chunks
                WHERE strategy = %s
                  AND document_id = ANY(%s)
                """,
                (strategy, document_ids),
            )

            for chunk, vector in zip(chunks, vectors):
                connection.execute(
                    """
                    INSERT INTO chunks (
                        strategy,
                        chunk_id,
                        document_id,
                        source,
                        page,
                        text,
                        metadata,
                        embedding
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (strategy, chunk_id)
                    DO UPDATE SET
                        document_id = EXCLUDED.document_id,
                        source = EXCLUDED.source,
                        page = EXCLUDED.page,
                        text = EXCLUDED.text,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        strategy,
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.source,
                        chunk.page,
                        chunk.text,
                        psycopg.types.json.Jsonb(chunk.metadata),
                        vector,
                    ),
                )


    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """TODO: filter permitted metadata in SQL, rank by cosine distance, return top-k.

        Return chunk ID, text, score and metadata. Parameterize user-supplied values.
        """
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"Expected {self.dimensions} dimensions, "
                f"got {len(query_vector)}"
            )

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        allowed_filters = {"category"}

        filters = filters or {}

        unsupported = set(filters) - allowed_filters
        if unsupported:
            raise ValueError(
                f"Unsupported filters: {sorted(unsupported)}"
            )

        conditions = ["strategy = %s"]
        params: list[Any] = [strategy]

        for key, value in filters.items():
            conditions.append("metadata ->> %s = %s")
            params.extend([key, str(value)])

        where_clause = " AND ".join(conditions)

        params.extend([query_vector, top_k])

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    chunk_id,
                    document_id,
                    source,
                    page,
                    text,
                    metadata,
                    1 - (embedding <=> %s::vector) AS score
                FROM chunks
                WHERE {where_clause}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (
                    query_vector,
                    *params[:-2],
                    query_vector,
                    top_k,
                ),
            ).fetchall()

        return [
            {
                "chunk_id": row[0],
                "document_id": row[1],
                "source": row[2],
                "page": row[3],
                "text": row[4],
                "metadata": row[5],
                "score": float(row[6]),
            }
            for row in rows
        ]

