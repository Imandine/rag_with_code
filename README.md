# RAG Haute Performance — Docling + Qdrant + Claude

Système RAG (Retrieval-Augmented Generation) combinant l'ingestion structurée Docling, la recherche hybride Qdrant (dense + BM25 + RRF) avec reranking cross-encoder multilingue, et la génération Claude avec mémoire conversationnelle. Backend FastAPI Python, frontend React + Vite TypeScript.

---

## Démarrage rapide (Docker Compose)

```bash
# 1. Copier et renseigner le fichier de configuration
cp .env.example .env
```

Ouvrir `.env` et renseigner au minimum :

| Variable | Obligatoire | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | ✅ | Clé API [OpenRouter](https://openrouter.ai) |
| `ADMIN_TOKEN` | ✅ prod / ⬜ dev | Jeton d'accès au back-office. Laisser vide pour désactiver l'auth en dev. Générer avec `openssl rand -hex 32` en prod. |
| `MINIO_SECRET_KEY` | ✅ | Mot de passe MinIO (changer la valeur par défaut en prod) |

```bash
# 2. Démarrer tous les services
docker compose up -d

# 3. Accéder à l'application
#   Frontend  → http://localhost:3000
#   API docs  → http://localhost:8000/docs
#   MinIO UI  → http://localhost:9001  (admin / MINIO_SECRET_KEY)
```

> **Premier démarrage** : Qdrant et MinIO créent leurs volumes au premier lancement.
> Les modèles HuggingFace (embeddings, BM25, reranker) sont téléchargés automatiquement
> dans le volume `hf_models` et mis en cache pour les redémarrages suivants.

---

## Démarrage en développement local (sans Docker)

```bash
# Prérequis : Qdrant et MinIO démarrés (via Docker ou standalone)
docker compose up -d qdrant minio

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (dans un autre terminal)
cd frontend
npm install
npm run dev        # → http://localhost:3000
```

Le proxy Vite (`vite.config.ts`) redirige automatiquement `/api/*` vers `http://localhost:8000`.

---

## Commandes Docker utiles

```bash
# Démarrer en arrière-plan
docker compose up -d

# Voir les logs en temps réel
docker compose logs -f backend

# Rebuild après modification du code
docker compose up -d --build backend
docker compose up -d --build frontend

# Arrêter tous les services
docker compose down

# Arrêter et supprimer les volumes (reset complet)
docker compose down -v
```

---

## Stack

| Composant | Rôle |
|---|---|
| **Docling** | Conversion PDF/DOCX/PPTX/XLSX/HTML/images → Markdown structuré + HybridChunker token-aware |
| **Qdrant** | Base vectorielle : index dense cosinus + index sparse BM25, fusion RRF |
| **paraphrase-multilingual-MiniLM-L12-v2** | Embeddings denses multilingues (384 dims) |
| **fastembed Qdrant/bm25** | Vecteurs sparse BM25 (lexical, stop-words FR) |
| **mmarco-mMiniLMv2-L12-H384-v1** | Reranker cross-encoder multilingue (14 langues) |
| **OpenRouter / Claude** | Génération avec mémoire conversationnelle et query rewriting |
| **FastAPI** | Backend Python, streaming SSE, auth par jeton |
| **React + Vite** | Frontend TypeScript, back-office admin, chat public |
| **MinIO** | Object storage (fichiers bruts + markdown) |
| **SQLite (WAL)** | Suivi des statuts d'indexation |
| **LibreOffice** | Conversion bureautique → PDF (dans le conteneur Docker) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  nginx :80                                               │
│    /api/* → proxy → backend:8000                        │
│    /*      → SPA React (dist statique)                  │
└─────────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
      ┌───────▼──────┐      ┌────────▼───────┐
      │  FastAPI      │      │   React + Vite  │
      │  backend:8000 │      │   (build nginx) │
      └───────┬───────┘      └────────────────┘
              │
     ┌────────┼────────┐
     │        │        │
  Qdrant   MinIO    SQLite
  :6333    :9000   /app/data/status.db
```

---

## Configuration complète

Voir [.env.example](.env.example) pour la liste de toutes les variables disponibles avec leurs valeurs par défaut et descriptions.
