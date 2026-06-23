"""Build the FAISS index from the document corpus.

Usage: python -m scripts.ingest
"""

from __future__ import annotations

from docsmind.config import get_settings
from docsmind.factory import build_embedder, new_store
from docsmind.ingestion.chunker import chunk_documents
from docsmind.ingestion.loaders import load_documents


def main() -> None:
    settings = get_settings()
    print(f"Loading documents from {settings.data_dir} ...")
    documents = load_documents(settings.data_dir)
    print(f"  loaded {len(documents)} document(s)")

    chunks = chunk_documents(
        documents,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    print(f"  produced {len(chunks)} chunk(s)")

    print(f"Embedding with {settings.embed_model} ...")
    embedder = build_embedder(settings)
    embeddings = embedder.encode([c.text for c in chunks])

    store = new_store(settings, dim=embedder.dim)
    store.add(chunks, embeddings)
    store.save(settings.index_dir)
    print(
        f"Saved {store.size} vectors (index_type={store.index_type}) "
        f"to {settings.index_dir}"
    )


if __name__ == "__main__":
    main()
