import argparse
_parser=argparse.ArgumentParser();_parser.add_argument('--output',default='results/tininess-control.json');output_path=_parser.parse_args().output
import sys,json
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fpmodel import *
from oracle import RationalOracle,power2
oracle=RationalOracle();counts=Counter();examples=[]
for a in range(256):
 for b in range(256):
  r=TOY.operation('MULSS',a,b)
  # Deliberate negative control: test tininess only from the stored exponent.
  flawed=r.flags & ~UNDERFLOW
  if r.flags&INEXACT and TOY.finite(r.word) and (r.word & TOY.inf)==0:flawed|=UNDERFLOW
  if flawed!=r.flags:
   counts['stored-result-tininess_disagreements']+=1
   if len(examples)<8:examples.append(dict(a=a,b=b,result=r.word,intel_flags=r.flags,stored_result_rule_flags=flawed))
  assert tuple(r)==oracle.op('MULSS',a,b)
# Exact rational boundary controls. These are mathematical values, not an extra ISA opcode.
fmt=BINARY32;oracle32=RationalOracle(8,23)
threshold=((1<<(23+2))-1)
rounds=[]
for n,k in [(threshold*2-1,-152),(threshold,-151),(threshold*2+1,-152)]:
 r=fmt.rounded(n,k);q=oracle32.round(n*power2(k))
 assert tuple(r)==q
 rounds.append(dict(n=n,exponent=k,word=r.word,flags=r.flags))
report=dict(counts=counts,toy_examples=examples,binary32_exact_boundary_controls=rounds,
 source='Intel SDM volume 1 sections 4.9.1.5 and 11.5.2.5',
 interpretation='Both independently coded rounding algorithms require the same correctly read ISA contract; agreement alone does not establish that contract.')
Path(output_path).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
