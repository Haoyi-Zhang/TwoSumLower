"""Minimal, read-only local C-API adapter to the system Z3 library.

No external solver service is used. A returned 'unsat' is a solver verdict,
not an independently replayed proof certificate.
"""
import argparse,ctypes,ctypes.util,json,time
from pathlib import Path

def evaluate(script:str)->str:
    name=ctypes.util.find_library('z3')
    if not name:raise RuntimeError('Local libz3 is unavailable; this optional solver experiment cannot run')
    lib=ctypes.CDLL(name)
    pointer=ctypes.c_void_p
    lib.Z3_mk_config.argtypes=[];lib.Z3_mk_config.restype=pointer
    lib.Z3_del_config.argtypes=[pointer];lib.Z3_del_config.restype=None
    lib.Z3_mk_context.argtypes=[pointer];lib.Z3_mk_context.restype=pointer
    lib.Z3_del_context.argtypes=[pointer];lib.Z3_del_context.restype=None
    lib.Z3_eval_smtlib2_string.argtypes=[pointer,ctypes.c_char_p];lib.Z3_eval_smtlib2_string.restype=ctypes.c_char_p
    conf=lib.Z3_mk_config();ctx=lib.Z3_mk_context(conf);lib.Z3_del_config(conf)
    try:
        out=lib.Z3_eval_smtlib2_string(ctx,script.encode('utf8'))
        return out.decode('utf8') if out else ''
    finally:lib.Z3_del_context(ctx)

def main():
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output',required=True);a=p.parse_args()
    script=Path(a.input).read_text();start=time.process_time();text=evaluate(script)
    status=next((x.strip() for x in text.splitlines() if x.strip() in ('sat','unsat','unknown')),'error')
    result=dict(input=a.input,input_bytes=len(script.encode()),status=status,solver_output=text,
                cpu_seconds=time.process_time()-start,independently_replayed_certificate=False)
    Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='solver_output'}));print(text)
    if status=='error':raise SystemExit(1)
if __name__=='__main__':main()
