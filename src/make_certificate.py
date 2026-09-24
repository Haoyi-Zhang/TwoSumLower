"""Produce the proof data and a register-only legacy byte string."""
import json
from pathlib import Path
from fpmodel import CANDIDATE,program_cost

def encode(program):
    codes={'ADDSS':b'\xf3\x0f\x58','SUBSS':b'\xf3\x0f\x5c','MULSS':b'\xf3\x0f\x59',
           'MINSS':b'\xf3\x0f\x5d','MAXSS':b'\xf3\x0f\x5f','ANDPS':b'\x0f\x54',
           'ORPS':b'\x0f\x56','XORPS':b'\x0f\x57','CMPSS':b'\xf3\x0f\xc2','BLENDVPS':b'\x66\x0f\x38\x14'}
    program_cost(program)
    out=bytearray()
    for op,d,s,imm in program:
        out.extend(codes[op]);out.append(0xc0|(d<<3)|s)
        if op=='CMPSS':out.append(imm)
    return bytes(out)

def produce():
    rows=[]
    for an,bn in [(True,False),(False,True),(True,True)]:
        for sa in ([False,True] if an else [False]):
            for sb in ([False,True] if bn else [False]):
                origin='a' if an else 'b'
                rows.append(dict(a_kind=('s' if sa else 'q') if an else 'non-nan',
                                 b_kind=('s' if sb else 'q') if bn else 'non-nan',
                                 s_origin=origin,e_origin=origin,invalid=int(sa or sb)))
    return dict(format=[8,23],rounding='RNE',ftz=False,daz=False,exception_masks='all-masked',
                entry=['a','b','+0','+0','+0','+0'],upper_lanes='all-zero',
                observed_flags=['invalid','divide-by-zero','overflow','underflow','inexact'],
                program_hex=encode(CANDIDATE).hex(),output_registers=[0,3],claimed_cost=list(program_cost(CANDIDATE)),
                arithmetic_mapping=[0,1,3,2,4,5],arithmetic_signs=[1,-1,1,1,1,1],
                zero_case_s_word=0x80000000,zero_case_e_word=0,zero_case_final_flags=list(range(32)),nan_cases=rows)

def main():
    cert=produce();Path('proofs/equivalence.json').write_text(json.dumps(cert,indent=2)+'\n')
    lines=['# Straight-line block, not a callable ABI function. No execution is performed.',
           '# xmm0=a, xmm1=b, xmm2..xmm5=+0; every upper lane is zero.',
           '# RNE; all numeric traps masked; DAZ=FTZ=0. Outputs xmm0 and xmm3.',
           '.intel_syntax noprefix','.text','.global twosum_block','twosum_block:']
    for op,d,s,imm in CANDIDATE:lines.append(f'    {op.lower()} xmm{d}, xmm{s}'+(f', {imm}' if op=='CMPSS' else ''))
    lines.append('.section .note.GNU-stack,"",@progbits')
    Path('src/kernel.S').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(instructions=8,bytes=len(bytes.fromhex(cert['program_hex'])))))
if __name__=='__main__':main()
