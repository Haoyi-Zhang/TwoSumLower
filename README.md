# minimum-cost-branch-free

A standalone proof-and-replay artifact for one branch-free binary32 TwoSum
lowering. It establishes two results under an explicit legacy SSE contract:

1. an eight-instruction, thirty-byte block preserves both result words and all
   five final sticky IEEE exception flags for every binary32 input pair; and
2. `(8,30)` is the lexicographic minimum in the declared event-bijective
   two-address lowering class.

The second statement is class-relative. This artifact does **not** prove minimum
cost in the complete ten-opcode grammar.

## Certified block and entry contract

```asm
ORPS  xmm2, xmm1
ORPS  xmm3, xmm0
ADDSS xmm0, xmm1
SUBSS xmm2, xmm0
ADDSS xmm3, xmm2
ADDSS xmm2, xmm0
SUBSS xmm1, xmm2
ADDSS xmm3, xmm1
```

Low lanes of `xmm0,xmm1` initially contain inputs `a,b`; outputs are the low lanes
of `xmm0,xmm3`. `xmm2..xmm5` and all upper 96-bit lanes must already be zero, and
inputs are writable. Loads, zeroing, stores, return, and ABI preservation are not
included in `(8,30)`.

Rounding is nearest, ties to even. DAZ and FTZ are disabled and numeric traps are
masked. The observation is the ordered pair of result words plus sticky invalid,
divide-by-zero, overflow, underflow, and inexact. The denormal-operand bit is
excluded. Ordered Intel-SSE NaN source selection, payload/sign retention with
quieting, negative indefinite, signed zeros, and exact instruction encodings are
specified in `proofs/semantics.md` and `proofs/soundness.md`.

## What “minimum” means here

The lower bound has two independent forms. First,
`proofs/liveness-lower-bound.md` proves two forced preservation barriers: after the
first event `a,b,s` are live, and after the second `a,b,s,x` are live. Destructive
two-address updates therefore require two auxiliary copies in addition to the six
event instructions. `src/liveness_checker.py` independently derives the forced
prefix and live sets, then recomputes the bound in a strictly more permissive copy
model and obtains auxiliary minima `2/1/1/0` for the declared and three
duplicate-entry variants.

Second, `proofs/event-bijective-minimality.json` defines a finite relaxed class of
six-register destructive ADDSS/SUBSS lowerings. Its six non-copy arithmetic events
must be in bijection with the ordered reference descriptors, and auxiliaries are
restricted to certified quotient-preserving copies or identities. The search
forgets NaN provenance, signed zero, and exact invalid unions, enlarging the state
space. `src/event_bijective_checker.py` independently reconstructs normalization,
successors, permutation quotient, pruning, frontiers, goals, candidate decoding,
membership, and byte arithmetic. It finds no goal at depths 0--7 and 34 goals at
depth 8. Duplicate-entry controls give instruction minima 7, 7, and 6. The two
lower-bound paths cross-check preservation cost without using an SMT verdict.

## Reproduction

From a fresh extraction, enter this repository root. Use Python 3 with assertions
enabled, a Linux `/proc`, GNU `as`, and `objcopy`. Quick, full, and solver-control
modes use no network, account, GPU, model API, or target-code execution. A local Z3
library is optional and needed only for the fixed solver controls. The separate
hardware mode requires an x86-64 SSE4.1 host and GCC; it executes the admitted
instructions as a finite diagnostic, not as a performance experiment or proof.

```sh
python reproduce.py --mode quick --output ../replay-quick
python reproduce.py --mode full --output ../replay-full
python reproduce.py --mode solver-controls --output ../replay-solver
python reproduce.py --mode hardware --output ../replay-hardware
```

Each output directory must be new or empty and outside the repository. If an outer
launcher interrupts a multi-stage run, repeat the same command with `--resume`;
completed stage outputs are parsed, compared with retained JSON, and skipped only
when they still match. `--stage NAME` runs selected stages and `--list-stages`
prints the names for a mode.

```sh
python reproduce.py --mode full --output ../replay-full --resume
python reproduce.py --mode full --list-stages
```

Stages run sequentially through `src/bounded.py`, with a 110-second CPU limit,
approximately 111-second wall limit, one worker, and a 2,200 MiB address-space cap
per stage. Every completed result is compared with retained JSON, and partial
progress is recorded atomically. Do not run with `python -O`, because assertions
are part of the finite tests.

Quick mode contains eleven stages and full mode contains twenty-one. Direct audit
and certificate commands are:

```sh
python src/bibliography_audit.py --output /tmp/bibliography-audit.json
python src/certificate_checker.py proofs/equivalence.json --output /tmp/equivalence.json
python src/liveness_checker.py proofs/liveness-lower-bound.json --output /tmp/liveness.json
python src/event_bijective_checker.py proofs/event-bijective-minimality.json --output /tmp/minimality.json
python tests/checker_independence.py --output /tmp/checker-independence.json
python tests/hardware_result_contract.py --output /tmp/hardware-result-contract.json
python tests/rounding_boundaries.py --output /tmp/rounding-boundaries.json
python tests/evidence_integrity.py --output /tmp/evidence-integrity.json
```

These commands audit the frozen 70-entry bibliography snapshot and 70-row source
ledger, check all-word block refinement, replay the analytic liveness bound,
reconstruct the complete finite class search, inspect the static dependency
boundary of the three claim-critical checkers, and reconcile the retained
bytes/cost/frontier/path evidence. In the full project, the bibliography
snapshot must agree field-for-field with `paper/references.bib` and the cited-key set
in `paper/main.tex`; in this standalone repository, the same audit runs without a
paper-side dependency. These checks are neither independent peer review nor a
proof-assistant kernel.

## Evidence map

| Evidence | Retained outcome | Main files |
|---|---|---|
| All-word refinement | Accepted; 8 instructions, 30 bytes; six arithmetic correspondences | `proofs/equivalence.json`, `results/symbolic-replay.json` |
| Analytic liveness lower bound | Auxiliary minima 2/1/1/0; instruction lower bound 8 | `proofs/liveness-lower-bound.json`, `results/liveness-lower-bound.json` |
| Event-bijective search cross-check | No goal through 7; 34 at depth 8; candidate membership | `proofs/event-bijective-minimality.json`, `results/event-bijective-minimality.json` |
| Duplicate-entry controls | Minima 7, 7, and 6 with terminal counts 17, 6, and 3 | same certificate/result |
| Liveness mutations | 32/32 directed corruptions rejected | `tests/liveness_mutations.py`, `results/liveness-mutations.json` |
| Search-certificate mutations | 46/46 directed corruptions rejected | `tests/event_bijective_mutations.py`, `results/event-bijective-mutations.json` |
| Static checker boundary | Three claim-critical checkers pass the AST-based forbidden-import/dynamic-execution audit | `tests/checker_independence.py`, `results/checker-independence.json` |
| Package evidence integrity | Candidate bytes, outputs, cost, frontier, and declared evidence paths reconcile | `tests/evidence_integrity.py`, `results/evidence-integrity.json` |
| Static assembly | Exact 30-byte match, independently of the optional host run | `src/kernel.S`, `results/assembly.json` |
| Toy primitive cross-check | 1,179,648 comparisons; zero disagreements | `results/toy-*.json` |
| Toy full programs | All 65,536 input pairs agree | `results/toy-programs.json` |
| Binary32 software diagnostics | 1,000 frozen pairs; zero reported mismatches | `inputs/binary32-cases.json`, `results/binary32.json` |
| Host SSE4.1 conformance | 18,000 primitive and 32,000 complete-block observations; zero mismatches on the recorded host | `src/sse_*_probe.c`, `tests/hardware_conformance.py`, `results/hardware-conformance.json` |
| Hardware result-comparison contract | Host vendor/architecture are provenance-only; changed observation or mismatch fields remain rejecting | `tests/hardware_result_contract.py`, `inputs/hardware-result-contract/*.json`, `results/hardware-result-contract.json` |
| Exact overflow boundary | Both exact implementations return $M$ with inexact only for $M+2^{102}$ and infinity with overflow+inexact at $M+2^{103}$ | `tests/rounding_boundaries.py`, `results/rounding-boundaries.json` |
| Frozen-pool coverage accounting | 180 any-NaN pairs (95 any-sNaN), 92 any-infinity, 179 any-subnormal, 92 any-zero; 121 MULSS primitive underflow contributions, while the ADDSS/SUBSS TwoSum graph freshly raises none | `inputs/binary32-cases.json`, `tests/hardware_conformance.py`, `results/hardware-conformance.json` |
| Equivalence mutations | 96 bad objects rejected; 28 wrong programs refuted; 4 equivalent mutants accepted | `results/mutations.json` |
| Guarded-copy family | 9 variants; 589,824 toy evaluations; zero mismatches | `results/guarded-copies.json` |
| Tininess control | 168 toy disagreements with an incorrect rule | `results/tininess-control.json` |
| Wrong orientation | Exact finite internal-overflow witnesses | `results/toy-programs.json`, `results/binary32.json` |
| Full ten-opcode lower bound | **Open**; retained solver runs are `UNKNOWN` | `results/lower-bound-*.json`, `results/lazy-state.json` |

Toy exhaustion uses a nonstandard eight-bit format with one sign, four exponent,
and three fraction bits. It validates the exact arithmetic implementations and
control behavior but is not a binary32 universal enumeration. The mathematical
proof provides the all-word result.

## Trust and limitations

The trusted base includes the written semantic lemmas, the stated Intel-SSE
interpretation, Python execution, and the checker implementations. Producer/checker
separation reduces common implementation dependencies but does not create
independent authorship. GNU assembly cross-checks bytes without execution. The
optional host mode adds finite instruction-level conformance evidence on the
recorded x86-64 processor, but it does not certify all inputs, Intel-specific
behavior, or performance; no timing conclusion is drawn.

The full ten-opcode grammar includes general ANDPS/ORPS/XORPS, MINSS, MAXSS,
CMPSS, and BLENDVPS behaviors outside the event-bijective class. A shorter program
using those effects has not been excluded. Historical SMT `UNKNOWN` outcomes are
retained as failed feasibility evidence and never reclassified as UNSAT.

The frozen binary32 set has exactly 1,000 pairs, while two earlier diagnostic pairs
outside it remain preserved; strict cumulative compliance with a 1,000-class
historical ceiling is therefore not claimed. See `../CURRENT-STATE.md` in the full
project package for the complete research and external-use holds.

## Layout

- `src/`: exact models, byte decoders, certificate checkers, bounded launchers, and
  historical solver prototypes.
- `proofs/`: human-readable semantics/soundness and machine-readable certificates.
- `tests/`: exhaustive reduced-format checks, mutation suites, controls, static
  assembly comparison, and the optional host-conformance driver.
- `inputs/`: exact frozen diagnostic and historical solver inputs.
- `results/`: retained raw JSON and resource records.
- `REVIEWER-GUIDE.md`: concise trust map, nine-perspective self-audit, skeptical-review questions, and exact external-use holds.
- `claim_evidence_ledger.csv`: claim-to-evidence mapping.
- `reference_snapshot.json`: exact parsed bibliography metadata and cited-key set needed for standalone replay.
- `reference_audit.csv`: one-row-per-citation metadata, identifier, verification, and calibration ledger.
- `external_resources.csv`: external source, tool, license, and integration record.

The artifact is released under the MIT License except for unbundled system tools
and scholarly sources, which retain their own terms.
