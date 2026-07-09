import uuid
from typing import Any
from uuid import UUID

from app.schemas.symbols import CodeSymbol
from app.services.tree_sitter_parser_service import ParsedFileResult

# Node kinds (per-language) that map to a symbol_type.
CLASS_KINDS = {"class_definition", "class_declaration"}
FUNCTION_KINDS = {"function_definition", "function_declaration", "function_expression"}
METHOD_KINDS = {"method_definition"}
IMPORT_KINDS = {"import_statement", "import_from_statement"}
EXPORT_KINDS = {"export_statement"}

CONTAINER_KINDS = CLASS_KINDS | FUNCTION_KINDS | METHOD_KINDS


def _text(source: str, node: Any) -> str:
    return source[node.start_byte() : node.end_byte()]


def _name_for(source: str, node: Any) -> str:
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _text(source, name_node)
    return node.kind()


def extract_symbols(
    parsed_file: ParsedFileResult, scan_id: UUID, file_id: UUID, file_path: str
) -> list[CodeSymbol]:
    """Walk a Tree-sitter parse tree and extract module/class/function/method/import symbols.

    Returns an empty list if the file failed to parse. Each symbol gets a
    `local_id` (used only within this call) so nested symbols can reference
    their parent via `local_parent_id` before Supabase assigns real UUIDs.
    """
    if not parsed_file.ok or parsed_file.root_node is None:
        return []

    source = parsed_file.source
    language = parsed_file.language
    symbols: list[CodeSymbol] = []

    module_local_id = str(uuid.uuid4())
    root = parsed_file.root_node
    symbols.append(
        CodeSymbol(
            scan_id=scan_id,
            file_id=file_id,
            symbol_type="module",
            symbol_name=file_path,
            qualified_name=file_path,
            start_line=root.start_position().row + 1,
            end_line=root.end_position().row + 1,
            start_byte=root.start_byte(),
            end_byte=root.end_byte(),
            raw_code=None,
            language=language,
            local_id=module_local_id,
            local_parent_id=None,
        )
    )

    def walk(node: Any, parent_local_id: str, inside_class: bool) -> None:
        for i in range(node.child_count()):
            child = node.child(i)
            kind = child.kind()

            if kind in CLASS_KINDS:
                local_id = str(uuid.uuid4())
                name = _name_for(source, child)
                symbols.append(
                    CodeSymbol(
                        scan_id=scan_id,
                        file_id=file_id,
                        symbol_type="class",
                        symbol_name=name,
                        qualified_name=name,
                        start_line=child.start_position().row + 1,
                        end_line=child.end_position().row + 1,
                        start_byte=child.start_byte(),
                        end_byte=child.end_byte(),
                        raw_code=_text(source, child),
                        language=language,
                        local_id=local_id,
                        local_parent_id=parent_local_id,
                    )
                )
                walk(child, local_id, inside_class=True)
                continue

            if kind in METHOD_KINDS or (kind in FUNCTION_KINDS and inside_class):
                local_id = str(uuid.uuid4())
                name = _name_for(source, child)
                symbols.append(
                    CodeSymbol(
                        scan_id=scan_id,
                        file_id=file_id,
                        symbol_type="method",
                        symbol_name=name,
                        qualified_name=name,
                        start_line=child.start_position().row + 1,
                        end_line=child.end_position().row + 1,
                        start_byte=child.start_byte(),
                        end_byte=child.end_byte(),
                        raw_code=_text(source, child),
                        language=language,
                        local_id=local_id,
                        local_parent_id=parent_local_id,
                    )
                )
                walk(child, local_id, inside_class=False)
                continue

            if kind in FUNCTION_KINDS:
                local_id = str(uuid.uuid4())
                name = _name_for(source, child)
                symbols.append(
                    CodeSymbol(
                        scan_id=scan_id,
                        file_id=file_id,
                        symbol_type="function",
                        symbol_name=name,
                        qualified_name=name,
                        start_line=child.start_position().row + 1,
                        end_line=child.end_position().row + 1,
                        start_byte=child.start_byte(),
                        end_byte=child.end_byte(),
                        raw_code=_text(source, child),
                        language=language,
                        local_id=local_id,
                        local_parent_id=parent_local_id,
                    )
                )
                walk(child, local_id, inside_class=False)
                continue

            if kind in IMPORT_KINDS:
                symbols.append(
                    CodeSymbol(
                        scan_id=scan_id,
                        file_id=file_id,
                        symbol_type="import",
                        symbol_name=_text(source, child).strip(),
                        qualified_name=None,
                        start_line=child.start_position().row + 1,
                        end_line=child.end_position().row + 1,
                        start_byte=child.start_byte(),
                        end_byte=child.end_byte(),
                        raw_code=_text(source, child),
                        language=language,
                        local_id=str(uuid.uuid4()),
                        local_parent_id=parent_local_id,
                    )
                )
                continue

            if kind in EXPORT_KINDS:
                symbols.append(
                    CodeSymbol(
                        scan_id=scan_id,
                        file_id=file_id,
                        symbol_type="export",
                        symbol_name=_text(source, child).strip()[:200],
                        qualified_name=None,
                        start_line=child.start_position().row + 1,
                        end_line=child.end_position().row + 1,
                        start_byte=child.start_byte(),
                        end_byte=child.end_byte(),
                        raw_code=_text(source, child),
                        language=language,
                        local_id=str(uuid.uuid4()),
                        local_parent_id=parent_local_id,
                    )
                )
                # Exported declarations (e.g. `export function foo() {}`) may
                # nest a function/class we still want to record.
                walk(child, parent_local_id, inside_class)
                continue

            # Not a symbol-bearing node itself; keep walking its children so
            # nested symbols (e.g. functions inside if-blocks) are still found.
            walk(child, parent_local_id, inside_class)

    walk(root, module_local_id, inside_class=False)
    return symbols
