# backend/tests/test_fail_analysis.py
from unittest.mock import patch

import pytest

from app.workflows.analysis.nodes.fail_analysis import fail_analysis

MODULE = "app.workflows.analysis.nodes.fail_analysis"


@pytest.mark.asyncio
async def test_marks_scan_failed_with_first_error_code():
    with patch(f"{MODULE}.scan_service.update_scan") as update_mock, patch(
        f"{MODULE}.scan_event_service.create_event"
    ) as event_mock:
        result = await fail_analysis({"scan_id": "s1", "errors": ["MISSING_CODE_CHUNKS"]})

    assert result == {"status": "failed"}
    update_mock.assert_called_once()
    assert update_mock.call_args.kwargs["status"] == "analysis_failed"
    assert update_mock.call_args.kwargs["error_code"] == "MISSING_CODE_CHUNKS"
    event_mock.assert_called_once()
    assert event_mock.call_args.args[1] == "analysis_failed"


@pytest.mark.asyncio
async def test_defaults_error_code_when_no_errors_present():
    with patch(f"{MODULE}.scan_service.update_scan") as update_mock, patch(
        f"{MODULE}.scan_event_service.create_event"
    ):
        await fail_analysis({"scan_id": "s1"})

    assert update_mock.call_args.kwargs["error_code"] == "ANALYSIS_FAILED"
