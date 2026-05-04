from sentence_transformers import SentenceTransformer
from config import settings

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: list[str]) -> dict:
    """Embeddings denses multilingues (384 dims). Le modèle est mis en cache en mémoire."""
    model = get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return {"dense": vecs.tolist()}
