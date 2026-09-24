"""Produce the small liveness certificate used by the analytic lower bound.

The model is deliberately more permissive than the declared machine class.
At unit cost an auxiliary may duplicate any currently live symbolic value into
an unused zero register.  The first two non-copy events are forced by the
reference DAG: ``s = add(a,b)`` and then ``x = sub(s,b)`` (up to the admitted
simultaneous sign reflection).  Each event is destructive and may overwrite
either source occurrence.

A lower bound in this relaxed model is therefore also a lower bound for the
strong event-bijective two-address class.  This producer is not used as the
checker; :mod:`liveness_checker` implements a separate replay algorithm.
"""
from __future__ import annotations

import argparse
import heapq
import json
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator

ZERO, A, B, S, X = "0", "a", "b", "s", "x"
LIVE_AFTER_S = frozenset((A, B, S))
LIVE_AFTER_X = frozenset((A, B, S, X))


def canonical(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(values))


def copies(state: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], str]]:
    """Duplicate any nonzero value into one unused zero slot."""
    if ZERO not in state:
        return
    for value in sorted(set(state) - {ZERO}):
        work = list(state)
        work.remove(ZERO)
        work.append(value)
        yield canonical(work), f"copy {value} into zero"


def event(
    state: tuple[str, ...], left: str, right: str, result: str
) -> Iterator[tuple[tuple[str, ...], str]]:
    counts = Counter(state)
    if not counts[left] or not counts[right]:
        return
    for overwritten in sorted({left, right}):
        work = list(state)
        work.remove(overwritten)
        work.append(result)
        yield canonical(work), f"{result}=op({left},{right}); overwrite {overwritten}"


def minimum_auxiliaries(initial: tuple[str, ...]) -> dict[str, object]:
    """Dijkstra replay for the two forced destructive events."""
    initial = canonical(initial)
    queue: list[tuple[int, int, tuple[str, ...], tuple[str, ...]]] = [
        (0, 0, initial, ()),
    ]
    best: dict[tuple[int, tuple[str, ...]], int] = {(0, initial): 0}

    while queue:
        cost, phase, state, trace = heapq.heappop(queue)
        if best.get((phase, state)) != cost:
            continue
        if phase == 2:
            return {
                "minimum_relaxed_auxiliaries": cost,
                "witness": list(trace),
                "terminal_multiset": list(state),
            }

        for successor, label in copies(state) or ():
            key = (phase, successor)
            next_cost = cost + 1
            if next_cost < best.get(key, 1 << 30):
                best[key] = next_cost
                heapq.heappush(queue, (next_cost, phase, successor, trace + (label,)))

        if phase == 0:
            transitions = event(state, A, B, S)
            required = LIVE_AFTER_S
        else:
            transitions = event(state, S, B, X)
            required = LIVE_AFTER_X
        for successor, label in transitions or ():
            if not required.issubset(successor):
                continue
            key = (phase + 1, successor)
            if cost < best.get(key, 1 << 30):
                best[key] = cost
                heapq.heappush(queue, (cost, phase + 1, successor, trace + (label,)))
    raise RuntimeError("no relaxed liveness witness")


def build_certificate() -> dict[str, object]:
    variants = (
        ("declared-entry", (A, B, ZERO, ZERO, ZERO, ZERO), 2),
        ("duplicate-a-control", (A, B, A, ZERO, ZERO, ZERO), 1),
        ("duplicate-b-control", (A, B, B, ZERO, ZERO, ZERO), 1),
        ("duplicate-both-control", (A, B, A, B, ZERO, ZERO), 0),
    )
    rows = []
    for name, initial, expected in variants:
        result = minimum_auxiliaries(initial)
        actual = result["minimum_relaxed_auxiliaries"]
        if actual != expected:
            raise RuntimeError(f"unexpected minimum for {name}: {actual}")
        rows.append(
            {
                "name": name,
                "initial_multiset": list(canonical(initial)),
                "expected_minimum_relaxed_auxiliaries": expected,
                **result,
            }
        )
    return {
        "schema": "two-address-liveness-barriers-v2",
        "register_count": 6,
        "forced_events": [
            {"result": S, "sources": [A, B], "live_after": sorted(LIVE_AFTER_S)},
            {"result": X, "sources": [S, B], "live_after": sorted(LIVE_AFTER_X)},
        ],
        "relaxed_auxiliary": "copy any current nonzero value into an unused zero register at unit cost",
        "reference_arithmetic_events": 6,
        "variants": rows,
        "declared_entry_auxiliary_lower_bound": 2,
        "declared_entry_instruction_lower_bound": 8,
        "scope": "strong event-bijective six-register destructive two-address class only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    certificate = build_certificate()
    output.write_text(json.dumps(certificate, indent=2, sort_keys=True) + "\n")
    print(json.dumps(certificate, sort_keys=True))


if __name__ == "__main__":
    main()
