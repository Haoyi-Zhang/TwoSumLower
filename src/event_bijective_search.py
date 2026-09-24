"""Produce a finite minimality certificate for event-bijective TwoSum lowerings.

The search is intentionally narrower than the full ten-opcode synthesis grammar.
It enumerates a precisely declared class of two-address ADDSS/SUBSS
reorientations whose six non-copy arithmetic events are in bijection with the
six reference events.  Auxiliary instructions are quotient-neutral zero
additions or proved bitwise identity/copy steps.  Register names are quotiented
by permutation because this class has no implicit-mask register.

The lower-bound search omits NaN provenance, signed-zero, and exact invalid-union
constraints.  That is a relaxation: emptiness through length seven remains a
sound lower bound for the fully checked subclass.  The separate equivalence
certificate establishes that the retained eight-instruction block satisfies the
stronger all-input obligations.
"""
from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

Term = tuple
A: Term = ("input", "a")
B: Term = ("input", "b")
ZERO: Term = ("zero",)


def term_key(term: Term) -> str:
    if term == ZERO:
        return "z"
    if term[0] == "input":
        return "i:" + term[1]
    return term[0] + "(" + term_key(term[1]) + "," + term_key(term[2]) + ")"


def negate(normal: tuple[int, Term]) -> tuple[int, Term]:
    return normal if normal[1] == ZERO else (-normal[0], normal[1])


@lru_cache(maxsize=None)
def canonical(term: Term) -> tuple[int, Term]:
    """Canonical no-input-NaN quotient under commutativity and odd symmetry."""
    if term == ZERO:
        return (1, ZERO)
    if term[0] == "input":
        return (1, term)
    op, left, right = term
    if op == "ADDSS" and (left == ZERO or right == ZERO):
        return canonical(right if left == ZERO else left)
    a = canonical(left)
    b = canonical(right)
    if op == "SUBSS":
        b = negate(b)
    p = tuple(sorted((a, b), key=repr))
    q = tuple(sorted((negate(a), negate(b)), key=repr))
    return (1, ("round", p)) if repr(p) <= repr(q) else (-1, ("round", q))


def reference() -> tuple[tuple[Term, Term], tuple[Term, ...]]:
    s = ("ADDSS", A, B)
    x = ("SUBSS", s, B)
    y = ("SUBSS", s, x)
    dx = ("SUBSS", A, x)
    dy = ("SUBSS", B, y)
    e = ("ADDSS", dx, dy)
    return (s, e), (s, x, y, dx, dy, e)


TARGET_OUTPUTS, TARGET_NODES = reference()
TARGET_DESCRIPTORS = tuple(canonical(node)[1] for node in TARGET_NODES)
if len(set(map(repr, TARGET_DESCRIPTORS))) != 6:
    raise RuntimeError("reference descriptors unexpectedly collide")
DESCRIPTOR_INDEX = {repr(desc): index for index, desc in enumerate(TARGET_DESCRIPTORS)}
ALL_EVENTS = (1 << len(TARGET_DESCRIPTORS)) - 1


def canonical_registers(registers: Iterable[Term]) -> tuple[Term, ...]:
    return tuple(sorted(registers, key=term_key))


def is_relaxed_goal(state: tuple[tuple[Term, ...], int]) -> bool:
    registers, used = state
    return (
        used == ALL_EVENTS
        and TARGET_OUTPUTS[0] in registers
        and any(canonical(term) == canonical(TARGET_OUTPUTS[1]) for term in registers)
    )


def unique_values(registers: Sequence[Term]) -> list[Term]:
    answer: list[Term] = []
    for term in registers:
        if term not in answer:
            answer.append(term)
    return answer


def successors(state: tuple[tuple[Term, ...], int]):
    """Enumerate exact quotient transitions, omitting removable no-ops."""
    registers, used = state
    values = unique_values(registers)
    for old_destination in values:
        remainder = list(registers)
        remainder.remove(old_destination)
        for source in values:
            # Arithmetic transitions.  A zero addition is an auxiliary quotient copy;
            # every other node must consume one previously unused reference descriptor.
            for opcode in ("ADDSS", "SUBSS"):
                result = (opcode, old_destination, source)
                new_used = used
                if not (opcode == "ADDSS" and (old_destination == ZERO or source == ZERO)):
                    index = DESCRIPTOR_INDEX.get(repr(canonical(result)[1]))
                    if index is None or ((used >> index) & 1):
                        continue
                    new_used = used | (1 << index)
                if result == old_destination:
                    continue
                yield canonical_registers((*remainder, result)), new_used

            # Supported quotient identities for ORPS, XORPS, and ANDPS.  Multiple
            # encodings that induce the same state need not be emitted separately.
            identity_results: set[Term] = set()
            if old_destination == ZERO or source == ZERO:
                copied = source if old_destination == ZERO else old_destination
                identity_results.add(copied)  # ORPS or XORPS with zero
                identity_results.add(ZERO)    # ANDPS with zero
            if old_destination == source:
                identity_results.add(ZERO)             # XORPS x,x
                identity_results.add(old_destination)  # ORPS/ANDPS x,x
            for result in identity_results:
                if result == old_destination:
                    continue
                yield canonical_registers((*remainder, result)), used


def search(initial: Sequence[Term], maximum_length: int) -> dict:
    start = (canonical_registers(initial), 0)
    frontier = {start}
    seen = {start}
    frontier_counts: list[int] = []
    goal_counts: list[int] = []
    generated_transition_counts: list[int] = []
    admitted_new_state_counts: list[int] = []
    first_goal = None

    for depth in range(maximum_length + 1):
        goals = sum(1 for state in frontier if is_relaxed_goal(state))
        frontier_counts.append(len(frontier))
        goal_counts.append(goals)
        if goals and first_goal is None:
            first_goal = depth
        if depth == maximum_length:
            break

        next_frontier = set()
        transitions = 0
        new_states = 0
        for state in frontier:
            for successor in successors(state):
                transitions += 1
                if successor in seen:
                    continue
                seen.add(successor)
                next_frontier.add(successor)
                new_states += 1

        next_depth = depth + 1
        # At most one new reference descriptor is consumed per remaining
        # instruction.  Pruning states that cannot reach all six by the requested
        # maximum length cannot remove a goal at or before that maximum.
        frontier = {
            state
            for state in next_frontier
            if state[1].bit_count() + (maximum_length - next_depth) >= len(TARGET_NODES)
        }
        generated_transition_counts.append(transitions)
        admitted_new_state_counts.append(new_states)

    return {
        "initial_multiset": [term_key(term) for term in canonical_registers(initial)],
        "maximum_length": maximum_length,
        "frontier_counts": frontier_counts,
        "goal_counts": goal_counts,
        "generated_transition_counts": generated_transition_counts,
        "admitted_new_state_counts_before_feasibility_pruning": admitted_new_state_counts,
        "unique_states_seen_including_feasibility_pruned": len(seen),
        "minimum_relaxed_goal_length": first_goal,
    }


def build_certificate() -> dict:
    variants = [
        ("declared-entry", (A, B, ZERO, ZERO, ZERO, ZERO), 8),
        ("duplicate-a-control", (A, B, A, ZERO, ZERO, ZERO), 7),
        ("duplicate-b-control", (A, B, B, ZERO, ZERO, ZERO), 7),
        ("duplicate-both-control", (A, B, A, B, ZERO, ZERO), 6),
    ]
    results = []
    for name, initial, cap in variants:
        result = search(initial, cap)
        result["name"] = name
        results.append(result)
    declared = results[0]
    if declared["minimum_relaxed_goal_length"] != 8:
        raise RuntimeError("declared entry did not establish the expected length-eight boundary")
    return {
        "schema": "exception-bijective-two-address-minimality-v1",
        "scope": (
            "Two-address ADDSS/SUBSS reorientations with a bijection to the six "
            "reference arithmetic-event descriptors and only certified quotient "
            "copy/identity auxiliaries"
        ),
        "reference_event_count": len(TARGET_NODES),
        "search_relaxations": [
            "NaN provenance constraints omitted",
            "signed-zero constraints omitted",
            "exact invalid-union constraints omitted",
            "register names quotiented by permutation",
            "removable quotient no-ops omitted",
        ],
        "declared_entry_minimum_instructions": 8,
        "declared_entry_minimum_bytes": 30,
        "byte_argument": (
            "Every class member consumes all six four-byte arithmetic-event "
            "instructions.  The length lower bound leaves two auxiliaries, and "
            "the shortest admitted auxiliary encoding is three bytes."
        ),
        "variants": results,
        "candidate": {
            "program_hex": "0f56d10f56d8f30f58c1f30f5cd0f30f58daf30f58d0f30f5ccaf30f58d9",
            "output_registers": [0, 3],
            "cost": [8, 30],
        },
        "interpretation": (
            "Complete finite exhaustion for the declared event-bijective class; "
            "not a lower bound for the full ten-opcode grammar."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build_certificate()
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "schema": result["schema"],
        "minimum_instructions": result["declared_entry_minimum_instructions"],
        "minimum_bytes": result["declared_entry_minimum_bytes"],
        "declared_goal_states_at_depth_eight": result["variants"][0]["goal_counts"][-1],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
