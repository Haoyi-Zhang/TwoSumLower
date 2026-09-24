"""Directed negative tests for the analytic liveness certificate checker."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from liveness_checker import Rejected, verify  # noqa: E402


def mutated(base: dict) -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []

    def add(name: str, mutator) -> None:
        value = copy.deepcopy(base)
        mutator(value)
        cases.append((name, value))

    add("schema", lambda x: x.__setitem__("schema", "v1"))
    add("register-count", lambda x: x.__setitem__("register_count", 5))
    add("event-count", lambda x: x.__setitem__("reference_arithmetic_events", 5))
    add("scope", lambda x: x.__setitem__("scope", "full grammar"))
    add("relaxation", lambda x: x.__setitem__("relaxed_auxiliary", "arbitrary expression"))
    add("top-field", lambda x: x.__setitem__("extra", True))
    add("drop-event", lambda x: x["forced_events"].pop())
    add("first-result", lambda x: x["forced_events"][0].__setitem__("result", "x"))
    add("first-source", lambda x: x["forced_events"][0]["sources"].__setitem__(0, "s"))
    add("first-live", lambda x: x["forced_events"][0]["live_after"].remove("a"))
    add("second-result", lambda x: x["forced_events"][1].__setitem__("result", "s"))
    add("second-source", lambda x: x["forced_events"][1]["sources"].__setitem__(1, "a"))
    add("second-live", lambda x: x["forced_events"][1]["live_after"].remove("s"))
    add("drop-variant", lambda x: x["variants"].pop())
    add("rename-variant", lambda x: x["variants"][0].__setitem__("name", "other"))
    add("initial", lambda x: x["variants"][0]["initial_multiset"].__setitem__(0, "a"))
    add("variant-field", lambda x: x["variants"][0].__setitem__("extra", 0))
    add("expected-min", lambda x: x["variants"][0].__setitem__("expected_minimum_relaxed_auxiliaries", 1))
    add("computed-min", lambda x: x["variants"][0].__setitem__("minimum_relaxed_auxiliaries", 1))
    add("empty-witness", lambda x: x["variants"][0].__setitem__("witness", []))
    add("extra-copy", lambda x: x["variants"][0]["witness"].insert(0, "copy a into zero"))
    add("bad-copy-source", lambda x: x["variants"][0]["witness"].__setitem__(0, "copy x into zero"))
    add("bad-event", lambda x: x["variants"][0]["witness"].__setitem__(-1, "x=op(s,a); overwrite s"))
    add("terminal", lambda x: x["variants"][0]["terminal_multiset"].__setitem__(0, "x"))
    add("control-a-min", lambda x: x["variants"][1].__setitem__("minimum_relaxed_auxiliaries", 0))
    add("control-b-min", lambda x: x["variants"][2].__setitem__("minimum_relaxed_auxiliaries", 0))
    add("control-both-min", lambda x: x["variants"][3].__setitem__("minimum_relaxed_auxiliaries", 1))
    add("aux-bound", lambda x: x.__setitem__("declared_entry_auxiliary_lower_bound", 1))
    add("instruction-bound", lambda x: x.__setitem__("declared_entry_instruction_lower_bound", 7))
    add("non-string-state", lambda x: x["variants"][0]["initial_multiset"].__setitem__(0, 0))
    add("short-state", lambda x: x["variants"][0]["initial_multiset"].pop())
    add("unknown-value", lambda x: x["variants"][0]["initial_multiset"].__setitem__(0, "q"))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    base = json.loads(Path("proofs/liveness-lower-bound.json").read_text())
    verify(base)
    rows = []
    for name, value in mutated(base):
        try:
            verify(value)
            rejected, reason = False, None
        except (Rejected, ValueError, TypeError, KeyError, IndexError) as exc:
            rejected, reason = True, str(exc)
        rows.append({"id": name, "rejected": rejected, "reason": reason})
    report = {
        "schema": "liveness-mutation-result-v1",
        "total": len(rows),
        "rejected": sum(row["rejected"] for row in rows),
        "accepted": sum(not row["rejected"] for row in rows),
        "rows": rows,
        "interpretation": "directed integrity attacks on the liveness certificate, not a proof of the checker itself",
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, sort_keys=True))
    if report["accepted"]:
        raise SystemExit("liveness checker accepted a directed mutation")


if __name__ == "__main__":
    main()
