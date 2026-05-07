import gc
import os
import tempfile
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from auth import require_admin
from config import settings
from pipeline.chunking import semantic_chunk
from pipeline.docling_chunker import chunk_docling_document
from qdrant_client.models import Filter, FieldCondition, MatchValue
from pipeline.embeddings import embed_texts
from pipeline.indexer import client as qdrant_client, index_chunks
from pipeline.ingestion import iter_document_batches
from storage import minio_client, status_store

# Toute la gestion documentaire est admin-only : seul le chat (/query) reste public.
router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(require_admin)])


class BatchDeleteRequest(BaseModel):
    doc_ids: list[str]


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
        raw_bytes = minio_client.get_raw(raw_key)
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        status_store.set_status(
            doc_id,
            status="converting",
            pages_done=0,
            chunks=0,
        )

        markdown_parts: list[str] = []
        total_chunks = 0
        doc_format = suffix.lower()
        total_pages: int | None = None
        ocr_used: bool | None = None

        for batch in iter_document_batches(tmp_path):
            md = batch["markdown"]
            document = batch.get("document")
            page_start = batch["page_start"]
            page_end = batch["page_end"]
            total_pages = batch["total_pages"]
            doc_format = batch["format"]
            ocr_used = batch["ocr_used"]

            markdown_parts.append(md)

            status_store.set_status(
                doc_id,
                status="chunking",
                pages_done=page_end,
                num_pages=total_pages,
                ocr_used=ocr_used,
                format=doc_format,
            )

            batch_meta = {
                "doc_id": doc_id,
                "source": filename,
                "page_start": page_start,
                "page_end": page_end,
            }

            # Stratégie : si Docling a produit un document structuré, on utilise le
            # HybridChunker (frontières structurelles + token-aware). Sinon (txt/md bruts)
            # on retombe sur le découpage par headers + caractères.
            if document is not None:
                try:
                    chunks = chunk_docling_document(
                        document, batch_meta, chunk_index_offset=total_chunks
                    )
                except Exception:
                    # Fallback robuste : si HybridChunker bute sur un doc atypique,
                    # on continue sur le markdown plutôt que d'échouer toute l'indexation.
                    chunks = semantic_chunk(md, batch_meta, chunk_index_offset=total_chunks)
            else:
                chunks = semantic_chunk(md, batch_meta, chunk_index_offset=total_chunks)

            if not chunks:
                continue

            status_store.set_status(doc_id, status="embedding", pages_done=page_end)
            embeddings = embed_texts([c["text"] for c in chunks])

            status_store.set_status(doc_id, status="indexing", pages_done=page_end)
            index_chunks(chunks, embeddings, doc_id, start_index=total_chunks)

            total_chunks += len(chunks)
            status_store.set_status(doc_id, chunks=total_chunks)
            del chunks, embeddings, batch, document
            gc.collect()

        full_markdown = "\n\n".join(markdown_parts)
        markdown_key = minio_client.put_markdown(doc_id, filename, full_markdown)
        minio_client.delete_raw(doc_id)

        status_store.set_status(
            doc_id,
            status="done",
            markdown_key=markdown_key,
            raw_key=None,
            num_pages=total_pages,
            num_words=len(full_markdown.split()),
            format=doc_format,
            chunks=total_chunks,
            pages_done=total_pages,
            ocr_used=ocr_used,
        )
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


def _delete_one(doc_id: str) -> None:
    qdrant_client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )
    minio_client.delete_doc(doc_id)
    status_store.delete(doc_id)


@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    _delete_one(doc_id)
    return {"status": "deleted"}


@router.post("/batch-delete")
def batch_delete_documents(payload: BatchDeleteRequest):
    """Supprime plusieurs documents en une seule requête. Ignore silencieusement les
    docs introuvables ; renvoie la liste des IDs réellement supprimés."""
    deleted: list[str] = []
    failed: list[dict] = []
    for doc_id in payload.doc_ids:
        try:
            _delete_one(doc_id)
            deleted.append(doc_id)
        except Exception as e:
            failed.append({"doc_id": doc_id, "error": str(e)})
    return {"deleted": deleted, "failed": failed, "count": len(deleted)}


@router.post("/{doc_id}/retry")
def retry_document(doc_id: str, background_tasks: BackgroundTasks):
    entry = status_store.get_status(doc_id)
    if not entry:
        raise HTTPException(404, "Document not found")
    if entry.get("status") not in {"error", "done"}:
        raise HTTPException(409, f"Document is currently being processed (status={entry.get('status')})")

    raw_key = entry.get("raw_key")
    filename = entry.get("filename")
    if not filename:
        raise HTTPException(400, "Document is missing its filename")

    # Si le raw a été supprimé (cas d'un doc 'done' qu'on veut réindexer), on tente de le reconstruire
    # depuis le markdown stocké. Sinon on demande un nouveau téléversement.
    if not raw_key:
        raise HTTPException(
            400,
            "Le fichier source n'est plus disponible (raw supprimé après indexation). "
            "Supprimez le document et téléversez-le à nouveau pour le réindexer.",
        )

    # Nettoyage des chunks partiellement indexés pour éviter les doublons
    qdrant_client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
    )

    status_store.set_status(
        doc_id,
        status="uploaded",
        error=None,
        chunks=0,
        pages_done=0,
        retried_at=datetime.now(timezone.utc).isoformat(),
    )

    background_tasks.add_task(process_document, doc_id, raw_key, filename)
    return {"doc_id": doc_id, "status": "retrying"}
