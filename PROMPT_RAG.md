# PROMPT : Construire le RAG le plus performant — Backend Python + Frontend React

## Vue d'ensemble

Tu vas construire un système RAG (Retrieval-Augmented Generation) de production, optimisé pour la précision et la vitesse. L'architecture se compose de :

- **Backend Python (FastAPI)** : pipeline d'ingestion via Docling, vectorisation dans Qdrant, recherche hybride, reranking, génération via Claude API
- **Frontend React (TypeScript)** : back office pour la gestion des documents, front office pour l'interface utilisateur de chat

---

## Architecture globale

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND React                        │
│  ┌─────────────────────┐    ┌──────────────────────────┐   │
│  │    Back Office       │    │      Front Office         │   │
│  │  - Upload documents  │    │  - Interface de chat      │   │
│  │  - Liste / delete    │    │  - Sources citées         │   │
│  │  - Statut traitement │    │  - Streaming des réponses │   │
│  └─────────────────────┘    └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                         FastAPI Backend
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                       │
   Docling Pipeline     Qdrant Vector DB        Claude API
  (PDF/DOCX/HTML→MD)   (dense + sparse)        (génération)
```

---

## Structure du projet

```
rag_project/
├── backend/
│   ├── main.py                    # Point d'entrée FastAPI
│   ├── config.py                  # Paramètres centralisés
│   ├── requirements.txt
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── ingestion.py           # Docling → texte structuré
│   │   ├── chunking.py            # Découpage sémantique
│   │   ├── embeddings.py          # Génération des embeddings
│   │   └── indexer.py             # Insertion dans Qdrant
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── searcher.py            # Recherche hybride dense+sparse
│   │   └── reranker.py            # Reranking cross-encoder
│   ├── generation/
│   │   ├── __init__.py
│   │   └── generator.py           # Claude API avec prompt caching
│   ├── api/
│   │   ├── __init__.py
│   │   ├── documents.py           # Routes CRUD documents
│   │   └── query.py               # Route RAG query
│   └── models/
│       ├── __init__.py
│       └── schemas.py             # Pydantic models
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── api/
│       │   ├── documents.ts       # Appels API back office
│       │   └── query.ts           # Appels API RAG
│       ├── components/
│       │   ├── backoffice/
│       │   │   ├── DocumentUpload.tsx
│       │   │   ├── DocumentList.tsx
│       │   │   └── ProcessingStatus.tsx
│       │   └── frontoffice/
│       │       ├── ChatInterface.tsx
│       │       ├── MessageBubble.tsx
│       │       ├── SourceCard.tsx
│       │       └── StreamingText.tsx
│       ├── hooks/
│       │   ├── useDocuments.ts
│       │   └── useChat.ts
│       └── types/
│           └── index.ts
├── docker-compose.yml             # Qdrant + backend + frontend
└── .env.example
```

---

## Backend — Implémentation détaillée

### 1. `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"
    vector_size: int = 1024  # BGE-M3

    # Embeddings
    embedding_model: str = "BAAI/bge-m3"  # multilingual, dense+sparse

    # Claude API
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"

    # RAG params (tuned for performance)
    top_k_dense: int = 20
    top_k_sparse: int = 20
    top_k_rerank: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 64

    class Config:
        env_file = ".env"

settings = Settings()
```

### 2. `pipeline/ingestion.py` — Docling

```python
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from pathlib import Path

def convert_document_to_markdown(file_path: str) -> dict:
    """
    Utilise Docling pour convertir tout type de document en Markdown structuré.
    Docling préserve la structure : titres, tableaux, listes, figures.
    """
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True            # OCR pour les PDFs scannés
    pipeline_options.do_table_structure = True # Extraction des tableaux

    converter = DocumentConverter()
    result = converter.convert(file_path)

    markdown_text = result.document.export_to_markdown()

    return {
        "text": markdown_text,
        "metadata": {
            "source": Path(file_path).name,
            "num_pages": getattr(result.document, "num_pages", None),
            "format": Path(file_path).suffix.lower()
        }
    }
```

### 3. `pipeline/chunking.py` — Découpage sémantique en deux passes

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

def semantic_chunk(text: str, metadata: dict, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """
    Découpe en deux passes :
    1. Par headers Markdown (respecte la structure du document Docling)
    2. RecursiveCharacterTextSplitter pour les sections trop grandes
    """
    headers_to_split_on = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    header_splits = md_splitter.split_text(text)

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", " "]
    )

    chunks = []
    for i, split in enumerate(char_splitter.split_documents(header_splits)):
        chunks.append({
            "text": split.page_content,
            "metadata": {
                **metadata,
                **split.metadata,  # headers Markdown hérités
                "chunk_index": i
            }
        })
    return chunks
```

### 4. `pipeline/embeddings.py` — BGE-M3 dense + sparse

```python
from FlagEmbedding import BGEM3FlagModel

_model = None

def get_model():
    global _model
    if _model is None:
        _model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    return _model

def embed_texts(texts: list[str]) -> dict:
    """
    BGE-M3 produit simultanément :
    - dense_vecs : embeddings denses (1024 dims)
    - lexical_weights : embeddings sparse (BM25-like)
    Les deux sont utilisés pour la recherche hybride dans Qdrant.
    """
    model = get_model()
    output = model.encode(
        texts,
        batch_size=12,
        max_length=512,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False
    )
    return {
        "dense": output["dense_vecs"].tolist(),
        "sparse": output["lexical_weights"]
    }
```

### 5. `pipeline/indexer.py` — Insertion dans Qdrant

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams,
    PointStruct, SparseVector
)
from config import settings

client = QdrantClient(url=settings.qdrant_url)

def ensure_collection():
    """Crée la collection Qdrant avec support dense + sparse (hybrid search)."""
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={"dense": VectorParams(size=settings.vector_size, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()}
        )

def index_chunks(chunks: list[dict], embeddings: dict, doc_id: str):
    """Insère les chunks avec vecteurs denses et sparse dans Qdrant."""
    points = []
    for i, (chunk, dense_vec, sparse_weights) in enumerate(
        zip(chunks, embeddings["dense"], embeddings["sparse"])
    ):
        sparse_indices = list(sparse_weights.keys())
        sparse_values = [float(sparse_weights[k]) for k in sparse_indices]

        points.append(PointStruct(
            id=f"{doc_id}_{i}",
            vector={
                "dense": dense_vec,
                "sparse": SparseVector(indices=sparse_indices, values=sparse_values)
            },
            payload={**chunk["metadata"], "text": chunk["text"], "doc_id": doc_id}
        ))

    client.upsert(collection_name=settings.qdrant_collection, points=points)
```

### 6. `retrieval/searcher.py` — Recherche hybride RRF

```python
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector, FusionQuery, Fusion
from pipeline.embeddings import embed_texts
from pipeline.indexer import client
from config import settings

def hybrid_search(query: str, top_k: int = 20) -> list[dict]:
    """
    Recherche hybride = dense + sparse fusionnés via RRF (Reciprocal Rank Fusion).
    Qdrant gère nativement la fusion RRF — aucune logique de fusion à écrire.
    """
    embeddings = embed_texts([query])
    dense_vec = embeddings["dense"][0]
    sparse_weights = embeddings["sparse"][0]
    sparse_indices = list(sparse_weights.keys())
    sparse_values = [float(sparse_weights[k]) for k in sparse_indices]

    results = client.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            {"query": dense_vec, "using": "dense", "limit": settings.top_k_dense},
            {"query": SparseVector(indices=sparse_indices, values=sparse_values), "using": "sparse", "limit": settings.top_k_sparse},
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True
    )

    return [{"text": r.payload["text"], "metadata": r.payload, "score": r.score} for r in results.points]
```

### 7. `retrieval/reranker.py` — Reranking cross-encoder

```python
from sentence_transformers import CrossEncoder

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
    return _reranker

def rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """
    Cross-encoder reranking : évalue chaque paire (query, chunk) individuellement.
    Bien plus précis que le cosine similarity seul pour le top final.
    """
    reranker = get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)

    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return [{"rerank_score": float(score), **doc} for doc, score in ranked[:top_k]]
```

### 8. `generation/generator.py` — Claude API avec prompt caching

```python
import anthropic
from config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """Tu es un assistant expert qui répond aux questions en te basant UNIQUEMENT sur les documents fournis.
Règles :
- Cite toujours les sources (nom du document, section)
- Si la réponse n'est pas dans les documents, dis-le clairement
- Sois précis et concis
- Réponds dans la langue de la question"""

def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"].get("source", "Document inconnu")
        section = chunk["metadata"].get("h1", chunk["metadata"].get("h2", ""))
        parts.append(f"[Source {i}: {source} — {section}]\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)

def generate_answer(query: str, chunks: list[dict]):
    """
    Génération streamée avec prompt caching sur le system prompt et le contexte.
    Le cache réduit la latence de ~50% et le coût de ~80% sur les requêtes répétées.
    """
    context = build_context(chunks)

    with client.messages.stream(
        model=settings.claude_model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Documents de référence :\n\n{context}",
                        "cache_control": {"type": "ephemeral"}
                    },
                    {"type": "text", "text": f"Question : {query}"}
                ]
            }
        ]
    ) as stream:
        for text in stream.text_stream:
            yield text
```

### 9. `api/documents.py` — Routes CRUD

```python
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from pipeline.ingestion import convert_document_to_markdown
from pipeline.chunking import semantic_chunk
from pipeline.embeddings import embed_texts
from pipeline.indexer import index_chunks, client as qdrant_client
from config import settings
import uuid, tempfile, os

router = APIRouter(prefix="/documents", tags=["documents"])

# En production : remplacer par Redis
processing_status: dict = {}

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    doc_id = str(uuid.uuid4())
    processing_status[doc_id] = {"status": "pending", "filename": file.filename, "doc_id": doc_id}

    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    background_tasks.add_task(process_document, doc_id, tmp_path, file.filename)
    return {"doc_id": doc_id, "status": "processing"}

async def process_document(doc_id: str, file_path: str, filename: str):
    try:
        processing_status[doc_id]["status"] = "converting"
        doc_data = convert_document_to_markdown(file_path)

        processing_status[doc_id]["status"] = "chunking"
        chunks = semantic_chunk(doc_data["text"], {**doc_data["metadata"], "doc_id": doc_id})

        processing_status[doc_id]["status"] = "embedding"
        embeddings = embed_texts([c["text"] for c in chunks])

        processing_status[doc_id]["status"] = "indexing"
        index_chunks(chunks, embeddings, doc_id)

        processing_status[doc_id] = {
            "status": "done", "filename": filename,
            "doc_id": doc_id, "chunks": len(chunks)
        }
    except Exception as e:
        processing_status[doc_id] = {"status": "error", "error": str(e), "doc_id": doc_id}
    finally:
        os.unlink(file_path)

@router.get("/")
def list_documents():
    return {"documents": list(processing_status.values())}

@router.get("/{doc_id}/status")
def get_status(doc_id: str):
    if doc_id not in processing_status:
        raise HTTPException(404, "Document not found")
    return processing_status[doc_id]

@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    qdrant_client.delete(
        collection_name=settings.qdrant_collection,
        points_selector={"filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]}}
    )
    processing_status.pop(doc_id, None)
    return {"status": "deleted"}
```

### 10. `api/query.py` — Route RAG streamée

```python
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
    top_chunks = rerank(request.query, candidates, top_k=5)

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
```

### 11. `models/schemas.py`

```python
from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str
```

### 12. `main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.documents import router as documents_router
from api.query import router as query_router
from pipeline.indexer import ensure_collection
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_collection()
    yield

app = FastAPI(title="RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(documents_router)
app.include_router(query_router)
```

### 13. `requirements.txt`

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
docling>=2.0.0
qdrant-client>=1.12.0
FlagEmbedding>=1.2.0
sentence-transformers>=3.3.0
langchain-text-splitters>=0.3.0
anthropic>=0.40.0
pydantic-settings>=2.0.0
python-multipart>=0.0.12
```

---

## Frontend — Implémentation détaillée

### Back Office — Gestion des documents

**`src/components/backoffice/DocumentUpload.tsx`**

```tsx
import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/html': ['.html'],
}

export function DocumentUpload({ onUpload }: { onUpload: () => void }) {
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback(async (files: File[]) => {
    setUploading(true)
    await Promise.all(
      files.map(async (file) => {
        const formData = new FormData()
        formData.append('file', file)
        await fetch('/api/documents/upload', { method: 'POST', body: formData })
      })
    )
    setUploading(false)
    onUpload()
  }, [onUpload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: ACCEPTED_TYPES })

  return (
    <div
      {...getRootProps()}
      style={{
        border: '2px dashed #ccc', borderRadius: 8, padding: 40,
        textAlign: 'center', cursor: 'pointer',
        background: isDragActive ? '#f0f4ff' : '#fafafa'
      }}
    >
      <input {...getInputProps()} />
      {uploading
        ? <p>Traitement en cours...</p>
        : <p>Glissez vos documents ici, ou cliquez pour sélectionner (PDF, DOCX, HTML)</p>
      }
    </div>
  )
}
```

**`src/hooks/useDocuments.ts`**

```tsx
import { useState, useEffect, useCallback } from 'react'

export function useDocuments() {
  const [documents, setDocuments] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    const res = await fetch('/api/documents/')
    const data = await res.json()
    setDocuments(data.documents)
    setLoading(false)
  }, [])

  const deleteDocument = async (docId: string) => {
    await fetch(`/api/documents/${docId}`, { method: 'DELETE' })
    refresh()
  }

  useEffect(() => { refresh() }, [refresh])

  // Polling pour les documents en cours de traitement
  useEffect(() => {
    const processing = documents.some(d => ['pending', 'converting', 'chunking', 'embedding', 'indexing'].includes(d.status))
    if (!processing) return
    const timer = setInterval(refresh, 2000)
    return () => clearInterval(timer)
  }, [documents, refresh])

  return { documents, deleteDocument, loading, refresh }
}
```

**`src/components/backoffice/DocumentList.tsx`**

```tsx
import { useDocuments } from '../../hooks/useDocuments'
import { DocumentUpload } from './DocumentUpload'

const STATUS_COLORS: Record<string, string> = {
  pending: '#999', converting: '#f90', chunking: '#f90',
  embedding: '#f90', indexing: '#f90', done: '#2a2', error: '#e33'
}

export function DocumentList() {
  const { documents, deleteDocument, refresh } = useDocuments()

  return (
    <div>
      <DocumentUpload onUpload={refresh} />
      <h3>Documents indexés</h3>
      {documents.map(doc => (
        <div key={doc.doc_id} style={{ display: 'flex', gap: 12, padding: 8, borderBottom: '1px solid #eee' }}>
          <span style={{ flex: 1 }}>{doc.filename}</span>
          <span style={{ color: STATUS_COLORS[doc.status] ?? '#666' }}>{doc.status}</span>
          {doc.chunks && <span style={{ color: '#666' }}>{doc.chunks} chunks</span>}
          {doc.status === 'done' && (
            <button onClick={() => deleteDocument(doc.doc_id)}>Supprimer</button>
          )}
        </div>
      ))}
    </div>
  )
}
```

### Front Office — Interface de chat

**`src/hooks/useChat.ts`**

```tsx
import { useState } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{ text: string; metadata: Record<string, any>; score: number }>
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  const sendQuery = async (query: string) => {
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: query }])
    setMessages(prev => [...prev, { role: 'assistant', content: '', sources: [] }])

    const response = await fetch('/api/query/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    })

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const lines = decoder.decode(value).split('\n')
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'sources') {
            setMessages(prev => {
              const msgs = [...prev]
              msgs[msgs.length - 1].sources = data.sources
              return msgs
            })
          } else if (data.type === 'token') {
            setMessages(prev => {
              const msgs = [...prev]
              msgs[msgs.length - 1].content += data.content
              return msgs
            })
          }
        } catch {}
      }
    }
    setLoading(false)
  }

  return { messages, sendQuery, loading }
}
```

**`src/components/frontoffice/ChatInterface.tsx`**

```tsx
import { useState, useRef, useEffect } from 'react'
import { useChat } from '../../hooks/useChat'

export function ChatInterface() {
  const [input, setInput] = useState('')
  const { messages, sendQuery, loading } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    sendQuery(input.trim())
    setInput('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 16 }}>
            <div style={{
              background: msg.role === 'user' ? '#e8f0fe' : '#fff',
              border: '1px solid #ddd', borderRadius: 8, padding: 12
            }}>
              <strong>{msg.role === 'user' ? 'Vous' : 'Assistant'}</strong>
              <p style={{ margin: '8px 0 0', whiteSpace: 'pre-wrap' }}>{msg.content}</p>
            </div>
            {msg.sources && msg.sources.length > 0 && (
              <div style={{ marginTop: 8, paddingLeft: 8, borderLeft: '3px solid #4285f4' }}>
                <small style={{ color: '#666' }}>Sources :</small>
                {msg.sources.map((src, j) => (
                  <div key={j} style={{ fontSize: 12, color: '#555', marginTop: 4 }}>
                    <strong>{src.metadata.source}</strong>
                    {src.metadata.h1 && ` — ${src.metadata.h1}`}
                    <span style={{ color: '#4285f4', marginLeft: 8 }}>
                      score: {src.score.toFixed(3)}
                    </span>
                    <p style={{ margin: '2px 0', color: '#777' }}>{src.text}…</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8, padding: 16, borderTop: '1px solid #eee' }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Posez votre question sur les documents..."
          disabled={loading}
          style={{ flex: 1, padding: 10, borderRadius: 6, border: '1px solid #ccc' }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{ padding: '10px 20px', borderRadius: 6, background: '#4285f4', color: '#fff', border: 'none' }}
        >
          {loading ? '...' : 'Envoyer'}
        </button>
      </form>
    </div>
  )
}
```

**`src/App.tsx`** — Navigation Back office / Front office

```tsx
import { useState } from 'react'
import { DocumentList } from './components/backoffice/DocumentList'
import { ChatInterface } from './components/frontoffice/ChatInterface'

export default function App() {
  const [view, setView] = useState<'backoffice' | 'frontoffice'>('frontoffice')

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif' }}>
      <nav style={{ background: '#1a1a2e', color: '#fff', display: 'flex', gap: 16, padding: '12px 24px' }}>
        <span style={{ fontWeight: 700, marginRight: 'auto' }}>RAG Haute Performance</span>
        <button
          onClick={() => setView('frontoffice')}
          style={{ background: view === 'frontoffice' ? '#4285f4' : 'transparent', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 4, cursor: 'pointer' }}
        >
          Chat
        </button>
        <button
          onClick={() => setView('backoffice')}
          style={{ background: view === 'backoffice' ? '#4285f4' : 'transparent', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 4, cursor: 'pointer' }}
        >
          Gestion documents
        </button>
      </nav>

      <main style={{ maxWidth: 900, margin: '0 auto', padding: 24 }}>
        {view === 'frontoffice' ? <ChatInterface /> : <DocumentList />}
      </main>
    </div>
  )
}
```

---

## Docker Compose

```yaml
version: '3.9'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - qdrant
    volumes:
      - ./backend:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000

volumes:
  qdrant_data:
```

---

## Variables d'environnement — `.env.example`

```
ANTHROPIC_API_KEY=sk-ant-...
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=documents
CLAUDE_MODEL=claude-sonnet-4-6
```

---

## Optimisations clés pour la performance maximale

| Composant | Choix technique | Raison |
|---|---|---|
| **Embeddings** | BGE-M3 (BAAI) | SOTA multilingue, produit dense + sparse en un seul passage |
| **Recherche** | Hybrid RRF dans Qdrant | Combine rappel sémantique (dense) et précision lexicale (sparse) |
| **Reranking** | Cross-encoder ms-marco | Réévalue 20 candidats → top 5 avec pertinence fine |
| **Chunking** | Markdown headers + RecursiveCharacterTextSplitter | Respecte la structure Docling, évite de couper au milieu d'une idée |
| **Génération** | Claude API + prompt caching | Cache system prompt + contexte → -80% coût, -50% latence |
| **UX** | Streaming SSE | Sources affichées avant la réponse, tokens en temps réel |
| **Inférence** | BGE-M3 fp16 | Moitié moins de VRAM, qualité identique |

---

## Vérification end-to-end

```bash
# 1. Démarrer Qdrant
docker-compose up -d qdrant

# 2. Démarrer le backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Démarrer le frontend
cd frontend
npm install
npm run dev

# 4. Tests
# - Aller sur http://localhost:3000 → onglet "Gestion documents"
# - Uploader un PDF → vérifier que le statut passe à "done"
# - Aller sur l'onglet "Chat" → poser une question sur le document
# - Vérifier : sources affichées avec scores, réponse streamée, citations correctes
# - Vérifier les vecteurs dans Qdrant dashboard : http://localhost:6333/dashboard
```
