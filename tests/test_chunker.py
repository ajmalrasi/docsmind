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
