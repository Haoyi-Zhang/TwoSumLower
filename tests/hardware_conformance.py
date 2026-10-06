"""Finite x86-64 SSE4.1 conformance check against the exact model.

This test executes the admitted primitive instructions and the complete reference
and candidate blocks on the current host.  It is diagnostic evidence, not a
universal proof and not a substitute for the written Intel-contract argument.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
import json
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fpmodel import (  # noqa: E402
    BINARY32, CANDIDATE, DIVZERO, INEXACT, INVALID, OVERFLOW, UNDERFLOW,
    execute, reference,
)

OPS = [
    ("ADDSS", 0), ("SUBSS", 0), ("MULSS", 0),
    ("MINSS", 0), ("MAXSS", 0),
    ("ANDPS", 0), ("ORPS", 0), ("XORPS", 0),
    ("BLENDVPS", 0),
] + [("CMPSS", imm) for imm in range(8)]


def cpu_vendor() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(errors="replace").splitlines():
            if line.startswith("vendor_id"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unreported"


def require_host() -> None:
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        raise SystemExit("hardware conformance requires an x86-64 host")
    try:
        text = Path("/proc/cpuinfo").read_text(errors="replace").lower()
    except OSError:
        text = ""
    if "sse4_1" not in text and "sse4.1" not in text:
        raise SystemExit("hardware conformance requires SSE4.1")
    if shutil.which("gcc") is None:
        raise SystemExit("hardware conformance requires gcc")


def compile_probe(source: Path, output: Path) -> None:
    command = [
        "gcc", "-O2", "-fno-fast-math", "-msse4.1",
        "-Wall", "-Wextra", "-Werror", "-o", str(output), str(source),
    ]
    run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if run.returncode:
        raise RuntimeError(f"probe compilation failed:\n{run.stdout}{run.stderr}")


def load_cases() -> tuple[dict, list[dict]]:
    data = json.loads((ROOT / "inputs" / "binary32-cases.json").read_text())
    cases = data["cases"]
    if len(cases) != 1000:
        raise AssertionError("the frozen hardware pool must contain exactly 1,000 pairs")
    return data, cases


def write_pool(path: Path, cases: list[dict]) -> None:
    with path.open("wb") as out:
        for row in cases:
            out.write(struct.pack("<II", int(row["a"], 0), int(row["b"], 0)))


def signed_kind(word: int) -> str:
    sign, _, _ = BINARY32.parts(word)
    return ("negative_" if sign else "positive_") + BINARY32.kind(word)


def coverage_summary(data: dict, cases: list[dict]) -> dict:
    """Describe the already frozen pool; do not add or resample inputs."""
    strata: Counter[str] = Counter()
    a_classes: Counter[str] = Counter()
    b_classes: Counter[str] = Counter()
    features: Counter[str] = Counter()
    primitive_flags: Counter[str] = Counter()
    reference_flags: Counter[str] = Counter()
    primitive_operations: Counter[str] = Counter()
    flag_bits = [
        (INVALID, "invalid"),
        (DIVZERO, "divide_by_zero"),
        (OVERFLOW, "overflow"),
        (UNDERFLOW, "underflow"),
        (INEXACT, "inexact"),
    ]

    for row in cases:
        a, b = int(row["a"], 0), int(row["b"], 0)
        strata[row["stratum"]] += 1
        a_classes[signed_kind(a)] += 1
        b_classes[signed_kind(b)] += 1
        if BINARY32.nan(a) or BINARY32.nan(b):
            features["any_nan"] += 1
        if BINARY32.nan(a) and BINARY32.nan(b):
            features["both_nan"] += 1
        if BINARY32.snan(a) or BINARY32.snan(b):
            features["any_signaling_nan"] += 1
        if BINARY32.infinity(a) or BINARY32.infinity(b):
            features["any_infinity"] += 1
        if BINARY32.kind(a) == "subnormal" or BINARY32.kind(b) == "subnormal":
            features["any_subnormal"] += 1
        if BINARY32.zero(a) or BINARY32.zero(b):
            features["any_zero"] += 1
        if ((BINARY32.zero(a) and a & BINARY32.sign)
                or (BINARY32.zero(b) and b & BINARY32.sign)):
            features["any_negative_zero"] += 1

        fresh = reference(BINARY32, a, b)[2]
        for bit, name in flag_bits:
            if fresh & bit:
                reference_flags[name] += 1

        for op, imm in OPS:
            masks = (0, BINARY32.sign) if op == "BLENDVPS" else (0,)
            for mask in masks:
                result = BINARY32.operation(op, a, b, imm, mask)
                primitive_operations[op] += 1
                for bit, name in flag_bits:
                    if result.flags & bit:
                        primitive_flags[name] += 1

    for _, name in flag_bits:
        primitive_flags[name] += 0
        reference_flags[name] += 0
    for feature in ("any_nan", "both_nan", "any_signaling_nan", "any_infinity",
                    "any_subnormal", "any_zero", "any_negative_zero"):
        features[feature] += 0

    return {
        "selection": data["selection"],
        "stratum_pair_counts": dict(sorted(strata.items())),
        "operand_class_counts": {
            "a": dict(sorted(a_classes.items())),
            "b": dict(sorted(b_classes.items())),
        },
        "pair_feature_counts": dict(sorted(features.items())),
        "primitive_operation_observation_counts": dict(sorted(primitive_operations.items())),
        "primitive_model_fresh_flag_observation_counts": dict(sorted(primitive_flags.items())),
        "reference_model_fresh_flag_pair_counts": dict(sorted(reference_flags.items())),
        "interpretation": (
            "Deterministic coverage accounting for the existing frozen 1,000-pair pool. "
            "Flag counts are model-predicted fresh contributions, not additional hardware "
            "observations or a statistical workload sample. Divide-by-zero remains zero "
            "because the frozen instruction grammar contains no division instruction."
        ),
    }


def trace_case(row: dict, cases: list[dict]) -> tuple[int, int, int]:
    """Bind each observation to its exact position in the frozen input pool."""
    index = int(row["case"])
    if not 0 <= index < len(cases):
        raise ValueError("observation case is outside the frozen pool")
    a, b = int(row["a"], 0), int(row["b"], 0)
    expected = cases[index]
    if (a, b) != (int(expected["a"], 0), int(expected["b"], 0)):
        raise ValueError("observation operands differ from the frozen case")
    return index, a, b


def compare_primitives(path: Path) -> dict:
    _, cases = load_cases()
    seen: set[tuple[int, int, int]] = set()
    mismatches: list[dict] = []
    mismatch_count = 0
    records = 0
    with path.open(newline="") as src:
        for row in csv.DictReader(src):
            case_index, a, b = trace_case(row, cases)
            op_index = int(row["op"])
            if not 0 <= op_index < len(OPS):
                raise ValueError("observation opcode is outside the probe contract")
            op, imm = OPS[op_index]
            mask = int(row["mask"], 0)
            masks = (0, BINARY32.sign) if op == "BLENDVPS" else (0,)
            if mask not in masks:
                raise ValueError("observation mask is outside the probe contract")
            key = (case_index, op_index, mask)
            if key in seen:
                raise ValueError("duplicate primitive observation")
            seen.add(key)
            got = (int(row["out"], 0), int(row["flags"]))
            expected = BINARY32.operation(op, a, b, imm, mask)
            want = (expected.word, expected.flags)
            records += 1
            if got != want:
                mismatch_count += 1
            if got != want and len(mismatches) < 32:
                mismatches.append({
                    "case": int(row["case"]), "op": op, "immediate": imm,
                    "a": f"0x{a:08x}", "b": f"0x{b:08x}",
                    "mask": f"0x{mask:08x}",
                    "hardware": [f"0x{got[0]:08x}", got[1]],
                    "model": [f"0x{want[0]:08x}", want[1]],
                })
    if len(seen) != len(cases) * (len(OPS) + 1):
        raise ValueError("incomplete primitive coverage: every operation/mask is required once per frozen pair")
    return {"observations": records, "mismatch_count": mismatch_count,
            "first_mismatches": mismatches}


def compare_blocks(path: Path) -> dict:
    _, cases = load_cases()
    seen: set[tuple[int, int]] = set()
    hardware_pair_mismatches: list[dict] = []
    reference_model_mismatches: list[dict] = []
    candidate_model_mismatches: list[dict] = []
    hardware_pair_mismatch_count = 0
    reference_model_mismatch_count = 0
    candidate_model_mismatch_count = 0
    records = 0
    with path.open(newline="") as src:
        for row in csv.DictReader(src):
            case_index, a, b = trace_case(row, cases)
            initial = int(row["initial"])
            if not 0 <= initial < 32:
                raise ValueError("observation initial flag mask is outside 0..31")
            key = (case_index, initial)
            if key in seen:
                raise ValueError("duplicate complete-block observation")
            seen.add(key)
            hw_reference = (int(row["ref_s"], 0), int(row["ref_e"], 0), int(row["ref_f"]))
            hw_candidate = (int(row["cand_s"], 0), int(row["cand_e"], 0), int(row["cand_f"]))
            model_reference_raw = reference(BINARY32, a, b)
            model_reference = (model_reference_raw[0], model_reference_raw[1],
                               model_reference_raw[2] | initial)
            model_candidate = execute(BINARY32, CANDIDATE, a, b, initial_flags=initial)
            records += 1
            base = {"case": int(row["case"]), "initial_flags": initial,
                    "a": f"0x{a:08x}", "b": f"0x{b:08x}"}
            if hw_reference != hw_candidate:
                hardware_pair_mismatch_count += 1
            if hw_reference != hw_candidate and len(hardware_pair_mismatches) < 32:
                hardware_pair_mismatches.append({**base,
                    "reference": [f"0x{hw_reference[0]:08x}", f"0x{hw_reference[1]:08x}", hw_reference[2]],
                    "candidate": [f"0x{hw_candidate[0]:08x}", f"0x{hw_candidate[1]:08x}", hw_candidate[2]]})
            if hw_reference != model_reference:
                reference_model_mismatch_count += 1
            if hw_reference != model_reference and len(reference_model_mismatches) < 32:
                reference_model_mismatches.append({**base,
                    "hardware": [f"0x{hw_reference[0]:08x}", f"0x{hw_reference[1]:08x}", hw_reference[2]],
                    "model": [f"0x{model_reference[0]:08x}", f"0x{model_reference[1]:08x}", model_reference[2]]})
            if hw_candidate != model_candidate:
                candidate_model_mismatch_count += 1
            if hw_candidate != model_candidate and len(candidate_model_mismatches) < 32:
                candidate_model_mismatches.append({**base,
                    "hardware": [f"0x{hw_candidate[0]:08x}", f"0x{hw_candidate[1]:08x}", hw_candidate[2]],
                    "model": [f"0x{model_candidate[0]:08x}", f"0x{model_candidate[1]:08x}", model_candidate[2]]})
    if len(seen) != len(cases) * 32:
        raise ValueError("incomplete block coverage: every initial flag mask is required once per frozen pair")
    return {
        "observations": records,
        "hardware_candidate_reference_mismatch_count": hardware_pair_mismatch_count,
        "hardware_reference_model_mismatch_count": reference_model_mismatch_count,
        "hardware_candidate_model_mismatch_count": candidate_model_mismatch_count,
        "first_hardware_candidate_reference_mismatches": hardware_pair_mismatches,
        "first_hardware_reference_model_mismatches": reference_model_mismatches,
        "first_hardware_candidate_model_mismatches": candidate_model_mismatches,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    require_host()
    with tempfile.TemporaryDirectory(prefix="twosum-hardware-") as temporary:
        temp = Path(temporary)
        pool = temp / "pool.bin"
        input_data, cases = load_cases()
        write_pool(pool, cases)
        case_count = len(cases)
        primitive_exe = temp / "primitive-probe"
        block_exe = temp / "block-probe"
        compile_probe(ROOT / "src" / "sse_primitive_probe.c", primitive_exe)
        compile_probe(ROOT / "src" / "sse_block_probe.c", block_exe)
        primitive_csv = temp / "primitive.csv"
        block_csv = temp / "block.csv"
        for command in ([str(primitive_exe), str(pool), str(primitive_csv)],
                        [str(block_exe), str(pool), str(block_csv)]):
            run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            if run.returncode:
                raise RuntimeError(f"hardware probe failed:\n{run.stdout}{run.stderr}")
        primitive = compare_primitives(primitive_csv)
        blocks = compare_blocks(block_csv)
    report = {
        "host_architecture": platform.machine(),
        "host_cpu_vendor": cpu_vendor(),
        "required_instruction_set": "legacy SSE through SSE4.1",
        "binary32_case_pairs": case_count,
        "coverage": coverage_summary(input_data, cases),
        "primitive": primitive,
        "complete_blocks": blocks,
        "all_comparisons_passed": (
            primitive["mismatch_count"] == 0
            and blocks["hardware_candidate_reference_mismatch_count"] == 0
            and blocks["hardware_reference_model_mismatch_count"] == 0
            and blocks["hardware_candidate_model_mismatch_count"] == 0
        ),
        "interpretation": (
            "Finite conformance on the current x86-64 SSE4.1 host: 18 primitive "
            "observations per frozen pair and 32 initial-flag observations per "
            "complete block. This is diagnostic hardware evidence, not all-input "
            "proof, an Intel-specific certification, or a timing experiment."
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    if not report["all_comparisons_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
