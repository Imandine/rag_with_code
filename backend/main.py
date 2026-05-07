from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.auth import router as auth_router
from api.documents import router as documents_router
from api.query import router as query_router
from pipeline.indexer import ensure_collection
from storage.minio_client import ensure_buckets
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_collection()
    ensure_buckets()
    yield

app = FastAPI(title="RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(query_router)
