import json
from uuid import uuid4

import httpx
import pytest
import respx

from app.schemas.finding import FindingRecord
from app.schemas.report import ReportMetrics
from app.services.report_builder_service import build_report_markdown


@pytest.mark.asyncio
@respx.mock
async def test_build_report_markdown_returns_mocked_response(monkeypatch):
    """Test that build_report_markdown calls Google AI and returns its response."""
    from app.core.config import settings
    
    # Set a test API key
    monkeypatch.setattr(settings, "google_api_key_chatbot", "test-chatbot-key")
    
    mock_markdown = "# Security Report\n\nFindings summary here..."
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"candidates": [{"content": {"role": "model", "parts": [{"text": mock_markdown}]}}]},
        )
    )
    
    scan_id = uuid4()
    findings = [
        FindingRecord(
            scan_id=scan_id,
            agent="security",
            title="SQL Injection vulnerability",
            description="User input is directly concatenated into SQL query",
            severity="critical",
            confidence=0.95,
            file_path="src/db/users.py",
            fingerprint="sql_inj_001",
        )
    ]
    metrics = ReportMetrics(
        total_findings=1,
        by_severity={"critical": 1},
        by_agent={"security": 1},
        files_affected=1,
    )
    risk_score = 85.5
    repo_url = "https://github.com/test/repo"
    
    result = await build_report_markdown(findings, metrics, risk_score, repo_url)
    
    assert result == mock_markdown
    
    # Verify the request was made and contains the input data
    assert route.called
    request = route.calls.last.request
    request_body = json.loads(request.content)
    
    # Verify the prompt includes our data
    all_content = request_body["systemInstruction"]["parts"][0]["text"] + " " + " ".join(
        p["text"] for c in request_body["contents"] for p in c["parts"]
    )
    assert "SQL Injection vulnerability" in all_content
    assert repo_url in all_content
    assert "85.5" in all_content or "85" in all_content  # Allow for different number formatting


@pytest.mark.asyncio
@respx.mock
async def test_build_report_markdown_includes_top_20_findings_only(monkeypatch):
    """Test that when >20 findings exist, only the top 20 are included in the prompt."""
    from app.core.config import settings
    
    # Set a test API key
    monkeypatch.setattr(settings, "google_api_key_chatbot", "test-chatbot-key")
    
    mock_markdown = "# Report with many findings"
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"candidates": [{"content": {"role": "model", "parts": [{"text": mock_markdown}]}}]},
        )
    )
    
    scan_id = uuid4()
    # Create 25 findings
    findings = [
        FindingRecord(
            scan_id=scan_id,
            agent="security",
            title=f"Finding {i}",
            description=f"Description for finding {i}",
            severity="high" if i < 10 else "medium",
            confidence=0.9 - (i * 0.01),
            file_path=f"src/file{i}.py",
            fingerprint=f"finding_{i}",
        )
        for i in range(25)
    ]
    metrics = ReportMetrics(
        total_findings=25,
        by_severity={"high": 10, "medium": 15},
        by_agent={"security": 25},
        files_affected=25,
    )
    risk_score = 75.0
    repo_url = "https://github.com/test/large-repo"
    
    result = await build_report_markdown(findings, metrics, risk_score, repo_url)
    
    assert result == mock_markdown
    
    # Verify the request includes the top 20 findings but not the rest
    request = route.calls.last.request
    request_body = json.loads(request.content)
    all_content = request_body["systemInstruction"]["parts"][0]["text"] + " " + " ".join(
        p["text"] for c in request_body["contents"] for p in c["parts"]
    )
    
    # Should include findings 0-19
    assert "Finding 0" in all_content
    assert "Finding 19" in all_content
    
    # Should NOT include findings 20-24
    assert "Finding 20" not in all_content
    assert "Finding 21" not in all_content
    assert "Finding 24" not in all_content


@pytest.mark.asyncio
@respx.mock
async def test_build_report_markdown_with_fewer_than_20_findings(monkeypatch):
    """Test that when <20 findings exist, all are included in the prompt."""
    from app.core.config import settings
    
    # Set a test API key
    monkeypatch.setattr(settings, "google_api_key_chatbot", "test-chatbot-key")
    
    mock_markdown = "# Small Report"
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"candidates": [{"content": {"role": "model", "parts": [{"text": mock_markdown}]}}]},
        )
    )
    
    scan_id = uuid4()
    # Create only 5 findings
    findings = [
        FindingRecord(
            scan_id=scan_id,
            agent="performance",
            title=f"Performance Issue {i}",
            description=f"Slow operation in function {i}",
            severity="medium",
            confidence=0.85,
            file_path=f"src/perf{i}.py",
            fingerprint=f"perf_{i}",
        )
        for i in range(5)
    ]
    metrics = ReportMetrics(
        total_findings=5,
        by_severity={"medium": 5},
        by_agent={"performance": 5},
        files_affected=5,
    )
    risk_score = 45.0
    repo_url = "https://github.com/test/small-repo"
    
    result = await build_report_markdown(findings, metrics, risk_score, repo_url)
    
    assert result == mock_markdown
    
    # Verify all 5 findings are in the request
    request = route.calls.last.request
    request_body = json.loads(request.content)
    all_content = request_body["systemInstruction"]["parts"][0]["text"] + " " + " ".join(
        p["text"] for c in request_body["contents"] for p in c["parts"]
    )
    
    # All findings should be present
    for i in range(5):
        assert f"Performance Issue {i}" in all_content
