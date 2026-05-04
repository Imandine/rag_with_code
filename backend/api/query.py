from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from retrieval.searcher import hybrid_search
from retrieval.reranker import rerank
from generation.generator import generate_answer
from models.schemas import QueryRequest
import json

router = APIRouter(prefix="/query", tags=["query"])

@router.post("/")
async def query_rag(request: QueryRequest):
    candidates = hybrid_search(request.query, top_k=20)
    top_chunks = rerank(request.query, candidates)

    sources = [
        {
            "text": c["text"][:200],
            "metadata": c["metadata"],
            "score": c.get("rerank_score", 0)
        }
        for c in top_chunks
    ]

    async def event_stream():
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
        for token in generate_answer(request.query, top_chunks):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
