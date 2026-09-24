# Two preservation barriers

This note proves the eight-instruction lower bound for the declared strong
event-bijective six-register destructive two-address class.  It does **not**
give a lower bound for the full ten-opcode grammar.

The reference dependency graph begins with two forced non-copy events:

1. `s = ADDSS(a,b)`;
2. `x = SUBSS(s,b)`, up to the admitted simultaneous sign reflection.

No later reference event is enabled before these two.  The strong class admits
only copies or semantic identities as auxiliary instructions, so an original
symbolic value that is destroyed cannot be reconstructed by an auxiliary.

## General destructive live-source barrier

Consider any fixed effectful source graph lowered to a destructive two-address
machine. If an enabled source event consumes two distinct symbolic values, both
source values remain live after that event, the result is also live, and the
admitted auxiliary operations cannot reconstruct a destroyed symbolic value,
then the lowering must contain a pre-existing duplicate of at least one source.
The reason is purely cardinal: the destructive instruction overwrites one of the
two source occurrences, yet the post-event state must retain both sources and the
new result. This lemma is independent of the attaining schedule and applies to
other fixed event-graph lowerings with the same hypotheses.

## Application to TwoSum

Immediately after the first event, `a`, `b`, and `s` are simultaneously live:
`a` is needed by the `d_a` event, `b` by the `d_b` event, and `s` by both the
ordered output and later events.  A destructive two-address instruction that
computes `s` overwrites its `a` or `b` destination.  Starting with one occurrence
of each input, at least one input occurrence must therefore have been duplicated.

Immediately after the second event, `a`, `b`, `s`, and `x` are simultaneously
live.  The event producing `x` overwrites its `s` or `b` destination.  Because
all four values are still required and auxiliaries cannot reconstruct a lost
value, a second duplicate must exist.  Thus any class member uses at least two
auxiliaries in addition to the six event-bijective arithmetic instructions:

```
6 event instructions + 2 preservation instructions = 8 instructions.
```

The certificate `liveness-lower-bound.json` checks the same argument in a
strictly more permissive relaxed model: one unit-cost auxiliary may copy any
current nonzero symbolic value into any unused zero register. The independent
checker first reconstructs the six reference descriptors with its own symbolic
normalizer, derives that only `s` and then `x` are enabled, and recomputes the two
live-after sets from the dependency graph. It then obtains minima `2/1/1/0` for
the declared entry, duplicate-`a`, duplicate-`b`, and duplicate-both controls and
replays each witness. The larger
finite event-bijective breadth-first search remains an independent cross-check
of class membership, quotient normalization, and reachability at depth eight.
