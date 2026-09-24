"""Run one scientific chunk with bounded resources and process accounting.

The launcher applies hard limits only after exec; no Python preexec callback is
used. Output is redirected to files so a full pipe cannot prevent supervision.
"""
import argparse,json,os,resource,signal,subprocess,sys,tempfile,time
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--label',required=True)
 p.add_argument('--log',default='results/resources.jsonl');p.add_argument('--seconds',type=int,default=105)
 p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
 if a.command and a.command[0]=='--':a.command=a.command[1:]
 if not a.command or not 1<=a.seconds<=110:raise SystemExit('command required; seconds in 1..110')
 env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
 before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic();swap_max=0;timed_out=False
 launcher=str(Path(__file__).with_name('limit_exec.py'))
 with tempfile.TemporaryDirectory(prefix='twosum-run-') as temp:
  so=Path(temp)/'stdout';se=Path(temp)/'stderr'
  with so.open('w') as out,se.open('w') as err:
   child=subprocess.Popen([sys.executable,launcher,str(a.seconds),*a.command],env=env,
                           stdout=out,stderr=err,start_new_session=True)
   while child.poll() is None:
    try:
     for line in Path(f'/proc/{child.pid}/status').read_text().splitlines():
      if line.startswith('VmSwap:'):swap_max=max(swap_max,int(line.split()[1]))
    except OSError:pass
    if time.monotonic()-start>a.seconds+1:
     timed_out=True
     try:os.killpg(child.pid,signal.SIGKILL)
     except ProcessLookupError:pass
     break
    time.sleep(.1)
   child.wait(timeout=3)
  stdout=so.read_text(errors='replace');stderr=se.read_text(errors='replace')
 after=resource.getrusage(resource.RUSAGE_CHILDREN)
 record=dict(label=a.label,command=a.command,exit_code=child.returncode,wall_seconds=round(time.monotonic()-start,6),
             cpu_seconds=round((after.ru_utime-before.ru_utime)+(after.ru_stime-before.ru_stime),6),
             child_peak_rss_kib=after.ru_maxrss,observed_swap_kib=swap_max,timeout=timed_out,resource_limit_signal=child.returncode in (-signal.SIGXCPU,-signal.SIGKILL),
             workers=1,address_space_limit_mib=2200,cpu_limit_seconds=a.seconds)
 path=Path(a.log);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a') as out:out.write(json.dumps(record,sort_keys=True)+'\n')
 print(json.dumps(record),flush=True);print(stdout,end='',flush=True);print(stderr,end='',file=sys.stderr,flush=True)
 raise SystemExit(124 if timed_out else child.returncode)
if __name__=='__main__':main()
