import json
from pathlib import Path
from zipfile import ZipFile

from docsmind.ingestion.whatsapp import (
    load_whatsapp_documents,
    parse_whatsapp_text,
    prepare_whatsapp_export,
    redact_message_text,
)


SAMPLE = """[21/03/26, 10:42:52\u202fPM] Alice Example: Call me at +91 98765 43210
\u200e[21/03/26, 10:43:10\u202fPM] Bob Example: First line
second line
\u200e[21/03/26, 10:44:00\u202fPM] Bob Example: \u200eimage omitted
\u200e[21/03/26, 10:45:00\u202fPM] Admin Example: \u200eThis message was deleted by admin ~\u202fAlice Example.
\u200e[21/03/26, 11:05:00\u202fPM] Alice Example: alice@example.com
"""


def test_parse_preserves_multiline_messages():
    messages = parse_whatsapp_text(SAMPLE)
    assert len(messages) == 5
    assert messages[0].timestamp.isoformat() == "2026-03-21T22:42:52"
    assert messages[1].text == "First line\nsecond line"


def test_redaction_removes_phone_and_email():
    clean = redact_message_text("Call +91 98765 43210 or a@example.com")
    assert "+91" not in clean
    assert "a@example.com" not in clean
    assert "[PHONE]" in clean
    assert "[EMAIL]" in clean


def test_prepare_and_load_windows(tmp_path: Path):
    archive_path = tmp_path / "chat.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("_chat.txt", SAMPLE)

    output = tmp_path / "chat.whatsapp.jsonl"
    report = prepare_whatsapp_export(
        archive_path,
        output,
        chat_name="TEST_CHAT",
    )

    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert report["participants"] == 3
    assert report["skipped_deleted"] == 1
    assert report["skipped_empty_or_media_only"] == 1
    assert {record["sender"] for record in records} == {
        "participant_0001",
        "participant_0002",
    }
    assert "Alice Example" not in output.read_text()
    assert "+91 98765 43210" not in output.read_text()

    documents = load_whatsapp_documents(
        output,
        window_minutes=10,
        max_messages=20,
    )
    assert len(documents) == 2
    assert documents[0].metadata["source_type"] == "whatsapp"
    assert documents[0].metadata["start_time"] == "2026-03-21T22:42:52"
    assert "participant_0001" in documents[0].text
