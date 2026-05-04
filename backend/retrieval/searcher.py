from pipeline.embeddings import embed_texts
from pipeline.indexer import client
from config import settings


def hybrid_search(query: str, top_k: int = 20) -> list[dict]:
    """Recherche dense cosinus dans Qdrant."""
    embeddings = embed_texts([query])
    dense_vec = embeddings["dense"][0]

    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=dense_vec,
        using="dense",
        limit=top_k,
        with_payload=True,
    )

    return [{"text": r.payload["text"], "metadata": r.payload, "score": r.score} for r in results.points]
