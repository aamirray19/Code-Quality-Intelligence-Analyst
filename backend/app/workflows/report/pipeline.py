"""Report generation pipeline orchestrator.

Orchestrates Phase 4 report generation by calling services from Tasks 4-8 in order:
1. Fetch findings for scan
2. Normalize findings
3. Deduplicate findings
4. Rank findings
5. Compute risk score
6. Compute report metrics
7. Build report markdown (LLM)
8. Save report to DB
9. Embed and index report in Qdrant
10. Update scan status to "reported"
"""

import logging
from datetime import datetime, timezone

from app.services import scan_event_service, scan_service
from app.services.finding_deduplication_service import deduplicate_findings
from app.services.finding_normalization_service import normalize_findings
from app.services.finding_query_service import fetch_findings_for_scan
from app.services.report_builder_service import build_report_markdown
from app.services.report_embedding_service import embed_and_index_report
from app.services.report_metrics_service import compute_report_metrics
from app.services.report_service import save_report
from app.services.risk_scoring_service import compute_risk_score
from app.services.severity_ranking_service import rank_findings

logger = logging.getLogger(__name__)


def _mark_report_failed(scan_id: str, error_code: str, message: str) -> None:
    """Record a report generation failure in the scans table and log an event.

    Mirrors the pattern in repo_scan_worker._mark_failed but uses
    status="report_failed" to distinguish Phase 4 failures from Phase 2/3.
    """
    try:
        scan_service.update_scan(
            scan_id,
            status="report_failed",
            error_code=error_code,
            error_message=message,
            failed_at=datetime.now(timezone.utc),
        )
        scan_event_service.create_event(
            scan_id, "report_generation_failed", message, {"error_code": error_code}
        )
    except Exception:  # noqa: BLE001 - failure reporting must not itself raise
        logger.exception("Failed to record report generation failure for scan_id=%s", scan_id)


async def run_report_generation(scan_id: str) -> None:
    """Run the complete Phase 4 report generation pipeline.

    Orchestrates all report generation services in order:
    1. fetch_findings_for_scan
    2. normalize_findings
    3. deduplicate_findings
    4. rank_findings
    5. compute_risk_score
    6. compute_report_metrics
    7. get_scan (to fetch repo URL)
    8. build_report_markdown (async, LLM call)
    9. save_report
    10. embed_and_index_report (async, Qdrant)
    11. update_scan with status="reported"
    12. log success event

    On any exception, calls _mark_report_failed and swallows the exception
    (does not re-raise), matching the Phase 3 failure isolation pattern.

    Args:
        scan_id: The scan UUID as a string.
    """
    try:
        # Step 1: Fetch findings
        findings = fetch_findings_for_scan(scan_id)

        # Step 2: Normalize findings
        normalized = normalize_findings(findings)

        # Step 3: Deduplicate findings
        deduped = deduplicate_findings(normalized)

        # Step 4: Rank findings
        ranked = rank_findings(deduped)

        # Step 5: Compute risk score
        risk_score = compute_risk_score(ranked)

        # Step 6: Compute report metrics
        metrics = compute_report_metrics(ranked)

        # Step 7: Fetch scan to get repo URL
        scan = scan_service.get_scan(scan_id)
        repo_url = scan.github_url if scan else ""

        # Step 8: Build report markdown (async LLM call)
        markdown = await build_report_markdown(ranked, metrics, risk_score, repo_url)

        # Step 9: Save report to DB
        report = save_report(scan_id, markdown, metrics, risk_score)

        # Step 10: Embed and index report in Qdrant (async)
        await embed_and_index_report(scan_id, report, ranked)

        # Step 11: Update scan status to "reported"
        scan_service.update_scan(scan_id, status="reported", reported_at=datetime.now(timezone.utc))

        # Step 12: Log success event
        scan_event_service.create_event(
            scan_id,
            "report_generated",
            "Report generation completed successfully.",
            {"report_id": str(report.id), "risk_score": risk_score},
        )

    except Exception as exc:  # noqa: BLE001 - Phase 4 failures must be self-contained
        error_code = "REPORT_GENERATION_FAILED"
        message = str(exc)
        logger.exception("Phase 4 report generation failed for scan_id=%s", scan_id)
        _mark_report_failed(scan_id, error_code, message)
