"""Exact regressions for the binary32 overflow boundary and one internal-overflow trace."""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fpmodel import BINARY32, CANDIDATE, INEXACT, OVERFLOW, execute, reference  # noqa: E402
from oracle import RationalOracle  # noqa: E402


def encoded(result) -> list[int]:
    return [int(result[0]), int(result[1])]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    maximum = (1 << 128) - (1 << 104)
    below = maximum + (1 << 102)
    threshold = maximum + (1 << 103)
    oracle = RationalOracle(8, 23)

    cases = []
    for name, exact, expected in (
        ("M_plus_2^102", below, [0x7F7FFFFF, INEXACT]),
        ("M_plus_2^103_threshold", threshold, [0x7F800000, OVERFLOW | INEXACT]),
    ):
        dyadic = encoded(BINARY32.rounded(exact, 0))
        rational = list(oracle.round(Fraction(exact, 1)))
        if dyadic != expected or rational != expected:
            raise AssertionError({"name": name, "dyadic": dyadic, "rational": rational, "expected": expected})
        cases.append({
            "name": name,
            "exact_integer": str(exact),
            "dyadic": {"word": f"0x{dyadic[0]:08x}", "flags": dyadic[1]},
            "rational": {"word": f"0x{rational[0]:08x}", "flags": rational[1]},
            "expected": {"word": f"0x{expected[0]:08x}", "flags": expected[1]},
        })

    a, b = 0x7F7FFFFF, 0xF3C00000
    rs, re, rf, rtrace = reference(BINARY32, a, b, trace=True)
    cs, ce, cf, _ = execute(BINARY32, CANDIDATE, a, b, trace=True)
    xstep = next(step for step in rtrace if step["name"] == "xeff")
    if not (rs == cs == 0x7F7FFFFE and xstep["result"] == 0x7F800000
            and xstep["raised"] == (OVERFLOW | INEXACT)
            and re == ce == 0xFFC00000 and rf == cf == 21):
        raise AssertionError({"reference": [rs, re, rf], "candidate": [cs, ce, cf], "xeff": xstep})

    report = {
        "maximum_finite": "2^128-2^104",
        "overflow_threshold": "M+2^103=2^128-2^103",
        "exact_rounding_cases": cases,
        "finite_sum_internal_overflow_witness": {
            "a": "0x7f7fffff",
            "b": "0xf3c00000",
            "sum": f"0x{rs:08x}",
            "reference_x": f"0x{xstep['result']:08x}",
            "reference_x_flags": xstep["raised"],
            "final_residual": f"0x{re:08x}",
            "final_flags": rf,
            "candidate_matches_reference": [rs, re, rf] == [cs, ce, cf],
        },
        "passed": True,
        "execution_scope": (
            "Two exact binary32 rounding-helper inputs and one retained program trace. "
            "This regression checks the written boundary and implementations; it is not a new universal proof."
        ),
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
