"""Central configuration — reads from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ContextForge configuration. All values read from environment."""

    model_config = SettingsConfigDict(
        env_prefix="CONTEXTFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── General ─────────────────────────────────────
    env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    auth_disabled: bool = True

    # ─── PostgreSQL ──────────────────────────────────
    postgres_uri: str = "postgresql://contextforge:changeme_postgres@localhost:5432/contextforge"
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="contextforge", alias="POSTGRES_USER")
    postgres_password: str = Field(default="changeme_postgres", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="contextforge", alias="POSTGRES_DB")

    # ─── TimescaleDB ────────────────────────────────
    timescale_host: str = Field(default="localhost", alias="TIMESCALE_HOST")
    timescale_port: int = Field(default=5433, alias="TIMESCALE_PORT")
    timescale_user: str = Field(default="contextforge", alias="TIMESCALE_USER")
    timescale_password: str = Field(default="changeme_timescale", alias="TIMESCALE_PASSWORD")
    timescale_db: str = Field(default="contextforge_ts", alias="TIMESCALE_DB")

    # ─── Neo4j ──────────────────────────────────────
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="changeme_neo4j", alias="NEO4J_PASSWORD")

    # ─── Qdrant ─────────────────────────────────────
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")

    # ─── Redis ──────────────────────────────────────
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str = Field(default="changeme_redis", alias="REDIS_PASSWORD")

    # ─── LiteLLM ────────────────────────────────────
    litellm_base_url: str = Field(default="http://localhost:4000", alias="LITELLM_BASE_URL")
    litellm_master_key: str = Field(default="sk-litellm-master-key", alias="LITELLM_MASTER_KEY")

    # ─── Langfuse ───────────────────────────────────
    langfuse_host: str = Field(default="http://localhost:3001", alias="LANGFUSE_HOST")
    langfuse_secret_key: str = Field(default="sk-lf-changeme", alias="LANGFUSE_SECRET_KEY")
    langfuse_public_key: str = Field(default="pk-lf-changeme", alias="LANGFUSE_PUBLIC_KEY")

    # ─── Embedding ──────────────────────────────────
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # ─── Reranker ───────────────────────────────────
    reranker: str = "cohere"  # cohere | bge-reranker-v2

    # ─── Budget Defaults ────────────────────────────
    max_tokens_per_run: int = 100_000
    max_cost_per_run_usd: float = 5.00
    max_iterations: int = 15
    max_tool_calls: int = 25

    # ─── Keycloak ───────────────────────────────────
    keycloak_issuer_url: str = Field(
        default="http://localhost:8180/realms/contextforge",
        alias="KEYCLOAK_ISSUER_URL",
    )
    keycloak_client_id: str = Field(default="contextforge-api", alias="KEYCLOAK_CLIENT_ID")

    @property
    def timescale_dsn(self) -> str:
        return (
            f"postgresql://{self.timescale_user}:{self.timescale_password}"
            f"@{self.timescale_host}:{self.timescale_port}/{self.timescale_db}"
        )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()
