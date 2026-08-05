import json

import pytest

from docsmind.ingestion.briskoda_chunks import (
    BriskodaChunkConfig,
    build_briskoda_chunks,
    chunk_manifest,
    is_diagnostic_dump,
    load_briskoda_posts,
)


def post(post_id, number, text, *, topic_id="10", title="DSG issue"):
    return {
        "topic_id": topic_id,
        "topic_title": title,
        "topic_url": f"https://example.test/topic/{topic_id}/",
        "post_id": str(post_id),
        "post_url": f"https://example.test/topic/{topic_id}/#post-{post_id}",
        "post_number": number,
        "posted_at": f"2026-01-{number:02d}T10:00:00Z",
        "author": "driver",
        "text": text,
    }


def test_short_reply_includes_previous_post_context():
    posts = [
        post("1", 1, "Reset the gearbox adaptation using VCDS before testing again."),
        post("2", 2, "That fixed it."),
    ]

    chunks = build_briskoda_chunks(posts)

    assert chunks[1]["strategy"] == "short_with_previous"
    assert "Reset the gearbox" in chunks[1]["text"]
    assert "That fixed it" in chunks[1]["text"]
    assert chunks[1]["source_post_ids"] == ["1", "2"]
    assert chunks[1]["post_url"].endswith("#post-2")


def test_long_post_is_sentence_split_with_stable_ids():
    text = " ".join(
        f"Diagnostic step {number} checks the gearbox sensor carefully."
        for number in range(80)
    )
    config = BriskodaChunkConfig(
        max_tokens=100,
        overlap_tokens=15,
        short_post_tokens=10,
        previous_context_tokens=40,
    )

    chunks = build_briskoda_chunks([post("99", 1, text)], config)

    assert len(chunks) > 1
    assert all(chunk["strategy"] == "long_post_split" for chunk in chunks)
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0]["id"] == "briskoda:10:99:0"
    assert all(chunk["chunk_count"] == len(chunks) for chunk in chunks)
    assert all(chunk["index_dense"] for chunk in chunks)
    assert all(chunk["index_lexical"] for chunk in chunks)


def test_diagnostic_dump_keeps_all_lexical_chunks_but_caps_dense_chunks():
    rows = "\n".join(
        f"IDE{number:05d}-ENG{number:06d}-Adaptation channel,active,3"
        for number in range(180)
    )
    text = (
        "VCDS FULL SCAN\nAddress 09: Cent. Elect.\nASAM Dataset: EV_BCMMQB\n"
        + rows
        + "\nElapsed Time: 01:58"
    )
    config = BriskodaChunkConfig(
        max_tokens=100,
        overlap_tokens=10,
        short_post_tokens=10,
        previous_context_tokens=40,
        diagnostic_dump_min_tokens=200,
        diagnostic_dump_min_lines=20,
        diagnostic_dense_chunk_cap=4,
    )

    assert is_diagnostic_dump(text, config)
    chunks = build_briskoda_chunks([post("dump", 1, text)], config)

    assert len(chunks) > 4
    assert all(chunk["strategy"] == "diagnostic_dump_split" for chunk in chunks)
    assert all(chunk["index_lexical"] for chunk in chunks)
    assert sum(chunk["index_dense"] for chunk in chunks) == 4
    assert chunks[0]["index_dense"]
    assert chunks[-1]["index_dense"]


def test_long_human_guide_is_not_misclassified_as_diagnostic_dump():
    text = "\n".join(
        f"Step {number}: Carefully remove the trim and inspect the connector."
        for number in range(120)
    )
    config = BriskodaChunkConfig(
        max_tokens=100,
        overlap_tokens=10,
        short_post_tokens=10,
        previous_context_tokens=40,
        diagnostic_dump_min_tokens=200,
        diagnostic_dump_min_lines=20,
    )

    assert not is_diagnostic_dump(text, config)


def test_loader_rejects_duplicate_post_ids(tmp_path):
    path = tmp_path / "posts.jsonl"
    row = post("1", 1, "A complete diagnostic description that is long enough.")
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")

    with pytest.raises(ValueError, match="Duplicate post_id"):
        load_briskoda_posts(path)


def test_manifest_counts_strategies_and_unique_ids():
    posts = [
        post("1", 1, "A detailed opening description of the gearbox problem."),
        post("2", 2, "Solved."),
    ]
    config = BriskodaChunkConfig()
    chunks = build_briskoda_chunks(posts, config)

    manifest = chunk_manifest(posts, chunks, config)

    assert manifest["source_posts"] == 2
    assert manifest["source_topics"] == 1
    assert manifest["chunks"] == 2
    assert manifest["unique_chunk_ids"] == 2
    assert manifest["strategy_counts"]["short_with_previous"] == 1
