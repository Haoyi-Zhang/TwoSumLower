"""Nine explicitly derived copy variants: certificates and exhaustive toy checks."""
import argparse,copy,itertools,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from certificate_checker import verify
from make_certificate import encode
from fpmodel import TOY,CANDIDATE,execute,reference,program_cost

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='results/guarded-copies.json');a=p.parse_args()
    base=json.loads(Path('proofs/equivalence.json').read_text());rows=[]
    references=[reference(TOY,x,y) for x in range(256) for y in range(256)]
    for left,right in itertools.product(('ORPS','XORPS','ADDSS'),repeat=2):
        prog=list(CANDIDATE);prog[0]=(left,2,1,0);prog[1]=(right,3,0,0)
        cert=copy.deepcopy(base);cert['program_hex']=encode(prog).hex();cert['claimed_cost']=list(program_cost(prog))
        proof=verify(cert);bad=0;first=None
        for i,(x,y) in enumerate(itertools.product(range(256),repeat=2)):
            got=execute(TOY,prog,x,y)
            if got!=references[i]:
                bad+=1
                if first is None:first=dict(a=x,b=y,expected=references[i],observed=got)
        rows.append(dict(copies=[left,right],cost=list(program_cost(prog)),certificate_accepted=proof['accepted'],
                         zero_additions=proof['arithmetic_zero_additions'],toy_pairs=65536,mismatches=bad,first_counterexample=first))
    report=dict(derived_variants=9,total_toy_evaluations=9*65536,rows=rows,
                interpretation='Nine specified copy choices only, not enumeration of the full instruction grammar.')
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    if any(r['mismatches'] for r in rows):raise SystemExit(1)
if __name__=='__main__':main()
