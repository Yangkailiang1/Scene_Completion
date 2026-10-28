"""Credential-scoped, cross-process admission for project runs and node chats."""
from contextlib import contextmanager
from pathlib import Path
import errno,os,tempfile,time
from .storage import fingerprint

@contextmanager
def endpoint_slot(base_url,api_key,*,limit=3,timeout=300,directory=None,pause_file=None,scope='account'):
    if type(limit) is not int or not 1<=limit<=32:raise ValueError('max_endpoint_concurrency must be between 1 and 32')
    if scope not in {'account','gateway'}:raise ValueError('invalid admission scope')
    if scope=='gateway':limit=min(3,limit)
    from urllib.parse import urlsplit
    endpoint=urlsplit(base_url)
    identity=[(endpoint.scheme.lower(),endpoint.netloc.lower()) if scope=='gateway' else base_url.rstrip('/'), 'gateway' if scope=='gateway' else fingerprint(api_key)]
    root=Path(directory or Path(tempfile.gettempdir())/'scene-model-admission')/fingerprint(identity)
    root.mkdir(parents=True,exist_ok=True);started=time.monotonic();announced=False;handle=None
    from .execution_events import emit,phase
    while handle is None:
        if pause_file and Path(pause_file).exists():
            from .scheduler import TaskBlocked
            raise TaskBlocked('pending',{'admission_paused':True})
        for n in range(limit):
            f=(root/f'slot-{n}.lock').open('a+b')
            if not f.seek(0,2):f.write(b'0');f.flush()
            f.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                handle=f;break
            except OSError as e:
                f.close()
                if e.errno not in {errno.EACCES,errno.EAGAIN,errno.EDEADLK}:raise
        if handle:break
        if not announced:
            phase('endpoint_wait');emit('endpoint_wait',limit=limit,scope=scope,message='等待同一网关的模型请求名额' if scope=='gateway' else '等待同一账号的模型请求名额');announced=True
        if time.monotonic()-started>=timeout:
            e=RuntimeError('model account admission timed out')
            e.response_diagnostic={'failure_category':'endpoint_busy','phase':'admission','transport_attempts':0,'retry_after_seconds':2};raise e
        time.sleep(.1)
    try:
        if announced:phase('model_wait');emit('endpoint_admitted',wait_seconds=round(time.monotonic()-started,2),limit=limit)
        yield
    finally:
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_UN)
        handle.close()
