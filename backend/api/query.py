from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from retrieval.searcher import hybrid_search
from retrieval.reranker import rerank
from generation.generator import generate_answer, rewrite_query
from models.schemas import QueryRequest
import json

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/")
async def query_rag(request: QueryRequest):
    # Rewriting LLM : "Et le prix ?" → "Quel est le prix de la directive UEMOA mentionnée ?"
    # Sans historique, c'est un no-op (pas d'appel LLM, latence inchangée).
    search_query = rewrite_query(request.query, request.history)

    candidates = hybrid_search(search_query, top_k=20)
    top_chunks = rerank(search_query, candidates)

    sources = [
        {
            "text": c["text"][:200],
            "metadata": c["metadata"],
            "score": c.get("rerank_score", 0)
        }
        for c in top_chunks
    ]

    async def event_stream():
        # On expose la requête réécrite pour debug côté client (badge UI optionnel)
        if search_query != request.query:
            yield f"data: {json.dumps({'type': 'rewrite', 'query': search_query})}\n\n"
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
        for token in generate_answer(request.query, top_chunks, history=request.history):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
