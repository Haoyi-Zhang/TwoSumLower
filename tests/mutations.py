"""128 predeclared certificate/program mutations with honest survivor accounting."""
import argparse,copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from certificate_checker import verify,Rejected,decode
from make_certificate import encode
from fpmodel import CANDIDATE,BINARY32,execute,reference,program_cost

def build(base):
    out=[]
    for b in range(32):
        x=copy.deepcopy(base);x['zero_case_e_word']^=1<<b
        out.append((f'R{b+1:02d}','result-evidence',x,None))
    for i in range(32):
        x=copy.deepcopy(base);x['zero_case_final_flags'][i]^=16
        out.append((f'F{i+1:02d}','flag-evidence',x,None))
    count=0
    for i,(op,d,s,imm) in enumerate(CANDIDATE):
        choices={'ORPS':['XORPS','ADDSS','SUBSS','ANDPS'],
                 'ADDSS':['SUBSS','MULSS','MINSS','MAXSS'],
                 'SUBSS':['ADDSS','MULSS','MINSS','MAXSS']}[op]
        for new in choices:
            count+=1;p=list(CANDIDATE);p[i]=(new,d,s,imm)
            x=copy.deepcopy(base);x['program_hex']=encode(p).hex();x['claimed_cost']=list(program_cost(p))
            out.append((f'O{count:02d}','opcode',x,p))
    for b in range(32):
        x=copy.deepcopy(base);x['claimed_cost'][1]^=1<<b
        out.append((f'C{b+1:02d}','cost-evidence',x,None))
    assert len(out)==128
    return out

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='results/mutations.json');args=parser.parse_args()
    base=json.loads(Path('proofs/equivalence.json').read_text());verify(base)
    cases=json.loads(Path('inputs/binary32-cases.json').read_text())['cases']
    pairs=[(c['id'],int(c['a'],0),int(c['b'],0)) for c in cases]
    expected=[reference(BINARY32,a,b) for _,a,b in pairs]
    rows=[]
    for name,category,cert,program in build(base):
        try:verify(cert);accepted=True;reason=None
        except (Rejected,ValueError,TypeError,KeyError,IndexError) as e:accepted=False;reason=str(e)
        row=dict(id=name,category=category,accepted=accepted,rejection=reason)
        if program is not None:
            diff=[]
            for (cid,a,b),ref in zip(pairs,expected):
                got=execute(BINARY32,program,a,b)
                if got!=ref:diff.append(dict(case=cid,a=f'0x{a:08x}',b=f'0x{b:08x}',reference=ref,observed=got))
            row.update(program=[list(x) for x in program],mismatches=len(diff),first_counterexample=diff[0] if diff else None,
                       classification='proved equivalent by restricted checker' if accepted else 'refuted by concrete case' if diff else 'unclassified: proof rejected but no diagnostic counterexample')
            if accepted and diff:raise AssertionError('checker accepted a concretely incorrect mutation')
        else:row['classification']='corrupted evidence rejected' if not accepted else 'unexpected evidence acceptance'
        rows.append(row)
    counts={}
    for row in rows:counts[row['classification']]=counts.get(row['classification'],0)+1
    report=dict(total=128,accepted=sum(r['accepted'] for r in rows),rejected=sum(not r['accepted'] for r in rows),
                categories={k:sum(r['category']==k for r in rows) for k in ['result-evidence','flag-evidence','opcode','cost-evidence']},
                classification_counts=counts,opcode_diagnostic_evaluations=32*len(pairs),rows=rows,
                interpretation='proof rejection alone does not establish program inequivalence; survivors and unclassified cases are retained')
    Path(args.output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
    if any(r['classification']=='unexpected evidence acceptance' for r in rows):raise SystemExit(1)
if __name__=='__main__':main()
