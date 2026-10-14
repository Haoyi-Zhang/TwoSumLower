"""Exact JSON integer and container-shape regressions for the three proof checkers.

This tests input admission only; it does not extend any mathematical search or
interpret a rejected malformed certificate as a new scientific result.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from certificate_checker import verify as verify_equivalence  # noqa: E402
from event_bijective_checker import verify as verify_event  # noqa: E402
from liveness_checker import verify as verify_liveness  # noqa: E402


def proof(name: str) -> dict:
    return json.loads((ROOT / "proofs" / name).read_text())


def replace_at(base: dict, path: tuple[str | int, ...], value: object) -> dict:
    changed = copy.deepcopy(base)
    cursor = changed
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    return changed


class CheckerSchemaRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.equivalence = proof("equivalence.json")
        cls.liveness = proof("liveness-lower-bound.json")
        cls.event = proof("event-bijective-minimality.json")

    def test_original_proofs_still_replay(self) -> None:
        self.assertTrue(verify_equivalence(self.equivalence)["accepted"])
        self.assertTrue(verify_liveness(self.liveness)["certificate_accepted"])
        event = verify_event(self.event)
        self.assertTrue(event["accepted"])
        self.assertEqual((event["minimum_instructions"], event["minimum_bytes"]), (8, 30))
        self.assertEqual(event["declared_entry_goal_states_at_depth_eight"], 34)

    def test_integer_fields_reject_float_and_bool(self) -> None:
        specifications = (
            (verify_equivalence, self.equivalence, (
                ("format", 0), ("format", 1), ("zero_case_s_word",),
                ("zero_case_e_word",), ("zero_case_final_flags", 0),
                ("zero_case_final_flags", 1), ("nan_cases", 0, "invalid"),
                ("nan_cases", 1, "invalid"),
            )),
            (verify_liveness, self.liveness, (
                ("register_count",), ("reference_arithmetic_events",),
                ("declared_entry_auxiliary_lower_bound",),
                ("declared_entry_instruction_lower_bound",),
                ("variants", 0, "expected_minimum_relaxed_auxiliaries"),
                ("variants", 0, "minimum_relaxed_auxiliaries"),
                ("variants", 3, "minimum_relaxed_auxiliaries"),
            )),
            (verify_event, self.event, (
                ("reference_event_count",),
                ("declared_entry_minimum_instructions",),
                ("declared_entry_minimum_bytes",),
                ("variants", 0, "maximum_length"),
                ("variants", 0, "frontier_counts", 0),
                ("variants", 0, "goal_counts", 0),
                ("variants", 0, "generated_transition_counts", 0),
                ("variants", 0, "admitted_new_state_counts_before_feasibility_pruning", 0),
                ("variants", 0, "unique_states_seen_including_feasibility_pruned"),
                ("variants", 0, "minimum_relaxed_goal_length"),
                ("candidate", "cost", 0), ("candidate", "cost", 1),
            )),
        )
        for checker, base, paths in specifications:
            for path in paths:
                original = base
                for key in path:
                    original = original[key]
                self.assertIs(type(original), int)
                for replacement in (float(original), bool(original)):
                    with self.subTest(checker=checker.__module__, path=path,
                                      replacement=repr(replacement)):
                        with self.assertRaises(ValueError):
                            checker(replace_at(base, path, replacement))

    def test_wrong_container_shapes_reject_cleanly(self) -> None:
        for checker, base in ((verify_equivalence, self.equivalence),
                              (verify_liveness, self.liveness),
                              (verify_event, self.event)):
            with self.subTest(checker=checker.__module__, field="top-level"):
                with self.assertRaises(ValueError):
                    checker([])
        malformed = (
            (verify_equivalence, self.equivalence, ("nan_cases",), {}),
            (verify_liveness, self.liveness, ("forced_events", 0), []),
            (verify_liveness, self.liveness, ("variants", 0), []),
            (verify_liveness, self.liveness, ("variants", 0, "name"), []),
            (verify_liveness, self.liveness, ("variants", 0, "witness"), {}),
            (verify_event, self.event, ("variants", 0), []),
            (verify_event, self.event, ("variants", 0, "frontier_counts"), {}),
            (verify_event, self.event, ("candidate",), []),
            (verify_event, self.event, ("candidate", "output_registers"), {}),
        )
        for checker, base, path, replacement in malformed:
            with self.subTest(checker=checker.__module__, path=path):
                with self.assertRaises(ValueError):
                    checker(replace_at(base, path, replacement))


if __name__ == "__main__":
    unittest.main()
