"""TODO: evaluate retrieved evidence and preserve per-query traces."""
from typing import Any
import re


def _normalize_text(text: str) -> str:
    """Normalize whitespace and casing for evidence comparison."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def _is_evidence_hit(
    question: dict[str, Any],
    hit: dict[str, Any],
) -> bool:
    """Check whether a retrieved chunk contains expected evidence."""

    expected_source = question["gold_source_id"]
    expected_page = question["gold_page"]

    source_matches = (
        hit.get("document_id") == expected_source
    )

    page_matches = (
        hit.get("page") == expected_page
    )

    evidence_quotes = [
        question["evidence_quote"]
    ]

    evidence_quotes.extend(
        question.get("alternative_evidence_quotes", [])
    )

    evidence_matches = any(
        _normalize_text(quote)
        in _normalize_text(hit.get("text", ""))
        for quote in evidence_quotes
    )

    return source_matches and page_matches and evidence_matches

def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """TODO: check source/page and enough gold evidence; keep hit@1 and hit@3 trace.

    Accept any documented alternative gold evidence. Do not infer human grounding
    or chunk coherence labels from exact string match.
    """
    top_hits = hits[:3]

    hit_results = [
        _is_evidence_hit(question, hit)
        for hit in top_hits
    ]

    hit_at_1 = bool(hit_results and hit_results[0])
    evidence_hit_at_3 = any(hit_results)

    return {
        "question_id": question["id"],
        "split": question["split"],
        "strategy": question.get("strategy", "unknown"),
        "question": question["question"],
        "expected_answer": question["expected_answer"],
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "filter": question.get("filter"),
        "hits": top_hits,
        "evidence_checks": hit_results,
        "hit_at_1": hit_at_1,
        "evidence_hit_at_3": evidence_hit_at_3,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """TODO: aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for trace in traces:
        key = (
            trace["strategy"],
            trace["split"],
        )
        groups.setdefault(key, []).append(trace)

    summary = {}

    for (strategy, split), group in sorted(groups.items()):
        total = len(group)

        hit_at_1_count = sum(
            trace["hit_at_1"]
            for trace in group
        )

        evidence_hit_at_3_count = sum(
            trace["evidence_hit_at_3"]
            for trace in group
        )

        summary.setdefault(strategy, {})
        summary[strategy][split] = {
            "total_questions": total,
            "hit_at_1_count": hit_at_1_count,
            "hit_at_1": hit_at_1_count / total,
            "evidence_hit_at_3_count": evidence_hit_at_3_count,
            "evidence_hit_at_3": evidence_hit_at_3_count / total,
        }

    return summary
