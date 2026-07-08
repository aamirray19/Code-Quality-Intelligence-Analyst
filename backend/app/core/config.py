from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_base_url: str = "http://localhost:8000"

    github_token: str | None = None
    max_repo_size_kb: int = 51200

    supabase_url: str
    supabase_service_role_key: str

    redis_url: str
    redis_queue_name: str = "repo_scan_queue"

    frontend_url: str = "http://localhost:8080"

    # Phase 2: repo cloning / file discovery
    repo_workspace_root: str = "/tmp/cqia/scans"
    git_clone_timeout_seconds: int = 120
    max_file_size_bytes: int = 500_000
    max_total_files: int = 5000

    # Phase 2: Qdrant Cloud
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection_code_chunks: str = "code_chunks"

    # Phase 2: Neo4j Aura
    neo4j_uri: str | None = None
    neo4j_username: str | None = None
    neo4j_password: str | None = None
    neo4j_database: str = "neo4j"

    # Phase 2: embeddings (BAAI/bge-large-en-v1.5 via HuggingFace Inference API)
    embedding_provider: str = "huggingface"
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    hf_api_token: str | None = None

    # Phase 2: worker
    worker_concurrency: int = 2

    # Phase 3: OpenRouter LLM client
    agent_llm_provider: str = "openrouter"
    agent_llm_model: str = "deepseek/deepseek-chat-v3-0324"
    openrouter_api_key_supervisor: str | None = None
    openrouter_api_key_security: str | None = None
    openrouter_api_key_performance: str | None = None
    openrouter_api_key_complexity: str | None = None
    openrouter_api_key_duplication: str | None = None
    openrouter_api_key_reliability: str | None = None
    agent_max_retries: int = 2
    agent_timeout_seconds: int = 120
    langgraph_recursion_limit: int = 50
    max_agent_context_chunks: int = 12
    max_findings_per_agent: int = 20

    # Phase 4: Report generation & RAG chatbot
    openrouter_api_key_chatbot: str | None = None
    qdrant_collection_agent_findings: str = "agent_findings"
    qdrant_collection_scan_reports: str = "scan_reports"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
