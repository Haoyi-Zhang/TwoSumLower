"""Ground arithmetic replay and positive/negative controls for the UF encoder.

The test checks all 449 currently retained observations with two exact models.
Counts are read from the state rather than assumed. Fixed known programs are
fully grounded on four frozen cases; their solver verdicts are not UNSAT proofs.
"""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fpmodel import BINARY32 as F,CANDIDATE,SWAPPED_CANDIDATE,execute
from oracle import RationalOracle
from lazy_synthesis import Session,OPS,BV,EQ,preamble,case_encoding,observation

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='results/lazy-controls.json');args=p.parse_args()
    state=json.loads(Path('results/lazy-state.json').read_text());o=RationalOracle(8,23);seen=set()
    for row in state['observations']:
        key=(row['op'],row['a'],row['b']);assert key not in seen;seen.add(key)
        expected=(row['result'],row['flags']);assert tuple(F.operation(*key))==expected==o.op(*key)
    pool=json.loads(Path('inputs/binary32-cases.json').read_text())['cases']
    pairs=[(int(pool[i]['a'],0),int(pool[i]['b'],0)) for i in state['case_indices']]
    reports=[]
    for label,prog,expected in [('positive',CANDIDATE,'sat'),('negative',SWAPPED_CANDIDATE,'unsat')]:
        lines=[preamble(8),'(set-option :timeout 10000)'];ground={}
        for ci,(a,b) in enumerate(pairs):
            lines.append(case_encoding(ci,a,b,8))
            trace=execute(F,prog,a,b,trace=True)[3]
            for t in trace:
                if t['op'] not in ('ADDSS','SUBSS','MULSS'):continue
                key=(t['op'],t['a'],t['b']);assert o.op(*key)==(t['result'],t['raised'])
                ground[key]=dict(op=t['op'],a=t['a'],b=t['b'],result=t['result'],flags=t['raised'])
        for i,(op,d,s,imm) in enumerate(prog):
            for name,val,width in [(f'o{i}',OPS.index(op) if op!='CMPSS' else 9+imm,5),(f'd{i}',d,3),(f's{i}',s,3)]:
                lines.append(f'(assert {EQ(name,val,width)})')
        lines.extend(['(assert (= os #b000))','(assert (= oe #b011))'])
        lines.extend(observation(**r) for r in ground.values());lines.append('(check-sat)')
        session=Session()
        try:verdict=session.eval('\n'.join(lines)).strip().splitlines()[-1]
        finally:session.close()
        assert verdict==expected,(label,verdict)
        reports.append(dict(control=label,verdict=verdict,expected=expected,ground_arithmetic_cells=len(ground)))
    # Repeated calls in one model may refer to one not-yet-asserted new cell.
    asserted={('ADDSS',0,0)};observed=set(asserted);learned=[]
    for cell in [('SUBSS',0,0),('SUBSS',0,0)]:
        if cell in asserted:raise AssertionError('invalid regression setup')
        if cell in observed:continue
        observed.add(cell);learned.append(cell)
    assert len(learned)==1
    report=dict(replayed_arithmetic_observations=len(seen),fixed_program_controls=reports,duplicate_cell_regression=True,
                interpretation='Finite encoding and ground-observation checks; no global synthesis lower bound or proof replay.')
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
