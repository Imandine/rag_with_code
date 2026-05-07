from sentence_transformers import SentenceTransformer
from config import settings

_model: SentenceTransformer | None = None

EMBED_BATCH_SIZE = 64


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: list[str], batch_size: int = EMBED_BATCH_SIZE) -> dict:
    """Embeddings denses multilingues. Encodage par mini-lots pour borner la mémoire."""
    model = get_model()
    if not texts:
        return {"dense": []}
    vecs = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return {"dense": vecs.tolist()}
