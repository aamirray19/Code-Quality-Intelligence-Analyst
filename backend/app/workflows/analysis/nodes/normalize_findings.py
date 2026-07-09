import asyncio
import hashlib

from app.services import scan_event_service
from app.workflows.analysis.state import AnalysisState, NormalizedFinding
from app.workflows.analysis.tools import supabase_metadata_tool

SEVERITY_MAP = {
    "critical": "extreme",
    "extreme": "extreme",
    "high": "high",
    "medium": "medium",
    "moderate": "medium",
    "low": "low",
    "minor": "low",
}

REQUIRED_FIELDS = ("title", "description", "severity")


def _fingerprint(scan_id, agent, file_path, symbol_name, start_line, end_line, title: str) -> str:
    raw = "|".join(
        [
            str(scan_id),
            agent,
            file_path or "",
            symbol_name or "",
            str(start_line or ""),
            str(end_line or ""),
            title.strip().lower(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _resolve_ids(scan_id, file_path: str | None, symbol_name: str | None) -> tuple[str | None, str | None]:
    if not file_path:
        return None, None
    file_row = supabase_metadata_tool.find_file_by_path(scan_id, file_path)
    if not file_row:
        return None, None
    if not symbol_name:
        return file_row["id"], None
    symbol_row = supabase_metadata_tool.find_symbol_by_name(scan_id, file_row["id"], symbol_name)
    return file_row["id"], (symbol_row["id"] if symbol_row else None)


def _normalize_one(scan_id, raw: dict) -> NormalizedFinding | None:
    if not all(raw.get(field) for field in REQUIRED_FIELDS):
        return None

    severity = SEVERITY_MAP.get(str(raw["severity"]).strip().lower())
    if severity is None:
        return None

    confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
    file_path = (raw.get("file_path") or "").lstrip("./").replace("\\", "/") or None
    symbol_name = raw.get("symbol_name")
    start_line = raw.get("start_line")
    end_line = raw.get("end_line")
    start_line = max(0, start_line) if isinstance(start_line, int) else None
    end_line = max(0, end_line) if isinstance(end_line, int) else None

    file_id, symbol_id = _resolve_ids(scan_id, file_path, symbol_name)

    return {
        "scan_id": scan_id,
        "agent": raw["agent"],
        "title": raw["title"],
        "description": raw["description"],
        "severity": severity,
        "confidence": confidence,
        "file_id": file_id,
        "symbol_id": symbol_id,
        "file_path": file_path,
        "symbol_name": symbol_name,
        "start_line": start_line,
        "end_line": end_line,
        "evidence": raw.get("evidence") or [],
        "recommendation": raw.get("recommendation"),
        "fingerprint": _fingerprint(scan_id, raw["agent"], file_path, symbol_name, start_line, end_line, raw["title"]),
        "related_agents": [],
    }


async def normalize_findings(state: AnalysisState) -> dict:
    scan_id = state["scan_id"]
    normalized: list[NormalizedFinding] = []
    dropped = 0

    for raw in state.get("raw_findings", []):
        result = await asyncio.to_thread(_normalize_one, scan_id, raw)
        if result is None:
            dropped += 1
            continue
        normalized.append(result)

    await asyncio.to_thread(
        scan_event_service.create_event,
        scan_id,
        "findings_normalized",
        f"Normalized {len(normalized)} findings, dropped {dropped} malformed.",
    )

    return {"normalized_findings": normalized}
