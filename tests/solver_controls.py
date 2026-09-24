"""Produce concrete positive/negative controls and a bounded tactical solver pilot."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from smt_encoding import synth
from fpmodel import CANDIDATE,SWAPPED_CANDIDATE

def fixed(program,pairs):
    text=synth(8,pairs,timeout=15000)
    names=['ADDSS','SUBSS','MULSS','MINSS','MAXSS','ANDPS','ORPS','XORPS','BLENDVPS']
    extra=[]
    for i,(op,d,s,imm) in enumerate(program):
        opindex=9+imm if op=='CMPSS' else names.index(op)
        extra += [f'(assert (= o{i} (_ bv{opindex} 5)))',f'(assert (= d{i} (_ bv{d} 3)))',f'(assert (= s{i} (_ bv{s} 3)))']
    extra += ['(assert (= os (_ bv0 3)))','(assert (= oe (_ bv3 3)))']
    return text.replace('(check-sat)','\n'.join(extra)+'\n(check-sat-using (then simplify solve-eqs fpa2bv bit-blast sat))')

def main():
    # These are a subset of the frozen 1,000 diagnostic classes, not a new input pool.
    data=json.loads(Path('inputs/binary32-cases.json').read_text())['cases']
    wanted=[(0x3f800001,0x33800000),(0x73c00000,0xff7fffff),(0x7fc00001,0xffc00001),(0x00800000,1)]
    assert all(any(int(c['a'],0)==a and int(c['b'],0)==b for c in data) for a,b in wanted)
    Path('inputs/solver-positive.smt2').write_text(fixed(CANDIDATE,wanted))
    Path('inputs/solver-negative.smt2').write_text(fixed(SWAPPED_CANDIDATE,wanted))
    free=synth(7,wanted,timeout=90000)
    free=free.replace('(check-sat)','(check-sat-using (then simplify solve-eqs fpa2bv bit-blast sat))')
    Path('inputs/lower-bound-tactical.smt2').write_text(free)
    print(json.dumps(dict(classes=len(wanted),positive_length=8,negative_length=8,free_length=7,free_timeout_ms=90000)))
if __name__=='__main__':main()
