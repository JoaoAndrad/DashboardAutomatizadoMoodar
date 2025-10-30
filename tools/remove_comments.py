#!/usr/bin/env python3
"""remove_comments.py

Small utility to remove Python comments (#) and optionally remove docstrings (triple-quoted
strings used as module/class/function docstrings) while preserving other string literals.

Usage:
  python remove_comments.py [--remove-docstrings] [--inplace] [--backup] [--dry-run] \
    [--outfile OUTFILE] path

By default it writes cleaned output to stdout. If --outfile is provided it writes there.
If --inplace is used the original file is replaced (optionally creating a .bak when --backup).
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import sys
import tokenize
from pathlib import Path
from typing import List, Tuple


def find_docstring_ranges(source: str) -> List[Tuple[int, int]]:
    """Return a list of (start_line, end_line) ranges for docstrings in the source.

    We detect Module, FunctionDef, AsyncFunctionDef and ClassDef docstrings by inspecting
    the AST nodes and checking whether the first body element is a Constant/Str string
    expression. Line numbers are 1-based.
    """
    # Also include standalone string expression nodes used as block comments
    ranges: List[Tuple[int, int]] = []
    try:
        module = ast.parse(source)
    except SyntaxError:
        return []

    def inspect(node: ast.AST) -> None:
        # For nodes that can have a docstring, check the first body element
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body:
                first = body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, (ast.Str, ast.Constant)):
                    # ast.Constant used in py3.8+; ensure it's a string
                    val = first.value.s if isinstance(first.value, ast.Str) else getattr(first.value, 'value', None)
                    if isinstance(val, str):
                        start = getattr(first, "lineno", None)
                        end = getattr(first, "end_lineno", start)
                        if start is not None:
                            ranges.append((start, end))

        # Additionally, collect ANY standalone string expression (Expr node whose value is a
        # string literal). These are commonly used as block comments and should be removed
        # when --remove-docstrings is requested.
        if isinstance(node, ast.Expr) and isinstance(getattr(node, 'value', None), (ast.Str, ast.Constant)):
            val = node.value.s if isinstance(node.value, ast.Str) else getattr(node.value, 'value', None)
            if isinstance(val, str):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", start)
                if start is not None:
                    ranges.append((start, end))

        # Recurse into all child nodes so nested definitions inside try/except or other
        # containers are inspected as well.
        for child in ast.iter_child_nodes(node):
            inspect(child)

    inspect(module)
    return ranges


def remove_comments_and_docstrings(source: str, remove_docstrings: bool = True) -> str:
    doc_ranges = find_docstring_ranges(source) if remove_docstrings else []

    def in_docstring(line: int) -> bool:
        for a, b in doc_ranges:
            if a <= line <= b:
                return True
        return False

    out_tokens = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except Exception:
        # If tokenization fails, return original
        return source

    for toknum, tokval, start, end, line in tokens:
        if toknum == tokenize.COMMENT:
            # skip comments entirely
            continue
        if remove_docstrings and toknum == tokenize.STRING:
            start_line = start[0]
            # Only remove standalone STRING tokens that are in the docstring ranges
            if in_docstring(start_line):
                continue
        out_tokens.append((toknum, tokval))

    try:
        new_src = tokenize.untokenize(out_tokens)
    except Exception:
        # If untokenize fails, fall back to original
        return source

    # Optionally remove blank lines (caller can do further processing) - handled in process_file
    return new_src


def process_file(path: Path, remove_docstrings: bool, inplace: bool, backup: bool, dry_run: bool, outfile: Path | None) -> None:
    src = path.read_text(encoding='utf-8')
    cleaned = remove_comments_and_docstrings(src, remove_docstrings=remove_docstrings)

    # Remove blank lines if requested via global flag (set by CLI parsing)
    if getattr(process_file, "remove_blank_lines", False):
        # Preserve indentation of existing lines; simply drop empty/whitespace-only lines
        lines = cleaned.splitlines()
        cleaned = "\n".join([ln for ln in lines if ln.strip() != ""]) + ("\n" if lines and lines[-1].endswith("\n") else "")

    if dry_run:
        print(f"--- DRY RUN: {path} ---", file=sys.stderr)
        print(cleaned)
        return

    if inplace:
        if backup:
            bak = path.with_suffix(path.suffix + '.bak')
            bak.write_text(src, encoding='utf-8')
        path.write_text(cleaned, encoding='utf-8')
        print(f"Wrote (inplace): {path}")
        return

    if outfile:
        outfile.write_text(cleaned, encoding='utf-8')
        print(f"Wrote: {outfile}")
        return

    # default to stdout
    print(cleaned)


def iter_py_files(path: Path):
    if path.is_file():
        yield path
    else:
        for p in path.rglob('*.py'):
            yield p


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Remove comments (#) and optional docstrings from Python files.")
    p.add_argument('path', help='File or directory to process')
    p.add_argument('--remove-docstrings', action='store_true', help='Also remove docstrings (module/function/class)')
    p.add_argument('--remove-blank-lines', action='store_true', help='Remove blank/whitespace-only lines from output')
    p.add_argument('--inplace', action='store_true', help='Overwrite original files')
    p.add_argument('--backup', action='store_true', help='When --inplace create a .bak with original content')
    p.add_argument('--dry-run', action='store_true', help='Print result to stdout instead of writing')
    p.add_argument('--outfile', help='Write single output to this file (only valid with a single input file)')

    args = p.parse_args(argv)
    path = Path(args.path)
    outfile = Path(args.outfile) if args.outfile else None

    if outfile and not path.is_file():
        print('When using --outfile, path must be a single file', file=sys.stderr)
        return 2

    for f in iter_py_files(path):
        # If only one file and outfile specified, pass it
        of = outfile if outfile and f.samefile(path) else None
        # attach flag to process_file for blank-line removal
        setattr(process_file, "remove_blank_lines", bool(args.remove_blank_lines))
        process_file(f, args.remove_docstrings, args.inplace, args.backup, args.dry_run, of)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
