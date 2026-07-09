from uuid import UUID, uuid5

from qdrant_client import models

from app.core.config import settings
from app.core.errors import AppError
from app.db.qdrant_client import get_qdrant_client
from app.schemas.finding import FindingRecord
from app.schemas.report import ReportRecord
from app.services.embedding_service import embed_texts
from app.services.qdrant_index_service import _ensure_findings_collection, _ensure_reports_collection


async def embed_and_index_report(
    scan_id: str, report: ReportRecord, findings: list[FindingRecord]
) -> None:
    """Embed and index report summary and findings into Qdrant.

    Creates document embeddings for:
    - Report summary (scan_reports collection)
    - Individual findings (agent_findings collection)
    - File-level summaries (agent_findings collection)
    - Agent-level summaries (agent_findings collection)

    Args:
        scan_id: The scan UUID as a string
        report: The generated report record
        findings: List of findings from all agents

    Raises:
        AppError: If Qdrant upsert fails
    """
    # Build all documents to embed
    documents: list[str] = []
    doc_metadata: list[dict] = []

    # 1. Report summary document
    report_summary_text = _build_report_summary_text(report)
    documents.append(report_summary_text)
    doc_metadata.append({"type": "scan_report", "scan_id": scan_id})

    # 2. Individual finding documents
    for finding in findings:
        finding_text = _build_finding_text(finding)
        documents.append(finding_text)
        doc_metadata.append({"type": "finding", "finding": finding, "scan_id": scan_id})

    # 3. File-level summary documents
    file_summaries = _build_file_summaries(findings, scan_id)
    for file_path, summary_text, metadata in file_summaries:
        documents.append(summary_text)
        doc_metadata.append({"type": "file_summary", "file_path": file_path, **metadata})

    # 4. Agent-level summary documents
    agent_summaries = _build_agent_summaries(findings, scan_id)
    for agent_name, summary_text, metadata in agent_summaries:
        documents.append(summary_text)
        doc_metadata.append({"type": "agent_summary", "agent": agent_name, **metadata})

    # Embed all documents in a single batch call
    try:
        vectors = embed_texts(documents)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            "EMBEDDING_FAILED", f"Failed to embed report documents: {exc}", 502
        ) from exc

    if len(vectors) != len(documents):
        raise AppError(
            "EMBEDDING_FAILED",
            f"Vector count mismatch: {len(vectors)} vectors for {len(documents)} documents",
            502,
        )

    # Build points for each collection
    agent_findings_points: list[models.PointStruct] = []
    scan_reports_points: list[models.PointStruct] = []

    for i, (doc_meta, vector) in enumerate(zip(doc_metadata, vectors)):
        if doc_meta["type"] == "scan_report":
            # Report summary goes to scan_reports collection
            point_id = _generate_report_summary_id(scan_id)
            payload = {
                "scan_id": scan_id,
                "doc_type": "scan_report",
                "content": documents[i],
            }
            scan_reports_points.append(
                models.PointStruct(id=point_id, vector=vector, payload=payload)
            )

        elif doc_meta["type"] == "finding":
            # Individual findings go to agent_findings collection
            finding = doc_meta["finding"]
            point_id = str(finding.id)
            payload = {
                "finding_id": str(finding.id),
                "scan_id": scan_id,
                "severity": finding.severity,
                "agent": finding.agent,
                "file_path": finding.file_path or "",
                "title": finding.title,
                "doc_type": "finding",
                "content": documents[i],
            }
            agent_findings_points.append(
                models.PointStruct(id=point_id, vector=vector, payload=payload)
            )

        elif doc_meta["type"] == "file_summary":
            # File summaries go to agent_findings collection
            file_path = doc_meta["file_path"]
            point_id = _generate_file_summary_id(scan_id, file_path)
            payload = {
                "scan_id": scan_id,
                "file_path": file_path,
                "doc_type": "file_summary",
                "content": documents[i],
                **doc_meta,
            }
            agent_findings_points.append(
                models.PointStruct(id=point_id, vector=vector, payload=payload)
            )

        elif doc_meta["type"] == "agent_summary":
            # Agent summaries go to agent_findings collection
            agent_name = doc_meta["agent"]
            point_id = _generate_agent_summary_id(scan_id, agent_name)
            payload = {
                "scan_id": scan_id,
                "agent": agent_name,
                "doc_type": "agent_summary",
                "content": documents[i],
                **doc_meta,
            }
            agent_findings_points.append(
                models.PointStruct(id=point_id, vector=vector, payload=payload)
            )

    # Ensure collections exist and upsert
    try:
        if vectors:
            vector_size = len(vectors[0])
            _ensure_findings_collection(vector_size)
            _ensure_reports_collection(vector_size)

        client = get_qdrant_client()

        # Upsert to agent_findings collection
        if agent_findings_points:
            client.upsert(
                collection_name=settings.qdrant_collection_agent_findings,
                points=agent_findings_points,
            )

        # Upsert to scan_reports collection
        if scan_reports_points:
            client.upsert(
                collection_name=settings.qdrant_collection_scan_reports,
                points=scan_reports_points,
            )

    except Exception as exc:
        raise AppError(
            "QDRANT_UPSERT_FAILED", f"Failed to upsert report into Qdrant: {exc}", 502
        ) from exc


def _build_report_summary_text(report: ReportRecord) -> str:
    """Build a text representation of the report summary for embedding."""
    # Use the first 2000 characters of the summary markdown as the embedded content
    # This ensures we don't exceed token limits while capturing the key information
    summary = report.summary_markdown[:2000]
    metrics = report.metrics

    text = f"""Code Quality Report Summary

Risk Score: {report.risk_score}/10

Total Findings: {metrics.total_findings}
Files Affected: {metrics.files_affected}

Findings by Severity:
{_format_dict(metrics.by_severity)}

Findings by Agent:
{_format_dict(metrics.by_agent)}

Summary:
{summary}
"""
    return text


def _build_finding_text(finding: FindingRecord) -> str:
    """Build a text representation of a finding for embedding."""
    text = f"""Finding: {finding.title}

Severity: {finding.severity}
Confidence: {finding.confidence}
Agent: {finding.agent}
File: {finding.file_path or 'N/A'}
Symbol: {finding.symbol_name or 'N/A'}
Lines: {finding.start_line}-{finding.end_line if finding.end_line else finding.start_line}

Description:
{finding.description}
"""

    if finding.recommendation:
        text += f"\nRecommendation:\n{finding.recommendation}\n"

    if finding.evidence:
        text += f"\nEvidence:\n" + "\n".join(f"- {ev}" for ev in finding.evidence[:3])

    return text


def _build_file_summaries(
    findings: list[FindingRecord], scan_id: str
) -> list[tuple[str, str, dict]]:
    """Build file-level summary documents grouped by file_path.

    Returns:
        List of (file_path, summary_text, metadata) tuples
    """
    # Group findings by file
    by_file: dict[str, list[FindingRecord]] = {}
    for finding in findings:
        if finding.file_path:
            by_file.setdefault(finding.file_path, []).append(finding)

    summaries = []
    for file_path, file_findings in by_file.items():
        severity_counts = {}
        for f in file_findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        text = f"""File Risk Summary: {file_path}

Total Findings: {len(file_findings)}
Severity Breakdown: {_format_dict(severity_counts)}

Findings:
"""
        for f in file_findings[:5]:  # Top 5 findings
            text += f"- {f.severity}: {f.title} (by {f.agent})\n"

        metadata = {
            "scan_id": scan_id,
            "file_path": file_path,
            "total_findings": len(file_findings),
            "severity_counts": severity_counts,
        }
        summaries.append((file_path, text, metadata))

    return summaries


def _build_agent_summaries(
    findings: list[FindingRecord], scan_id: str
) -> list[tuple[str, str, dict]]:
    """Build agent-level summary documents grouped by agent.

    Returns:
        List of (agent_name, summary_text, metadata) tuples
    """
    # Group findings by agent
    by_agent: dict[str, list[FindingRecord]] = {}
    for finding in findings:
        by_agent.setdefault(finding.agent, []).append(finding)

    summaries = []
    for agent_name, agent_findings in by_agent.items():
        severity_counts = {}
        for f in agent_findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        text = f"""Agent Analysis Summary: {agent_name}

Total Findings: {len(agent_findings)}
Severity Breakdown: {_format_dict(severity_counts)}

Top Findings:
"""
        for f in agent_findings[:5]:  # Top 5 findings
            text += f"- {f.severity}: {f.title} ({f.file_path or 'N/A'})\n"

        metadata = {
            "scan_id": scan_id,
            "agent": agent_name,
            "total_findings": len(agent_findings),
            "severity_counts": severity_counts,
        }
        summaries.append((agent_name, text, metadata))

    return summaries


def _format_dict(d: dict) -> str:
    """Format a dictionary as a string for text embedding."""
    return ", ".join(f"{k}: {v}" for k, v in sorted(d.items()))


def _generate_report_summary_id(scan_id: str) -> str:
    """Generate a deterministic ID for the report summary point."""
    namespace = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace UUID
    return str(uuid5(namespace, f"report:{scan_id}"))


def _generate_file_summary_id(scan_id: str, file_path: str) -> str:
    """Generate a deterministic ID for a file summary point."""
    namespace = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid5(namespace, f"file:{scan_id}:{file_path}"))


def _generate_agent_summary_id(scan_id: str, agent_name: str) -> str:
    """Generate a deterministic ID for an agent summary point."""
    namespace = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid5(namespace, f"agent:{scan_id}:{agent_name}"))
