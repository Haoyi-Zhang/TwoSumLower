import argparse
_parser=argparse.ArgumentParser();_parser.add_argument('--output',default='results/residual-exploration.json');output_path=_parser.parse_args().output
from pathlib import Path
import sys,json
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fpmodel import *
counts=Counter();examples={}
for a in range(256):
 for b in range(256):
  if not (TOY.finite(a) and TOY.finite(b)):continue
  s,e,f=reference(TOY,a,b)
  if not TOY.finite(s) or not TOY.finite(e):continue
  aa=TOY.arithmetic('SUBSS',a,s);ea=TOY.arithmetic('ADDSS',aa.word,b)
  bb=TOY.arithmetic('SUBSS',b,s);eb=TOY.arithmetic('ADDSS',bb.word,a)
  vals=(ea.word,eb.word)
  pred=all(x==e or TOY.zero(x) for x in vals)
  out=ea.word|eb.word
  key='or_equal' if out==e else 'or_unequal'
  counts[key]+=1
  if not pred:
   counts['not_error_or_zero']+=1
   examples.setdefault('not_error_or_zero',dict(a=a,b=b,reference=(s,e,f),ea=ea,eb=eb))
  if out!=e:examples.setdefault(key,dict(a=a,b=b,reference=(s,e,f),ea=ea,eb=eb))
Path(output_path).write_text(json.dumps(dict(counts=counts,examples=examples),indent=2)+'\n')
print(json.dumps(dict(counts=counts,examples=examples)))
