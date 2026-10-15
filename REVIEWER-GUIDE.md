# Reviewer guide

This guide maps the retained claims, replay commands, and checker trust boundary.

## One-sentence result

Under the explicit masked legacy-SSE entry and observation contract, the retained eight-instruction, thirty-byte block has the same ordered binary32 result words and final five-bit sticky flag projection as the six-event reference for every input pair and initial mask; `(8,30)` is minimal in the declared event-bijective destructive two-address lowering class, not in the full ten-opcode grammar.

## Fast verification path

From the standalone artifact root:

```sh
python reproduce.py --mode quick --output ../replay-quick
```

The quick mode replays the all-input certificate, analytic liveness lower bound, complete event-bijective class search, checker-dependency audit, host-provenance comparison fixtures, exact overflow-boundary regressions, cross-file evidence audit, static assembly, binary32 diagnostics, and directed equivalence mutations. Full mode adds the complete reduced-format and lower-bound mutation campaigns. Solver controls and native hardware diagnostics remain separate because neither is a theorem dependency.

## Claim-critical trust split

The all-input checker does not import the executable floating-point model or certificate producer. The liveness checker derives the forced prefix and runs a separate 0-1 search. The event-bijective checker independently rebuilds the quotient and frontier. `tests/checker_independence.py` mechanically checks these import/process/network boundaries. This is defect containment within one research workflow; it is not independent authorship.

`tests/evidence_integrity.py` additionally cross-checks the candidate byte string, outputs, `(8,30)` cost, depth-eight frontier, all artifact-local paths named by the claim-evidence ledger, and paper/project-root paths when it runs inside the full package. It detects packaging drift but cannot validate a mathematical lemma by comparing files that all repeat it.

## Questions a skeptical reviewer should ask

1. **Why is the class scientifically meaningful?** It is the exact lowering problem for a fixed six-event effectful source graph when the backend may schedule and orient events but may not replace them with qualitatively different mask-synthesis computations. The theorem measures destructive register-preservation overhead.
2. **Why does the lower bound not prove the original ten-opcode minimum?** The full grammar permits mask construction, selection, min/max, multiplication, and programs that do not preserve the source event multiset. The retained quotient does not conservatively cover those mechanisms.
3. **Why are finite tests present if the theorem is symbolic?** They test implementations, models, certificate corruption handling, and hardware interpretation. They are never used as the universal equivalence argument. The primitive corpus's 121 underflow contributions arise in MULSS. The accepted TwoSum graph contains only ADDSS/SUBSS, and the finite-lattice lemma proves those operations cannot freshly raise underflow; final underflow and divide-by-zero equality still requires preservation of arbitrary incoming sticky bits. The multiplication tininess campaign tests the general rounding helper, not dynamic underflow in the accepted graph.
4. **Where is the overflow boundary?** For RNE binary32, the threshold is the midpoint $T_O=M+2^{103}=2^{128}-2^{103}$ between maximum finite $M$ and the next unbounded-exponent precision-24 grid point. The exact regression checks both rounding implementations at $M+2^{102}$ and $T_O$ and separately replays the finite-sum/internal-overflow witness. It does not change either rounding implementation or replace the proof.
5. **Why may hardware replay run on a different vendor?** The produced JSON retains host vendor and architecture as provenance, but replay comparison excludes only those two labels. Observation counts, mismatch counts, coverage, instruction-set requirement, and verdict remain load-bearing. Small JSON fixtures verify that a provenance-only change is accepted and that altered observations or mismatches are rejected; the fixture test itself performs no hardware execution.
6. **What remains trusted?** The stated SSE semantics, mathematical lemmas, Python runtime and checker code, decoder-to-ISA interpretation, and human inspection of the research claims.
7. **What would strengthen the work further?** A proof-assistant formalization or a replayable full-grammar absence certificate would reduce the trusted base or broaden scope, respectively. Neither exists in this package.
