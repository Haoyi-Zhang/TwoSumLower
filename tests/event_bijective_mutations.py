"""Directed corruptions of the finite event-bijective minimality certificate."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from event_bijective_checker import verify  # noqa: E402


def rejected(document) -> bool:
    try:
        verify(document)
    except (ValueError, TypeError, KeyError, IndexError):
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    base = json.loads((ROOT / "proofs" / "event-bijective-minimality.json").read_text())
    mutants = []

    # Every retained frontier count is load-bearing and independently recomputed.
    for vi, variant in enumerate(base["variants"]):
        for di in range(len(variant["frontier_counts"])):
            m = copy.deepcopy(base)
            m["variants"][vi]["frontier_counts"][di] += 1
            mutants.append((f"frontier-{vi}-{di}", m))

    # Each terminal goal count and summary boundary is also checked.
    for vi, variant in enumerate(base["variants"]):
        m = copy.deepcopy(base)
        m["variants"][vi]["goal_counts"][-1] += 1
        mutants.append((f"goal-{vi}", m))
    for field, replacement in (("declared_entry_minimum_instructions", 7),
                               ("declared_entry_minimum_bytes", 29)):
        m = copy.deepcopy(base); m[field] = replacement
        mutants.append((field, m))

    # Scope, relaxations, candidate cost, outputs, and encoding are checked.
    m = copy.deepcopy(base); m["scope"] += " altered"; mutants.append(("scope", m))
    m = copy.deepcopy(base); m["reference_event_count"] = 5; mutants.append(("event-count", m))
    m = copy.deepcopy(base); m["byte_argument"] += " altered"; mutants.append(("byte-argument", m))
    m = copy.deepcopy(base); m["interpretation"] += " altered"; mutants.append(("interpretation", m))
    m = copy.deepcopy(base); m["search_relaxations"] = m["search_relaxations"][:-1]; mutants.append(("relaxations", m))
    m = copy.deepcopy(base); m["candidate"]["cost"] = [8, 29]; mutants.append(("candidate-cost", m))
    m = copy.deepcopy(base); m["candidate"]["output_registers"] = [0, 2]; mutants.append(("candidate-output", m))
    m = copy.deepcopy(base)
    raw = bytearray.fromhex(m["candidate"]["program_hex"]); raw[1] = 0x54
    m["candidate"]["program_hex"] = raw.hex(); mutants.append(("candidate-opcode", m))

    failures = [name for name, document in mutants if not rejected(document)]
    breakdown = {
        "frontier_counts": sum(len(v["frontier_counts"]) for v in base["variants"]),
        "terminal_goal_counts": len(base["variants"]),
        "declared_minima": 2,
        "other_load_bearing_fields": 8,
    }
    assert sum(breakdown.values()) == len(mutants) == 46
    result = {
        "mutations": len(mutants),
        "breakdown": breakdown,
        "rejected": len(mutants) - len(failures),
        "accepted_corruptions": failures,
        "all_corruptions_rejected": not failures,
        "interpretation": "Directed certificate-integrity checks, not independent proof or a statistical reliability estimate.",
    }
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
