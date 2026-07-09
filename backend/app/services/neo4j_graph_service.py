from uuid import UUID

from app.core.errors import AppError
from app.db.neo4j_client import get_neo4j_driver
from app.schemas.indexes import Neo4jIndexResult

CONSTRAINTS = [
    "create constraint repository_full_name_unique if not exists "
    "for (r:Repository) require r.full_name is unique",
    "create constraint scan_id_unique if not exists for (s:Scan) require s.scan_id is unique",
    "create constraint file_id_unique if not exists for (f:File) require f.file_id is unique",
    "create constraint symbol_id_unique if not exists for (s:Symbol) require s.symbol_id is unique",
]


def ensure_constraints() -> None:
    driver = get_neo4j_driver()
    with driver.session() as session:
        for statement in CONSTRAINTS:
            session.run(statement)


def upsert_code_graph(
    scan_id: UUID,
    repo_full_name: str,
    html_url: str,
    branch: str,
    commit_sha: str,
    files: list[dict],
    symbols: list[dict],
) -> Neo4jIndexResult:
    """Create/merge the code graph for a scan: Repository, Scan, File, Symbol,
    and Import nodes with the minimum relationships from phase2.md 8.4.

    `files` and `symbols` are the raw Supabase rows (dicts) returned after
    storing `scan_files` / `code_symbols`, so real ids are available for
    graph node keys and parent/child linking.

    CallExpression nodes are intentionally not created yet: call-expression
    extraction is an optional-later feature (phase2.md 5.6) not implemented
    in symbol_extraction_service, and the spec explicitly recommends starting
    with a simple graph first.
    """
    nodes_upserted = 0
    relationships_upserted = 0

    try:
        ensure_constraints()
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run(
                "MERGE (r:Repository {full_name: $full_name}) "
                "SET r.html_url = $html_url "
                "MERGE (s:Scan {scan_id: $scan_id}) "
                "SET s.branch = $branch, s.commit_sha = $commit_sha "
                "MERGE (r)-[:HAS_SCAN]->(s)",
                full_name=repo_full_name,
                html_url=html_url,
                scan_id=str(scan_id),
                branch=branch,
                commit_sha=commit_sha,
            )
            nodes_upserted += 2
            relationships_upserted += 1

            for file_row in files:
                session.run(
                    "MATCH (s:Scan {scan_id: $scan_id}) "
                    "MERGE (f:File {file_id: $file_id}) "
                    "SET f.scan_id = $scan_id, f.path = $path, f.language = $language "
                    "MERGE (s)-[:HAS_FILE]->(f)",
                    scan_id=str(scan_id),
                    file_id=file_row["id"],
                    path=file_row["relative_path"],
                    language=file_row.get("language"),
                )
                nodes_upserted += 1
                relationships_upserted += 1

            for symbol_row in symbols:
                if symbol_row["symbol_type"] == "import":
                    session.run(
                        "MATCH (f:File {file_id: $file_id}) "
                        "MERGE (i:Import {scan_id: $scan_id, file_id: $file_id, name: $name}) "
                        "MERGE (f)-[:IMPORTS]->(i)",
                        file_id=symbol_row["file_id"],
                        scan_id=str(scan_id),
                        name=symbol_row["symbol_name"],
                    )
                    nodes_upserted += 1
                    relationships_upserted += 1
                    continue

                session.run(
                    "MERGE (sym:Symbol {symbol_id: $symbol_id}) "
                    "SET sym.scan_id = $scan_id, sym.name = $name, "
                    "sym.qualified_name = $qualified_name, sym.type = $type, "
                    "sym.start_line = $start_line, sym.end_line = $end_line",
                    symbol_id=symbol_row["id"],
                    scan_id=str(scan_id),
                    name=symbol_row["symbol_name"],
                    qualified_name=symbol_row.get("qualified_name"),
                    type=symbol_row["symbol_type"],
                    start_line=symbol_row["start_line"],
                    end_line=symbol_row["end_line"],
                )
                nodes_upserted += 1

                parent_symbol_id = symbol_row.get("parent_symbol_id")
                if parent_symbol_id:
                    session.run(
                        "MATCH (parent:Symbol {symbol_id: $parent_id}) "
                        "MATCH (child:Symbol {symbol_id: $child_id}) "
                        "MERGE (parent)-[:CONTAINS]->(child)",
                        parent_id=parent_symbol_id,
                        child_id=symbol_row["id"],
                    )
                else:
                    session.run(
                        "MATCH (f:File {file_id: $file_id}) "
                        "MATCH (sym:Symbol {symbol_id: $symbol_id}) "
                        "MERGE (f)-[:DEFINES]->(sym)",
                        file_id=symbol_row["file_id"],
                        symbol_id=symbol_row["id"],
                    )
                relationships_upserted += 1
    except Exception as exc:  # neo4j driver raises various transport/API errors
        raise AppError("NEO4J_UPSERT_FAILED", f"Failed to upsert code graph into Neo4j: {exc}", 502) from exc

    return Neo4jIndexResult(
        scan_id=scan_id,
        nodes_upserted=nodes_upserted,
        relationships_upserted=relationships_upserted,
    )
