"""Generate quantifier-free result-bit constraints for the declared machine grammar.

IEEE flags are deliberately omitted in the synthesis pilot. This is a relaxation:
UNSAT would be a necessary-condition lower bound (subject to trusted encoding and
proof replay). SAT is NOT an all-input equivalence result.
"""
from pathlib import Path
import argparse,json
from fpmodel import BINARY32,reference

def prefix(ebits=8,fbits=23,timeout=90000):
 n=1+ebits+fbits;sgn=1<<(n-1);inf=((1<<ebits)-1)<<fbits;q=1<<(fbits-1);mask=(1<<n)-1
 def bv(x):return f'(_ bv{x} {n})'
 lines=[f'(set-option :timeout {timeout})','(set-option :smt.random_seed 1729)',
        '(set-option :sat.random_seed 1729)','(set-option :parallel.enable false)',
        '(set-logic QF_FPBV)',f'(define-sort W () (_ BitVec {n}))',f'(define-sort F () (_ FloatingPoint {ebits} {fbits+1}))',
        f'(define-fun asfp ((a W)) F ((_ to_fp {ebits} {fbits+1}) a))',
        f'(define-fun nan ((a W)) Bool (and (= (bvand a {bv(inf)}) {bv(inf)}) (not (= (bvand a {bv((1<<fbits)-1)}) {bv(0)}))))',
        f'(define-fun sign ((a W)) Bool (= (bvand a {bv(sgn)}) {bv(sgn)}))',
        f'(define-fun canon ((a W) (b W) (r F)) W (ite (nan a) (bvor a {bv(q)}) (ite (nan b) (bvor b {bv(q)}) (ite (fp.isNaN r) {bv(sgn|inf|q)} (fp.to_ieee_bv r)))))',
        '(define-fun add ((a W) (b W)) W (canon a b (fp.add RNE (asfp a) (asfp b))))',
        '(define-fun sub ((a W) (b W)) W (canon a b (fp.sub RNE (asfp a) (asfp b))))',
        '(define-fun mul ((a W) (b W)) W (canon a b (fp.mul RNE (asfp a) (asfp b))))',
        '(define-fun minimum ((a W) (b W)) W (ite (fp.lt (asfp a) (asfp b)) a b))',
        '(define-fun maximum ((a W) (b W)) W (ite (fp.gt (asfp a) (asfp b)) a b))',
        '(define-fun unord ((a W) (b W)) Bool (or (nan a) (nan b)))']
 predicates=['(fp.eq (asfp a) (asfp b))','(fp.lt (asfp a) (asfp b))','(fp.leq (asfp a) (asfp b))',
             '(unord a b)','(not (fp.eq (asfp a) (asfp b)))','(not (fp.lt (asfp a) (asfp b)))',
             '(not (fp.leq (asfp a) (asfp b)))','(not (unord a b))']
 for i,p in enumerate(predicates):lines.append(f'(define-fun cmp{i} ((a W) (b W)) W (ite {p} {bv(mask)} {bv(0)}))')
 branches=['(add a b)','(sub a b)','(mul a b)','(minimum a b)','(maximum a b)',
           '(bvand a b)','(bvor a b)','(bvxor a b)','(ite (sign m) b a)']+[f'(cmp{i} a b)' for i in range(8)]
 expr=branches[-1]
 for i in reversed(range(len(branches)-1)):expr=f'(ite (= op (_ bv{i} 5)) {branches[i]} {expr})'
 lines.append(f'(define-fun dispatch ((op (_ BitVec 5)) (a W) (b W) (m W)) W {expr})')
 return lines,bv

def select(selector,items):
 expr=items[-1]
 for i in reversed(range(len(items)-1)):expr=f'(ite (= {selector} (_ bv{i} 3)) {items[i]} {expr})'
 return expr

def synth(length,inputs,timeout=90000,byte_bound=None):
 lines,bv=prefix(timeout=timeout)
 for i in range(length):
  for name,width,bound in [('o',5,17),('d',3,6),('s',3,6)]:
   var=f'{name}{i}';lines+=[f'(declare-fun {var} () (_ BitVec {width}))',f'(assert (bvult {var} (_ bv{bound} {width})))']
 for o in ['os','oe']:lines+=[f'(declare-fun {o} () (_ BitVec 3))',f'(assert (bvult {o} (_ bv6 3)))']
 if byte_bound is not None:
  costs=[]
  for i in range(length):
   # Widen to 64 bits to make the exact cost field and no-wrap precondition explicit.
   costs.append(f'(ite (bvult o{i} (_ bv5 5)) (_ bv4 64) (ite (bvult o{i} (_ bv8 5)) (_ bv3 64) (_ bv5 64)))')
  total='(_ bv0 64)'
  for cost in costs:total=f'(bvadd {total} {cost})'
  lines.append(f'(assert (bvult {total} (_ bv{byte_bound} 64)))')
 for case,(a,b) in enumerate(inputs):
  state=[bv(a),bv(b)]+[bv(0)]*4
  for i in range(length):
   aa=select(f'd{i}',state);bb=select(f's{i}',state)
   out=f'v{case}_{i}'
   lines.append(f'(define-fun {out} () W (dispatch o{i} {aa} {bb} {state[0]}))')
   nextstate=[]
   for r in range(6):
    name=f'r{case}_{i}_{r}'
    lines.append(f'(define-fun {name} () W (ite (= d{i} (_ bv{r} 3)) {out} {state[r]}))');nextstate.append(name)
   state=nextstate
  expected=reference(BINARY32,a,b)
  lines.append(f'(assert (= {select("os",state)} {bv(expected[0])}))')
  lines.append(f'(assert (= {select("oe",state)} {bv(expected[1])}))')
 lines.append('(check-sat)')
 lines.append('(get-info :reason-unknown)')
 # A model is requested separately only after a SAT verdict; an unknown is retained, not hidden.
 return '\n'.join(lines)+'\n'

def equivalence(timeout=90000):
 lines,bv=prefix(timeout=timeout)
 lines+=['(declare-fun a () W)','(declare-fun b () W)',
         '(define-fun ss () W (add a b))','(define-fun xx () W (sub ss b))',
         '(define-fun yy () W (sub ss xx))','(define-fun dx () W (sub a xx))',
         '(define-fun dy () W (sub b yy))','(define-fun ee () W (add dx dy))',
         '(define-fun nx () W (sub b ss))','(define-fun ndx () W (add a nx))',
         '(define-fun ny () W (add nx ss))','(define-fun ndy () W (sub b ny))',
         '(define-fun ne () W (add ndx ndy))','(assert (not (= ee ne)))','(check-sat)','(get-info :reason-unknown)']
 return '\n'.join(lines)+'\n'

def main():
 p=argparse.ArgumentParser();p.add_argument('kind',choices=['synthesis','equivalence']);p.add_argument('--output',required=True)
 p.add_argument('--inputs',default='inputs/synthesis-cases.json');p.add_argument('--length',type=int,default=7)
 p.add_argument('--timeout-ms',type=int,default=90000);p.add_argument('--byte-bound',type=int);a=p.parse_args()
 if a.kind=='equivalence':text=equivalence(a.timeout_ms)
 else:
  data=json.loads(Path(a.inputs).read_text());pairs=[(int(x['a'],0),int(x['b'],0)) for x in data['cases']]
  text=synth(a.length,pairs,a.timeout_ms,a.byte_bound)
 Path(a.output).write_text(text)
 print(json.dumps(dict(kind=a.kind,bytes=len(text.encode()),timeout_ms=a.timeout_ms,flags_encoded=False)))
if __name__=='__main__':main()
