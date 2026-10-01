# Executable semantics and oracle boundary

## Word model

For exponent width `E` and fraction width `f`, the word width is `1+E+f`, exponent bias is `2^(E-1)-1`, and the quiet NaN bit is fraction bit `f-1`. Subnormal words use significand `fraction` and exponent `emin-f`; normal words use significand `2^f+fraction` and exponent `stored_exponent-bias-f`. The working models are `(E,f)=(8,23)` and the explicitly nonstandard toy `(4,3)`.

The dyadic implementation stores an exact finite quantity as integer `n` times `2^k`, aligns sums with integer shifts, multiplies significands exactly, and rounds with quotient/remainder and ties-to-even. It never evaluates a numerical operation by executing a host binary32 instruction.

The rational oracle independently converts finite words to exact `Fraction` values. For the toy format it searches an enumerated sorted table of representable nonnegative values; for binary32 it searches the monotone encoding range without enumerating that range. Nearest neighbors and exact rational distances determine rounding. NaN/infinity/zero dispatch is separately implemented. Both implementations use the same written ISA contract; agreement cannot validate a shared misunderstanding of that contract.

## Overflow boundary

For binary32, the largest finite magnitude is `M=(2-2^-23)2^127 = 2^128-2^104`. The next point on the unbounded-exponent precision-24 grid is `2^128`; therefore the round-to-nearest overflow threshold is their midpoint, `T_O=M+2^103=2^128-2^103`. Exact magnitudes in `(M,T_O)` are outside the stored finite range but still round back to `M` with inexact only. At `T_O`, ties-to-even selects the upper grid point and the stored result is infinity with overflow and inexact. In particular, `M+2^102` is `2^102` from `M` and `3*2^102` from `2^128`, so both exact rounding implementations must return word `0x7f7fffff` with only inexact.

`tests/rounding_boundaries.py` checks this case and the exact threshold against both implementations without changing either rounding algorithm. It also replays the finite-sum/internal-overflow witness `a=0x7f7fffff`, `b=0xf3c00000`. These are exact helper and program-trace regressions, not a new universal proof.

## Tininess: a contract-level negative control

Intel SDM Volume 1 section 4.9.1.5 specifies tininess after rounding to destination precision with an *unbounded exponent range*. It is not equivalent to testing whether the final stored result is subnormal.

Let `p=f+1`, `mu=2^(emin-f)`, and `m=2^emin`. Immediately below `m`, the unbounded-exponent p-bit grid has spacing `mu/2`; its nearest predecessor is `m-mu/2`. Its midpoint with `m` is `T=m-mu/4`, and at that midpoint ties-to-even selects `m`. Thus a positive exact result is tiny precisely when it is smaller than `T`. Under masked exceptions the underflow bit is raised only when this tininess condition and final inexactness both hold. A result can therefore store the minimum normal while raising both underflow and inexact.

The test intentionally compares this rule against a wrong stored-subnormal-only rule for every toy MULSS operand pair. The current result contains 168 differences. This detects a shared-contract error that an integer-versus-rational agreement check alone would not reveal. Direct rational binary32 rounding boundary tests use exact dyadics; these are rounding-helper tests, not additional binary32 operand-pair classes or hardware observations.

This multiplication control must not be conflated with the accepted TwoSum graph. That graph contains only ADDSS and SUBSS. For finite binary32 sources, every exact sum or difference is an integer multiple of the minimum subnormal `mu`; a nonzero result below the minimum normal is therefore an exactly representable subnormal, and a zero result is exact. Hence this ADDSS/SUBSS graph cannot freshly raise underflow. Underflow and divide-by-zero remain in the observation because either bit may be set initially and must be preserved by sticky-state equivalence.

## Non-arithmetic opcodes

* ANDPS, ORPS, and XORPS operate on raw words and contribute no numeric flags.
* Legacy BLENDVPS selects the second source when the sign bit of the current pre-instruction `xmm0` low lane is set; otherwise it retains the first source. No numeric flag is generated. There is no freely chosen mask operand.
* MINSS/MAXSS return the second source unchanged if either input is NaN or if ordered operands compare equal, including signed-zero ties. Either quiet or signaling NaN sets invalid. A selected signaling NaN remains signaling.
* CMPSS admits exactly immediates 0..7: equal, less-than, less-or-equal, unordered, not-equal, not-less-than, not-less-or-equal, and ordered. The result is an all-one word or an all-zero word. Predicates 0,3,4,7 raise invalid on signaling NaNs; predicates 1,2,5,6 raise invalid on any NaN. No unordered comparison is silently interpreted as ordinary real comparison.

All six physical registers are writable. Output selectors are an ordered pair in 0..5. No copy or register renaming is implicitly charged zero. The initial zero registers are an explicit precondition; no general-purpose register, literal pool, stack, memory input, or branch is admitted.

## Scope of evidence

The toy primitive campaign performs 18 complete pairwise passes: three arithmetic operations, two MIN/MAX operations, eight comparison predicates, three bitwise operations, and two low-lane blend-mask classes. This is 18 x 65,536 = 1,179,648 primitive comparisons. It does not enumerate all length-eight programs, all machine states, or binary32 words.

Binary32 validation uses 1,000 frozen diagnostic operand pairs, including a 24-word boundary Cartesian product and 424 seeded pairs. Two earlier exploratory SMT-pilot operand pairs lie outside that frozen set. The historical aggregate is therefore 1,002 distinct operand pairs, a two-pair excess if the 1,000-class cap is interpreted cumulatively over pilots and validation; this is retained as a resource-contract hold rather than hidden by reclassifying or deleting inputs. No broader coverage claim is made. The reproduction test preserves the originally frozen set unchanged.

The symbolic proof's eight NaN patterns quantify over arbitrary words of the appropriate classes. They are not a sampling scheme. A successful toy or binary32 finite test cannot replace that proof, and the proof does not certify the full ten-opcode emulator on every binary32 instruction input.
