"""Freeze a diagnostic set before the binary32/mutation validation campaign."""
import json,random
from pathlib import Path

def main():
    positive=[0,1,0x007fffff,0x00800000,0x3f800000,0x3f800001,0x7f7fffff,0x73c00000,0x7f800000,0x7fc00001,0x7f800001,0x33800000]
    words=[x|s for x in positive for s in (0,0x80000000)]
    pairs=[(a,b,'edge-product') for a in words for b in words]
    rng=random.Random(20260914)
    while len(pairs)<1000:
        a,b=rng.getrandbits(32),rng.getrandbits(32)
        if not any(x==a and y==b for x,y,_ in pairs):pairs.append((a,b,'seeded-word-pair'))
    payload=dict(seed=20260914,edge_words=[f'0x{x:08x}' for x in words],
                 selection='24 edge words squared, followed by 424 distinct seeded word pairs; diagnostics, not a held-out benchmark',
                 cases=[dict(id=f'C{i+1:04d}',a=f'0x{a:08x}',b=f'0x{b:08x}',stratum=t) for i,(a,b,t) in enumerate(pairs)])
    Path('inputs/binary32-cases.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(dict(classes=len(pairs),edge_pairs=576,seeded_pairs=424)))
if __name__=='__main__':main()
