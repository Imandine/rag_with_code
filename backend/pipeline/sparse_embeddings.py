from fastembed import SparseTextEmbedding

# BM25 lexical : indispensable en complément du dense pour les requêtes exactes
# (noms propres, codes douaniers, références d'articles, sigles UEMOA/CEDEAO).
# Tokenizer multilingue, stop-words FR — la langue principale du corpus.
SPARSE_MODEL_NAME = "Qdrant/bm25"
SPARSE_LANGUAGE = "french"

_model: SparseTextEmbedding | None = None


def get_sparse_model() -> SparseTextEmbedding:
    global _model
    if _model is None:
        _model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME, language=SPARSE_LANGUAGE)
    return _model


def embed_sparse(texts: list[str]) -> list[dict]:
    """Retourne une liste de dicts {indices, values} compatibles avec qdrant SparseVector."""
    if not texts:
        return []
    model = get_sparse_model()
    out = []
    for emb in model.embed(texts):
        out.append({
            "indices": emb.indices.tolist(),
            "values": [float(v) for v in emb.values],
        })
    return out


def embed_sparse_query(text: str) -> dict:
    """Variante optimisée pour la requête (ne calcule pas l'IDF, juste TF + tokens)."""
    if not text:
        return {"indices": [], "values": []}
    model = get_sparse_model()
    # Pour la requête, fastembed expose query_embed qui produit un encodage adapté.
    emb = next(iter(model.query_embed([text])))
    return {
        "indices": emb.indices.tolist(),
        "values": [float(v) for v in emb.values],
    }
