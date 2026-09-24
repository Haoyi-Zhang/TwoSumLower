"""Independently replay the two preservation barriers in a liveness certificate.

This checker intentionally imports neither the certificate producer nor the
finite event-bijective search.  It uses a separate breadth-first algorithm and
validates both the numeric minima and every retained witness trace.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterable, Iterator

ZERO = "0"
ALLOWED = frozenset((ZERO, "a", "b", "s", "x"))
EXPECTED_VARIANTS = {
    "declared-entry": ("0", "0", "0", "0", "a", "b"),
    "duplicate-a-control": ("0", "0", "0", "a", "a", "b"),
    "duplicate-b-control": ("0", "0", "0", "a", "b", "b"),
    "duplicate-both-control": ("0", "0", "a", "a", "b", "b"),
}


# A second, local symbolic model links the two abstract liveness events to the
# declared event-bijective reference graph.  It deliberately shares no code with
# event_bijective_search.py or event_bijective_checker.py.
TA = ("leaf", "a")
TB = ("leaf", "b")
TZ = ("zero",)


def flip_normal(value: tuple[int, tuple]) -> tuple[int, tuple]:
    sign, body = value
    return value if body == TZ else (-sign, body)


def normalize_term(term: tuple) -> tuple[int, tuple]:
    if term == TZ:
        return (1, TZ)
    if term[0] == "leaf":
        return (1, term)
    opcode, left, right = term
    if opcode == "plus" and (left == TZ or right == TZ):
        return normalize_term(right if left == TZ else left)
    a = normalize_term(left)
    b = normalize_term(right)
    if opcode == "minus":
        b = flip_normal(b)
    direct = tuple(sorted((a, b), key=repr))
    reflected = tuple(sorted((flip_normal(a), flip_normal(b)), key=repr))
    if repr(direct) <= repr(reflected):
        return (1, ("rounded", direct))
    return (-1, ("rounded", reflected))


def derive_forced_prefix() -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    s = ("plus", TA, TB)
    x = ("minus", s, TB)
    y = ("minus", s, x)
    da = ("minus", TA, x)
    db = ("minus", TB, y)
    error = ("plus", da, db)
    named_terms = (("s", s), ("x", x), ("y", y), ("da", da), ("db", db), ("e", error))
    bodies = {repr(normalize_term(term)[1]): name for name, term in named_terms}
    reject(len(bodies) == len(named_terms), "reference event descriptors collide")

    def enabled(values: tuple[tuple, ...], consumed: set[str]) -> set[str]:
        found: set[str] = set()
        for left in values:
            for right in values:
                for opcode in ("plus", "minus"):
                    if opcode == "plus" and (left == TZ or right == TZ):
                        continue  # quotient copy, not a reference arithmetic event
                    name = bodies.get(repr(normalize_term((opcode, left, right))[1]))
                    if name is not None and name not in consumed:
                        found.add(name)
        return found

    first = enabled((TA, TB, TZ), set())
    reject(first == {"s"}, f"reference graph does not force s first: {sorted(first)}")
    second = enabled((TA, TB, s, TZ), {"s"})
    reject(second == {"x"}, f"reference graph does not force x second: {sorted(second)}")

    dependencies = (
        ("s", ("a", "b")),
        ("x", ("s", "b")),
        ("y", ("s", "x")),
        ("da", ("a", "x")),
        ("db", ("b", "y")),
        ("e", ("da", "db")),
    )
    outputs = {"s", "e"}

    def live_after(prefix_length: int, available: set[str]) -> list[str]:
        required = set(outputs)
        for _, sources in dependencies[prefix_length:]:
            required.update(sources)
        return sorted(available & required)

    live_s = live_after(1, {"a", "b", "s"})
    live_x = live_after(2, {"a", "b", "s", "x"})
    derived = (
        {"result": "s", "sources": ["a", "b"], "live_after": live_s},
        {"result": "x", "sources": ["s", "b"], "live_after": live_x},
    )
    return derived, ("s", "x")


class Rejected(ValueError):
    """The retained certificate is malformed or states a false result."""


def reject(condition: bool, message: str) -> None:
    if not condition:
        raise Rejected(message)


def canon(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(sorted(values))
    reject(len(result) == 6, "every liveness state must contain six registers")
    reject(set(result).issubset(ALLOWED), "unknown symbolic value in liveness state")
    return result


def copy_edges(state: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
    if ZERO not in state:
        return
    for value in set(state):
        if value == ZERO:
            continue
        next_state = list(state)
        next_state[next_state.index(ZERO)] = value
        yield tuple(sorted(next_state))


def event_edges(
    state: tuple[str, ...], sources: tuple[str, str], result: str
) -> Iterator[tuple[str, ...]]:
    left, right = sources
    counts = Counter(state)
    if counts[left] == 0 or counts[right] == 0:
        return
    for victim in set(sources):
        next_state = list(state)
        next_state[next_state.index(victim)] = result
        yield tuple(sorted(next_state))


def minimum_copies(initial: tuple[str, ...], events: tuple[dict[str, Any], ...]) -> int:
    """0-1 BFS: event edges cost zero; relaxed copies cost one."""
    start = (0, canon(initial))
    distance: dict[tuple[int, tuple[str, ...]], int] = {start: 0}
    queue = deque([start])
    while queue:
        phase, state = queue.popleft()
        cost = distance[(phase, state)]
        if phase == len(events):
            return cost

        for successor in copy_edges(state) or ():
            key = (phase, successor)
            if cost + 1 < distance.get(key, 1 << 30):
                distance[key] = cost + 1
                queue.append(key)

        spec = events[phase]
        sources = tuple(spec["sources"])
        required = set(spec["live_after"])
        for successor in event_edges(state, sources, spec["result"]) or ():
            if not required.issubset(successor):
                continue
            key = (phase + 1, successor)
            if cost < distance.get(key, 1 << 30):
                distance[key] = cost
                queue.appendleft(key)
    raise Rejected("relaxed liveness instance has no terminal state")


def replay_witness(
    initial: tuple[str, ...], events: tuple[dict[str, Any], ...], witness: list[str]
) -> tuple[int, tuple[str, ...]]:
    state = canon(initial)
    phase = 0
    copies = 0
    for step in witness:
        if step.startswith("copy ") and step.endswith(" into zero"):
            reject(ZERO in state, "witness copy has no unused zero register")
            value = step[len("copy ") : -len(" into zero")]
            reject(value in state and value != ZERO, "witness copies an unavailable value")
            work = list(state)
            work[work.index(ZERO)] = value
            state = tuple(sorted(work))
            copies += 1
            continue
        reject(phase < len(events), "witness contains an extra event")
        spec = events[phase]
        expected_prefix = f"{spec['result']}=op({spec['sources'][0]},{spec['sources'][1]}); overwrite "
        reject(step.startswith(expected_prefix), "witness event does not match forced prefix")
        victim = step[len(expected_prefix) :]
        reject(victim in spec["sources"], "witness overwrites a non-source")
        reject(victim in state, "witness overwrites an absent source")
        other = spec["sources"][1] if victim == spec["sources"][0] else spec["sources"][0]
        reject(other in state, "witness lacks the other event source")
        work = list(state)
        work[work.index(victim)] = spec["result"]
        state = tuple(sorted(work))
        reject(set(spec["live_after"]).issubset(state), "witness violates a live-after barrier")
        phase += 1
    reject(phase == len(events), "witness does not execute both forced events")
    return copies, state


def verify(data: dict[str, Any]) -> dict[str, Any]:
    reject(isinstance(data, dict), "certificate must be a JSON object")
    expected_top = {
        "schema",
        "register_count",
        "forced_events",
        "relaxed_auxiliary",
        "reference_arithmetic_events",
        "variants",
        "declared_entry_auxiliary_lower_bound",
        "declared_entry_instruction_lower_bound",
        "scope",
    }
    reject(set(data) == expected_top, "unexpected top-level liveness fields")
    reject(data["schema"] == "two-address-liveness-barriers-v2", "wrong liveness schema")
    reject(data["register_count"] == 6, "wrong register count")
    reject(data["reference_arithmetic_events"] == 6, "wrong event count")
    reject(data["scope"] == "strong event-bijective six-register destructive two-address class only", "wrong scope")
    reject(
        data["relaxed_auxiliary"]
        == "copy any current nonzero value into an unused zero register at unit cost",
        "wrong relaxation",
    )

    raw_events = data["forced_events"]
    reject(isinstance(raw_events, list) and len(raw_events) == 2, "two forced events required")
    events = tuple(raw_events)
    expected_events, forced_prefix = derive_forced_prefix()
    reject(events == expected_events, "forced-event or live-set mismatch")

    rows = data["variants"]
    reject(isinstance(rows, list) and len(rows) == 4, "four entry variants required")
    reject({row.get("name") for row in rows} == set(EXPECTED_VARIANTS), "entry variants mismatch")
    minima: dict[str, int] = {}
    for row in rows:
        expected_fields = {
            "name",
            "initial_multiset",
            "expected_minimum_relaxed_auxiliaries",
            "minimum_relaxed_auxiliaries",
            "witness",
            "terminal_multiset",
        }
        reject(set(row) == expected_fields, "unexpected variant fields")
        name = row["name"]
        initial = canon(row["initial_multiset"])
        reject(initial == EXPECTED_VARIANTS[name], f"wrong initial multiset for {name}")
        minimum = minimum_copies(initial, events)
        reject(row["expected_minimum_relaxed_auxiliaries"] == minimum, f"wrong expected minimum for {name}")
        reject(row["minimum_relaxed_auxiliaries"] == minimum, f"wrong computed minimum for {name}")
        copies, terminal = replay_witness(initial, events, row["witness"])
        reject(copies == minimum, f"nonminimal witness for {name}")
        reject(list(terminal) == row["terminal_multiset"], f"wrong terminal multiset for {name}")
        minima[name] = minimum

    reject(minima == {
        "declared-entry": 2,
        "duplicate-a-control": 1,
        "duplicate-b-control": 1,
        "duplicate-both-control": 0,
    }, "control minima do not match 2/1/1/0")
    reject(data["declared_entry_auxiliary_lower_bound"] == 2, "wrong auxiliary lower bound")
    reject(data["declared_entry_instruction_lower_bound"] == 8, "wrong instruction lower bound")
    reject(
        data["declared_entry_instruction_lower_bound"]
        == data["reference_arithmetic_events"] + data["declared_entry_auxiliary_lower_bound"],
        "instruction lower bound does not decompose into events plus auxiliaries",
    )
    return {
        "schema": "liveness-check-result-v1",
        "certificate_accepted": True,
        "independent_algorithm": (
            "independent symbolic forced-prefix derivation plus zero-one breadth-first search "
            "and explicit witness replay"
        ),
        "forced_prefix_derived": list(forced_prefix),
        "live_sets_derived": [event["live_after"] for event in expected_events],
        "reference_descriptors_distinct": True,
        "variant_minima": minima,
        "declared_entry_auxiliary_lower_bound": 2,
        "declared_entry_instruction_lower_bound": 8,
        "scope": data["scope"],
        "interpretation": (
            "A mechanically replayed analytic lower bound for the declared class; "
            "it is neither a full-ten-opcode lower bound nor independent human review."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.certificate).read_text())
    report = verify(data)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
