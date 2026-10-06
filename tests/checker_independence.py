"""Audit static dependency boundaries of the three claim-critical checkers.

This is a narrow, replayable structural check.  It does not prove that the
checkers are correct or independently authored; it verifies that they do not
silently import the certificate producers, executable floating-point models,
SMT bindings, or process/network facilities that the documented trust split
excludes.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKERS = {
    "all-input-equivalence": ROOT / "src" / "certificate_checker.py",
    "liveness-lower-bound": ROOT / "src" / "liveness_checker.py",
    "event-bijective-minimality": ROOT / "src" / "event_bijective_checker.py",
}
FORBIDDEN_MODULE_ROOTS = {
    "fpmodel", "oracle", "make_certificate", "liveness_lower_bound",
    "event_bijective_search", "canonical_synthesis", "lazy_synthesis",
    "smt_encoding", "solver_api", "z3", "ctypes", "subprocess", "socket",
    "urllib", "http", "requests",
}
FORBIDDEN_DYNAMIC_CALLS = {"eval", "exec", "compile", "__import__"}


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def audit(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports: set[str] = set()
    dynamic_calls: set[str] = set()
    external_calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if not name:
                continue
            if name.split(".")[-1] in FORBIDDEN_DYNAMIC_CALLS:
                dynamic_calls.add(name)
            if name.startswith(("subprocess.", "os.system", "os.popen", "ctypes.", "socket.", "urllib.", "requests.")):
                external_calls.add(name)
    roots = {name.split(".")[0] for name in imports if name}
    forbidden_imports = sorted(roots & FORBIDDEN_MODULE_ROOTS)
    if forbidden_imports or dynamic_calls or external_calls:
        raise AssertionError({
            "file": str(path.relative_to(ROOT)),
            "forbidden_imports": forbidden_imports,
            "dynamic_calls": sorted(dynamic_calls),
            "external_calls": sorted(external_calls),
        })
    return {
        "file": path.relative_to(ROOT).as_posix(),
        "imports": sorted(imports),
        "forbidden_imports": [],
        "dynamic_code_calls": [],
        "external_process_or_network_calls": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = {name: audit(path) for name, path in CHECKERS.items()}
    report = {
        "schema": "checker-independence-audit-v1",
        "passed": True,
        "checkers": rows,
        "verified_boundary": (
            "No claim-critical checker imports a certificate producer, the project floating-point "
            "models/oracle, solver bindings, or process/network facilities; no dynamic code execution "
            "primitive appears in their AST."
        ),
        "boundary": (
            "Static source-structure audit only. It does not establish checker soundness, independent "
            "authorship, proof-assistant verification, or absence of correlated conceptual errors."
        ),
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
