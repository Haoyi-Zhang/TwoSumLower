"""Resumable finite-case synthesis with exact, lazily refined arithmetic.

All non-arithmetic instructions are bit-vector encoded, including flags. ADD,
SUB and MUL are initially uninterpreted 37-bit result/flag functions. Every
learned ground observation is checked by both integer and rational semantics.
UNSAT is only a solver verdict until a separate proof certificate is replayed.
SAT on a finite pool is not universal equivalence. No result is called optimal.
"""
import argparse,ctypes,ctypes.util,json,os,re,sys,time
from pathlib import Path
from fpmodel import BINARY32 as F,reference,execute,program_cost
from oracle import RationalOracle

OPS=['ADDSS','SUBSS','MULSS','MINSS','MAXSS','ANDPS','ORPS','XORPS','BLENDVPS']+['CMPSS']*8
BV=lambda x,w=32:f'(_ bv{x} {w})'
EQ=lambda name,x,w=3:f'(= {name} {BV(x,w)})'

class Session:
    def __init__(self):
        self.lib=ctypes.CDLL(ctypes.util.find_library('z3'));p=ctypes.c_void_p;l=self.lib
        l.Z3_mk_config.argtypes=[];l.Z3_mk_config.restype=p;l.Z3_mk_context.argtypes=[p];l.Z3_mk_context.restype=p
        l.Z3_del_config.argtypes=[p];l.Z3_del_context.argtypes=[p]
        l.Z3_eval_smtlib2_string.argtypes=[p,ctypes.c_char_p];l.Z3_eval_smtlib2_string.restype=ctypes.c_char_p
        c=l.Z3_mk_config();self.ctx=l.Z3_mk_context(c);l.Z3_del_config(c)
    def eval(self,text):
        r=self.lib.Z3_eval_smtlib2_string(self.ctx,text.encode());answer=r.decode() if r else ''
        if '(error ' in answer:raise RuntimeError(answer)
        return answer
    def close(self):self.lib.Z3_del_context(self.ctx)

def select(s,items):
    x=items[-1]
    for i in reversed(range(len(items)-1)):x=f'(ite {EQ(s,i)} {items[i]} {x})'
    return x

def preamble(length):
    l=['(set-option :timeout 1000)','(set-option :smt.random_seed 1729)','(set-option :parallel.enable false)',
       '(set-logic QF_UFBV)','(define-sort W () (_ BitVec 32))','(define-sort R () (_ BitVec 37))',
       '(define-fun nan ((a W)) Bool (and (= (bvand a #x7f800000) #x7f800000) (not (= (bvand a #x007fffff) #x00000000))))',
       '(define-fun snan ((a W)) Bool (and (nan a) (= (bvand a #x00400000) #x00000000)))',
       '(define-fun sign ((a W)) Bool (= (bvand a #x80000000) #x80000000))',
       '(define-fun zero ((a W)) Bool (= (bvand a #x7fffffff) #x00000000))',
       '(define-fun unord ((a W) (b W)) Bool (or (nan a) (nan b)))',
       '(define-fun eqnum ((a W) (b W)) Bool (and (not (unord a b)) (or (= a b) (and (zero a) (zero b)))))',
       '(define-fun less ((a W) (b W)) Bool (and (not (unord a b)) (not (eqnum a b)) (ite (= (sign a) (sign b)) (ite (sign a) (bvugt a b) (bvult a b)) (sign a))))',
       '(define-fun leq ((a W) (b W)) Bool (or (less a b) (eqnum a b)))',
       '(define-fun pack ((w W) (i Bool)) R (concat (ite i #b00001 #b00000) w))']
    for op in ['ADDSS','SUBSS','MULSS']:l.append(f'(declare-fun {op} (W W) R)')
    branches=['(ADDSS a b)','(SUBSS a b)','(MULSS a b)',
              '(pack (ite (less a b) a b) (unord a b))','(pack (ite (less b a) a b) (unord a b))',
              '(pack (bvand a b) false)','(pack (bvor a b) false)','(pack (bvxor a b) false)',
              '(pack (ite (sign m) b a) false)']
    predicates=['(eqnum a b)','(less a b)','(leq a b)','(unord a b)',
                '(not (eqnum a b))','(not (less a b))','(not (leq a b))','(not (unord a b))']
    for i,p in enumerate(predicates):
        invalid='(unord a b)' if i in (1,2,5,6) else '(or (snan a) (snan b))'
        branches.append(f'(pack (ite {p} #xffffffff #x00000000) {invalid})')
    expr=branches[-1]
    for i in reversed(range(16)):expr=f'(ite {EQ("op",i,5)} {branches[i]} {expr})'
    l.append(f'(define-fun dispatch ((op (_ BitVec 5)) (a W) (b W) (m W)) R {expr})')
    for i in range(length):
        for f,w,n in [('o',5,17),('d',3,6),('s',3,6)]:
            l.extend([f'(declare-fun {f}{i} () (_ BitVec {w}))',f'(assert (bvult {f}{i} {BV(n,w)}))'])
    for x in ('os','oe'):l.extend([f'(declare-fun {x} () (_ BitVec 3))',f'(assert (bvult {x} {BV(6,3)}))'])
    return '\n'.join(l)

def case_encoding(cid,a,b,length):
    l=[];state=[BV(a),BV(b)]+[BV(0)]*4;flags='#b00000'
    for i in range(length):
        aa=f'a{cid}_{i}';bb=f'b{cid}_{i}';vv=f'v{cid}_{i}';ff=f'f{cid}_{i}'
        l.extend([f'(define-fun {aa} () W {select(f"d{i}",state)})',f'(define-fun {bb} () W {select(f"s{i}",state)})',
                  f'(define-fun {vv} () R (dispatch o{i} {aa} {bb} {state[0]}))',
                  f'(define-fun {ff} () (_ BitVec 5) (bvor {flags} ((_ extract 36 32) {vv})))'])
        flags=ff;new=[]
        for r in range(6):
            name=f'r{cid}_{i}_{r}';l.append(f'(define-fun {name} () W (ite {EQ(f"d{i}",r)} ((_ extract 31 0) {vv}) {state[r]}))');new.append(name)
        state=new
    target=reference(F,a,b)
    l.extend([f'(assert (= {select("os",state)} {BV(target[0])}))',f'(assert (= {select("oe",state)} {BV(target[1])}))',
              f'(assert (= {flags} {BV(target[2],5)}))'])
    return '\n'.join(l)

def observation(op,a,b,result,flags):
    return f'(assert (= ({op} {BV(a)} {BV(b)}) {BV((flags<<32)|result,37)}))'

def values(text):
    pattern=r'\(([A-Za-z][A-Za-z0-9_]*)\s+(#x[0-9a-fA-F]+|#b[01]+|\(_ bv[0-9]+ [0-9]+\))\)'
    result={}
    for name,v in re.findall(pattern,text):
        result[name]=int(v[2:],16) if v.startswith('#x') else int(v[2:],2) if v.startswith('#b') else int(v.split()[1][2:])
    return result

def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n');temp.replace(path)

def main():
    p=argparse.ArgumentParser();p.add_argument('--length',type=int,default=7);p.add_argument('--seconds',type=int,default=18)
    p.add_argument('--state',default='results/lazy-state.json');p.add_argument('--max-new-iterations',type=int,default=200)
    args=p.parse_args();path=Path(args.state)
    if not 1<=args.length<=8 or not 1<=args.seconds<=90:raise SystemExit('length 1..8; seconds 1..90')
    pool=json.loads(Path('inputs/binary32-cases.json').read_text())['cases'];pairs=[(int(c['a'],0),int(c['b'],0)) for c in pool]
    wanted=[(0x3f800001,0x33800000),(0x73c00000,0xff7fffff),(0x7fc00001,0xffc00001),(0x00800000,1)]
    state=json.loads(path.read_text()) if path.exists() else dict(length=args.length,case_indices=[pairs.index(x) for x in wanted],observations=[],iterations=0,prefixes=[],status='exploratory',events=[])
    if state['length']!=args.length:raise SystemExit('state length mismatch')
    observations={(row['op'],row['a'],row['b']):row for row in state['observations']}
    prefixes={tuple(tuple(ins) for ins in pref) for pref in state['prefixes']}
    oracle=RationalOracle(8,23);session=Session();start=time.monotonic();iterations=0
    try:
        session.eval(preamble(args.length))
        for ci,index in enumerate(state['case_indices']):session.eval(case_encoding(ci,*pairs[index],args.length))
        for row in observations.values():session.eval(observation(**row))
        while time.monotonic()-start<args.seconds and iterations<args.max_new_iterations:
            if len(prefixes)>=49000 or len(observations)>=49000:state['status']='configured-coverage-stop';break
            verdict=session.eval('(check-sat)').strip().splitlines()[0]
            if verdict=='unknown':
                state['events'].append(dict(iteration=state['iterations'],event='solver-unknown',detail=session.eval('(get-info :reason-unknown)')))
                state['status']='resumable-unknown';break
            if verdict=='unsat':state['status']='solver-unsat-not-independently-replayed';break
            if verdict!='sat':raise RuntimeError(verdict)
            names=[f'{f}{i}' for i in range(args.length) for f in ('o','d','s')]+['os','oe']
            names += [f'{x}{ci}_{i}' for ci in range(len(state['case_indices'])) for i in range(args.length) for x in ('a','b','v')]
            model=values(session.eval('(get-value ('+' '.join(names)+'))'))
            if set(names)-model.keys():raise RuntimeError('incomplete model parsing')
            program=[(OPS[model[f'o{i}']],model[f'd{i}'],model[f's{i}'],model[f'o{i}']-9 if model[f'o{i}']>=9 else 0) for i in range(args.length)]
            for k in range(1,args.length+1):prefixes.add(tuple(program[:k]))
            learned=[]
            asserted_keys=set(observations)
            for ci in range(len(state['case_indices'])):
                for i in range(args.length):
                    op=OPS[model[f'o{i}']]
                    if op not in ('ADDSS','SUBSS','MULSS'):continue
                    a,b=model[f'a{ci}_{i}'],model[f'b{ci}_{i}'];actual=F.operation(op,a,b)
                    if tuple(actual)!=oracle.op(op,a,b):raise AssertionError('independent arithmetic oracle disagrees')
                    if model[f'v{ci}_{i}']!=((actual.flags<<32)|actual.word):
                        key=(op,a,b)
                        if key in asserted_keys:raise AssertionError('model violates an asserted observation')
                        if key in observations:continue  # repeated cell in this model, not yet asserted
                        row=dict(op=op,a=a,b=b,result=actual.word,flags=actual.flags);observations[key]=row;learned.append(row)
            if learned:
                session.eval('\n'.join(observation(**row) for row in learned))
            else:
                outputs=(model['os'],model['oe']);wrong=None
                for index,(a,b) in enumerate(pairs):
                    if execute(F,program,a,b,outputs)!=reference(F,a,b):wrong=index;break
                if wrong is None:
                    state['status']='finite-pool-candidate-not-universally-proved';state['candidate']=dict(program=program,outputs=outputs,cost=program_cost(program));break
                if wrong in state['case_indices']:raise AssertionError('concrete program disagrees with a fully refined selected case')
                state['case_indices'].append(wrong);session.eval(case_encoding(len(state['case_indices'])-1,*pairs[wrong],args.length))
                state['events'].append(dict(iteration=state['iterations'],event='added-counterexample',case=pool[wrong]['id']))
            state['iterations']+=1;iterations+=1
            # Persist every iteration: cancellation retains finished oracle-checked evidence.
            state['observations']=list(observations.values());state['prefixes']=[[list(x) for x in pref] for pref in sorted(prefixes)]
            state['status']='resumable';save(path,state)
        state['observations']=list(observations.values());state['prefixes']=[[list(x) for x in pref] for pref in sorted(prefixes)]
        state['last_chunk']=dict(new_iterations=iterations,wall_seconds=time.monotonic()-start)
        save(path,state)
        print(json.dumps(dict(status=state['status'],iterations=state['iterations'],prefixes=len(prefixes),observations=len(observations),selected_cases=len(state['case_indices']),wall_seconds=time.monotonic()-start)))
    finally:session.close()
if __name__=='__main__':main()
