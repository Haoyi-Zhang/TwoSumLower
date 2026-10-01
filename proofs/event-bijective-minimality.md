# Event-bijective two-address minimality proof

## Claim and boundary

This proof establishes the lexicographic minimum `(8 instructions, 30 bytes)`
for the declared **event-bijective two-address class**. It does not establish a
minimum in the complete ten-opcode grammar. The attaining block is separately
checked for all binary32 input words and sticky flags by the raw-word
equivalence certificate.

The class contains six-register destructive programs. Exactly six non-copy
`ADDSS` or `SUBSS` instructions must correspond bijectively to the six ordered
arithmetic events of the reference graph

```
s  = ADDSS(a,b)
x  = SUBSS(s,b)
y  = SUBSS(s,x)
dx = SUBSS(a,x)
dy = SUBSS(b,y)
e  = ADDSS(dx,dy)
```

Auxiliary instructions may only induce a certified quotient identity or copy:
`ORPS`/`XORPS` with a zero operand, `ANDPS` with zero, `XORPS r,r`,
`ORPS r,r`, `ANDPS r,r`, or `ADDSS` with zero. The entry multiset is
`{a,b,0,0,0,0}`. The goal contains the literal ordered sum expression
`ADDSS(a,b)`, a quotient-equal residual, and all six distinct event descriptors.

## Analytic instruction lower bound: two preservation barriers

The reference dependency graph forces `s = ADDSS(a,b)` first and
`x = SUBSS(s,b)` second, up to the admitted simultaneous sign reflection. No
other reference event is enabled before `x`.

Immediately after `s`, the values `a`, `b`, and `s` are all live: `a` is needed
by `dx`, `b` by `x` and `dy`, and `s` by the ordered output and later events.
Computing `s` with a destructive two-address instruction overwrites its `a` or
`b` destination. Starting with one occurrence of each input, one input must
therefore have been duplicated before this event.

Immediately after `x`, the values `a`, `b`, `s`, and `x` are all live. Producing
`x` overwrites its `s` or `b` destination. The first duplicate preserves only
the value destroyed while forming `s`; it cannot also preserve whichever source
is destroyed while forming `x`. Strong-class auxiliaries are copies or
identities and cannot reconstruct a lost symbolic value. A second auxiliary is
therefore necessary. Since the class requires exactly six arithmetic events,
every member has at least `6 + 2 = 8` instructions.

`proofs/liveness-lower-bound.json` checks a strictly more permissive abstraction:
a unit-cost auxiliary may copy any current nonzero symbolic value into any unused
zero register. `src/liveness_checker.py` independently recomputes minimum
auxiliary counts `2/1/1/0` for the declared entry, duplicate-`a`, duplicate-`b`,
and duplicate-both controls and replays each witness. Thirty-two directed
mutations attack the schema, scope, forced events, live sets, entry states,
minima, terminal states, and witnesses. This small replay is the primary
executable check of the analytic lower bound.

## Relaxed quotient used for the lower bound

For the lower-bound search only, a term is normalized by:

1. commutativity of rounded addition;
2. simultaneous sign reflection of both operands and the rounded result;
3. elimination of addition with the quotient zero;
4. erasure of register names by multiset canonicalization.

The search omits NaN provenance, signed-zero distinctions, and exact invalid-flag
union constraints. These omissions strictly enlarge the set of admitted
behaviors. Therefore every strongly correct class member maps to a path in the
relaxed graph, while a missing relaxed path rules out a strong path. This is the
one-way implication required for a lower bound; the relaxed search is never used
to prove the attaining block correct.

A state is `(R,M)`, where `R` is a sorted multiset of six normalized symbolic
register expressions and `M` is a six-bit mask of consumed reference-event
descriptors. One destructive instruction replaces one occurrence of a
destination expression. A nonzero arithmetic instruction is admitted only when
its normalized event descriptor is one of the six reference descriptors and its
bit in `M` is not yet set. An admitted copy or identity leaves `M` unchanged.

Register permutation is sound for this class because none of its instructions
has an implicit register operand. In particular, the full grammar's legacy
`BLENDVPS` instruction is outside the class and cannot invalidate this quotient.
The search omits a transition only when it leaves the quotient state unchanged.
Such a no-op cannot be necessary in a shortest path.

## Complete finite search

Breadth-first enumeration starts at the declared entry. At depth `d`, a state is
pruned when its event mask has too few set bits to consume all six descriptors in
the remaining `L-d` instructions. Since one instruction can consume at most one
new descriptor, this pruning cannot remove a goal at or before limit `L`.
Duplicate states are removed only after their complete quotient representation
matches.

For the declared entry and limit eight, the frontier sizes are

```
1, 11, 81, 320, 806, 2159, 2130, 276, 552
```

and the goal counts are

```
0, 0, 0, 0, 0, 0, 0, 0, 34.
```

Thus no relaxed goal is reachable through seven instructions, and 34 quotient
goal states are reachable at eight. Because the strong class is a subset of the
relaxation, this supplies a second eight-instruction lower-bound route and checks
that the class transition system agrees with the smaller liveness argument.

The producer records every frontier count, goal count, transition count,
pre-pruning new-state count, and total number of visited states. The independent
checker reimplements normalization, successor construction, pruning, candidate
decoding, and the complete search without importing the producer, floating-point
model, equivalence checker, or an SMT solver. It requires exact equality with all
retained counts.

## Byte lower bound and attainment

Every class member consumes the six distinct reference events. Every scalar
legacy register-register `ADDSS` or `SUBSS` instruction in the declared encoding
model occupies four bytes. At the instruction minimum of eight, the remaining two
instructions are auxiliaries. The shortest admitted auxiliary encodings occupy
three bytes. Hence every eight-instruction member costs at least

```
6 * 4 + 2 * 3 = 30 bytes.
```

The retained candidate decodes to six scalar arithmetic instructions and two
three-byte `ORPS` copies, reaches the goal, consumes every descriptor once, and
has cost `(8,30)`. It therefore attains the lexicographic lower bound.

## Discriminating duplicate-entry controls

The same complete search is rerun after placing pre-existing input duplicates in
otherwise identical six-register entries. With an extra `a`, the minimum is seven
instructions and there are 17 goals at the bound. With an extra `b`, the minimum
is seven with six goals. With both duplicates, the minimum is six with three
goals. These controls would fail to discriminate if the search were merely
counting the six arithmetic events. Their 8/7/7/6 pattern isolates the two
preservation instructions forced by destructive two-address updates under the
declared entry state.

## Integrity attacks

The liveness mutation suite makes 32 directed changes to every load-bearing field
family, and every altered object is rejected. The finite-search mutation suite has
46 directed corruptions: 32 retained frontier counts, four terminal goal counts,
two declared minima, and eight other fields (class scope, event count, relaxation
inventory, byte argument, interpretation, candidate bytes, candidate output
selectors, and candidate cost). All 46 altered objects are rejected. These tests
attack certificate plumbing and field coverage; they are not independent
mathematical proofs or statistical reliability estimates.
