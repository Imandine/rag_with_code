from pathlib import Path
from pydantic_settings import BaseSettings

# Un seul .env partagé à la racine du projet (parent du dossier backend)
ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"
    vector_size: int = 384  # paraphrase-multilingual-MiniLM-L12-v2

    # Embeddings
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # OpenRouter
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-sonnet-4.5"
    openrouter_referer: str | None = None
    openrouter_app_name: str | None = None

    # RAG params
    top_k_dense: int = 20
    top_k_rerank: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 64

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_raw_bucket: str = "raw-documents"
    minio_markdown_bucket: str = "markdown-documents"

    # Status store
    status_db_path: str = "/app/data/status.db"

    # Auth — un jeton partagé donne accès au back-office (upload, suppression, retry).
    # Si vide, l'authentification est désactivée (pratique en dev) et tous les endpoints
    # admin sont ouverts. En prod, définir ADMIN_TOKEN dans le .env.
    admin_token: str | None = None

    class Config:
        env_file = str(ROOT_ENV)
        extra = "ignore"


settings = Settings()
