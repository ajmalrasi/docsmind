"""Build the configured vector index from the document corpus.

Usage: python -m scripts.ingest
"""

from __future__ import annotations

from docsmind.config import get_settings
from docsmind.factory import build_embedder, new_store
from docsmind.ingestion.chunker import chunk_documents
from docsmind.ingestion.loaders import load_documents
from docsmind.index.embedding_manifest import save_embedding_manifest


def main() -> None:
    settings = get_settings()
    print(f"Loading documents from {settings.data_dir} ...")
    documents = load_documents(
        settings.data_dir,
        whatsapp_window_minutes=settings.whatsapp_window_minutes,
        whatsapp_max_messages=settings.whatsapp_max_messages,
    )
    print(f"  loaded {len(documents)} document(s)")

    chunks = chunk_documents(
        documents,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    print(f"  produced {len(chunks)} chunk(s)")

    embedder = build_embedder(settings)
    print(
        f"Embedding with {embedder.provider_name}:{embedder.model_name} "
        f"(dimension={embedder.dim}) ..."
    )
    embeddings = embedder.embed_documents([c.text for c in chunks])

    store = new_store(settings, dim=embedder.dim)
    store.add(chunks, embeddings)
    store.save(settings.index_dir)
    save_embedding_manifest(settings.index_dir, embedder)
    location = (
        settings.opensearch_endpoint
        if settings.vector_backend == "opensearch"
        else str(settings.index_dir)
    )
    print(
        f"Saved {store.size} vectors (index_type={store.index_type}) "
        f"to {location}"
    )


if __name__ == "__main__":
    main()
