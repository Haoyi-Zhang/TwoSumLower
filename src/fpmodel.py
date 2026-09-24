"""Exact dyadic RNE model. No host floating-point instructions implement the model.

Five IEEE flags are projected from masked SSE semantics; denormal-operand is
intentionally not observed. Tininess uses destination-precision rounding with an unbounded exponent range.
Intel NaN selection: first source if NaN, otherwise second; quiet the result.
This source is authored for this project, not copied from a floating-point library.
"""
from dataclasses import dataclass
from typing import NamedTuple

INVALID, DIVZERO, OVERFLOW, UNDERFLOW, INEXACT = 1, 2, 4, 8, 16

class Result(NamedTuple):
    word: int
    flags: int

@dataclass(frozen=True)
class Format:
    ebits: int
    fbits: int
    def __post_init__(self):
        if self.ebits < 3 or self.fbits < 2:
            raise ValueError('The model requires ebits >= 3 and fbits >= 2')
    @property
    def width(self): return 1+self.ebits+self.fbits
    @property
    def sign(self): return 1 << (self.width-1)
    @property
    def mask(self): return (1 << self.width)-1
    @property
    def fracmask(self): return (1 << self.fbits)-1
    @property
    def expmax(self): return (1 << self.ebits)-1
    @property
    def bias(self): return (1 << (self.ebits-1))-1
    @property
    def emin(self): return 1-self.bias
    @property
    def emax(self): return self.expmax-1-self.bias
    @property
    def inf(self): return self.expmax << self.fbits
    @property
    def quiet(self): return 1 << (self.fbits-1)
    @property
    def indefinite(self): return self.sign | self.inf | self.quiet
    def parts(self, w):
        if not 0 <= w <= self.mask: raise ValueError('word out of range')
        return bool(w & self.sign), (w >> self.fbits) & self.expmax, w & self.fracmask
    def kind(self, w):
        _, e, f = self.parts(w)
        if e == self.expmax:
            return ('qnan' if f & self.quiet else 'snan') if f else 'inf'
        if e == 0: return 'subnormal' if f else 'zero'
        return 'normal'
    def nan(self,w): return (w & self.inf)==self.inf and (w & self.fracmask)!=0
    def snan(self,w): return self.nan(w) and not (w & self.quiet)
    def infinity(self,w): return (w & ~self.sign)==self.inf
    def zero(self,w): return (w & ~self.sign)==0
    def finite(self,w): return (w & self.inf)!=self.inf
    def dyadic(self,w):
        s,e,f = self.parts(w)
        if e == self.expmax: raise ValueError('nonfinite word')
        m = f if e==0 else (1<<self.fbits)+f
        k = (self.emin if e==0 else e-self.bias)-self.fbits
        return (-m if s else m), k
    def rounded(self, n:int, k:int, zero_sign:bool=False)->Result:
        """Round the exact dyadic n*2**k to the target word (ties to even)."""
        if n == 0: return Result(self.sign if zero_sign else 0, 0)
        sign = self.sign if n < 0 else 0
        n = abs(n)
        # Intel SDM 4.9.1.5: test tininess after p-bit rounding with an
        # UNBOUNDED exponent, not after rounding into subnormal storage.
        # The boundary below min-normal is min-normal - min-subnormal/4.
        te = self.emin-self.fbits-2
        threshold = (1 << (self.fbits+2))-1
        tiny = ((n << (k-te)) < threshold) if k>=te else (n < (threshold << (te-k)))
        top = n.bit_length()-1+k
        unit = max(top-self.fbits, self.emin-self.fbits)
        shift = unit-k
        if shift > 0:
            q, rem = divmod(n, 1 << shift)
            half = 1 << (shift-1)
            q += rem > half or (rem == half and (q & 1))
            inex = rem != 0
        else:
            q = n << (-shift)
            inex = False
        if q == 0:
            return Result(sign, (INEXACT | UNDERFLOW) if inex else 0)
        # A carry must normalize without losing any bits.
        if q.bit_length() > self.fbits+1:
            assert q == (1 << (self.fbits+1))
            q >>= 1
            unit += 1
        top = q.bit_length()-1+unit
        if top > self.emax:
            return Result(sign | self.inf, OVERFLOW | INEXACT)
        if q < (1 << self.fbits) and unit == self.emin-self.fbits:
            flags = (UNDERFLOW | INEXACT) if inex else 0
            return Result(sign | q, flags)
        # Normal significand is exactly fbits+1 bits at this point.
        assert q.bit_length() == self.fbits+1, (n,k,q,unit)
        e = unit+self.fbits+self.bias
        return Result(sign | (e << self.fbits) | (q & self.fracmask), (INEXACT | (UNDERFLOW if tiny else 0)) if inex else 0)
    def arithmetic(self,op:str,a:int,b:int)->Result:
        if op not in ('ADDSS','SUBSS','MULSS'): raise ValueError(op)
        # SUB never flips the sign or payload of an input NaN.
        if self.nan(a) or self.nan(b):
            src = a if self.nan(a) else b
            return Result(src | self.quiet, INVALID if self.snan(a) or self.snan(b) else 0)
        if op == 'MULSS':
            s = (a ^ b) & self.sign
            if (self.infinity(a) and self.zero(b)) or (self.infinity(b) and self.zero(a)):
                return Result(self.indefinite,INVALID)
            if self.infinity(a) or self.infinity(b): return Result(s | self.inf,0)
            x,ex=self.dyadic(a); y,ey=self.dyadic(b)
            return self.rounded(x*y, ex+ey, bool(s))
        bb = b ^ self.sign if op == 'SUBSS' else b
        if self.infinity(a) or self.infinity(bb):
            if self.infinity(a) and self.infinity(bb) and bool((a ^ bb) & self.sign):
                return Result(self.indefinite,INVALID)
            return Result(a if self.infinity(a) else bb,0)
        x,ex=self.dyadic(a); y,ey=self.dyadic(bb)
        base=min(ex,ey)
        n=(x << (ex-base)) + (y << (ey-base))
        return self.rounded(n,base, bool((a & bb) & self.sign))
    def ordered_compare(self,a,b):
        """Return -1, 0, 1 on non-NaN operands, including both infinities."""
        if self.nan(a) or self.nan(b): raise ValueError('unordered')
        if self.zero(a) and self.zero(b): return 0
        if a == b: return 0
        sa,sb=bool(a & self.sign),bool(b & self.sign)
        if sa != sb: return -1 if sa else 1
        return (-1 if a>b else 1) if sa else (-1 if a<b else 1)
    def operation(self,op,a,b,imm=0,blend_mask=0)->Result:
        self.parts(a);self.parts(b)
        if op in ('ADDSS','SUBSS','MULSS'): return self.arithmetic(op,a,b)
        if op=='ANDPS': return Result(a & b,0)
        if op=='ORPS': return Result(a | b,0)
        if op=='XORPS': return Result(a ^ b,0)
        if op=='BLENDVPS':
            self.parts(blend_mask)
            return Result(b if blend_mask & self.sign else a,0)
        unordered=self.nan(a) or self.nan(b)
        if op in ('MINSS','MAXSS'):
            if unordered: return Result(b,INVALID)
            c=self.ordered_compare(a,b)
            return Result(a if (c<0 if op=='MINSS' else c>0) else b,0)
        if op=='CMPSS':
            if not 0<=imm<=7: raise ValueError('legacy CMPSS predicates are 0..7')
            bad=(self.snan(a) or self.snan(b) or (unordered and imm in (1,2,5,6)))
            c=None if unordered else self.ordered_compare(a,b)
            pred=(not unordered and c==0,not unordered and c<0,not unordered and c<=0,
                  unordered,unordered or c!=0,unordered or c>=0,unordered or c>0,not unordered)[imm]
            return Result(self.mask if pred else 0, INVALID if bad else 0)
        raise ValueError(op)

BINARY32=Format(8,23)
TOY=Format(4,3)
FLAG_NAMES={1:'invalid',2:'divide-by-zero',4:'overflow',8:'underflow',16:'inexact'}

def reference(fmt:Format,a:int,b:int,initial_flags=0,trace=False):
    """SC'25 Algorithm 1 in its published operand order, under the explicit ISA model."""
    f=initial_flags; steps=[]
    def call(name,op,x,y):
        nonlocal f
        r=fmt.operation(op,x,y); f|=r.flags
        steps.append(dict(name=name,op=op,a=x,b=y,result=r.word,raised=r.flags,sticky=f))
        return r.word
    s=call('s','ADDSS',a,b)
    xeff=call('xeff','SUBSS',s,b)
    yeff=call('yeff','SUBSS',s,xeff)
    dx=call('dx','SUBSS',a,xeff)
    dy=call('dy','SUBSS',b,yeff)
    e=call('e','ADDSS',dx,dy)
    return (s,e,f,steps) if trace else (s,e,f)

# All costs include copies; no MOV opcode and no three-operand ADDSS are assumed.
CANDIDATE=[('ORPS',2,1,0),('ORPS',3,0,0),('ADDSS',0,1,0),('SUBSS',2,0,0),
           ('ADDSS',3,2,0),('ADDSS',2,0,0),('SUBSS',1,2,0),('ADDSS',3,1,0)]
SWAPPED_CANDIDATE=[('ORPS',2,0,0),('ORPS',3,0,0),('ADDSS',0,1,0),('SUBSS',2,0,0),
           ('ADDSS',1,2,0),('ADDSS',2,0,0),('SUBSS',3,2,0),('ADDSS',3,1,0)]
# Literal lowering of the reference DAG; 9 instructions, hence NOT admitted by the cap.
REFERENCE_LOWERING=[('ORPS',2,0,0),('ADDSS',2,1,0),('ORPS',3,2,0),('SUBSS',3,1,0),
                    ('SUBSS',0,3,0),('ORPS',4,2,0),('SUBSS',4,3,0),('SUBSS',1,4,0),
                    ('ADDSS',0,1,0)]
OP_BYTES={'ADDSS':4,'SUBSS':4,'MULSS':4,'MINSS':4,'MAXSS':4,
          'ANDPS':3,'ORPS':3,'XORPS':3,'CMPSS':5,'BLENDVPS':5}

def program_cost(program,cap=8):
    if len(program)>cap: raise ValueError('length cap exceeded')
    total=0
    for op,dst,src,imm in program:
        if op not in OP_BYTES: raise ValueError('opcode outside grammar')
        if not (isinstance(dst,int) and isinstance(src,int) and 0<=dst<6 and 0<=src<6):
            raise ValueError('register outside grammar')
        if (op=='CMPSS' and not 0<=imm<8) or (op!='CMPSS' and imm!=0):
            raise ValueError('invalid immediate')
        total+=OP_BYTES[op]
    if total >= 1<<64: raise OverflowError('64-bit cost overflow')
    return len(program),total

def execute(fmt,program,a,b,outputs=(0,3),initial_flags=0,trace=False,cap=8):
    program_cost(program,cap)
    if not all(isinstance(x,int) and 0<=x<6 for x in outputs) or len(outputs)!=2:
        raise ValueError('output register')
    regs=[a,b,0,0,0,0]; f=initial_flags; steps=[]
    for op,dst,src,imm in program:
        aa,bb,mask=regs[dst],regs[src],regs[0]
        r=fmt.operation(op,aa,bb,imm,mask)
        regs[dst]=r.word;f|=r.flags
        steps.append(dict(op=op,dst=dst,src=src,imm=imm,a=aa,b=bb,mask=mask,
                          result=r.word,raised=r.flags,sticky=f))
    ans=(regs[outputs[0]],regs[outputs[1]],f)
    return (*ans,steps) if trace else ans
