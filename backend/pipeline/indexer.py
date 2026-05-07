import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from config import settings
from pipeline.sparse_embeddings import embed_sparse

UPSERT_BATCH_SIZE = 256

client = QdrantClient(url=settings.qdrant_url)


def ensure_collection():
    """Crée la collection avec un index dense (cosinus) + un index sparse BM25.

    Pour une collection préexistante sans config sparse, on l'ajoute via update_collection :
    les anciens points n'auront que le vecteur dense (pas grave, RRF tolère ça), les nouveaux
    auront les deux.
    """
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={
                "dense": VectorParams(size=settings.vector_size, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(),
            },
        )
        return

    # Collection déjà présente : vérifie qu'elle a bien le sparse, sinon migre.
    info = client.get_collection(settings.qdrant_collection)
    has_sparse = bool(getattr(info.config.params, "sparse_vectors", None))
    if not has_sparse:
        client.update_collection(
            collection_name=settings.qdrant_collection,
            sparse_vectors_config={"sparse": SparseVectorParams()},
        )


def _build_points(
    chunks: list[dict],
    dense_vectors: list[list[float]],
    sparse_vectors: list[dict],
    doc_id: str,
    start_index: int,
) -> list[PointStruct]:
    points = []
    for i, (chunk, dense_vec, sparse) in enumerate(zip(chunks, dense_vectors, sparse_vectors)):
        vector = {
            "dense": dense_vec,
            "sparse": SparseVector(indices=sparse["indices"], values=sparse["values"]),
        }
        points.append(
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_OID, f"{doc_id}_{start_index + i}")),
                vector=vector,
                payload={**chunk["metadata"], "text": chunk["text"], "doc_id": doc_id},
            )
        )
    return points


def index_chunks(chunks: list[dict], embeddings: dict, doc_id: str, start_index: int = 0):
    """Insère les chunks par mini-lots avec vecteurs dense + sparse."""
    dense_vectors = embeddings["dense"]
    if not chunks:
        return

    # Calcul des sparse vectors localement (pas besoin de les passer entre couches : ils
    # dépendent uniquement du texte des chunks).
    sparse_vectors = embed_sparse([c["text"] for c in chunks])

    total = len(chunks)
    for offset in range(0, total, UPSERT_BATCH_SIZE):
        slice_chunks = chunks[offset:offset + UPSERT_BATCH_SIZE]
        slice_dense = dense_vectors[offset:offset + UPSERT_BATCH_SIZE]
        slice_sparse = sparse_vectors[offset:offset + UPSERT_BATCH_SIZE]
        points = _build_points(slice_chunks, slice_dense, slice_sparse, doc_id, start_index + offset)
        client.upsert(collection_name=settings.qdrant_collection, points=points)
