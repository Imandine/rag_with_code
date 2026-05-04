import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from config import settings

client = QdrantClient(url=settings.qdrant_url)


def ensure_collection():
    """Crée la collection Qdrant avec un index dense cosinus."""
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={"dense": VectorParams(size=settings.vector_size, distance=Distance.COSINE)},
        )


def index_chunks(chunks: list[dict], embeddings: dict, doc_id: str):
    """Insère les chunks avec vecteurs denses dans Qdrant."""
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_OID, f"{doc_id}_{i}")),
            vector={"dense": dense_vec},
            payload={**chunk["metadata"], "text": chunk["text"], "doc_id": doc_id},
        )
        for i, (chunk, dense_vec) in enumerate(zip(chunks, embeddings["dense"]))
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points)
