"""Retrieval-quality eval (Phase 3) — does hybrid + rerank actually beat dense?

This is the evidence for the hardest interview question about Phase 3: "how did
you KNOW your retrieval improved?" It builds the corpus once, then runs three
retrievers over a labeled query set and reports the same metrics for each.

Configs compared:
    dense          Phase 1 — embeddings only
    hybrid         Phase 3 — dense + BM25, fused with RRF (no reranker)
    hybrid+rerank  Phase 3 — same, then a cross-encoder reorders the top
                   candidates (needs the model; pass --rerank, best on beast)

Metrics (source-level relevance — did we retrieve a chunk from the right doc?):
    Hit@1   fraction of queries whose #1 result is from the correct doc
    Hit@3   fraction whose top-3 contains the correct doc
    MRR     mean reciprocal rank of the first correct chunk (rank sensitive)

Usage:
    python -m scripts.retrieval_eval            # dense vs hybrid
    python -m scripts.retrieval_eval --rerank   # also run hybrid+rerank
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter

from docsmind.config import get_settings
from docsmind.factory import build_embedder
from docsmind.index.faiss_store import FaissVectorStore
from docsmind.ingestion.chunker import chunk_documents
from docsmind.ingestion.loaders import load_documents
from docsmind.retrieval.reranker import CrossEncoderReranker
from docsmind.retrieval.retriever import HybridRetriever, Retriever

_EVAL_FILE = "data/eval/retrieval_queries.json"
_RANK_DEPTH = 5  # how deep we look when computing the first-correct rank


def _load_queries() -> list[dict]:
    with open(_EVAL_FILE, encoding="utf-8") as f:
        return json.load(f)["queries"]


def _score(retriever, queries: list[dict], source_counts: Counter, k: int) -> dict:
    """All retrieval metrics in one pass.

    Relevance is binary at the chunk level: a retrieved chunk is relevant iff it
    comes from the query's labeled source doc. The "relevant set" for a query is
    therefore *every* chunk from that doc, which is what lets Recall@k and NDCG@k
    mean something (they need multiple relevant items).
    """
    hit1 = hit3 = rr_sum = recall_sum = ndcg_sum = 0.0
    for item in queries:
        results = retriever.retrieve(item["q"], k)
        src = item["source"]
        # rels[i] = 1 if the chunk at rank i+1 is from the correct doc.
        rels = [1 if r.chunk.source == src else 0 for r in results]

        # Hit@1 / Hit@3 / MRR — based on the FIRST relevant chunk's rank.
        first = next((i + 1 for i, x in enumerate(rels) if x), None)
        if first is not None:
            hit1 += first == 1
            hit3 += first <= 3
            rr_sum += 1.0 / first

        # Recall@k — of all relevant chunks, what share landed in the top k.
        total_relevant = source_counts[src]
        if total_relevant:
            recall_sum += sum(rels) / total_relevant

        # NDCG@k — reward relevant chunks, discounted by how low they sit.
        dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))
        ideal_hits = min(total_relevant, k)  # best case: relevant chunks fill the top
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
        if idcg:
            ndcg_sum += dcg / idcg

    n = len(queries)
    return {
        "hit@1": hit1 / n,
        "hit@3": hit3 / n,
        "mrr": rr_sum / n,
        "recall": recall_sum / n,
        "ndcg": ndcg_sum / n,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rerank", action="store_true", help="also evaluate hybrid+rerank"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="override chunk size (smaller => more chunks => harder retrieval)",
    )
    args = parser.parse_args()

    settings = get_settings()
    queries = _load_queries()
    chunk_size = args.chunk_size or settings.chunk_size
    print(f"Corpus: {settings.data_dir} | queries: {len(queries)} | chunk_size: {chunk_size}\n")

    # Build the corpus once and share the store across all retrievers.
    documents = load_documents(settings.data_dir)
    chunks = chunk_documents(
        documents,
        chunk_size=chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    embedder = build_embedder(settings)
    embeddings = embedder.encode([c.text for c in chunks])
    store = FaissVectorStore(dim=embedder.dim, index_type="flat")
    store.add(chunks, embeddings)
    # How many chunks each doc produced = size of its relevant set (for Recall/NDCG).
    source_counts = Counter(c.source for c in chunks)
    print(f"Indexed {store.size} chunks from {len(documents)} docs.\n")

    configs = {
        "dense": Retriever(embedder, store),
        "hybrid": HybridRetriever(
            embedder, store, candidate_k=settings.candidate_k, fusion_k=settings.fusion_k
        ),
    }
    if args.rerank:
        configs["hybrid+rerank"] = HybridRetriever(
            embedder,
            store,
            candidate_k=settings.candidate_k,
            fusion_k=settings.fusion_k,
            reranker=CrossEncoderReranker(settings.reranker_model),
        )

    hdr = f"{'config':<16}{'Hit@1':>8}{'Hit@3':>8}{'MRR':>8}{'R@'+str(_RANK_DEPTH):>8}{'NDCG@'+str(_RANK_DEPTH):>9}"
    print(hdr)
    print("-" * len(hdr))
    for name, retriever in configs.items():
        m = _score(retriever, queries, source_counts, _RANK_DEPTH)
        print(
            f"{name:<16}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}{m['mrr']:>8.3f}"
            f"{m['recall']:>8.2f}{m['ndcg']:>9.3f}"
        )


if __name__ == "__main__":
    main()
