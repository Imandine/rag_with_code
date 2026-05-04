import os
import tempfile
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from config import settings
from pipeline.chunking import semantic_chunk
from qdrant_client.models import Filter, FieldCondition, MatchValue
from pipeline.embeddings import embed_texts
from pipeline.indexer import client as qdrant_client, index_chunks
from pipeline.ingestion import convert_document_to_markdown
from storage import minio_client, status_store

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    doc_id = str(uuid.uuid4())
    data = await file.read()
    raw_key = minio_client.put_raw(doc_id, file.filename, data, file.content_type)

    status_store.set_status(
        doc_id,
        filename=file.filename,
        raw_key=raw_key,
        status="uploaded",
        uploaded_at=datetime.now(timezone.utc).isoformat(),
    )

    background_tasks.add_task(process_document, doc_id, raw_key, file.filename)
    return {"doc_id": doc_id, "status": "uploaded"}


def process_document(doc_id: str, raw_key: str, filename: str):
    tmp_path = None
    try:
        status_store.set_status(doc_id, status="converting")
        raw_bytes = minio_client.get_raw(raw_key)
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        doc_data = convert_document_to_markdown(tmp_path)
        meta = doc_data["metadata"]
        meta["source"] = filename  # nom d'origine, pas le chemin tmp
        markdown = doc_data["text"]

        markdown_key = minio_client.put_markdown(doc_id, filename, markdown)
        # Le raw n'est plus nécessaire une fois le markdown produit
        minio_client.delete_raw(doc_id)
        status_store.set_status(
            doc_id,
            status="markdown_stored",
            markdown_key=markdown_key,
            raw_key=None,
            num_pages=meta.get("num_pages"),
            num_words=meta.get("num_words"),
            format=meta.get("format"),
        )

        status_store.set_status(doc_id, status="chunking")
        chunks = semantic_chunk(markdown, {**meta, "doc_id": doc_id})
        status_store.set_status(doc_id, chunks=len(chunks))

        status_store.set_status(doc_id, status="embedding")
        embeddings = embed_texts([c["text"] for c in chunks])

        status_store.set_status(doc_id, status="indexing")
        index_chunks(chunks, embeddings, doc_id)

        # Le markdown reste conservé pour visualisation post-indexation
        status_store.set_status(doc_id, status="done")
    except Exception as e:
        status_store.set_status(doc_id, status="error", error=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/")
def list_documents():
    docs = sorted(
        status_store.list_all(),
        key=lambda d: d.get("uploaded_at", ""),
        reverse=True,
    )
    return {"documents": docs}


@router.get("/{doc_id}/status")
def get_status(doc_id: str):
    entry = status_store.get_status(doc_id)
    if not entry:
        raise HTTPException(404, "Document not found")
    return entry


@router.get("/{doc_id}/markdown", response_class=PlainTextResponse)
def get_markdown(doc_id: str):
    try:
        return minio_client.get_markdown(doc_id)
    except Exception:
        raise HTTPException(404, "Markdown not found")


@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    qdrant_client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )
    minio_client.delete_doc(doc_id)
    status_store.delete(doc_id)
    return {"status": "deleted"}
