"""Durable finalization independent of an interactive controller's lifetime."""
import os
from pathlib import Path
import subprocess
import sys
import time

from .case_dag import run_lock
from .semantic_backend import read_json, write_json


def launch_detached(command, *, cwd, log):
    """Reparent on POSIX so host background-task cleanup cannot kill delivery."""
    log = Path(log).resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        with log.open('ab') as stream:
            return subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=stream,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW).pid
    reader, writer = os.pipe()
    intermediate = os.fork()
    if intermediate == 0:
        os.close(reader)
        os.setsid()
        pid = os.fork()
        if pid:
            os.write(writer, str(pid).encode())
            os._exit(0)
        os.close(writer)
        os.chdir(cwd)
        inp = os.open(os.devnull, os.O_RDONLY)
        out = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.dup2(inp, 0)
        os.dup2(out, 1)
        os.dup2(out, 2)
        os.execvpe(command[0], command, os.environ)
        os._exit(127)
    os.close(writer)
    data = os.read(reader, 128)
    os.close(reader)
    os.waitpid(intermediate, 0)
    if not data:
        raise RuntimeError('detached delivery launcher failed before PID handoff')
    return int(data)


def status(root):
    path = Path(root) / 'delivery_job.json'
    data = read_json(path) if path.exists() else {'status': 'not_started'}
    if data.get('status') in ('starting', 'running') and data.get('pid'):
        try:
            os.kill(data['pid'], 0)
        except ProcessLookupError:
            return {**data, 'status': 'unexpected_exit', 'ready_to_deliver': False}
    return data


def start(root, config):
    root, config = Path(root).resolve(), Path(config).resolve()
    with run_lock(root / '.delivery_job_control'):
        previous = status(root)
        if previous['status'] in ('starting', 'running') or previous.get('ready_to_deliver'):
            return previous
        # No other scheduler/finalizer may hold this run at admission time.
        with run_lock(root):
            command = [sys.executable, str(Path(__file__).parents[1] / 'scene_delivery_job.py'),
                'worker', '--run-dir', str(root), '--review-config', str(config)]
            pid = launch_detached(command, cwd=Path(__file__).resolve().parents[3],
                log=root / 'delivery_job.log')
            data = {'status': 'starting', 'pid': pid, 'started_unix': time.time(),
                'ready_to_deliver': False, 'scope': 'finalization_only', 'review_config': str(config)}
            write_json(root / 'delivery_job.json', data)
    return data


def worker(root, config):
    root = Path(root).resolve()
    # The short launcher holds a different control lock until PID/state commit.
    with run_lock(root / '.delivery_job_control'):
        data = read_json(root / 'delivery_job.json')
        if data['pid'] != os.getpid():
            raise ValueError('delivery worker differs from admitted PID')
        data['status'] = 'running'
        write_json(root / 'delivery_job.json', data)
    try:
        from .finalize import run
        result = run(root, config)
        write_json(root / 'delivery_job_result.json', result)
        data.update(status='complete' if result.get('ready_to_deliver') else 'action_required',
            ready_to_deliver=result.get('ready_to_deliver', False), finished_unix=time.time())
    except Exception as exc:
        data.update(status='action_required', ready_to_deliver=False,
            error_type=type(exc).__name__, error=str(exc), finished_unix=time.time())
        raise
    finally:
        write_json(root / 'delivery_job.json', data)
    return data
