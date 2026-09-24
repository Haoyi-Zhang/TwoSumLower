import argparse,json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fpmodel import *
from oracle import RationalOracle

def crosscheck(group):
    fmt=TOY;oracle=RationalOracle();counts={};failures=[];checks=0;disagreements=0
    ops={'arithmetic':[('ADDSS',0),('SUBSS',0),('MULSS',0)],
         'selection':[('MINSS',0),('MAXSS',0)]+[('CMPSS',i) for i in range(8)],
         'bitwise':[('ANDPS',0),('ORPS',0),('XORPS',0)],
         'blend':[('BLENDVPS',0)]}[group]
    for op,imm in ops:
        key=op+(f'/{imm}' if op=='CMPSS' else '');n=0
        masks=(0,fmt.sign) if op=='BLENDVPS' else (0,)
        for a in range(256):
            for b in range(256):
                for mask in masks:
                    got=tuple(fmt.operation(op,a,b,imm,mask));expected=oracle.op(op,a,b,imm,mask)
                    checks+=1;n+=1
                    if got!=expected:
                        disagreements+=1
                        if len(failures)<32:failures.append(dict(op=op,imm=imm,a=a,b=b,mask=mask,got=got,expected=expected))
        counts[key]=n
    return dict(format={'exponent_bits':4,'fraction_bits':3,'words':256},group=group,
                counts=counts,checks=checks,disagreement_count=disagreements,first_disagreements=failures,
                interpretation='complete pairwise reduced-format cross-check, not a binary32 proof')

def programs():
    cnt=Counter();first={};nonfinite_first={};totals=Counter();maxsteps=0
    for a in range(256):
        for b in range(256):
            ref=reference(TOY,a,b);finite=TOY.finite(a) and TOY.finite(b)
            got=execute(TOY,CANDIDATE,a,b)
            swap=execute(TOY,SWAPPED_CANDIDATE,a,b)
            literal=execute(TOY,REFERENCE_LOWERING,a,b,(2,0),cap=9)
            # A deliberate wrong sign in the critical reflected subtraction.
            badprog=list(CANDIDATE);badprog[3]=('ADDSS',2,0,0)
            bad=execute(TOY,badprog,a,b)
            totals['all']+=1;totals['finite' if finite else 'nonfinite']+=1
            for name,answer in [('candidate',got),('swapped',swap),('literal',literal),('negative_control',bad)]:
                if answer!=ref:
                    cnt[name]+=1
                    if finite:cnt[name+'_finite']+=1
                    if name not in first:first[name]=dict(a=a,b=b,reference=ref,observed=answer,
                        source_trace=reference(TOY,a,b,trace=True)[3],
                        candidate_trace=execute(TOY,REFERENCE_LOWERING if name=='literal' else CANDIDATE if name=='candidate' else SWAPPED_CANDIDATE if name=='swapped' else badprog,a,b,outputs=(2,0) if name=='literal' else (0,3),cap=9 if name=='literal' else 8,trace=True)[3])
            if ref[2]&UNDERFLOW:cnt['reference_underflow']+=1
            if ref[2]&DIVZERO:cnt['reference_divzero']+=1
            if finite and ref[1]==TOY.sign:cnt['reference_negative_zero_residual']+=1
            if finite and got[1]==TOY.sign:cnt['candidate_negative_zero_residual']+=1
            if finite and TOY.finite(ref[0]) and (ref[2]&OVERFLOW):cnt['finite_sum_internal_overflow']+=1
    return dict(format={'exponent_bits':4,'fraction_bits':3},pair_counts=dict(totals),
                mismatches_and_events=dict(cnt),first_examples=first,
                candidate_cost=program_cost(CANDIDATE),literal_cost=program_cost(REFERENCE_LOWERING,cap=9),
                literal_within_length_cap=False,interpretation='finite exhaustive experiment; no unrestricted synthesis lower bound')

def main():
    p=argparse.ArgumentParser();p.add_argument('group',choices=['arithmetic','selection','bitwise','blend','programs']);p.add_argument('--output',required=True);args=p.parse_args()
    report=programs() if args.group=='programs' else crosscheck(args.group)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('first_examples','first_disagreements')},sort_keys=True))
    if report.get('disagreement_count',0) or report.get('mismatches_and_events',{}).get('candidate',0):raise SystemExit(1)
if __name__=='__main__':main()
