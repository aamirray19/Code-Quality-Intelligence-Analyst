from app.db.neo4j_client import get_neo4j_driver

DB_IMPORT_PATTERNS = ["supabase", "sqlalchemy", "psycopg", "pymongo", "redis", "qdrant", "neo4j"]


def get_symbol_neighbors(scan_id, symbol_id: str, depth: int = 1) -> list[dict]:
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            f"MATCH (s:Symbol {{symbol_id: $symbol_id, scan_id: $scan_id}})"
            f"-[:CONTAINS*1..{int(depth)}]-(n:Symbol) "
            "RETURN DISTINCT n.symbol_id AS symbol_id, n.name AS name, n.type AS type",
            symbol_id=symbol_id,
            scan_id=str(scan_id),
        )
        return [dict(record) for record in result]


def get_file_imports(scan_id, file_id: str) -> list[dict]:
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (f:File {file_id: $file_id, scan_id: $scan_id})-[:IMPORTS]->(i:Import) "
            "RETURN i.name AS name",
            file_id=file_id,
            scan_id=str(scan_id),
        )
        return [dict(record) for record in result]


def get_call_chain(scan_id, symbol_id: str, depth: int = 2) -> list[dict]:
    """Best-effort call-chain lookup. The Phase 2 graph has no CallExpression
    nodes (documented limitation), so this returns containment-based
    neighbors as a proxy for "related symbols" rather than a true call
    graph. Callers must not assume this reflects actual call relationships."""
    return get_symbol_neighbors(scan_id, symbol_id, depth=depth)


def get_central_symbols(scan_id, limit: int = 20) -> list[dict]:
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (s:Symbol {scan_id: $scan_id})<-[:CONTAINS]-() "
            "WITH s, count(*) AS in_degree "
            "RETURN s.symbol_id AS symbol_id, s.name AS name, in_degree "
            "ORDER BY in_degree DESC LIMIT $limit",
            scan_id=str(scan_id),
            limit=limit,
        )
        return [dict(record) for record in result]


def find_external_call_sites(scan_id, name_pattern: str) -> list[dict]:
    """Heuristic: matches Import node names against `name_pattern`
    (case-insensitive substring). Not a true call-site lookup — Phase 2's
    graph doesn't record call expressions, only import statements."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (f:File {scan_id: $scan_id})-[:IMPORTS]->(i:Import) "
            "WHERE toLower(i.name) CONTAINS toLower($pattern) "
            "RETURN f.path AS file_path, i.name AS import_name",
            scan_id=str(scan_id),
            pattern=name_pattern,
        )
        return [dict(record) for record in result]


def find_database_call_sites(scan_id) -> list[dict]:
    """Heuristic: reuses the same Import-name matching as
    `find_external_call_sites`, scanning a fixed list of common DB-client
    import name fragments. Same limitation as `find_external_call_sites`."""
    driver = get_neo4j_driver()
    matches: list[dict] = []
    with driver.session() as session:
        for pattern in DB_IMPORT_PATTERNS:
            result = session.run(
                "MATCH (f:File {scan_id: $scan_id})-[:IMPORTS]->(i:Import) "
                "WHERE toLower(i.name) CONTAINS $pattern "
                "RETURN f.path AS file_path, i.name AS import_name",
                scan_id=str(scan_id),
                pattern=pattern,
            )
            matches.extend(dict(record) for record in result)
    return matches
