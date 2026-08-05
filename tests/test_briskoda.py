import json

from docsmind.ingestion.briskoda import load_briskoda_documents
from scripts.crawl_briskoda import max_page_from_urls, normalize_topic_url, page_url


def test_normalize_topic_url_removes_page_query_and_fragment():
    result = normalize_topic_url(
        "https://www.briskoda.net/forums/topic/472970-ignition-switch/"
        "page/2/?foo=bar#comments"
    )
    assert result == (
        "https://www.briskoda.net/forums/topic/472970-ignition-switch/",
        "472970",
    )


def test_max_page_and_page_url():
    assert max_page_from_urls(["https://example.test/page/2/", "https://example.test/page/18/"]) == 18
    assert page_url("https://example.test/topic/", 1) == "https://example.test/topic/"
    assert page_url("https://example.test/topic/", 3) == "https://example.test/topic/page/3/"


def test_load_briskoda_documents(tmp_path):
    path = tmp_path / "sample.briskoda.jsonl"
    path.write_text(
        json.dumps(
            {
                "topic_id": "123",
                "topic_title": "DSG gearbox issue",
                "topic_url": "https://example.test/topic/123/",
                "post_id": "456",
                "post_url": "https://example.test/topic/123/#elComment_456",
                "author": "driver",
                "posted_at": "2024-05-21T10:30:00Z",
                "post_number": 12,
                "text": "Cleaned post content.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    documents = load_briskoda_documents(path)

    assert len(documents) == 1
    assert documents[0].text == "Topic: DSG gearbox issue\n\nCleaned post content."
    assert documents[0].metadata["source_type"] == "briskoda"
    assert documents[0].metadata["post_id"] == "456"
    assert documents[0].metadata["source_url"].endswith("#elComment_456")
