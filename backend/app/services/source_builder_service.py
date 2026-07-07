"""Service for building structured context blocks from retrieved documents and graph data."""


def build_context_block(docs: list[dict], graph_context: dict | None) -> str:
    """Build a formatted context block from retrieved docs and optional graph context.

    Combines retrieved documents (findings, code chunks, summaries) and graph context
    (imports, symbols) into a structured text block for LLM consumption.

    Args:
        docs: List of retrieved documents, each with:
            - text: The document content
            - source_type: Type of source (finding, code_chunk, file_summary, etc.)
            - payload: Original metadata
            - score: Relevance score
        graph_context: Optional dict with 'imports' and 'symbols' keys from Neo4j graph

    Returns:
        Formatted string with structured context sections
    """
    sections = []

    # Build relevant context section
    if docs:
        sections.append("=== Relevant Context ===\n")
        
        # Group docs by source type for cleaner presentation
        by_type: dict[str, list[dict]] = {}
        for doc in docs:
            source_type = doc.get("source_type", "unknown")
            if source_type not in by_type:
                by_type[source_type] = []
            by_type[source_type].append(doc)
        
        # Order: findings first, then code chunks, then summaries
        type_order = ["finding", "code_chunk", "file_summary", "agent_summary", "scan_report"]
        
        for doc_type in type_order:
            if doc_type in by_type:
                type_label = doc_type.replace("_", " ").title()
                for doc in by_type[doc_type]:
                    sections.append(f"\n{type_label}:\n{doc['text']}\n")
        
        # Add any remaining types not in the predefined order
        for doc_type, doc_list in by_type.items():
            if doc_type not in type_order:
                type_label = doc_type.replace("_", " ").title()
                for doc in doc_list:
                    sections.append(f"\n{type_label}:\n{doc['text']}\n")
    else:
        sections.append("=== Relevant Context ===\n\nNo relevant context found.\n")

    # Build graph context section if provided
    if graph_context:
        sections.append("\n=== Graph Context ===\n")
        
        imports = graph_context.get("imports", [])
        if imports:
            sections.append("\nImports:\n")
            for imp in imports:
                imported_symbol = imp.get("imported_symbol", "unknown")
                source_file = imp.get("source_file", "unknown")
                sections.append(f"  - {imported_symbol} (from {source_file})\n")
        
        symbols = graph_context.get("symbols", [])
        if symbols:
            sections.append("\nDefined Symbols:\n")
            for sym in symbols:
                symbol_name = sym.get("symbol_name", "unknown")
                symbol_type = sym.get("symbol_type", "unknown")
                start_line = sym.get("start_line", "?")
                sections.append(f"  - {symbol_name} ({symbol_type}, line {start_line})\n")

    return "".join(sections)
