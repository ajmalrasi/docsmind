"""Forum-aware retrieval units for BRISKODA posts.

Raw forum posts are the source records. Retrieval chunks are a derived artifact:
short replies borrow limited context from the previous post, normal posts remain
whole, and unusually long posts are sentence-split with overlap.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.utils import get_tokenizer

_tokenize = get_tokenizer()


@dataclass(frozen=True)
class BriskodaChunkConfig:
    """Token budgets for forum-aware retrieval units."""

    max_tokens: int = 700
    overlap_tokens: int = 100
    short_post_tokens: int = 40
    previous_context_tokens: int = 300
    diagnostic_dump_min_tokens: int = 4_000
    diagnostic_dump_min_lines: int = 100
    diagnostic_dense_chunk_cap: int = 8

    def validate(self) -> None:
        if self.max_tokens < 64:
            raise ValueError("max_tokens must be at least 64")
        if not 0 <= self.overlap_tokens < self.max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")
        if not 0 < self.short_post_tokens < self.max_tokens:
            raise ValueError("short_post_tokens must be between 1 and max_tokens")
        if not 0 < self.previous_context_tokens < self.max_tokens:
            raise ValueError(
                "previous_context_tokens must be between 1 and max_tokens"
            )
        if self.diagnostic_dump_min_tokens < self.max_tokens:
            raise ValueError("diagnostic_dump_min_tokens must be at least max_tokens")
        if self.diagnostic_dump_min_lines < 10:
            raise ValueError("diagnostic_dump_min_lines must be at least 10")
        if self.diagnostic_dense_chunk_cap < 1:
            raise ValueError("diagnostic_dense_chunk_cap must be at least 1")


_DIAGNOSTIC_SIGNALS = (
    re.compile(r"\bVCDS\b", re.IGNORECASE),
    re.compile(r"\b(?:FULL SCAN|Auto-Scan)\b", re.IGNORECASE),
    re.compile(r"^Address [0-9A-F]{2}:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(?:IDE|ENG|MAS)\d+", re.MULTILINE),
    re.compile(r"\bASAM Dataset:\s", re.IGNORECASE),
    re.compile(r"^Elapsed Time:\s", re.IGNORECASE | re.MULTILINE),
)


def is_diagnostic_dump(text: str, config: BriskodaChunkConfig) -> bool:
    """Identify unusually large machine-generated VCDS/diagnostic listings.

    The thresholds deliberately require both size and several independent format
    signals. A long human-written repair guide should not be classified as a dump
    merely because it mentions VCDS once.
    """
    if count_tokens(text) < config.diagnostic_dump_min_tokens:
        return False
    if len(text.splitlines()) < config.diagnostic_dump_min_lines:
        return False
    return sum(bool(pattern.search(text)) for pattern in _DIAGNOSTIC_SIGNALS) >= 3


def _representative_indices(total: int, cap: int) -> set[int]:
    """Choose stable, evenly spaced chunks, always including both ends."""
    if total <= cap:
        return set(range(total))
    if cap == 1:
        return {0}
    return {round(index * (total - 1) / (cap - 1)) for index in range(cap)}


def count_tokens(text: str) -> int:
    """Count tokens using the same tokenizer family LlamaIndex uses."""
    return len(_tokenize(text))


def load_briskoda_posts(path: Path | str) -> list[dict[str, Any]]:
    """Load and validate the crawler's post-level JSONL."""
    path = Path(path)
    posts: list[dict[str, Any]] = []
    seen_post_ids: set[str] = set()

    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                post = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on {path}:{line_number}") from exc

            required = ("topic_id", "topic_title", "post_id", "post_url", "text")
            missing = [key for key in required if not str(post.get(key, "")).strip()]
            if missing:
                raise ValueError(
                    f"Missing {', '.join(missing)} on {path}:{line_number}"
                )

            post_id = str(post["post_id"])
            if post_id in seen_post_ids:
                raise ValueError(f"Duplicate post_id {post_id} on {path}:{line_number}")
            seen_post_ids.add(post_id)
            posts.append(post)

    return posts


def _last_sentence_chunk(text: str, max_tokens: int) -> str:
    if count_tokens(text) <= max_tokens:
        return text.strip()
    splitter = SentenceSplitter(chunk_size=max_tokens, chunk_overlap=0)
    return splitter.split_text(text)[-1].strip()


def _base_record(post: dict[str, Any], *, chunk_index: int) -> dict[str, Any]:
    topic_id = str(post["topic_id"])
    post_id = str(post["post_id"])
    return {
        "id": f"briskoda:{topic_id}:{post_id}:{chunk_index}",
        "source_type": "briskoda",
        "topic_id": topic_id,
        "topic_title": str(post["topic_title"]).strip(),
        "topic_url": str(post.get("topic_url", "")),
        "post_id": post_id,
        "post_url": str(post["post_url"]),
        "post_number": int(post.get("post_number") or 0),
        "posted_at": str(post.get("posted_at", "")),
        "author": str(post.get("author", "")),
        "chunk_index": chunk_index,
    }


def build_briskoda_chunks(
    posts: Iterable[dict[str, Any]],
    config: BriskodaChunkConfig | None = None,
) -> list[dict[str, Any]]:
    """Transform ordered forum posts into stable, citation-ready chunks."""
    config = config or BriskodaChunkConfig()
    config.validate()

    topics: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        topics[str(post["topic_id"])].append(post)
    for topic_posts in topics.values():
        topic_posts.sort(
            key=lambda post: (
                int(post.get("post_number") or 0),
                str(post.get("posted_at", "")),
                str(post["post_id"]),
            )
        )

    chunks: list[dict[str, Any]] = []
    for topic_posts in topics.values():
        previous: dict[str, Any] | None = None
        for post in topic_posts:
            title = str(post["topic_title"]).strip()
            text = str(post["text"]).strip()
            post_number = int(post.get("post_number") or 0)
            post_tokens = count_tokens(text)

            if post_tokens < config.short_post_tokens and previous is not None:
                previous_text = _last_sentence_chunk(
                    str(previous["text"]), config.previous_context_tokens
                )
                previous_number = int(previous.get("post_number") or 0)
                chunk_text = (
                    f"Topic: {title}\n\n"
                    f"Previous post #{previous_number}:\n{previous_text}\n\n"
                    f"Current post #{post_number}:\n{text}"
                )
                record = _base_record(post, chunk_index=0)
                record.update(
                    {
                        "text": chunk_text,
                        "strategy": "short_with_previous",
                        "chunk_count": 1,
                        "source_post_ids": [
                            str(previous["post_id"]),
                            str(post["post_id"]),
                        ],
                        "token_count": count_tokens(chunk_text),
                        "index_dense": True,
                        "index_lexical": True,
                    }
                )
                chunks.append(record)
                previous = post
                continue

            header = f"Topic: {title}\n\nPost #{post_number}:\n"
            full_text = header + text
            if count_tokens(full_text) <= config.max_tokens:
                record = _base_record(post, chunk_index=0)
                record.update(
                    {
                        "text": full_text,
                        "strategy": (
                            "short_without_previous"
                            if post_tokens < config.short_post_tokens
                            else "whole_post"
                        ),
                        "chunk_count": 1,
                        "source_post_ids": [str(post["post_id"])],
                        "token_count": count_tokens(full_text),
                        "index_dense": True,
                        "index_lexical": True,
                    }
                )
                chunks.append(record)
                previous = post
                continue

            body_budget = max(64, config.max_tokens - count_tokens(header) - 8)
            overlap = min(config.overlap_tokens, body_budget - 1)
            parts = SentenceSplitter(
                chunk_size=body_budget,
                chunk_overlap=overlap,
            ).split_text(text)
            diagnostic_dump = is_diagnostic_dump(text, config)
            dense_indices = (
                _representative_indices(len(parts), config.diagnostic_dense_chunk_cap)
                if diagnostic_dump
                else set(range(len(parts)))
            )
            for chunk_index, part in enumerate(parts):
                part_header = (
                    f"Topic: {title}\n\n"
                    f"Post #{post_number}, part {chunk_index + 1} of {len(parts)}:\n"
                )
                chunk_text = part_header + part.strip()
                record = _base_record(post, chunk_index=chunk_index)
                record.update(
                    {
                        "text": chunk_text,
                        "strategy": (
                            "diagnostic_dump_split"
                            if diagnostic_dump
                            else "long_post_split"
                        ),
                        "chunk_count": len(parts),
                        "source_post_ids": [str(post["post_id"])],
                        "token_count": count_tokens(chunk_text),
                        "index_dense": chunk_index in dense_indices,
                        "index_lexical": True,
                    }
                )
                chunks.append(record)
            previous = post

    return chunks


def chunk_manifest(
    posts: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    config: BriskodaChunkConfig,
) -> dict[str, Any]:
    """Create auditable counts for a derived chunk artifact."""
    strategy_counts: dict[str, int] = defaultdict(int)
    for chunk in chunks:
        strategy_counts[str(chunk["strategy"])] += 1
    return {
        "source_posts": len(posts),
        "source_topics": len({str(post["topic_id"]) for post in posts}),
        "chunks": len(chunks),
        "unique_chunk_ids": len({str(chunk["id"]) for chunk in chunks}),
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "dense_eligible_chunks": sum(
            bool(chunk.get("index_dense", True)) for chunk in chunks
        ),
        "lexical_eligible_chunks": sum(
            bool(chunk.get("index_lexical", True)) for chunk in chunks
        ),
        "diagnostic_dump_posts": len(
            {
                str(chunk["post_id"])
                for chunk in chunks
                if chunk["strategy"] == "diagnostic_dump_split"
            }
        ),
        "diagnostic_lexical_only_chunks": sum(
            chunk["strategy"] == "diagnostic_dump_split"
            and not bool(chunk.get("index_dense", True))
            for chunk in chunks
        ),
        "config": asdict(config),
    }
