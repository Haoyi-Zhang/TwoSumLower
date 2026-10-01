"""Regression fixtures for host-provenance versus scientific-result comparison."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reproduce import normalized  # noqa: E402


def load(name: str) -> object:
    return json.loads((ROOT / "inputs" / "hardware-result-contract" / name).read_text())


def equal(left: object, right: object) -> bool:
    return normalized("hardware-conformance", left) == normalized("hardware-conformance", right)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    retained = load("retained.json")
    provenance = load("provenance-only.json")
    observation = load("observation-change.json")
    mismatch = load("mismatch-change.json")
    report = {
        "provenance_only_change_accepted": equal(retained, provenance),
        "observation_count_change_rejected": not equal(retained, observation),
        "mismatch_change_rejected": not equal(retained, mismatch),
        "provenance_fields": ["host_architecture", "host_cpu_vendor"],
        "load_bearing_examples": ["primitive.observations", "complete_blocks.observations", "mismatch counts"],
        "execution_scope": (
            "Four small JSON fixtures test comparison semantics only. No processor instructions "
            "are executed and no new hardware observations are claimed."
        ),
    }
    report["passed"] = all(report[k] for k in (
        "provenance_only_change_accepted",
        "observation_count_change_rejected",
        "mismatch_change_rejected",
    ))
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
