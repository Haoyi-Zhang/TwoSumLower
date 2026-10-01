# Soundness of the supplied equivalence certificate

## Status and exact claim

This is a mathematical argument checked by an executable, restricted symbolic checker. It is not a proof-assistant development, an independently reviewed theorem, or a SAT/SMT UNSAT certificate. This file proves the all-word refinement obligation, not minimality; the separate `event-bijective-minimality.md` and its independent finite checker establish the class-relative minimum. The checker has an implementation separate from the certificate producer, dyadic model, and rational oracle; the same research workflow developed all of them.

**Theorem.** For every pair of binary32 input words `a,b` and every initial five-flag mask `F` in `0..31`, the byte sequence in `equivalence.json` returns the same ordered pair of result words and final five-flag mask as the six-operation reference below, under the declared masked Intel-SSE semantics and register-entry precondition. Its exact static block cost is `(8,30)` in the declared instruction/byte lexicographic order. No lower-cost exclusion follows.

The theorem concerns refinement of this specific operational reference. It does not claim that the two returned values sum to the exact real sum on exceptional inputs. In particular, an infinite sum or an internally overflowing reference can produce a NaN residual, and the implementation must preserve that behavior.

## 1. Contract

Words have 1 sign bit, 8 exponent bits, and 23 fraction bits. Precision is 24, exponent bias 127, and the smallest positive subnormal is `mu = 2^-149`. Rounding is nearest with ties to even; gradual underflow is enabled (`DAZ=FTZ=0`); all numeric exceptions, including the denormal-operand exception, are masked. The observed flags are invalid, divide-by-zero, overflow, underflow, and inexact. The denormal-operand status bit and other machine state are not part of the observation.

For arithmetic NaN propagation, the first source is selected if it is a NaN, otherwise the second NaN source is selected; the quiet bit is set and other bits are retained. An sNaN in either source sets invalid. An invalid arithmetic operation with no input NaN returns the fixed negative indefinite word `0xffc00000`. These are the Intel SDM SSE rules used in this project, not a claim that IEEE 754 alone fixes all payload choices.

Registers `xmm0,xmm1` initially contain `a,b` in their low lanes. Registers `xmm2..xmm5` are initially all-zero. All upper 96 bits of every register are zero. The inputs are writable. Only the ten named legacy register-to-register opcodes are admitted; there is no free copy, memory operand, VEX form, or hidden constant. The zeroed-entry condition is a precondition, not a cost-free claim about a callable ABI function.

The certificate's program uses only ADDSS, SUBSS, and bitwise copies. The checker decodes all ten opcodes so it can reject outside encodings, but the proof language is intentionally incomplete for general uses of the other opcodes.

## 2. Reference and block

Writing `+r` and `-r` for ordered rounded operations, the reference is:

```
s  = a +r b
x  = s -r b
y  = s -r x
dx = a -r x
dy = b -r y
e  = dx +r dy
```

The byte-checked block, in Intel destination-first assembly notation, is:

```
ORPS  xmm2, xmm1     # copy b
ORPS  xmm3, xmm0     # copy a
ADDSS xmm0, xmm1     # s
SUBSS xmm2, xmm0     # n = b -r s
ADDSS xmm3, xmm2     # dx'
ADDSS xmm2, xmm0     # y'
SUBSS xmm1, xmm2     # dy'
ADDSS xmm3, xmm1     # e'
```

The outputs are `xmm0,xmm3`. Copies are exact on every bit pattern and set no observed flag. They do not quiet signaling NaNs. The proof separates (i) inputs without NaNs, including infinities, (ii) signed-zero output bits, and (iii) inputs containing NaNs. The cases are exhaustive and disjoint except for signed zeros, which refine case (i).

## 3. A closed quotient for inputs without NaNs

Let `Q` be the set of finite binary32 values, with the two zero encodings identified, together with the two infinities and one additional value `N`. `N` denotes the fixed indefinite NaN. Define a conceptual involution `neg` which negates finite nonzero values and infinities and fixes zero and `N`. It is not implemented by toggling a NaN sign bit.

Starting from inputs without NaNs, the supported arithmetic/copy fragment can generate no NaN other than `N`. This follows inductively: copies preserve operands; an invalid ADDSS or SUBSS without an input NaN generates indefinite; an operation receiving indefinite propagates the same quiet NaN. Hence `Q` is closed under this fragment.

Let `U(x,y)` be rounded addition on `Q`. Signed zeros are forgotten, and any invalid result is represented by `N`. Let `E(x,y)` be the five-bit flag contribution of that operation. Flags from child expressions are not included in `E`; program flags are the union of contributions from executed nodes.

**Lemma 1 (symmetry).** For every `x,y` in `Q`:

```
U(x,y) = U(y,x)
U(neg(x),neg(y)) = neg(U(x,y))
E(x,y) = E(y,x) = E(neg(x),neg(y))
```

For finite operands, exact addition is commutative and odd. The finite representable set, including subnormal values, is symmetric, and ties-to-even rounding respects this symmetry. The binary32 overflow threshold is `M+2^103=2^128-2^103`, which is symmetric in sign, and the masked infinities are sign-reflections. The decision whether a finite operation is exact or overflows does not depend on simultaneous sign reversal or operand exchange. Lemma 3 strengthens the underflow component for this graph: ADDSS/SUBSS never freshly raise it. For infinities, the same-sign, opposite-sign, and finite-plus-infinite cases verify the identities directly. For `N`, the quiet NaN propagates and contributes no new invalid flag; conceptual negation fixes it. Generated invalid results, from opposite infinities, yield the same `N` and invalid bit under each symmetry. Zero signs cannot change any of the five flag contributions. This covers all cases.

**Lemma 2 (subtraction representation).** On `Q`, ordered subtraction and its newly generated flags are represented by `U(x,neg(y))` and `E(x,neg(y))`. No statement about sign-toggling an arbitrary input NaN is made.

The finite and infinite cases follow from their subtraction rules. The only NaN in `Q` is the same quiet indefinite before and after conceptual negation, so propagation also agrees.

## 4. Rounded-value equality and flag correspondence

All equalities in this subsection are in `Q`. Put `s=U(a,b)` and `x=U(s,neg(b))`. The block computes

```
n = U(b,neg(s)) = neg(x)
dx' = U(a,n) = U(a,neg(x)) = dx
y' = U(n,s) = U(s,neg(x)) = y
dy' = U(b,neg(y')) = dy
e' = U(dx',dy') = e.
```

The first equality for `n` uses simultaneous negation and commutativity; later ones substitute equal quotient values. These equalities do not assume a finite rounded sum, an absence of internal overflow, exact virtual operands, or an error-free-transform theorem.

The arithmetic nodes of the candidate correspond to reference node indices `[0,1,3,2,4,5]`, with result orientations `[+,-,+,+,+,+]`. The newly generated flags agree pairwise by Lemma 1 or Lemma 2. Every reference arithmetic node occurs exactly once in the correspondence; every candidate arithmetic node is accounted for. Reordering the two virtual/error computations is permitted because the observation is final sticky flags, not exception timing, and all traps are masked.

Therefore both programs have equal sum and residual values in `Q` and equal unions of freshly generated flags on all inputs without NaNs. Distinct nonzero finite values and infinities have unique binary32 encodings. Generated `N` has one fixed encoding. Only the two zero encodings remain to be distinguished.

## 5. Signed-zero discharge

**Lemma 3 (no rounded nonzero cancellation to zero).** For finite binary32 operands, the exact sum or difference is an integer multiple of `mu`. If it is nonzero, its magnitude is at least `mu`, so nearest rounding cannot produce zero. Any exact result smaller in magnitude than the minimum normal is itself a representable subnormal, so ADDSS/SUBSS cannot newly raise the masked underflow flag in this contract.

The lemma is about sums/differences, not products. The general MULSS model needs the separate tininess rule described in `semantics.md`.

It follows that an ADDSS result is negative zero exactly when both operands are negative zero. A SUBSS result is negative zero exactly when its left operand is negative zero and its right operand is positive zero. Exact cancellation of equal nonzero operands produces positive zero under nearest rounding.

**Lemma 4 (the reference residual is never negative zero).** If its final addition returned negative zero, both `dx` and `dy` would have to be negative zero. The necessary left-operand conditions of their subtractions force `a=b=-0`. Direct signed-zero propagation at these inputs gives:

```
s=-0, x=+0, y=-0, dx=-0, dy=+0, e=+0.
```

This contradicts the required negative-zero residual.

**Lemma 5 (the candidate residual is never negative zero).** If `e'` were negative zero, `dx'` and `dy'` would both be negative zero. `dx'=a+r n` requires `a=n=-0`. `n=b-r s` requires `b=-0`. Thus again both inputs must be negative zero. Direct propagation gives:

```
s=-0, n=+0, dx'=+0, y'=+0, dy'=-0, e'=+0.
```

This is a contradiction. The checker's recursive necessary-condition analysis may omit the positive-zero condition of a subtraction's right operand: that weakens a necessary condition, so it is safe for this exclusion proof.

Finally, the checker requires the sum output to have exactly the same ordered raw addition expression `ADDSS(a,b)` in both programs. Thus its signed-zero bit agrees directly. Lemmas 4 and 5 lift the quotient equality of the residual to exact word equality.

## 6. Arbitrary input NaNs

This proof cannot reuse Lemma 1 on arbitrary NaN payloads: ordered source priority makes raw arithmetic noncommutative on NaNs, and subtraction does not negate an input NaN's sign.

Instead, attach to each input NaN its symbolic origin (`a` or `b`), its entire arbitrary sign/payload word, and a signaling bit. An arithmetic operation with a NaN source returns the quieted first NaN source; it raises invalid precisely when at least one source is signaling. The symbolic checker recursively propagates these origins in the actual ordered graph.

There are eight symbolic input patterns: two with only `a` NaN (quiet or signaling), two with only `b` NaN, and four with both NaN. Each pattern universally quantifies over its allowed payloads and signs and over every value of any non-NaN input. These are not eight representative bit-pattern tests.

In each pattern, every executed arithmetic node of both programs has a NaN operand. Consequently no such node raises overflow, underflow, divide-by-zero, or inexact. The first ordered addition sees both original operands and raises invalid if either is signaling. Later reuses of an original signaling operand may raise invalid again but cannot change the final sticky union. Both outputs have origin `a` when `a` is NaN, and origin `b` otherwise, with the quiet bit set. The eight rows in the certificate are compared with a separately computed symbolic propagation for both programs.

Intermediate NaN payloads need not be equal: with two NaN inputs, the reflected subtraction can propagate `b` where the reference propagates `a`. The proof requires only the specified final observations and verifies their origins directly.

## 7. All initial flag states and upper lanes

If both programs generate the same fresh flag union `G`, an arbitrary initial flag mask `F` yields `F | G` for both. Neither block reads nor clears status. This proves equality simultaneously for all 32 initial flag masks. The all-negative-zero evidence in the certificate additionally checks the concrete identity map on those masks; it is not a replacement for the symbolic union argument.

Legacy scalar arithmetic and CMPSS preserve the destination's upper 96 bits. Bitwise instructions combine zero upper lanes into zero. BLENDVPS sees zero upper mask lanes in `xmm0`, so it retains zero upper destination lanes. Thus the all-zero upper-lane precondition is invariant under the whole frozen grammar. The numerical certificate only admits a smaller fragment, but its low-lane proof therefore denotes a well-defined legacy block.

## 8. Decoder, cost, and general checker soundness

The decoder recognizes only the listed legacy register encodings, rejects memory ModRM forms, rejects registers above `xmm5`, rejects non-legacy CMPSS immediates, and rejects a length outside 1..8. It derives register operands and instruction lengths from the bytes rather than trusting a textual disassembly. Register indices and the two cost components are range-checked; costs must be unsigned 64-bit integers. There are no displacement/immediate costs except the CMPSS predicate byte, and no REX or VEX encodings.

The symbolic state transformer admits ADDSS and SUBSS plus only these bitwise identities: OR/XOR with an all-zero operand copy the other operand; AND with zero and XOR of identical words produce zero; OR/AND of identical words preserve that word. All are exact and flag-free. In particular, a general AND/OR/XOR expression is not treated as a numerical identity.

For the supplied eight-instruction block, each raw arithmetic expression normalizes using only Lemmas 1 and 2: recursive normalization of its children, operand exchange, and simultaneous conceptual negation. Induction on its syntax proves that equal signed normal forms have equal `Q` denotations. Equal root descriptors also have equal newly generated flags, by the same induction on their operands and Lemma 1. The checked bijection accounts for every non-copy arithmetic instruction, including non-output instructions. The guarded zero-addition rule below accounts separately for any excluded arithmetic copies; none occurs in the primary block. The separate zero and NaN obligations then lift the quotient proof to exact final observations.

These arguments establish soundness for an accepted certificate in this restricted proof language, assuming the decoder, Python execution, and mathematical lemmas are correct. They do not prove checker completeness. A rejected certificate can describe a valid equivalent program. The mutation experiment deliberately retains such cases rather than counting every rejection as a proof of semantic inequality.

The block has two three-byte ORPS instructions and six four-byte arithmetic instructions, so its cost is `(8,30)`. The GNU assembler cross-check agrees with the certificate's actual 30 bytes without executing them. Initial register setup, loads, stores, function return, and caller preservation are excluded by the declared block model. No conclusion about throughput, latency, global ISA minimality, or even a lower-cost program in the frozen ten-opcode grammar is implied.

## 9. Guarded floating-point copies

The checker also accepts the nine derived blocks obtained by replacing either initial ORPS with ORPS, XORPS, or ADDSS, without changing registers or the remaining six instructions. This is a small stated family, not a search-space exhaustion claim. In particular, the floating addition is *not* an unconditional bitwise copy.

**Lemma 6 (zero addition on the quotient).** For every `v` in `Q`, `U(0,v)=U(v,0)=v`, with no newly generated observed flag. For finite `v`, addition is exact; for infinities it returns the same infinity; for the sole quiet indefinite it propagates that NaN without invalid. Zero signs have already been quotiented. Thus the normalizer may erase an ADDSS node with a known bitwise +0 operand on this quotient. Its omitted contribution is exactly zero in the no-input-NaN case.

For raw input NaNs the lemma does not apply. An ADDSS with +0 can quiet a signaling input and set invalid; with a negative-zero input it can erase the sign. The checker therefore retains the original raw expression and every executed arithmetic node for the NaN and signed-zero subproofs. A zero-addition node on a non-NaN operand is classified as non-NaN and exact, including the infinity case. If its other operand is a NaN, the existing ordered provenance rule applies. The sum still has to be the original ordered addition of the two untouched inputs, so its invalid contribution observes both initial signaling bits. Explicit symbolic propagation over all eight NaN patterns checks the complete flag union, including any early invalid contribution from an arithmetic copy. No invalid contribution is silently erased.

For signed zeros, the original recursive necessary-condition analysis is applied to the raw graph containing these additions. It uses the actual +0 leaf: +0 added to a value cannot yield -0 under this contract. The all-negative-zero input case is still checked. Therefore quotient erasure cannot erase an observable negative-zero counterexample.

**Corollary (derived copy family).** All nine blocks preserve the reference observations for every input pair and initial five-flag mask. Four use only three-byte bitwise copies and have cost `(8,30)`; four use one arithmetic copy and have cost `(8,31)`; one uses two arithmetic copies and has cost `(8,32)`. This establishes minimal byte cost only among these nine specified blocks, not among all length-eight programs in the frozen grammar. Their certificates are derived and checked by the family test, followed by 589,824 complete toy program evaluations.

The extension also resolves both previously unclassified single-opcode mutants: they are valid arithmetic-copy variants, not undetected wrong programs. The current 128-mutation result contains 96 rejected corrupt evidence objects, 28 concretely refuted opcode mutants, and four equivalent opcode mutants accepted by the checker. The checker remains incomplete outside its supported symbolic identities.

## 10. Trusted base and remaining obligation

The trusted base comprises the selected Intel-SSE semantic contract, the mathematical argument above, the checker/decoder source and its Python runtime, and the mapping from that contract to the intended processor semantics. Independent integer/rational finite cross-checks and static assembly tests provide implementation evidence, not a proof of this trusted base. No target instructions were executed.

The full-ten-opcode minimum-cost question remains separate: to establish lexicographic optimality there, one must exclude every admitted program of length at most seven and every length-eight program below 30 bytes. The retained solver pilots exclude neither set and produce no independently replayable full-grammar lower-bound certificate. The separate event-bijective proof does establish `(8,30)` for its explicitly narrower two-address class; neither that class theorem nor historical arithmetic-count results discharge the larger grammar with comparisons, multiplication, general bitwise synthesis, conditional selection, and exact exceptional behavior.
