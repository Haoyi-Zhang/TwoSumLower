"""Small symbolic checker for the supplied exception-preserving TwoSum certificate.

This module deliberately does NOT import fpmodel, oracle, an SMT solver, or the
certificate producer. Its soundness argument is in proofs/soundness.md and the
manuscript. It is a restricted proof language, not a complete decision procedure
for every program in the ten-opcode search grammar.

It checks: legacy instruction decoding and exact static cost; sign-symmetric
rounded-expression identities on the no-input-NaN quotient; a bijection of
exception-generating operation descriptors plus guarded zero additions; symbolic NaN provenance for every
input NaN/signaling pattern; and absence of a negative-zero residual.
"""
from functools import lru_cache
from pathlib import Path
import argparse,json

class Rejected(ValueError):pass

def require(condition,message):
    if not condition:raise Rejected(message)


def decode(code:bytes):
    """Independent decoder for register-only legacy encodings in this grammar."""
    decoded=[];i=0
    while i<len(code):
        start=i
        if code[i:i+2]==b'\x0f\x54':op='ANDPS';i+=2
        elif code[i:i+2]==b'\x0f\x56':op='ORPS';i+=2
        elif code[i:i+2]==b'\x0f\x57':op='XORPS';i+=2
        elif code[i:i+4]==b'\x66\x0f\x38\x14':op='BLENDVPS';i+=4
        elif code[i:i+2]==b'\xf3\x0f':
            require(i+2<len(code),'truncated scalar opcode')
            operations={0x58:'ADDSS',0x5c:'SUBSS',0x59:'MULSS',0x5d:'MINSS',0x5f:'MAXSS',0xc2:'CMPSS'}
            require(code[i+2] in operations,'unknown scalar opcode')
            op=operations[code[i+2]];i+=3
        else:raise Rejected('encoding outside the legacy register-only grammar')
        require(i<len(code),'missing ModRM')
        modrm=code[i];i+=1
        require(modrm & 0xc0==0xc0,'memory addressing is excluded')
        d=(modrm>>3)&7;s=modrm&7
        require(d<6 and s<6,'only xmm0 through xmm5 are admitted')
        imm=0
        if op=='CMPSS':
            require(i<len(code),'missing comparison predicate');imm=code[i];i+=1
            require(imm<8,'only legacy predicates 0..7 are admitted')
        decoded.append((op,d,s,imm,i-start))
    require(0<len(decoded)<=8,'instruction count must be in 1..8')
    return decoded

A=('input','a');B=('input','b');ZERO=('zero',)

def source_graph():
    s=('ADDSS',A,B);x=('SUBSS',s,B);y=('SUBSS',s,x)
    dx=('SUBSS',A,x);dy=('SUBSS',B,y);e=('ADDSS',dx,dy)
    return (s,e),[s,x,y,dx,dy,e]

def machine_graph(decoded,outputs):
    regs=[A,B,ZERO,ZERO,ZERO,ZERO];nodes=[];all_nodes=[]
    for op,d,s,imm,_ in decoded:
        x,y=regs[d],regs[s]
        if op in ('ADDSS','SUBSS'):
            node=(op,x,y);regs[d]=node;all_nodes.append(node)
            # Adding an exact bitwise +0 is value-neutral only in the quotient.
            # It can quiet sNaN / erase -0: raw NaN and zero proofs still run.
            if not (op=='ADDSS' and (x==ZERO or y==ZERO)):nodes.append(node)
        elif op in ('ORPS','XORPS') and (x==ZERO or y==ZERO):
            regs[d]=y if x==ZERO else x
        elif op=='ANDPS' and (x==ZERO or y==ZERO):regs[d]=ZERO
        elif op=='XORPS' and x==y:regs[d]=ZERO
        elif op in ('ORPS','ANDPS') and x==y:regs[d]=x
        else:raise Rejected('instruction is valid but not justified by this restricted proof language')
    return tuple(regs[o] for o in outputs),nodes,all_nodes

def neg(t):
    return t if t[1]==('zero',) else (-t[0],t[1])

@lru_cache(maxsize=None)
def canonical(raw):
    if raw==ZERO:return (1,('zero',))
    if raw[0]=='input':return (1,raw)
    op,x,y=raw
    if op=='ADDSS' and (x==ZERO or y==ZERO):return canonical(y if x==ZERO else x)
    a,b=canonical(x),canonical(y)
    if op=='SUBSS':b=neg(b)
    p=tuple(sorted((a,b),key=repr));q=tuple(sorted((neg(a),neg(b)),key=repr))
    # Oddness and commutativity of rounded addition are used ONLY in the
    # no-input-NaN quotient; zero signs and input NaNs are checked separately.
    return (1,('round',p)) if repr(p)<=repr(q) else (-1,('round',q))

def force_negative_zero(raw):
    """Necessary initial negative-zero leaves; None denotes an impossible NZ."""
    if raw==ZERO:return None
    if raw[0]=='input':return frozenset([raw[1]])
    op,x,y=raw;left=force_negative_zero(x)
    if left is None:return None
    if op=='SUBSS':return left  # additionally requires +0 on right; safely omitted
    right=force_negative_zero(y)
    return None if right is None else left|right

def zero_sign(raw):
    """Evaluate the all-negative-zero input case using only signed-zero rules."""
    if raw==ZERO:return False
    if raw[0]=='input':return True
    op,x,y=raw;a,b=zero_sign(x),zero_sign(y)
    return a and b if op=='ADDSS' else a and not b


def nan_provenance(raw,inputs,memo):
    """(origin, signaling, accumulated invalid); origin None is non-NaN unknown."""
    if raw in memo:return memo[raw]
    if raw==ZERO:return (None,False,False)
    if raw[0]=='input':return inputs[raw[1]]
    _,x,y=raw
    xo,xs,xi=nan_provenance(x,inputs,memo);yo,ys,yi=nan_provenance(y,inputs,memo)
    if raw[0]=='ADDSS' and (x==ZERO or y==ZERO) and xo is None and yo is None:
        answer=(None,False,xi or yi)  # non-NaN + zero is exact, including infinity
        memo[raw]=answer;return answer
    require(xo is not None or yo is not None,'NaN subproof encountered an unclassified arithmetic operation')
    answer=(xo if xo is not None else yo,False,xi or yi or xs or ys)
    memo[raw]=answer;return answer


def check_nan_cases(outputs,nodes):
    rows=[]
    for an,bn in [(True,False),(False,True),(True,True)]:
        for sa in ([False,True] if an else [False]):
            for sb in ([False,True] if bn else [False]):
                state={'a':('a' if an else None,sa,False),'b':('b' if bn else None,sb,False)}
                memo={};acc=False
                for node in nodes:acc|=nan_provenance(node,state,memo)[2]
                out=[nan_provenance(node,state,memo) for node in outputs]
                expected='a' if an else 'b'
                require(all(o[0]==expected and not o[1] for o in out),'NaN output provenance or quieting differs')
                require(acc==(sa or sb),'NaN-case invalid flag differs')
                rows.append(dict(a_kind=('s' if sa else 'q') if an else 'non-nan',
                                 b_kind=('s' if sb else 'q') if bn else 'non-nan',
                                 s_origin=out[0][0],e_origin=out[1][0],invalid=int(acc)))
    return rows


def verify(cert):
    require(isinstance(cert,dict),'certificate must be an object')
    require(cert.get('rounding')=='RNE' and cert.get('ftz') is False and cert.get('daz') is False,
            'rounding and gradual-underflow contract mismatch')
    require(cert.get('exception_masks')=='all-masked','unmasked traps are outside this proof')
    require(cert.get('format')==[8,23],'this certificate targets binary32 only')
    require(cert.get('entry')==['a','b','+0','+0','+0','+0'],'entry register contract mismatch')
    require(cert.get('upper_lanes')=='all-zero','upper-lane invariant mismatch')
    require(cert.get('observed_flags')==['invalid','divide-by-zero','overflow','underflow','inexact'],
            'flag projection mismatch')
    text=cert.get('program_hex');require(type(text) is str and len(text)<=80,'invalid code field')
    try:code=bytes.fromhex(text)
    except ValueError:raise Rejected('code is not hexadecimal')
    decoded=decode(code)
    cost=cert.get('claimed_cost')
    require(type(cost) is list and len(cost)==2 and all(type(x) is int and 0<=x<2**64 for x in cost),
            'cost must be two unsigned 64-bit integers')
    require(cost==[len(decoded),len(code)],'declared cost does not match independent decoding')
    outputs=cert.get('output_registers')
    require(type(outputs) is list and len(outputs)==2 and all(type(x) is int and 0<=x<6 for x in outputs),
            'invalid output registers')
    target,t_nodes=source_graph();candidate,c_nodes,c_all_nodes=machine_graph(decoded,outputs)
    # The sum is an ordered bitwise-identical operation, not just a commuted real sum.
    require(candidate[0]==target[0],'sum output is not the same ordered addition')
    require(canonical(candidate[1])==canonical(target[1]),'rounded-value identity does not replay')
    mapping=cert.get('arithmetic_mapping');signs=cert.get('arithmetic_signs')
    require(type(mapping) is list and len(mapping)==len(c_nodes)==len(t_nodes),
            'arithmetic operation count or map length mismatch')
    require(all(type(x) is int for x in mapping) and sorted(mapping)==list(range(len(t_nodes))),
            'exception correspondence must be a bijection')
    require(type(signs) is list and len(signs)==len(mapping) and all(type(x) is int and x in (-1,1) for x in signs),
            'invalid orientation evidence')
    for node,index,orientation in zip(c_nodes,mapping,signs):
        nc,nt=canonical(node),canonical(t_nodes[index])
        require(nc[1]==nt[1],'exception-generating descriptor differs')
        require(nc==(nt if orientation==1 else neg(nt)),'arithmetic orientation does not replay')
    for term in [target[1],candidate[1]]:
        needed=force_negative_zero(term)
        require(needed is None or {'a','b'}<=needed,'negative-zero residual not excluded by the supplied argument')
        require(not zero_sign(term),'all-negative-zero case has a negative-zero residual')
    require(cert.get('zero_case_s_word')==0x80000000 and zero_sign(candidate[0]),'zero sum witness differs')
    require(cert.get('zero_case_e_word')==0,'zero residual witness differs')
    require(cert.get('zero_case_final_flags')==list(range(32)),'sticky initial-flag extension differs')
    rows=check_nan_cases(candidate,c_all_nodes)
    require(rows==check_nan_cases(target,t_nodes),'source NaN cases differ')
    require(cert.get('nan_cases')==rows,'NaN provenance evidence is inconsistent')
    return dict(accepted=True,instructions=len(decoded),bytes=len(code),arithmetic_pairs=len(mapping),
                nan_symbolic_patterns=len(rows),initial_flag_masks=32,arithmetic_zero_additions=len(c_all_nodes)-len(c_nodes),
                scope='all binary32 input words under the explicitly defined masked Intel-SSE semantics',
                result='equivalence upper-bound certificate; NOT a minimum-cost certificate',
                trust='symbolic checker plus mathematical soundness lemmas; not a proof-assistant kernel or external review')

def main():
    p=argparse.ArgumentParser();p.add_argument('certificate');p.add_argument('--output');a=p.parse_args()
    try:result=verify(json.loads(Path(a.certificate).read_text()))
    except (Rejected,ValueError,TypeError,KeyError,IndexError) as exc:
        result=dict(accepted=False,error=str(exc))
    if a.output:Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))
    if not result['accepted']:raise SystemExit(1)
if __name__=='__main__':main()
