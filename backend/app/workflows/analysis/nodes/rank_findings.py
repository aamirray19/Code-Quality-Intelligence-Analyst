# backend/app/workflows/analysis/nodes/rank_findings.py
from app.workflows.analysis.state import AnalysisState

SEVERITY_ORDER = {"extreme": 0, "high": 1, "medium": 2, "low": 3}


def _sort_key(finding: dict) -> tuple:
    return (
        SEVERITY_ORDER.get(finding["severity"], 3),
        -finding["confidence"],
        -len(finding.get("evidence") or []),
        -len(finding.get("related_agents") or []),
    )


async def rank_findings(state: AnalysisState) -> dict:
    ranked = sorted(state.get("deduped_findings", []), key=_sort_key)
    return {"ranked_findings": ranked}
