from llama_index.core.schema import Document

from docsmind.ingestion.chunker import chunk_documents


def test_chunks_carry_source_and_text():
    doc = Document(
        text="Sentence one. Sentence two. " * 50,
        metadata={"file_name": "guide.md"},
    )
    chunks = chunk_documents([doc], chunk_size=64, chunk_overlap=8)
    assert len(chunks) >= 1
    assert all(c.text for c in chunks)
    assert all(c.source == "guide.md" for c in chunks)


def test_source_falls_back_to_unknown():
    doc = Document(text="No metadata here. " * 30, metadata={})
    chunks = chunk_documents([doc], chunk_size=64, chunk_overlap=8)
    assert all(c.source == "unknown" for c in chunks)


def test_whatsapp_chunks_repeat_anonymous_window_metadata():
    doc = Document(
        text="[2026-03-21T22:42:52] participant_0001: A long message. " * 80,
        metadata={
            "file_name": "VAGBAY/2026-03-21/window-00001",
            "source_type": "whatsapp",
            "chat": "VAGBAY",
            "start_time": "2026-03-21T22:42:52",
            "end_time": "2026-03-21T22:45:00",
            "participants": ["participant_0001"],
        },
    )
    chunks = chunk_documents([doc], chunk_size=128, chunk_overlap=8)
    assert len(chunks) > 1
    assert all(chunk.text.startswith("Chat: VAGBAY\n") for chunk in chunks)
    assert all("Participants: participant_0001" in chunk.text for chunk in chunks)
