"""Reproduce retained evidence in isolated, resumable bounded stages.

Historical full-grammar solver UNKNOWN results are feasibility records, not proof
certificates.  This driver replays positive evidence and fixed controls only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def normalized(name: str, value: object) -> object:
    # Solver elapsed time and echoed input depend on the local process.  The
    # logical verdict and exact retained input size remain compared.
    if name.startswith("solver-") and isinstance(value, dict):
        return {k: v for k, v in value.items() if k not in ("cpu_seconds", "input")}
    return value


def stage_groups() -> dict[str, list[tuple[str, list[str]]]]:
    common = [
        ("bibliography-audit", ["src/bibliography_audit.py"]),
        ("symbolic-replay", ["src/certificate_checker.py", "proofs/equivalence.json"]),
        ("liveness-lower-bound", ["src/liveness_checker.py", "proofs/liveness-lower-bound.json"]),
        ("event-bijective-minimality", ["src/event_bijective_checker.py", "proofs/event-bijective-minimality.json"]),
        ("checker-independence", ["tests/checker_independence.py"]),
        ("evidence-integrity", ["tests/evidence_integrity.py"]),
        ("assembly", ["tests/assembly.py"]),
        ("binary32", ["tests/binary32.py"]),
        ("mutations", ["tests/mutations.py"]),
    ]
    toy = [("toy-" + group, ["tests/pilot.py", group])
           for group in ("arithmetic", "selection", "bitwise", "blend", "programs")]
    extended = [
        ("tininess-control", ["tests/tininess.py"]),
        ("residual-exploration", ["tests/explore_residuals.py"]),
        ("guarded-copies", ["tests/guarded_copies.py"]),
        ("liveness-mutations", ["tests/liveness_mutations.py"]),
        ("event-bijective-mutations", ["tests/event_bijective_mutations.py"]),
    ]
    solver = [("solver-" + name, ["src/solver_api.py", "inputs/solver-" + name + ".smt2"])
              for name in ("positive", "negative")]
    solver += [("lazy-controls", ["tests/lazy_controls.py"])]
    hardware = [("hardware-conformance", ["tests/hardware_conformance.py"])]
    return {
        "quick": common,
        "full": common + toy + extended,
        "solver-controls": solver,
        "hardware": hardware,
    }


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def load_result(path: Path) -> object:
    return json.loads(path.read_text())


def result_matches(name: str, result: Path, expected: Path) -> bool:
    try:
        return normalized(name, load_result(result)) == normalized(name, load_result(expected))
    except (OSError, json.JSONDecodeError):
        return False


def aggregate_resources(resource_dir: Path, destination: Path, names: list[str]) -> None:
    lines: list[str] = []
    for name in names:
        path = resource_dir / (name + ".jsonl")
        if path.exists():
            lines.extend(line for line in path.read_text().splitlines() if line.strip())
    destination.write_text(("\n".join(lines) + "\n") if lines else "")


def main() -> None:
    groups = stage_groups()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=tuple(groups), default="full")
    parser.add_argument("--output", help="Result directory outside the artifact")
    parser.add_argument("--resume", action="store_true",
                        help="Verify completed stage results and continue an existing output directory")
    parser.add_argument("--stage", action="append", default=[],
                        help="Run only this stage from the chosen mode; may be repeated")
    parser.add_argument("--list-stages", action="store_true")
    args = parser.parse_args()
    if not __debug__:
        raise SystemExit("Do not run tests with python -O: assertions are required.")
    available = groups[args.mode]
    available_names = [name for name, _ in available]
    if args.list_stages:
        print("\n".join(available_names))
        return
    if not args.output:
        parser.error("--output is required unless --list-stages is used")
    if args.stage:
        unknown = sorted(set(args.stage) - set(available_names))
        if unknown:
            raise SystemExit("Stages are not in mode %s: %s" % (args.mode, ", ".join(unknown)))
        requested = set(args.stage)
        selected = [(name, command) for name, command in available if name in requested]
    else:
        selected = available
    out = Path(args.output).expanduser().resolve()
    if out == ROOT or ROOT in out.parents:
        raise SystemExit("Use an output directory outside the artifact.")
    if out.exists() and any(out.iterdir()) and not args.resume:
        raise SystemExit("The output directory must be new or empty, or use --resume.")
    out.mkdir(parents=True, exist_ok=True)
    resources_dir = out / "stage-resources"
    resources_dir.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONOPTIMIZE="")
    checks: list[dict[str, object]] = []
    selected_names = [name for name, _ in selected]
    progress_path = out / "reproduction.partial.json"

    def save_progress() -> None:
        atomic_json(progress_path, {
            "mode": args.mode,
            "selected_stages": selected_names,
            "completed_checks": checks,
            "complete": False,
            "resume_supported": True,
        })
        aggregate_resources(resources_dir, out / "resources.jsonl", selected_names)

    for name, command_tail in selected:
        result = out / (name + ".json")
        expected = ROOT / "results" / (name + ".json")
        log = out / (name + ".log")
        if not expected.exists():
            raise SystemExit("Missing retained result for stage " + name)
        if args.resume and result_matches(name, result, expected):
            print("Verified existing " + name, flush=True)
            checks.append({
                "name": name,
                "execution": "verified-existing",
                "command_passed": True,
                "retained_result_matches": True,
            })
            save_progress()
            continue
        temporary_result = out / ("." + name + ".result.tmp")
        temporary_log = out / ("." + name + ".log.tmp")
        resource_log = resources_dir / (name + ".jsonl")
        for path in (temporary_result, temporary_log, resource_log):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        bounded_command = [
            sys.executable, "src/bounded.py",
            "--label", "reproduce-" + name,
            "--log", str(resource_log),
            "--seconds", "110", "--",
            sys.executable, *command_tail, "--output", str(temporary_result),
        ]
        print("Checking " + name, flush=True)
        try:
            run = subprocess.run(
                bounded_command, cwd=ROOT, env=env, timeout=118,
                text=True, capture_output=True,
            )
            temporary_log.write_text(run.stdout + run.stderr)
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            temporary_log.write_text(stdout + stderr + "\nouter driver timeout\n")
            os.replace(temporary_log, log)
            save_progress()
            raise SystemExit("Timed out stage %s; rerun the same command with --resume" % name)
        os.replace(temporary_log, log)
        if run.returncode:
            print(run.stdout)
            print(run.stderr)
            save_progress()
            raise SystemExit("Failed stage %s; rerun with --resume after inspection" % name)
        if not temporary_result.exists():
            save_progress()
            raise SystemExit("Stage %s produced no result" % name)
        actual = load_result(temporary_result)
        wanted = load_result(expected)
        if normalized(name, actual) != normalized(name, wanted):
            failed = out / (name + ".mismatch.json")
            os.replace(temporary_result, failed)
            save_progress()
            raise SystemExit("Retained-result mismatch at %s; see %s" % (name, failed))
        os.replace(temporary_result, result)
        checks.append({
            "name": name,
            "execution": "ran",
            "command_passed": True,
            "retained_result_matches": True,
        })
        save_progress()

    completed = {check["name"] for check in checks}
    common_names = {name for name, _ in groups["quick"]}
    mode_complete = set(selected_names) == set(available_names)
    report = {
        "mode": args.mode,
        "selected_stages": selected_names,
        "mode_complete": mode_complete,
        "all_selected_stages_passed": True,
        "resume_supported": True,
        "checks": checks,
        "bibliography_metadata_and_citation_ledger_audited": "bibliography-audit" in completed,
        "all_input_equivalence_certificate_replayed": "symbolic-replay" in completed,
        "analytic_liveness_lower_bound_replayed": "liveness-lower-bound" in completed,
        "event_bijective_class_search_space_exhausted": "event-bijective-minimality" in completed,
        "event_bijective_class_minimum_cost_proved": "event-bijective-minimality" in completed,
        "checker_dependency_boundary_audited": "checker-independence" in completed,
        "cross_file_evidence_integrity_audited": "evidence-integrity" in completed,
        "hardware_diagnostic_conformance_passed": "hardware-conformance" in completed,
        "full_ten_opcode_search_space_exhausted": False,
        "full_ten_opcode_minimum_cost_proved": False,
        "interpretation": (
            "Deterministic, resumable replay of the selected retained evidence. "
            "Quick/full mode checks the bibliography ledger, all-input equivalence "
            "certificate, analytic liveness lower bound, and complete finite "
            "exhaustion of the declared event-bijective class. Hardware mode is a "
            "finite host diagnostic. None of these is independent peer review or a "
            "proof of optimality in the full ten-opcode grammar."
        ),
    }
    atomic_json(out / "reproduction.json", report)
    try:
        progress_path.unlink()
    except FileNotFoundError:
        pass
    aggregate_resources(resources_dir, out / "resources.jsonl", selected_names)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
