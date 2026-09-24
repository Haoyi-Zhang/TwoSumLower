"""Limit an already-exec'ed child, arrange parent-death cleanup, then exec."""
import ctypes,os,resource,signal,sys
seconds=int(sys.argv[1]);command=sys.argv[2:]
if not command:raise SystemExit('missing child command')
resource.setrlimit(resource.RLIMIT_AS,(2200*1024**2,2200*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(seconds,seconds+1))
if hasattr(os,'sched_getaffinity'):
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
# Linux PR_SET_PDEATHSIG prevents a canceled outer tool from leaving a solver.
parent=os.getppid()
if sys.platform.startswith('linux'):
 libc=ctypes.CDLL(None,use_errno=True)
 if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:
  raise OSError(ctypes.get_errno(),'PR_SET_PDEATHSIG failed')
 if parent==1 or os.getppid()!=parent:raise SystemExit('supervisor is no longer present')
os.execvpe(command[0],command,os.environ)
