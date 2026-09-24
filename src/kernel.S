# Straight-line block, not a callable ABI function. No execution is performed.
# xmm0=a, xmm1=b, xmm2..xmm5=+0; every upper lane is zero.
# RNE; all numeric traps masked; DAZ=FTZ=0. Outputs xmm0 and xmm3.
.intel_syntax noprefix
.text
.global twosum_block
twosum_block:
    orps xmm2, xmm1
    orps xmm3, xmm0
    addss xmm0, xmm1
    subss xmm2, xmm0
    addss xmm3, xmm2
    addss xmm2, xmm0
    subss xmm1, xmm2
    addss xmm3, xmm1
.section .note.GNU-stack,"",@progbits
