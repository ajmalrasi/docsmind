import json

import httpx
import pytest

from docsmind.ingestion.chunker import chunk_documents
from docsmind.ingestion.loaders import load_documents
from docsmind.ingestion.wikipedia import load_wikipedia_documents
from scripts.fetch_wikipedia import (
    fetch_wikipedia_page,
    load_manifest,
    validate_unique_records,
    wikipedia_html_to_sections,
)


SAMPLE_HTML = """
<div class="mw-parser-output">
  <table class="infobox">
    <tr><th>Platform</th><td>MQB</td></tr>
    <tr><th>Engine</th><td>EA888</td></tr>
  </table>
  <p>The Golf is a compact car produced by Volkswagen.</p>
  <h2>Powertrain <span class="mw-editsection">[edit]</span></h2>
  <p>The GTI uses a turbocharged engine.<sup class="reference">[1]</sup></p>
  <ul><li>EA888 petrol engine</li><li>Direct-shift gearbox</li></ul>
  <h2>Sources</h2>
  <ul><li>Large bibliography entry</li></ul>
  <div class="navbox">Unrelated navigation text</div>
</div>
"""


def _record() -> dict:
    return {
        "requested_title": "Volkswagen Golf",
        "title": "Volkswagen Golf",
        "page_id": 123,
        "revision_id": 456,
        "source_url": "https://en.wikipedia.org/wiki/Volkswagen_Golf",
        "language": "en",
        "fetched_at": "2026-08-05T00:00:00+00:00",
        "license": "CC BY-SA 4.0",
        "sections": wikipedia_html_to_sections(SAMPLE_HTML),
    }


def test_html_normalization_preserves_headings_lists_and_tables():
    sections = wikipedia_html_to_sections(SAMPLE_HTML)

    assert [section["title"] for section in sections] == ["Lead", "Powertrain"]
    assert "Platform | MQB" in sections[0]["text"]
    assert "Engine | EA888" in sections[0]["text"]
    assert "- EA888 petrol engine" in sections[1]["text"]
    assert "Unrelated navigation text" not in sections[1]["text"]
    assert "Large bibliography entry" not in sections[1]["text"]
    assert "[1]" not in sections[1]["text"]


def test_load_wikipedia_documents_preserves_revision_and_citation(tmp_path):
    path = tmp_path / "cars.wikipedia.jsonl"
    path.write_text(json.dumps(_record()) + "\n", encoding="utf-8")

    documents = load_wikipedia_documents(path)

    assert len(documents) == 2
    assert documents[0].doc_id == "wikipedia:123:456:0"
    assert documents[0].metadata["source_type"] == "wikipedia"
    assert documents[0].metadata["revision_id"] == 456
    assert documents[0].metadata["section"] == "Lead"
    assert documents[0].metadata["source_url"].endswith("/Volkswagen_Golf")


def test_generic_loader_discovers_wikipedia_jsonl(tmp_path):
    path = tmp_path / "cars.wikipedia.jsonl"
    path.write_text(json.dumps(_record()) + "\n", encoding="utf-8")

    documents = load_documents(tmp_path)

    assert len(documents) == 2
    assert all(doc.metadata["source_type"] == "wikipedia" for doc in documents)


def test_chunks_cite_article_url(tmp_path):
    path = tmp_path / "cars.wikipedia.jsonl"
    path.write_text(json.dumps(_record()) + "\n", encoding="utf-8")
    documents = load_wikipedia_documents(path)

    chunks = chunk_documents(documents, chunk_size=128, chunk_overlap=16)

    assert chunks
    assert all(
        chunk.source == "https://en.wikipedia.org/wiki/Volkswagen_Golf"
        for chunk in chunks
    )


def test_fetch_page_records_resolved_title_and_revision():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("DocsMind/")
        return httpx.Response(
            200,
            json={
                "parse": {
                    "title": "Volkswagen Golf",
                    "pageid": 123,
                    "revid": 456,
                    "text": SAMPLE_HTML,
                }
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "DocsMind/test"},
    ) as client:
        record = fetch_wikipedia_page(
            client,
            "VW Golf",
            language="en",
            max_retries=0,
        )

    assert record["requested_title"] == "VW Golf"
    assert record["title"] == "Volkswagen Golf"
    assert record["revision_id"] == 456
    assert record["source_url"].endswith("/Volkswagen_Golf")
    assert len(record["html_sha256"]) == 64


def test_manifest_rejects_duplicate_pages(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"language": "en", "pages": ["Golf", "Golf"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_manifest(manifest)


def test_canonical_duplicate_pages_are_rejected():
    records = [
        {"page_id": 123, "requested_title": "CARIAD"},
        {"page_id": 123, "requested_title": "Volkswagen Group"},
    ]

    with pytest.raises(ValueError, match="same canonical page"):
        validate_unique_records(records)
