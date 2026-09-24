"""Independent replay checker for the event-bijective minimality certificate.

This file intentionally does not import event_bijective_search,
certificate_checker, fpmodel, an SMT solver, or the certificate producer.  It
recomputes the finite quotient search with separate term names and control flow,
checks the retained counts exactly, and independently decodes class membership
and cost of the supplied legacy SSE block.  The all-input bit/flag theorem is
checked by the separate equivalence checker.
"""
from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path

X = ("leaf", "a")
Y = ("leaf", "b")
O = ("zero",)


def stable(t):
    if t == O:
        return "0"
    if t[0] == "leaf":
        return t[1]
    return t[0] + "[" + stable(t[1]) + ";" + stable(t[2]) + "]"


def flip(pair):
    sign, body = pair
    return pair if body == O else (-sign, body)


@lru_cache(maxsize=None)
def norm(t):
    if t == O:
        return (1, O)
    if t[0] == "leaf":
        return (1, t)
    tag, p, q = t
    if tag == "plus" and (p == O or q == O):
        return norm(q if p == O else p)
    np, nq = norm(p), norm(q)
    if tag == "minus":
        nq = flip(nq)
    direct = tuple(sorted((np, nq), key=repr))
    reflected = tuple(sorted((flip(np), flip(nq)), key=repr))
    if repr(direct) <= repr(reflected):
        return (1, ("rounded", direct))
    return (-1, ("rounded", reflected))


def source_terms():
    total = ("plus", X, Y)
    hi = ("minus", total, Y)
    lo = ("minus", total, hi)
    ex = ("minus", X, hi)
    ey = ("minus", Y, lo)
    error = ("plus", ex, ey)
    return (total, error), (total, hi, lo, ex, ey, error)


OUTS, EVENTS = source_terms()
EVENT_BODY = tuple(norm(e)[1] for e in EVENTS)
BODY_TO_BIT = {repr(body): 1 << i for i, body in enumerate(EVENT_BODY)}
FULL = (1 << len(EVENTS)) - 1


def bag(items):
    return tuple(sorted(items, key=stable))


def values(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def terminal(state):
    registers, mask = state
    if mask != FULL or OUTS[0] not in registers:
        return False
    return any(norm(term) == norm(OUTS[1]) for term in registers)


def expand(state):
    registers, mask = state
    distinct = values(registers)
    for destination in distinct:
        leftovers = list(registers)
        leftovers.remove(destination)
        for source in distinct:
            for tag in ("plus", "minus"):
                made = (tag, destination, source)
                updated_mask = mask
                if not (tag == "plus" and (destination == O or source == O)):
                    bit = BODY_TO_BIT.get(repr(norm(made)[1]))
                    if bit is None or mask & bit:
                        continue
                    updated_mask = mask | bit
                if made != destination:
                    yield (bag((*leftovers, made)), updated_mask)

            possible = set()
            if destination == O or source == O:
                possible.add(source if destination == O else destination)
                possible.add(O)
            if destination == source:
                possible.add(destination)
                possible.add(O)
            for made in possible:
                if made != destination:
                    yield (bag((*leftovers, made)), mask)


@lru_cache(maxsize=None)
def replay(initial, limit):
    origin = (bag(initial), 0)
    current = {origin}
    visited = {origin}
    fronts = []
    goals = []
    transition_counts = []
    new_counts = []
    first = None
    for depth in range(limit + 1):
        number = sum(1 for state in current if terminal(state))
        fronts.append(len(current))
        goals.append(number)
        if number and first is None:
            first = depth
        if depth == limit:
            break
        candidates = set()
        transitions = 0
        fresh = 0
        for state in current:
            for nxt in expand(state):
                transitions += 1
                if nxt in visited:
                    continue
                visited.add(nxt)
                candidates.add(nxt)
                fresh += 1
        new_depth = depth + 1
        current = {
            state for state in candidates
            if state[1].bit_count() + (limit - new_depth) >= len(EVENTS)
        }
        transition_counts.append(transitions)
        new_counts.append(fresh)
    return {
        "initial_multiset": [stable(t) if t != O else "0" for t in bag(initial)],
        "maximum_length": limit,
        "frontier_counts": fronts,
        "goal_counts": goals,
        "generated_transition_counts": transition_counts,
        "admitted_new_state_counts_before_feasibility_pruning": new_counts,
        "unique_states_seen_including_feasibility_pruned": len(visited),
        "minimum_relaxed_goal_length": first,
    }


def decode_legacy(hex_text):
    code = bytes.fromhex(hex_text)
    decoded = []
    i = 0
    while i < len(code):
        begin = i
        if code[i:i+2] == b"\x0f\x54":
            op = "ANDPS"; i += 2
        elif code[i:i+2] == b"\x0f\x56":
            op = "ORPS"; i += 2
        elif code[i:i+2] == b"\x0f\x57":
            op = "XORPS"; i += 2
        elif code[i:i+2] == b"\xf3\x0f" and i + 2 < len(code):
            table = {0x58: "ADDSS", 0x5c: "SUBSS"}
            if code[i+2] not in table:
                raise ValueError("candidate opcode outside checked class")
            op = table[code[i+2]]; i += 3
        else:
            raise ValueError("candidate encoding outside checked class")
        if i >= len(code):
            raise ValueError("missing ModRM")
        modrm = code[i]; i += 1
        if modrm & 0xC0 != 0xC0:
            raise ValueError("memory form outside class")
        d, s = (modrm >> 3) & 7, modrm & 7
        if d >= 6 or s >= 6:
            raise ValueError("register outside class")
        decoded.append((op, d, s, i - begin))
    return code, decoded


def candidate_membership(candidate):
    code, program = decode_legacy(candidate["program_hex"])
    regs = [X, Y, O, O, O, O]
    used = 0
    for op, d, s, _ in program:
        left, right = regs[d], regs[s]
        if op in ("ADDSS", "SUBSS"):
            tag = "plus" if op == "ADDSS" else "minus"
            made = (tag, left, right)
            if not (op == "ADDSS" and (left == O or right == O)):
                bit = BODY_TO_BIT.get(repr(norm(made)[1]))
                if bit is None or used & bit:
                    raise ValueError("candidate arithmetic event is outside the bijection")
                used |= bit
            regs[d] = made
        elif op in ("ORPS", "XORPS") and (left == O or right == O):
            regs[d] = right if left == O else left
        elif op == "ANDPS" and (left == O or right == O):
            regs[d] = O
        elif op == "XORPS" and left == right:
            regs[d] = O
        elif op in ("ORPS", "ANDPS") and left == right:
            regs[d] = left
        else:
            raise ValueError("candidate identity step is outside the declared class")
    outputs = candidate["output_registers"]
    if len(outputs) != 2 or any(type(x) is not int or not 0 <= x < 6 for x in outputs):
        raise ValueError("invalid candidate outputs")
    if regs[outputs[0]] != OUTS[0] or norm(regs[outputs[1]]) != norm(OUTS[1]):
        raise ValueError("candidate does not reach the relaxed class goal")
    if used != FULL:
        raise ValueError("candidate does not consume all reference events")
    cost = [len(program), len(code)]
    if candidate["cost"] != cost:
        raise ValueError("candidate cost mismatch")
    return {"class_member": True, "instructions": cost[0], "bytes": cost[1]}


def verify(document):
    if document.get("schema") != "exception-bijective-two-address-minimality-v1":
        raise ValueError("unexpected schema")
    expected_specs = [
        ("declared-entry", (X, Y, O, O, O, O), 8),
        ("duplicate-a-control", (X, Y, X, O, O, O), 7),
        ("duplicate-b-control", (X, Y, Y, O, O, O), 7),
        ("duplicate-both-control", (X, Y, X, Y, O, O), 6),
    ]
    expected_relaxations = [
        "NaN provenance constraints omitted",
        "signed-zero constraints omitted",
        "exact invalid-union constraints omitted",
        "register names quotiented by permutation",
        "removable quotient no-ops omitted",
    ]
    if document.get("search_relaxations") != expected_relaxations:
        raise ValueError("search relaxation inventory mismatch")
    expected_scope = (
        "Two-address ADDSS/SUBSS reorientations with a bijection to the six "
        "reference arithmetic-event descriptors and only certified quotient "
        "copy/identity auxiliaries"
    )
    if document.get("scope") != expected_scope:
        raise ValueError("scope mismatch")
    if document.get("reference_event_count") != len(EVENTS):
        raise ValueError("reference event count mismatch")
    expected_byte_argument = (
        "Every class member consumes all six four-byte arithmetic-event "
        "instructions.  The length lower bound leaves two auxiliaries, and "
        "the shortest admitted auxiliary encoding is three bytes."
    )
    if document.get("byte_argument") != expected_byte_argument:
        raise ValueError("byte argument mismatch")
    expected_interpretation = (
        "Complete finite exhaustion for the declared event-bijective class; "
        "not a lower bound for the full ten-opcode grammar."
    )
    if document.get("interpretation") != expected_interpretation:
        raise ValueError("interpretation mismatch")
    retained = document.get("variants")
    if not isinstance(retained, list) or len(retained) != len(expected_specs):
        raise ValueError("variant inventory mismatch")
    replayed = []
    producer_initials = {
        "declared-entry": ["i:a", "i:b", "z", "z", "z", "z"],
        "duplicate-a-control": ["i:a", "i:a", "i:b", "z", "z", "z"],
        "duplicate-b-control": ["i:a", "i:b", "i:b", "z", "z", "z"],
        "duplicate-both-control": ["i:a", "i:a", "i:b", "i:b", "z", "z"],
    }
    for stored, (name, initial, limit) in zip(retained, expected_specs):
        actual = replay(initial, limit)
        if stored.get("name") != name:
            raise ValueError("variant name mismatch")
        if stored.get("initial_multiset") != producer_initials[name]:
            raise ValueError(f"initial multiset mismatch for {name}")
        for field, value in actual.items():
            if field == "initial_multiset":
                continue
            if stored.get(field) != value:
                raise ValueError(f"replay mismatch for {name}: {field}")
        replayed.append({"name": name, "minimum_relaxed_goal_length": actual["minimum_relaxed_goal_length"],
                         "goal_states_at_bound": actual["goal_counts"][-1]})
    if replayed[0]["minimum_relaxed_goal_length"] != 8:
        raise ValueError("length-eight lower bound did not replay")
    if [x["minimum_relaxed_goal_length"] for x in replayed[1:]] != [7, 7, 6]:
        raise ValueError("duplicate-input controls did not discriminate")
    member = candidate_membership(document["candidate"])
    if document.get("declared_entry_minimum_instructions") != 8:
        raise ValueError("declared instruction minimum mismatch")
    # Six scalar arithmetic instructions are four bytes each; every admitted
    # auxiliary identity/copy instruction is at least three bytes.
    derived_bytes = 6 * 4 + 2 * 3
    if document.get("declared_entry_minimum_bytes") != derived_bytes:
        raise ValueError("declared byte minimum mismatch")
    if member["instructions"] != 8 or member["bytes"] != derived_bytes:
        raise ValueError("candidate does not attain the lexicographic lower bound")
    if document["candidate"].get("cost") != [8, derived_bytes]:
        raise ValueError("candidate declared cost mismatch")
    return {
        "accepted": True,
        "scope": document["scope"],
        "minimum_instructions": 8,
        "minimum_bytes": derived_bytes,
        "declared_entry_goal_states_at_depth_eight": replayed[0]["goal_states_at_bound"],
        "controls": replayed[1:],
        "candidate": member,
        "search_relaxations_rechecked": document["search_relaxations"],
        "interpretation": "Complete finite replay for the declared class; not full ten-opcode optimality.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = verify(json.loads(Path(args.certificate).read_text()))
    except (ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError) as exc:
        result = {"accepted": False, "error": str(exc)}
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
