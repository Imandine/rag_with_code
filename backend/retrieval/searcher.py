from qdrant_client.models import (
    Fusion,
    FusionQuery,
    Prefetch,
    SparseVector,
)

from config import settings
from pipeline.embeddings import embed_texts
from pipeline.indexer import client
from pipeline.sparse_embeddings import embed_sparse_query


def hybrid_search(query: str, top_k: int = 20, candidate_pool: int = 40) -> list[dict]:
    """Recherche hybride dense + BM25 fusionnée par RRF côté Qdrant.

    `candidate_pool` : nombre de candidats récupérés par chaque branche avant fusion. Plus
    large que `top_k` pour donner de la marge au rerank en aval.
    """
    dense = embed_texts([query])["dense"][0]
    sparse_raw = embed_sparse_query(query)

    prefetch = [
        Prefetch(query=dense, using="dense", limit=candidate_pool),
    ]
    if sparse_raw["indices"]:
        prefetch.append(
            Prefetch(
                query=SparseVector(
                    indices=sparse_raw["indices"],
                    values=sparse_raw["values"],
                ),
                using="sparse",
                limit=candidate_pool,
            )
        )

    results = client.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=prefetch,
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )

    return [
        {"text": r.payload["text"], "metadata": r.payload, "score": r.score}
        for r in results.points
    ]
