"""Sound syntactic reductions for the finite result-only synthesis relaxation.

This generator supplies no UNSAT proof. Register permutation and commuting
independent instructions preserve full masked semantics; dead-code deletion is
used only in the result-bit relaxation because it can change sticky flags.
"""
import argparse,json
from pathlib import Path
from smt_encoding import synth

def either(xs):return '(or '+ ' '.join(xs)+')' if xs else 'false'
def both(xs):return '(and '+ ' '.join(xs)+')' if xs else 'true'
def equal(x,k,w=3):return f'(= {x} (_ bv{k} {w}))'
def restrictions(n):
    lines=[]
    for i in range(n):
        lines.append(f'(define-fun nop{i} () Bool {both([equal(f"o{i}",6,5),equal(f"d{i}",0),equal(f"s{i}",0)])})')
    for i in range(n):
        same=f'(= d{i} s{i})';copyop=either([equal(f'o{i}',5,5),equal(f'o{i}',6,5)])
        lines.append(f'(assert (=> (and {same} {copyop}) nop{i}))')
        if i+1<n:lines.append(f'(assert (=> nop{i} nop{i+1}))')
        for r in range(3,6):
            before=either([equal(f'{field}{j}',r-1) for j in range(i) for field in ('d','s')])
            lines.append(f'(assert (=> {equal(f"d{i}",r)} {before}))')
            lines.append(f'(assert (=> {equal(f"s{i}",r)} (or {before} {equal(f"d{i}",r-1)})))')
        if i+1<n:
            j=i+1
            independent=both([f'(not (= d{i} d{j}))',f'(not (= d{i} s{j}))',f'(not (= d{j} s{i}))',
                              f'(not (and {equal(f"o{j}",8,5)} {equal(f"d{i}",0)}))',
                              f'(not (and {equal(f"o{i}",8,5)} {equal(f"d{j}",0)}))',f'(not nop{i})',f'(not nop{j})'])
            key=lambda k:f'(concat o{k} (concat d{k} s{k}))'
            lines.append(f'(assert (=> {independent} (bvule {key(i)} {key(j)})))')
        # A non-NOP definition must reach a later syntactic read or an output.
        live=[]
        for j in range(i+1,n):
            read=either([f'(= d{i} d{j})',f'(= d{i} s{j})',both([equal(f'o{j}',8,5),equal(f'd{i}',0)])])
            intact=both([f'(not (and (not nop{k}) (= d{i} d{k})))' for k in range(i+1,j)])
            live.append(both([f'(not nop{j})',read,intact]))
        intact=both([f'(not (and (not nop{k}) (= d{i} d{k})))' for k in range(i+1,n)])
        live.append(both([either([f'(= d{i} os)',f'(= d{i} oe)']),intact]))
        lines.append(f'(assert (=> (not nop{i}) {either(live)}))')
    return '\n'.join(lines)

def main():
    p=argparse.ArgumentParser();p.add_argument('--length',type=int,default=7);p.add_argument('--timeout-ms',type=int,default=90000)
    p.add_argument('--output',default='inputs/lower-bound-canonical.smt2');p.add_argument('--byte-bound',type=int);args=p.parse_args()
    if not 1<=args.length<=8:raise SystemExit('length must be 1..8')
    pairs=[(0x3f800001,0x33800000),(0x73c00000,0xff7fffff),(0x7fc00001,0xffc00001),(0x00800000,1)]
    text=synth(args.length,pairs,timeout=args.timeout_ms,byte_bound=args.byte_bound)
    text=text.replace('(check-sat)',restrictions(args.length)+'\n(check-sat-using (then simplify solve-eqs fpa2bv bit-blast sat))')
    Path(args.output).write_text(text)
    print(json.dumps(dict(length=args.length,classes=len(pairs),bytes=len(text.encode()),flags_encoded=False,
                         reductions=['temporary-first-mention','independent-adjacent-order','result-only-dead-write','trailing-noops'])))
if __name__=='__main__':main()
