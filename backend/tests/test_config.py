import os


def test_settings_loads_required_fields(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    from app.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.max_repo_size_kb == 51200
    assert settings.redis_queue_name == "repo_scan_queue"
    assert settings.frontend_url == "http://localhost:8080"


def test_settings_loads_phase_4_fields(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENROUTER_API_KEY_CHATBOT", "chatbot-key-123")
    monkeypatch.setenv("QDRANT_COLLECTION_AGENT_FINDINGS", "agent_findings_test")
    monkeypatch.setenv("QDRANT_COLLECTION_SCAN_REPORTS", "scan_reports_test")

    from app.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.openrouter_api_key_chatbot == "chatbot-key-123"
    assert settings.qdrant_collection_agent_findings == "agent_findings_test"
    assert settings.qdrant_collection_scan_reports == "scan_reports_test"
