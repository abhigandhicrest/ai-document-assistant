"""Application settings.

Values come from environment variables or python-ai/.env. Defaults are safe
for local development, and blank LLM settings do not stop the service from
starting. The health check never needs an API key or an embedding model.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# python-ai/ directory, so relative storage paths stay inside this project.
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Typed view of the environment variables used by this service."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8001
    allowed_origins: str = ""

    upload_dir: str = "storage/uploads"
    max_upload_size_mb: int = 10

    chunk_size: int = 800
    chunk_overlap: int = 120

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    chroma_persist_dir: str = "storage/chroma"
    metadata_db_path: str = "storage/metadata/documents.db"

    laravel_storage_dir: str = "../storage/app/private"
    top_k: int = 4

    llm_provider: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: int = 45

    api_token: str = ""

    def path_inside_project(self, configured_path: str) -> Path:
        """Resolve a storage path relative to python-ai/, unless it is already absolute."""
        path = Path(configured_path)
        if path.is_absolute():
            return path
        return BASE_DIR / path


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them for the life of the process."""
    return Settings()
