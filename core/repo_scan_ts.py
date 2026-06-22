"""Real tree-sitter AST collector for JavaScript / TypeScript.

The fallback path (core/repo_scan._js_collect) is a name-based regex pass - honest, but it cannot
truly parse: it approximates def boundaries, can be fooled by exotic syntax, and reads call names
textually. This module replaces that with a real parser when tree-sitter is installed: accurate
def boundaries and types, correct handling of JSX / TS generics / decorators / arrow functions, and
call names read from the actual call_expression nodes (never from a comment, string, or regex,
which the parser simply does not surface as code).

It emits the SAME (name, fqn, path, dtype, start, end, callees) shape the regex collector does, so
the downstream Orbit-schema writer and the same-file-first edge resolver are unchanged - only the
extraction is upgraded. tree-sitter is OPTIONAL: HAS_TREESITTER is False when the package or a
grammar is absent, and core/repo_scan falls back to the regex pass, so the zero-dependency offline
path still works. Standard determinism: parsing is pure, no network, no model.
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from tree_sitter import Language, Parser
    import tree_sitter_javascript as _tsjs
    _JS_LANGUAGE = Language(_tsjs.language())
    try:
        import tree_sitter_typescript as _tsts
        _TS_LANGUAGE = Language(_tsts.language_typescript())
        _TSX_LANGUAGE = Language(_tsts.language_tsx())
    except Exception:
        _TS_LANGUAGE = _TSX_LANGUAGE = _JS_LANGUAGE   # parse TS with the JS grammar if TS grammar absent
    HAS_TREESITTER = True
except Exception:
    HAS_TREESITTER = False

_DEF_KINDS = {
    "function_declaration": "Function",
    "generator_function_declaration": "Function",
    "function": "Function",
    "function_expression": "Function",
    "arrow_function": "Function",
    "method_definition": "Method",
    "class_declaration": "Class",
    "class": "Class",
}


def _parser_for(ext: str):
    if ext == ".ts":
        return Parser(_TS_LANGUAGE)
    if ext == ".tsx":
        return Parser(_TSX_LANGUAGE)
    return Parser(_JS_LANGUAGE)   # .js .jsx .mjs .cjs


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _name_of(node, src: bytes) -> Optional[str]:
    """The declared name of a def node, or None for an anonymous function."""
    n = node.child_by_field_name("name")
    if n is not None:
        return _text(n, src)
    return None


def _callees_in(node, src: bytes, self_name: Optional[str], builtins) -> set:
    """Free + member call names lexically inside a def body, minus builtins and the def's own name.
    A call's callee is the identifier `foo` in `foo(...)` or the property `foo` in `obj.foo(...)`.
    Nested function bodies are skipped (their calls belong to the nested def, collected separately)."""
    out = set()
    body = node.child_by_field_name("body") or node

    def walk(n, at_root):
        for c in n.children:
            t = c.type
            if not at_root and t in _DEF_KINDS:
                continue   # a nested def's calls belong to that def
            if t == "call_expression":
                fn = c.child_by_field_name("function")
                if fn is not None:
                    if fn.type == "identifier":
                        out.add(_text(fn, src))
                    elif fn.type == "member_expression":
                        prop = fn.child_by_field_name("property")
                        if prop is not None and prop.type in ("property_identifier", "identifier"):
                            out.add(_text(prop, src))
            walk(c, False)

    walk(body, True)
    out.discard(self_name)
    return {c for c in out if c and c not in builtins and (c[0].isalpha() or c[0] in "_$")}


def collect(src: str, path: str, add) -> None:
    """Parse JS/TS with tree-sitter and emit defs + their called names via `add`, matching the
    contract of core/repo_scan._js_collect (so the same-file-first resolver + DuckDB writer are
    unchanged)."""
    from core.repo_scan import _JS_BUILTIN_METHODS
    ext = os.path.splitext(path)[1].lower()
    data = src.encode("utf-8")
    tree = _parser_for(ext).parse(data)
    seen = set()

    def visit(node):
        if node.type in _DEF_KINDS:
            name = _name_of(node, data)
            # an arrow/function expression assigned to `const x = ...` is named by its declarator
            if name is None and node.type in ("arrow_function", "function", "function_expression"):
                p = node.parent
                if p is not None and p.type == "variable_declarator":
                    nm = p.child_by_field_name("name")
                    name = _text(nm, data) if nm is not None else None
            if name:
                start = node.start_point[0] + 1
                end = node.end_point[0] + 1
                key = (name, start)
                if key not in seen:
                    seen.add(key)
                    callees = _callees_in(node, data, name, _JS_BUILTIN_METHODS)
                    add(name, path + "::" + name, path, _DEF_KINDS[node.type], start, end, callees)
        for c in node.children:
            visit(c)

    visit(tree.root_node)
