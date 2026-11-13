
"""Pipeline entry point for the Data Ingestion Engineering lab."""
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .chunking import fixed_size, by_paragraph
from .embeddings import MyEmbedder
from .ingestion import load_pdf
from .store import PgVectorStore

from .evaluation import evaluate_query, summarize


def get_embeddings(
    chunks,
    strategy: str,
    embedder: MyEmbedder,
    cache: dict,
    cache_path: Path,
) -> list[list[float]]:
    """Load cached embeddings or generate and save missing vectors."""

    strategy_cache = cache["vectors"].setdefault(strategy, {})

    vectors = []
    missing_chunks = []

    for chunk in chunks:
        text_hash = hashlib.sha256(
            chunk.text.encode("utf-8")
        ).hexdigest()

        cached = strategy_cache.get(chunk.chunk_id)

        if (
            cached
            and cached["text_hash"] == text_hash
            and len(cached["vector"]) == embedder.dimensions
        ):
            vectors.append(cached["vector"])
        else:
            vectors.append(None)
            missing_chunks.append((len(vectors) - 1, chunk, text_hash))

    if missing_chunks:
        print(
            f"Strategy {strategy}: "
            f"generating {len(missing_chunks)} missing embeddings..."
        )

        new_vectors = embedder.embed_documents(
            [chunk.text for _, chunk, _ in missing_chunks]
        )

        for (position, chunk, text_hash), vector in zip(
            missing_chunks, new_vectors
        ):
            if len(vector) != embedder.dimensions:
                raise ValueError("Unexpected embedding dimensions")

            vectors[position] = vector

            strategy_cache[chunk.chunk_id] = {
                "text_hash": text_hash,
                "vector": vector,
            }

        # Save immediately so completed embeddings survive interruptions.
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = cache_path.with_suffix(".tmp")

        temporary_path.write_text(
            json.dumps(cache),
            encoding="utf-8",
        )

        temporary_path.replace(cache_path)

    return vectors


def main() -> None:
    """Load corpus, chunk, embed, and store the three strategies."""

    root = Path(__file__).resolve().parent.parent
    load_dotenv(dotenv_path=root / ".env")

    # Load source manifest.
    manifest_path = root / "data" / "manifest" / "sources.json"

    with manifest_path.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    # Load benchmark questions.
    benchmark_path = root / "benchmark" / "questions.json"

    with benchmark_path.open("r", encoding="utf-8") as file:
        benchmark = json.load(file)

    questions = benchmark["questions"]

    # Load documents and retain only manifest pages.
    pages = []

    for document in manifest["documents"]:
        document_id = document["document_id"]
        source = document["source_path_or_url"]
        pdf_path = root / source

        all_pages = load_pdf(
            path=pdf_path,
            document_id=document_id,
            source=source,
        )

        selected_page_numbers = set(document["pages"])
        category_by_page = {}

        for chapter in document["chapters"]:
            for page_number in chapter["pages"]:
                category_by_page[page_number] = chapter["category"]

        for page in all_pages:
            if page.page not in selected_page_numbers:
                continue

            page.metadata["category"] = category_by_page[page.page]
            pages.append(page)

    # Validate the content corpus.
    content_pages = [
        page for page in pages
        if page.text.strip()
    ]

    if len(content_pages) < 30:
        raise ValueError(
            f"Expected at least 30 content pages, found {len(content_pages)}"
        )

    if len(content_pages) != len(pages):
        raise ValueError(
            "Some selected manifest pages contain no extractable text"
        )

    # Build the three required retrieval strategies.
    chunks_a = [
        chunk
        for page in content_pages
        for chunk in fixed_size(page, size=500, overlap=50)
    ]

    chunks_b = [
        chunk
        for page in content_pages
        for chunk in by_paragraph(page, max_size=500)
    ]

    # Strategy C uses the same chunks as B.
    # The only difference is metadata filtering during retrieval.
    chunks_c = chunks_b

    strategies = {
        "A": chunks_a,
        "B": chunks_b,
        "C": chunks_c,
    }

    # Initialize the same embedding model for all strategies.
    embedder = MyEmbedder(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Load or initialize the embedding cache.
    cache_path = root / ".cache" / "embeddings.json"

    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

        if (
            cache.get("model_name") != embedder.model_name
            or cache.get("dimensions") != embedder.dimensions
        ):
            raise ValueError(
                "Embedding cache model or dimensions do not match"
            )
    else:
        cache = {
            "model_name": embedder.model_name,
            "dimensions": embedder.dimensions,
            "vectors": {},
        }

    # Generate or reuse document embeddings.
    vectors_a = get_embeddings(
        chunks_a, "A", embedder, cache, cache_path
    )

    vectors_b = get_embeddings(
        chunks_b, "B", embedder, cache, cache_path
    )

    # Strategy C reuses B's chunks and embeddings.
    vectors_c = vectors_b

    print("\nEmbedding results:")
    print("Provider: Sentence Transformers (local)")
    print(f"Model: {embedder.model_name}")
    print(f"Dimensions: {embedder.dimensions}")
    print(f"Strategy A vectors: {len(vectors_a)}")
    print(f"Strategy B vectors: {len(vectors_b)}")
    print(f"Strategy C vectors: {len(vectors_c)}")

    # Initialize PostgreSQL + pgvector.
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL is not configured")

    store = PgVectorStore(
        database_url=database_url,
        dimensions=embedder.dimensions,
    )

    store.create_schema()

    # Store chunks and embeddings for each strategy.
    store.upsert("A", chunks_a, vectors_a)
    store.upsert("B", chunks_b, vectors_b)
    store.upsert("C", chunks_c, vectors_c)

    print("\nVector store results:")
    print("Strategy A: stored")
    print("Strategy B: stored")
    print("Strategy C: stored")

    # Report chunking statistics.
    print("\nChunking results:")

    for strategy, chunks in strategies.items():
        lengths = [len(chunk.text) for chunk in chunks]

        print(f"Strategy {strategy}:")
        print(f"  Total chunks: {len(chunks)}")
        print(f"  Average length: {sum(lengths) / len(lengths):.2f}")
        print(f"  Min length: {min(lengths)}")
        print(f"  Max length: {max(lengths)}")

    # Validate benchmark splits.
    dev_questions = [
        question for question in questions
        if question["split"] == "dev"
    ]

    test_questions = [
        question for question in questions
        if question["split"] == "test"
    ]

        # Run retrieval and evaluation for all strategies.
    traces = []

    for question in questions:
        query_vector = embedder.embed_query(question["question"])

        for strategy in ["A", "B", "C"]:
            filters = (
                question.get("filter")
                if strategy == "C"
                else None
            )

            hits = store.search(
                strategy=strategy,
                query_vector=query_vector,
                top_k=3,
                filters=filters,
            )

            evaluation_question = {
                **question,
                "strategy": strategy,
            }

            trace = evaluate_query(
                evaluation_question,
                hits,
            )

            traces.append(trace)

    # Summarize evaluation results.
    summary = summarize(traces)

    # Save traces and summary.
    output_dir = root / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)

    traces_path = output_dir / "evaluation_traces.json"
    summary_path = output_dir / "evaluation_summary.json"

    traces_path.write_text(
        json.dumps(traces, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nEvaluation results:")

    for strategy, splits in summary.items():
        print(f"\nStrategy {strategy}")

        for split, metrics in splits.items():
            print(f"  {split}:")
            print(
                f"    Hit@1: "
                f"{metrics['hit_at_1_count']}/"
                f"{metrics['total_questions']} "
                f"({metrics['hit_at_1']:.2%})"
            )
            print(
                f"    Evidence Hit@3: "
                f"{metrics['evidence_hit_at_3_count']}/"
                f"{metrics['total_questions']} "
                f"({metrics['evidence_hit_at_3']:.2%})"
            )

    print("\nEvaluation completed.")
    print(f"Total evaluation traces: {len(traces)}")
    print(f"Traces saved: {traces_path}")
    print(f"Summary saved: {summary_path}")


if __name__ == "__main__":
    main()
