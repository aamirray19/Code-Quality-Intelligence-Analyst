from unittest.mock import patch

import pytest

from app.workflows.analysis.nodes.mark_scan_analyzed import mark_scan_analyzed

MODULE = "app.workflows.analysis.nodes.mark_scan_analyzed"


@pytest.mark.asyncio
async def test_marks_scan_status_analyzed_and_logs_event():
    with patch(f"{MODULE}.scan_service.update_scan") as update_mock, patch(
        f"{MODULE}.scan_event_service.create_event"
    ) as event_mock:
        result = await mark_scan_analyzed({"scan_id": "scan-1"})

    assert result == {"status": "analyzed"}
    assert update_mock.call_args.kwargs["status"] == "analyzed"
    assert event_mock.call_args.args[1] == "analysis_completed"
