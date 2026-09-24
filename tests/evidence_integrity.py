"""Cross-check the retained certificates, byte string, results, and claim ledger.

The purpose is to detect packaging drift: a checker can pass while a manuscript
ledger or a second certificate still names a stale cost, byte string, scope, or
result path.  This audit is deterministic and has no network dependency.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent


def load(relative: str) -> object:
    return json.loads((ROOT / relative).read_text())


def split_paths(field: str) -> list[str]:
    return [part.strip() for part in field.split(";") if part.strip() and part.strip() != "none"]


def resolve_recorded(path: str) -> Path:
    if path.startswith("paper/") or path in ("research-plan.md", "CURRENT-STATE.md"):
        return PROJECT / path
    if path.startswith("artifact/"):
        # In the full package ROOT is project/artifact; in the standalone
        # repository the artifact contents are the repository root.
        return PROJECT / path if (PROJECT / "artifact").is_dir() else ROOT / path.removeprefix("artifact/")
    return ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    equivalence = load("proofs/equivalence.json")
    minimality = load("proofs/event-bijective-minimality.json")
    liveness = load("proofs/liveness-lower-bound.json")
    assembly = load("results/assembly.json")
    symbolic = load("results/symbolic-replay.json")
    minimum_result = load("results/event-bijective-minimality.json")
    liveness_result = load("results/liveness-lower-bound.json")

    candidate = minimality["candidate"]
    expected_cost = [8, 30]
    assert equivalence["claimed_cost"] == expected_cost
    assert candidate["cost"] == expected_cost
    assert symbolic["instructions"] == 8 and symbolic["bytes"] == 30
    assert assembly["assembled_instructions"] == 8 and assembly["assembled_bytes"] == 30
    assert assembly["certificate_bytes_match"] is True
    assert minimum_result["candidate"]["instructions"] == 8
    assert minimum_result["candidate"]["bytes"] == 30
    assert liveness["declared_entry_instruction_lower_bound"] == 8
    assert liveness_result["declared_entry_instruction_lower_bound"] == 8
    assert equivalence["program_hex"] == candidate["program_hex"]
    assert equivalence["output_registers"] == candidate["output_registers"] == [0, 3]
    declared = next(row for row in minimality["variants"] if row["name"] == "declared-entry")
    assert declared["minimum_relaxed_goal_length"] == 8
    assert declared["goal_counts"][:8] == [0] * 8
    assert declared["goal_counts"][8] == 34
    assert minimum_result["minimum_instructions"] == 8
    assert minimum_result["declared_entry_goal_states_at_depth_eight"] == 34

    ledger_path = ROOT / "claim_evidence_ledger.csv"
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and len({row["claim_id"] for row in rows}) == len(rows)
    required = {
        "claim_id", "claim", "maturity", "theorem_or_manuscript",
        "checker_or_experiment", "source_or_input", "raw_result",
        "figure_or_table", "boundary", "fresh_recheck",
    }
    assert set(rows[0]) == required
    missing: list[dict[str, str]] = []
    declared_paths: set[str] = set()
    artifact_local_paths: set[str] = set()
    project_side_paths: set[str] = set()
    full_project_present = (PROJECT / "paper").is_dir()
    for row in rows:
        for field in ("theorem_or_manuscript", "checker_or_experiment", "source_or_input", "raw_result"):
            for recorded in split_paths(row[field]):
                # A value may contain a section suffix after a real filename.
                token = recorded.split()[0].rstrip(",")
                if not any(token.endswith(ext) for ext in (".py", ".json", ".md", ".tex", ".bib", ".csv", ".S", ".c", ".smt2", ".jsonl")):
                    continue
                declared_paths.add(token)
                project_side = token.startswith("paper/") or token in ("research-plan.md", "CURRENT-STATE.md")
                (project_side_paths if project_side else artifact_local_paths).add(token)
                # The standalone repository intentionally omits paper/ and the two
                # project-root documents.  In a full project extraction those
                # paths are mandatory; in the standalone extraction the audit
                # still requires every artifact-local path and checks the fixed
                # declaration count, so the retained report is context-invariant.
                if project_side and not full_project_present:
                    continue
                resolved = resolve_recorded(token)
                exists = bool(list(resolved.parent.glob(resolved.name))) if "*" in resolved.name else resolved.exists()
                if not exists:
                    missing.append({"claim_id": row["claim_id"], "field": field, "path": token})
        assert row["claim"].strip() and row["maturity"].strip() and row["boundary"].strip()
    if missing:
        raise AssertionError({"missing_ledger_paths": missing})

    report = {
        "schema": "evidence-integrity-audit-v1",
        "passed": True,
        "candidate_program_hex_consistent": True,
        "candidate_outputs_consistent": True,
        "candidate_cost_consistent": expected_cost,
        "minimum_frontier_consistent": {"first_goal_depth": 8, "depth_eight_goals": 34},
        "claim_ledger_rows": len(rows),
        "unique_claim_ids": len(rows),
        "ledger_paths_declared": len(declared_paths),
        "artifact_local_paths_required": len(artifact_local_paths),
        "project_side_paths_required_when_present": len(project_side_paths),
        "boundary": (
            "Internal cross-file consistency only. Every artifact-local path is required in both "
            "packages; paper/ and project-root paths are additionally required when the audit runs "
            "inside the full project. The audit does not validate mathematical lemmas, bibliographic "
            "truth, or the open full-ten-opcode minimum."
        ),
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
