"""Implement fixed-size and structure-aware chunking."""
from .models import Chunk, DocumentPage
import re

def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """TODO: split text into overlapping windows and retain page metadata."""
    if size <= 0:
        raise ValueError("size must be greater than 0")

    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    text = page.text

    if not text:
        return []

    chunks: list[Chunk] = []

    start = 0

    while start < len(text):
        end = min(start + size, len(text))

        chunk_text = text[start:end]

        # Stable ID based on document, page and character positions.
        chunk_id = (
            f"{page.document_id}:"
            f"{page.page}:"
            f"fixed:{start}:{end}"
        )

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=chunk_text,
                metadata={
                    **page.metadata,
                    "chunk_start": start,
                    "chunk_end": end,
                    "chunk_strategy": "fixed_size",
                },
            )
        )

        start += size - overlap

    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """TODO: group paragraphs, split oversized paragraphs and retain metadata."""
    if max_size <= 0:
        raise ValueError("max_size must be greater than 0")

    text = page.text

    if not text.strip():
        return []

    # Identify paragraphs separated by one or more blank lines.
    paragraph_matches = list(
        re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, re.DOTALL)
    )

    # Fallback in case the text has no paragraph boundaries.
    if not paragraph_matches:
        return []

    # Each segment stores (text, original_start, original_end).
    segments = []

    for match in paragraph_matches:
        paragraph = match.group().strip()
        paragraph_start = match.start()
        paragraph_end = match.end()

        if len(paragraph) <= max_size:
            segments.append(
                (paragraph, paragraph_start, paragraph_end)
            )
            continue

        # Split oversized paragraphs without cutting words when possible.
        cursor = 0

        while cursor < len(paragraph):
            end = min(cursor + max_size, len(paragraph))

            if end < len(paragraph):
                split_at = paragraph.rfind(" ", cursor, end)

                if split_at > cursor:
                    end = split_at

            segment_text = paragraph[cursor:end].strip()

            if segment_text:
                # Account for whitespace removed by strip().
                actual_start = paragraph.find(segment_text, cursor)
                actual_end = actual_start + len(segment_text)

                segments.append(
                    (
                        segment_text,
                        paragraph_start + actual_start,
                        paragraph_start + actual_end,
                    )
                )

            cursor = end

            # Skip whitespace between split segments.
            while cursor < len(paragraph) and paragraph[cursor].isspace():
                cursor += 1

    # Group adjacent segments while staying within max_size.
    grouped = []
    current_parts = []
    current_start = None
    current_end = None
    current_length = 0

    for segment_text, start, end in segments:
        separator_length = 2 if current_parts else 0
        new_length = current_length + separator_length + len(segment_text)

        if current_parts and new_length > max_size:
            grouped.append(
                ("\n\n".join(current_parts), current_start, current_end)
            )

            current_parts = []
            current_start = None
            current_end = None
            current_length = 0

            separator_length = 0

        if not current_parts:
            current_start = start

        current_parts.append(segment_text)
        current_end = end
        current_length += separator_length + len(segment_text)

    if current_parts:
        grouped.append(
            ("\n\n".join(current_parts), current_start, current_end)
        )

    chunks = []

    for index, (chunk_text, start, end) in enumerate(grouped):
        chunk_id = (
            f"{page.document_id}:"
            f"{page.page}:"
            f"paragraph:{start}:{end}"
        )

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=chunk_text,
                metadata={
                    **page.metadata,
                    "chunk_start": start,
                    "chunk_end": end,
                    "chunk_strategy": "by_paragraph",
                    "chunk_index": index,
                },
            )
        )

    return chunks
