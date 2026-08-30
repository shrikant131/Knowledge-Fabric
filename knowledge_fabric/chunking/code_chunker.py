"""Structure-aware code chunking.

The Connector Framework design calls for AST-aware chunking via tree-sitter.
This module tries tree-sitter first (if the language grammars are available
in the environment) and falls back to a regex-based function/class boundary
splitter otherwise, so the pipeline runs the same either way -- only the
`_split_symbols` implementation changes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

try:
    import tree_sitter_languages  # type: ignore
    _HAS_TREE_SITTER = True
except ImportError:
    _HAS_TREE_SITTER = False


@dataclass
class CodeSymbol:
    name: str
    kind: str          # "function" | "class" | "module"
    start_line: int
    end_line: int
    text: str


_PY_DEF_RE = re.compile(r"^(?P<indent>\s*)(?:async\s+)?def\s+(?P<name>\w+)\s*\(", re.MULTILINE)
_PY_CLASS_RE = re.compile(r"^(?P<indent>\s*)class\s+(?P<name>\w+)\s*[:\(]", re.MULTILINE)
_JAVA_METHOD_RE = re.compile(
    r"^\s*(?:public|private|protected|static|final|synchronized|\s)*"
    r"[\w<>\[\],\s]+?\s+(?P<name>\w+)\s*\([^;{]*\)\s*(?:throws[\w,\s]+)?\{",
    re.MULTILINE,
)
_JAVA_CLASS_RE = re.compile(r"^\s*(?:public|private|protected|static|final|\s)*class\s+(?P<name>\w+)", re.MULTILINE)


def _split_python_regex(source: str) -> list[CodeSymbol]:
    return _split_by_markers(source, [
        (_PY_CLASS_RE, "class"),
        (_PY_DEF_RE, "function"),
    ])


def _split_java_regex(source: str) -> list[CodeSymbol]:
    return _split_by_markers(source, [
        (_JAVA_CLASS_RE, "class"),
        (_JAVA_METHOD_RE, "function"),
    ])


def _split_by_markers(source: str, patterns: list[tuple[re.Pattern, str]]) -> list[CodeSymbol]:
    lines = source.splitlines()
    markers: list[tuple[int, str, str]] = []  # (line_no, name, kind)
    for pattern, kind in patterns:
        for m in pattern.finditer(source):
            line_no = source[: m.start()].count("\n")
            markers.append((line_no, m.group("name"), kind))
    markers.sort(key=lambda t: t[0])

    if not markers:
        return [CodeSymbol(name="<module>", kind="module", start_line=0,
                            end_line=len(lines), text=source)]

    symbols: list[CodeSymbol] = []
    if markers[0][0] > 0:
        header = "\n".join(lines[: markers[0][0]]).strip()
        if header:
            symbols.append(CodeSymbol("<module>", "module", 0, markers[0][0], header))

    for i, (line_no, name, kind) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(lines)
        text = "\n".join(lines[line_no:end])
        symbols.append(CodeSymbol(name=name, kind=kind, start_line=line_no, end_line=end, text=text))
    return symbols


_REGEX_SPLITTERS = {
    "python": _split_python_regex,
    "java": _split_java_regex,
}


def split_code_symbols(source: str, language: str) -> list[CodeSymbol]:
    """Split source into function/class-level symbols.

    Uses tree-sitter when available for the given language; otherwise falls
    back to a regex-based splitter. Both paths produce the same CodeSymbol
    shape so downstream chunking code doesn't care which was used.
    """
    if _HAS_TREE_SITTER:
        try:
            return _split_with_tree_sitter(source, language)
        except Exception:
            pass  # fall through to regex splitter

    splitter = _REGEX_SPLITTERS.get(language)
    if splitter is None:
        return [CodeSymbol(name="<module>", kind="module", start_line=0,
                            end_line=len(source.splitlines()), text=source)]
    return splitter(source)


def _split_with_tree_sitter(source: str, language: str) -> list[CodeSymbol]:
    parser = tree_sitter_languages.get_parser(language)
    tree = parser.parse(source.encode("utf-8"))
    lines = source.splitlines()
    symbols: list[CodeSymbol] = []

    node_types = {
        "python": {"function_definition": "function", "class_definition": "class"},
        "java": {"method_declaration": "function", "class_declaration": "class"},
    }.get(language, {})

    def walk(node):
        if node.type in node_types:
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            name = source[name_node.start_byte:name_node.end_byte] if name_node else "<anonymous>"
            start_line = node.start_point[0]
            end_line = node.end_point[0] + 1
            symbols.append(CodeSymbol(
                name=name, kind=node_types[node.type],
                start_line=start_line, end_line=end_line,
                text="\n".join(lines[start_line:end_line]),
            ))
            return  # don't descend into nested defs for top-level chunking
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    if not symbols:
        return [CodeSymbol(name="<module>", kind="module", start_line=0, end_line=len(lines), text=source)]
    return sorted(symbols, key=lambda s: s.start_line)
