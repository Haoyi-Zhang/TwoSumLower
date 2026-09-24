# Reviewer guide and artifact-only self-audit

This file is a structured internal self-audit of the frozen paper and artifact. It is not an independent review, an acceptance prediction, or a substitute for accountable human authors and external peer review.

## One-sentence result

Under the explicit masked legacy-SSE entry and observation contract, the retained eight-instruction, thirty-byte block has the same ordered binary32 result words and final five-bit sticky flag projection as the six-event reference for every input pair and initial mask; `(8,30)` is minimal in the declared event-bijective destructive two-address lowering class, not in the full ten-opcode grammar.

## Fast verification path

From the standalone artifact root:

```sh
python reproduce.py --mode quick --output ../replay-quick
```

The quick mode replays the all-input certificate, analytic liveness lower bound, complete event-bijective class search, checker-dependency audit, cross-file evidence audit, static assembly, binary32 diagnostics, and directed equivalence mutations. Full mode adds the complete reduced-format and lower-bound mutation campaigns. Solver controls and native hardware diagnostics remain separate because neither is a theorem dependency.

## Nine-perspective gate

Scores are internal readiness indicators on a 1--5 scale, not external reviewer scores.

| Perspective | Readiness | Confidence | Principal rejection risk | Repair now present | Residual boundary |
|---|---:|---:|---|---|---|
| Scope and significance | 4 | medium | The event-bijective class could look candidate-shaped or narrower than the original superoptimization question. | The paper now identifies the class as lowering a fixed effectful source graph after algebraic optimization is frozen, states a reusable destructive live-source barrier lemma, and reports duplicate-entry controls. | Full ten-opcode optimality is open and must not be inferred. |
| Domain method / compiler relevance | 4 | medium-high | Zeroed temporaries and block-only cost could be mistaken for callable-routine cost. | Entry, outputs, upper lanes, flags, encodings, and excluded ABI work are fixed before the theorem and repeated in the artifact. | Different entry states or ABIs are different optimization problems. |
| Formal correctness | 4 | medium | A bespoke checker may share conceptual errors with the proof. | Written lemmas, three separate checkers, producer/checker separation, a static dependency audit, exact model cross-checks, negative controls, and 206 directed mutations attack distinct failure modes. | No proof-assistant kernel or independently generated proof trace is claimed. |
| Empirical / performance methodology | 4 | high | Finite tests or one native host could be overread as universal proof or speed evidence. | The manuscript separates theorem dependencies from diagnostics and reports zero timing claims. | Native evidence is finite and from one recorded AMD host. |
| Artifact and reproducibility | 5 | high | Stale files, hidden dependencies, or interrupted runs could undermine replay. | Bounded resumable stages, atomic outputs, clean-archive replay, static checker-boundary audit, and cross-file path/cost/byte/frontier checks are included. | Local tool availability and Python/TeX implementations remain in the trusted environment. |
| Related-work adversary | 4 | medium | Numerical TwoSum work, Alive-FP, or superoptimization literature could subsume the result. | The paper distinguishes numerical identities, raw-word/flag refinement, destructive lowering cost, and full-grammar synthesis; 70 cited records have an auditable use ledger. | Literature completeness is not a systematic-review theorem. |
| Generality and boundary attack | 4 | high | Readers may silently transfer the theorem to all SSE programs, other modes, or performance. | The title, abstract, theorem, conclusion, state file, and reproduction report carry the same class qualifier and nonclaims. | General bitwise, selection, multiplication, and non-event-bijective constructions remain unexcluded. |
| Accessibility and story | 4 | medium | Fifty acmsmall pages and a large appendix may obscure the core proof. | The main text follows contract, construction, refinement, lower bound, evidence, and limits; a separate one-column review build is provided. | Editorial shortening may still be desirable after human review. |
| Meta-review / decision synthesis | 4 | medium | Strong correctness but narrow minimum theorem may be judged below TOPLAS significance. | The paper makes the preservation-overhead theorem and exact exceptional refinement the central contribution rather than presenting incomplete full-grammar search as a result. | Venue fit is ultimately an editorial judgment; acceptance cannot be guaranteed internally. |

## Claim-critical trust split

The all-input checker does not import the executable floating-point model or certificate producer. The liveness checker derives the forced prefix and runs a separate 0-1 search. The event-bijective checker independently rebuilds the quotient and frontier. `tests/checker_independence.py` mechanically checks these import/process/network boundaries. This is defect containment within one research workflow; it is not independent authorship.

`tests/evidence_integrity.py` additionally cross-checks the candidate byte string, outputs, `(8,30)` cost, depth-eight frontier, all artifact-local paths named by the claim-evidence ledger, and paper/project-root paths when it runs inside the full package. It detects packaging drift but cannot validate a mathematical lemma by comparing files that all repeat it.

## Questions a skeptical reviewer should ask

1. **Why is the class scientifically meaningful?** It is the exact lowering problem for a fixed six-event effectful source graph when the backend may schedule and orient events but may not replace them with qualitatively different mask-synthesis computations. The theorem measures destructive register-preservation overhead.
2. **Why does the lower bound not prove the original ten-opcode minimum?** The full grammar permits mask construction, selection, min/max, multiplication, and programs that do not preserve the source event multiset. The retained quotient does not conservatively cover those mechanisms.
3. **Why are finite tests present if the theorem is symbolic?** They test implementations, models, certificate corruption handling, and hardware interpretation. They are never used as the universal equivalence argument. The frozen-pool report also exposes category and flag coverage rather than implying it: the primitive corpus exercises underflow 121 times, but none of the 1,000 complete reference pairs raises underflow, so full-block underflow equivalence is supported by the proof, not by extrapolation from the host campaign.
4. **What remains trusted?** The stated SSE semantics, mathematical lemmas, Python runtime and checker code, decoder-to-ISA interpretation, and human inspection of the research claims.
5. **What would strengthen the work further?** A proof-assistant formalization or a replayable full-grammar absence certificate would reduce the trusted base or broaden scope, respectively. Neither exists in this package.

## External-use holds

Before submission, the named human authors must independently verify the proofs, code, references, novelty, contribution statements, and generative-AI disclosure, then assume accountability under the live ACM/TOPLAS policies. The package performs no submission, public upload, correspondence, or independent peer review.
