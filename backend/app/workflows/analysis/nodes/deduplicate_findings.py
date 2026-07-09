import asyncio

from app.workflows.analysis.state import AnalysisState, NormalizedFinding

SEVERITY_ORDER = {"extreme": 0, "high": 1, "medium": 2, "low": 3}


def _merge_key(finding: NormalizedFinding) -> tuple:
    return (
        finding["file_path"],
        finding["symbol_name"],
        finding["start_line"],
        finding["end_line"],
        finding["title"].strip().lower(),
    )


def _dedupe(findings: list[NormalizedFinding]) -> list[NormalizedFinding]:
    groups: dict[str, list[NormalizedFinding]] = {}
    for finding in findings:
        groups.setdefault(finding["fingerprint"], []).append(finding)

    # Second pass: merge across agents using the looser cross-agent key
    # (same file/symbol/line-range/similar title) per phase3.md 10.7.
    merged_by_loose_key: dict[tuple, list[NormalizedFinding]] = {}
    for group in groups.values():
        loose_key = _merge_key(group[0])
        merged_by_loose_key.setdefault(loose_key, []).extend(group)

    deduped: list[NormalizedFinding] = []
    for group in merged_by_loose_key.values():
        group.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 3))
        primary = dict(group[0])
        related_agents = sorted({f["agent"] for f in group if f["agent"] != primary["agent"]})
        primary["related_agents"] = related_agents
        deduped.append(primary)

    return deduped


async def deduplicate_findings(state: AnalysisState) -> dict:
    deduped = await asyncio.to_thread(_dedupe, state.get("normalized_findings", []))
    return {"deduped_findings": deduped}
