"""A fixed 1,000-class diagnostic test; not an exhaustive binary32 proof."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fpmodel import BINARY32 as F,reference,execute,CANDIDATE,SWAPPED_CANDIDATE,REFERENCE_LOWERING
from oracle import RationalOracle

def oref(o,a,b,initial=0):
    flags=initial
    def run(op,x,y):
        nonlocal flags
        w,f=o.op(op,x,y);flags|=f;return w
    s=run('ADDSS',a,b);x=run('SUBSS',s,b);y=run('SUBSS',s,x)
    dx=run('SUBSS',a,x);dy=run('SUBSS',b,y);e=run('ADDSS',dx,dy)
    return s,e,flags

def oexecute(o,p,a,b,outputs=(0,3)):
    r=[a,b,0,0,0,0];flags=0
    for op,d,s,i in p:
        w,f=o.op(op,r[d],r[s],i,r[0]);r[d]=w;flags|=f
    return r[outputs[0]],r[outputs[1]],flags

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='results/binary32.json');args=p.parse_args()
    cases=json.loads(Path('inputs/binary32-cases.json').read_text())['cases'];o=RationalOracle(8,23)
    checks=0;fail=[];swap=[];sticky=0;counts={}
    ops=[(x,0) for x in ['ADDSS','SUBSS','MULSS','MINSS','MAXSS','ANDPS','ORPS','XORPS']]+[('CMPSS',i) for i in range(8)]+[('BLENDVPS',0)]
    for c in cases:
        a,b=int(c['a'],0),int(c['b'],0)
        for op,imm in ops:
            for mask in ((0,0x80000000) if op=='BLENDVPS' else (0,)):
                x=tuple(F.operation(op,a,b,imm,mask));y=o.op(op,a,b,imm,mask);checks+=1
                if x!=y:fail.append(dict(id=c['id'],kind='opcode',op=op,imm=imm,mask=mask,got=x,expected=y))
        ref=reference(F,a,b);rational=oref(o,a,b);cand=execute(F,CANDIDATE,a,b);ocand=oexecute(o,CANDIDATE,a,b)
        literal=execute(F,REFERENCE_LOWERING,a,b,(2,0),cap=9)
        if not(ref==rational==cand==ocand==literal):fail.append(dict(id=c['id'],kind='program',reference=ref,oracle=rational,candidate=cand,oracle_candidate=ocand,literal=literal))
        bad=execute(F,SWAPPED_CANDIDATE,a,b)
        if bad!=ref:swap.append(dict(id=c['id'],a=c['a'],b=c['b'],reference=ref,observed=bad))
        for init in range(32):
            sticky+=1
            if reference(F,a,b,init)!=execute(F,CANDIDATE,a,b,initial_flags=init):
                fail.append(dict(id=c['id'],kind='sticky',initial=init))
        key=F.kind(a)+'/'+F.kind(b);counts[key]=counts.get(key,0)+1
    a,b=0x73c00000,0xff7fffff
    witness=dict(a=f'0x{a:08x}',b=f'0x{b:08x}',reference=reference(F,a,b,trace=True),candidate=execute(F,CANDIDATE,a,b,trace=True),wrong_orientation=execute(F,SWAPPED_CANDIDATE,a,b,trace=True))
    report=dict(classes=len(cases),primitive_checks=checks,program_pair_checks=len(cases),initial_mask_checks=sticky,
                disagreements=len(fail),first_disagreements=fail[:32],wrong_orientation_mismatches=len(swap),wrong_orientation_examples=swap[:8],
                input_class_counts=counts,orientation_witness=witness,interpretation='fixed binary32 finite diagnostics; all-input proof is separate')
    Path(args.output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('input_class_counts','orientation_witness','first_disagreements','wrong_orientation_examples')}))
    if fail:raise SystemExit(1)
if __name__=='__main__':main()
