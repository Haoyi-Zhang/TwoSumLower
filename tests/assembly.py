"""Assemble and inspect bytes only. This test never executes the target block."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from certificate_checker import decode

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='results/assembly.json');args=p.parse_args()
    cert=json.loads(Path('proofs/equivalence.json').read_text())
    with tempfile.TemporaryDirectory(prefix='twosum-asm-') as t:
        obj=Path(t)/'block.o';raw=Path(t)/'text.bin'
        subprocess.run(['as','--64','-o',str(obj),'src/kernel.S'],check=True,timeout=10)
        subprocess.run(['objcopy','-O','binary','--only-section=.text',str(obj),str(raw)],check=True,timeout=10)
        code=raw.read_bytes()
    decoded=decode(code)
    assert code.hex()==cert['program_hex']
    assert [len(decoded),len(code)]==cert['claimed_cost']
    result=dict(assembled_instructions=len(decoded),assembled_bytes=len(code),certificate_bytes_match=True,
                instruction_lengths=[i[-1] for i in decoded],target_executed=False,
                interpretation='static assembler cross-check, not hardware testing or performance evidence')
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
