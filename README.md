# RAG Haute Performance — Docling + Qdrant + Claude

Système RAG (Retrieval-Augmented Generation) de production combinant l'ingestion structurée Docling, la recherche hybride Qdrant (dense + sparse) avec reranking cross-encoder, et la génération Claude avec prompt caching. Backend FastAPI Python, frontend React + Vite TypeScript.

## Architecture

L'architecture complète, la structure du projet et les détails d'implémentation se trouvent dans [PROMPT_RAG.md](./PROMPT_RAG.md).

## Démarrage rapide

```bash
# 0. Configurer le .env unique (à la racine)
cp .env.example .env
# puis renseigner OPENROUTER_API_KEY (ou basculer sur ANTHROPIC_API_KEY)

# 1. Lancer Qdrant
docker-compose up -d qdrant

# 2. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Frontend
cd frontend
npm install
npm run dev
```

## Provider LLM

Par défaut le backend utilise **OpenRouter** via le SDK Anthropic ([guide officiel](https://openrouter.ai/docs/guides/community/anthropic-agent-sdk)). Pour basculer sur l'API Anthropic directe, mettre `LLM_PROVIDER=anthropic` dans le `.env` (le prompt caching n'est activé que dans ce mode).

Un seul `.env` à la racine est partagé par le backend Python et `docker-compose`.

## Stack

- Docling — conversion PDF/DOCX/HTML vers Markdown structuré
- Qdrant — base vectorielle avec recherche hybride dense + sparse (RRF)
- BGE-M3 — embeddings multilingues denses et sparse
- Cross-encoder ms-marco — reranking précis du top-K
- OpenRouter / Anthropic — génération via SDK Anthropic (provider configurable)
- FastAPI — backend Python avec streaming SSE
- React + Vite — frontend TypeScript (back office et front office)
