"""Synthetic regressions for CSV coverage and partial-replay claim separation.

No native probe or solver is executed. CSVs use the existing frozen input pool
and model-generated observations. The report tests stub only stage dispatch;
their reports are fixtures, not theorem evidence. All fixtures stay beside the
requested output, outside the artifact, and are retained for inspection.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import reproduce
import hardware_conformance as hw


def fixture_report(selected: list[str], directory: Path) -> dict:
    artifact = directory / "artifact"
    (artifact / "results").mkdir(parents=True)
    names = ["symbolic-replay", "liveness-lower-bound", "event-bijective-minimality"]
    for name in names:
        (artifact / "results" / (name + ".json")).write_text("{}", encoding="utf-8")
    output = directory / "replay"
    argv = ["reproduce.py", "--mode", "quick", "--output", str(output)]
    for name in selected:
        argv += ["--stage", name]
    groups = {"quick": [(name, []) for name in names] if selected else []}

    def synthetic_stage(command, **kwargs):
        Path(command[-1]).write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "synthetic dispatcher fixture\n", "")

    with mock.patch.object(reproduce, "ROOT", artifact), \
            mock.patch.object(reproduce, "stage_groups", return_value=groups), \
            mock.patch.object(reproduce.subprocess, "run", side_effect=synthetic_stage), \
            mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
        reproduce.main()
    return json.loads((output / "reproduction.json").read_text(encoding="utf-8"))


def synthetic_rows(cases: list[dict], block: bool) -> list[dict]:
    rows = []
    for index, case in enumerate(cases):
        a, b = int(case["a"], 0), int(case["b"], 0)
        if block:
            for initial in range(32):
                s, e, f = hw.reference(hw.BINARY32, a, b, initial)
                rows.append(dict(case=index, initial=initial, a=hex(a), b=hex(b),
                                 ref_s=hex(s), ref_e=hex(e), ref_f=f,
                                 cand_s=hex(s), cand_e=hex(e), cand_f=f))
        else:
            for op_index, (op, imm) in enumerate(hw.OPS):
                for mask in ((0, hw.BINARY32.sign) if op == "BLENDVPS" else (0,)):
                    result = hw.BINARY32.operation(op, a, b, imm, mask)
                    rows.append(dict(case=index, op=op_index, a=hex(a), b=hex(b),
                                     mask=hex(mask), out=hex(result.word), flags=result.flags))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output == ROOT or ROOT in output.parents:
        raise SystemExit("Use an output outside the artifact for synthetic fixtures.")
    output.parent.mkdir(parents=True, exist_ok=True)
    fixture_dir = Path(tempfile.mkdtemp(prefix="evidence-contracts-", dir=output.parent))
    rows = []
    names = ["symbolic-replay", "liveness-lower-bound", "event-bijective-minimality"]
    for index, flags in enumerate(itertools.product((False, True), repeat=3)):
        selected = [name for name, present in zip(names, flags) if present]
        directory = fixture_dir / ("report-" + str(index))
        report = fixture_report(selected, directory)
        expected = flags[0] and flags[2]
        passed = (report["event_bijective_class_minimum_cost_proved"] is expected
                  and report["event_bijective_class_search_space_exhausted"] is flags[2]
                  and report["all_input_equivalence_certificate_replayed"] is flags[0]
                  and report["analytic_liveness_lower_bound_replayed"] is flags[1]
                  and report["full_ten_opcode_minimum_cost_proved"] is False)
        rows.append(dict(id="report-" + str(index), passed=passed,
                         selected=selected, expected_combined_minimum=expected,
                         observed_combined_minimum=report["event_bijective_class_minimum_cost_proved"]))

    _, cases = hw.load_cases()
    # Reuse the full frozen domain: no additional binary32 input classes.
    for block in (False, True):
        kind = "blocks" if block else "primitives"
        original = synthetic_rows(cases, block)
        comparator = hw.compare_blocks if block else hw.compare_primitives
        for change in ("control", "empty", "missing", "duplicate", "wrong-pair", "bad-domain", "wrong-result"):
            altered = [dict(row) for row in original]
            if change == "empty":
                altered = []
            elif change == "missing":
                altered.pop()
            elif change == "duplicate":
                altered[-1] = dict(altered[0])
            elif change == "wrong-pair":
                altered[0]["a"] = "0xffffffff"
            elif change == "bad-domain":
                altered[0]["initial" if block else "op"] = 32
            elif change == "wrong-result":
                altered[0]["cand_f" if block else "flags"] ^= 1
            path = fixture_dir / (kind + "-" + change + ".csv")
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(original[0]))
                writer.writeheader()
                writer.writerows(altered)
            rejected = False
            try:
                parsed = comparator(path)
            except (ValueError, AssertionError, KeyError, IndexError):
                rejected, parsed = True, None
            if change in ("control", "wrong-result"):
                mismatch = (parsed["hardware_candidate_model_mismatch_count"] if block
                            else parsed["mismatch_count"]) if parsed is not None else None
                passed = not rejected and mismatch == (1 if change == "wrong-result" else 0)
            else:
                passed = rejected
            rows.append(dict(id=kind + "-" + change, passed=passed,
                             coverage_rejected=rejected))
    report = dict(tests=len(rows), passed=all(row["passed"] for row in rows), rows=rows,
                  scope="Eight synthetic partial-replay reports and fourteen model-generated CSV controls; no native instructions or additional input classes.")
    output.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
