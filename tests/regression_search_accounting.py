"""Supplementary accounting coverage; neither a new lower bound nor a timing test."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import event_bijective_checker as checker
import event_bijective_search as producer


def load_certificate():
    return json.loads((ROOT / 'proofs' / 'event-bijective-minimality.json').read_text(encoding='utf-8'))


def accounting_mutations(base):
    paths = [
        ('generated_transition_counts', 3),
        ('admitted_new_state_counts_before_feasibility_pruning', 3),
        ('unique_states_seen_including_feasibility_pruned', None),
        ('goal_counts', 3),
    ]
    result = []
    for field, index in paths:
        changed = deepcopy(base)
        variant = changed['variants'][0]
        if index is None:
            before = variant[field]
            variant[field] += 1
            path = ['variants', 0, field]
        else:
            before = variant[field][index]
            variant[field][index] += 1
            path = ['variants', 0, field, index]
        result.append((path, before, before + 1, changed))
    return result


def different_leaves(left, right, path=()):
    if type(left) is not type(right):
        return [list(path)]
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return [list(path)]
        return [p for key in left for p in different_leaves(left[key], right[key], path + (key,))]
    if isinstance(left, list):
        if len(left) != len(right):
            return [list(path)]
        return [p for i, (a, b) in enumerate(zip(left, right))
                for p in different_leaves(a, b, path + (i,))]
    return [] if left == right else [list(path)]


def spelling(term):
    """Common literal syntax only; no normalization or project sort keys."""
    if term == ('zero',):
        return '0'
    if term[0] in ('input', 'leaf'):
        return term[1]
    tag = {'ADDSS': '+', 'SUBSS': '-', 'plus': '+', 'minus': '-'}[term[0]]
    return '(' + spelling(term[1]) + tag + spelling(term[2]) + ')'


def state_spelling(state):
    registers, mask = state
    return (tuple(sorted(spelling(t) for t in registers)), mask)


def literal_first_edges():
    """All first-step transitions from {a,b,0,0,0,0}, with multiplicity.

    Only the sum event is enabled. Two source orientations consume its bit.
    Zero additions retain their raw shape; bitwise identities copy or erase.
    Erasing either input has two encodings in the distinct-value successor loop.
    """
    entries = [
        (['b', '(a+b)', '0', '0', '0', '0'], 1),
        (['a', '(b+a)', '0', '0', '0', '0'], 1),
        (['b', '(a+0)', '0', '0', '0', '0'], 0),
        (['a', '(b+0)', '0', '0', '0', '0'], 0),
        (['b', '0', '0', '0', '0', '0'], 0),
        (['b', '0', '0', '0', '0', '0'], 0),
        (['a', '0', '0', '0', '0', '0'], 0),
        (['a', '0', '0', '0', '0', '0'], 0),
        (['a', 'b', '(0+a)', '0', '0', '0'], 0),
        (['a', 'b', '(0+b)', '0', '0', '0'], 0),
        (['a', 'b', '(0+0)', '0', '0', '0'], 0),
        (['a', 'a', 'b', '0', '0', '0'], 0),
        (['a', 'b', 'b', '0', '0', '0'], 0),
    ]
    return Counter((tuple(sorted(registers)), mask) for registers, mask in entries)


def snapshot():
    base = load_certificate()
    generated = producer.build_certificate()
    accepted = checker.verify(base)
    mutations = []
    for path, old, new, changed in accounting_mutations(base):
        try:
            checker.verify(changed)
        except ValueError as error:
            outcome = [type(error).__name__, str(error)]
        else:
            outcome = ['accepted']
        mutations.append({'path': path, 'old': old, 'new': new, 'outcome': outcome})
    tiny = []
    for cap in range(3):
        initial = (producer.A, producer.B, producer.ZERO, producer.ZERO, producer.ZERO, producer.ZERO)
        independent_initial = (checker.X, checker.Y, checker.O, checker.O, checker.O, checker.O)
        tiny.append({'producer': producer.search(initial, cap),
                     'checker': checker.replay(independent_initial, cap)})
    return {'complete_generated_certificate': generated, 'accepted': accepted,
            'mutations': mutations, 'bounded_searches': tiny, 'original_after': checker.verify(base)}


class SearchAccountingRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_certificate()
        cls.accepted = checker.verify(cls.base)  # Cold replay before any mutation.

    def test_positive_full_certificate_and_duplicate_controls(self):
        self.assertEqual(producer.build_certificate(), self.base)
        self.assertTrue(self.accepted['accepted'])
        self.assertEqual((self.accepted['minimum_instructions'], self.accepted['minimum_bytes']), (8, 30))
        self.assertEqual(self.base['variants'][0]['unique_states_seen_including_feasibility_pruned'], 68433)
        self.assertEqual([v['minimum_relaxed_goal_length'] for v in self.base['variants']], [8, 7, 7, 6])
        self.assertEqual([v['goal_counts'][-1] for v in self.base['variants']], [34, 17, 6, 3])

    def test_four_single_field_mutations_reject_without_contaminating_original(self):
        untouched = deepcopy(self.base)
        cases = accounting_mutations(self.base)
        self.assertEqual(len(cases), 4)
        self.assertEqual(self.base['variants'][0]['goal_counts'][3], 0)
        for path, old, new, changed in cases:
            with self.subTest(path=path):
                self.assertEqual(different_leaves(self.base, changed), [path])
                self.assertEqual(new, old + 1)
                with self.assertRaisesRegex(ValueError, 'replay mismatch for declared-entry: ' + path[2]):
                    checker.verify(changed)
        self.assertEqual(self.base, untouched)
        self.assertEqual(checker.verify(self.base), self.accepted)

    def test_literal_first_transition_multiset_and_pre_prune_accounting(self):
        raw = (producer.A, producer.B, producer.ZERO, producer.ZERO, producer.ZERO, producer.ZERO)
        independent = (checker.X, checker.Y, checker.O, checker.O, checker.O, checker.O)
        expected = literal_first_edges()
        self.assertEqual(sum(expected.values()), 13)
        self.assertEqual(len(expected), 11)
        self.assertEqual(Counter(state_spelling(s) for s in producer.successors((producer.canonical_registers(raw), 0))), expected)
        self.assertEqual(Counter(state_spelling(s) for s in checker.expand((checker.bag(independent), 0))), expected)
        # Limits one/two cannot consume six events: all 11 new states are seen
        # before pruning, despite every next frontier becoming empty.
        for cap in range(3):
            for result in (producer.search(raw, cap), checker.replay(independent, cap)):
                self.assertEqual(result['frontier_counts'], [1] + [0] * cap)
                self.assertEqual(result['goal_counts'], [0] * (cap + 1))
                self.assertEqual(result['generated_transition_counts'], [] if cap == 0 else [13] + [0] * (cap - 1))
                self.assertEqual(result['admitted_new_state_counts_before_feasibility_pruning'], [] if cap == 0 else [11] + [0] * (cap - 1))
                self.assertEqual(result['unique_states_seen_including_feasibility_pruned'], 1 if cap == 0 else 12)
                self.assertIsNone(result['minimum_relaxed_goal_length'])


if __name__ == '__main__':
    unittest.main()
