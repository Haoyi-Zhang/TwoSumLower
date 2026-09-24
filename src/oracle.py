"""Independent rational oracle for reduced-format finite rounding.

It enumerates representable nonnegative finite values, bisects an exact Fraction,
and compares distances, rather than using the dyadic encoder's shift/round logic.
Special cases are implemented separately from fpmodel's operation dispatcher.
Small formats use an enumerated ordered table; binary32 uses a monotone search through finite encodings.
"""
from fractions import Fraction
from bisect import bisect_left

def power2(e): return Fraction(1<<e,1) if e>=0 else Fraction(1,1<<(-e))

class RationalOracle:
    def __init__(self,e=4,f=3):
        self.e,self.f=e,f;self.n=1+e+f;self.S=1<<(e+f)
        self.E=(1<<e)-1;self.F=(1<<f)-1;self.B=(1<<(e-1))-1
        self.I=self.E<<f;self.Q=1<<(f-1);self.M=(1<<self.n)-1
        self.values=[self.value(w) for w in range(self.I)] if self.n<=12 else None
        self.overflow_threshold=power2(self.E-self.B)-power2(self.E-self.B-f-2)
        # threshold = 2**(emax+1) - half an ulp at the largest finite number
    def kind(self,w):
        e=(w>>self.f)&self.E;v=w&self.F
        if e!=self.E: return 'z' if e==0 and v==0 else 'f'
        return 'i' if v==0 else ('q' if v&self.Q else 's')
    def value(self,w):
        exp=(w>>self.f)&self.E; frac=w&self.F
        if exp==self.E: raise ValueError('nonfinite')
        m=frac if exp==0 else frac+(1<<self.f)
        v=m*power2((1-self.B if exp==0 else exp-self.B)-self.f)
        return -v if w&self.S else v
    def round(self,v,negative_zero=False):
        sign=self.S if v<0 or (v==0 and negative_zero) else 0
        v=abs(v)
        if v>=self.overflow_threshold: return sign|self.I,20
        if self.values is not None:
            ix=bisect_left(self.values,v)
            get=lambda w:self.values[w]
        else:
            # Monotone search through encodings; at most n-1 comparisons.
            lo,hi=0,self.I
            while lo<hi:
                mid=(lo+hi)//2
                if self.value(mid)<v:lo=mid+1
                else:hi=mid
            ix=lo;get=self.value
        if ix<self.I and get(ix)==v:return sign|ix,0
        if ix==self.I:chosen=ix-1
        else:
            lo=ix-1;hi=ix;dl=v-get(lo);dh=get(hi)-v
            chosen=lo if dl<dh or (dl==dh and lo%2==0) else hi
        tiny_threshold=power2(1-self.B)-power2(1-self.B-self.f-2)
        return sign|chosen,16|(8 if 0<v<tiny_threshold else 0)
    def op(self,op,a,b,imm=0,mask=0):
        if op=='ANDPS':return a&b,0
        if op=='ORPS':return a|b,0
        if op=='XORPS':return a^b,0
        if op=='BLENDVPS':return (b if mask>=self.S else a),0
        ka,kb=self.kind(a),self.kind(b)
        na,nb=ka in ('q','s'),kb in ('q','s')
        if op=='CMPSS':
            un=na or nb
            if un: out=imm in (3,4,5,6)
            else:
                def key(w,k):
                    if k=='i':return (0 if w&self.S else 2,Fraction(0))
                    return 1,self.value(w)
                aa,bb=key(a,ka),key(b,kb)
                out=(aa==bb,aa<bb,aa<=bb,False,aa!=bb,aa>=bb,aa>bb,True)[imm]
            bad=ka=='s' or kb=='s' or ((na or nb) and imm in (1,2,5,6))
            return self.M if out else 0, int(bad)
        if op in ('MINSS','MAXSS'):
            if na or nb:return b,1
            def key(w,k):
                if k=='i':return (0 if w&self.S else 2,Fraction(0))
                return 1,self.value(w)
            aa,bb=key(a,ka),key(b,kb)
            take=aa<bb if op=='MINSS' else aa>bb
            return (a if take else b),0
        if na or nb:return (a if na else b)|self.Q,int(ka=='s' or kb=='s')
        sa,sb=bool(a&self.S),bool(b&self.S)
        indef=self.S|self.I|self.Q
        if op=='MULSS':
            if (ka=='i' and kb=='z') or (kb=='i' and ka=='z'):return indef,1
            if ka=='i' or kb=='i':return (self.S if sa!=sb else 0)|self.I,0
            return self.round(self.value(a)*self.value(b),sa!=sb)
        if op not in ('ADDSS','SUBSS'):raise ValueError(op)
        effective_sb=sb^(op=='SUBSS')
        if ka=='i' or kb=='i':
            if ka=='i' and kb=='i' and sa!=effective_sb:return indef,1
            return (a if ka=='i' else ((self.S if effective_sb else 0)|self.I)),0
        x,y=self.value(a),self.value(b)
        v=x-y if op=='SUBSS' else x+y
        return self.round(v,sa and effective_sb)
