from sentence_transformers import CrossEncoder

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
    return _reranker

def rerank(
    query: str,
    candidates: list[dict],
    max_k: int = 8,
    min_k: int = 1,
    score_drop: float = 3.0,
) -> list[dict]:
    """
    Cross-encoder reranking : évalue chaque paire (query, chunk).
    Sélection dynamique : on garde les chunks dont le score est proche du meilleur
    (best - score_drop), bornée par [min_k, max_k]. Évite de forcer 5 sources
    quand 1 ou 2 suffisent — ou d'en couper quand plusieurs sont pertinentes.
    """
    if not candidates:
        return []

    reranker = get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)

    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    best = float(ranked[0][1])
    threshold = best - score_drop

    selected = [
        {"rerank_score": float(score), **doc}
        for doc, score in ranked
        if float(score) >= threshold
    ]
    if len(selected) < min_k:
        selected = [{"rerank_score": float(s), **d} for d, s in ranked[:min_k]]
    return selected[:max_k]
