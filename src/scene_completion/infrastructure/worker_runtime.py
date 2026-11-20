"""Project processes and heartbeats; web process never hosts a production DAG."""

import json
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from scene_completion.infrastructure.storage import read_json, write_json


def pid_alive(pid):
    if os.name == "nt":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87
        try:
            code = ctypes.c_ulong()
            ok = kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
            return not ok or code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def user_hold(project):
    try:
        hold = read_json(Path(project) / "run/pause_requested.json")
    except FileNotFoundError:
        return None
    return hold if hold.get("by") == "user" else None


def read_job(project):
    p = Path(project)
    job = read_json(p / "job.json") if (p / "job.json").exists() else {"status": "ready"}
    hb = p / "worker-heartbeat.json"
    if job.get("status") == "running" and hb.exists():
        row = read_json(hb)
        if (
            job.get("worker_token")
            and row.get("pid") == job.get("pid")
            and row.get("worker_token") == job["worker_token"]
        ):
            job.update(worker_heartbeat=row["at"])
    if value := user_hold(p):
        job["control_state"] = (
            ("pausing" if value.get("action") == "pause" else "stopping")
            if job.get("status") == "running"
            else ("paused" if value.get("action") == "pause" else "stopped")
        )
    return job


def job_lock(project):
    from scene_completion.workflow_core.storage import run_lock

    return run_lock(Path(project) / "job-state", blocking=True)


def same_run(left, right):
    return all(left.get(key) == right.get(key) for key in ("worker_token", "started_at"))


def live_job(job):
    return job.get("status") == "running" and (
        job.get("worker_heartbeat", job.get("started_at", 0)) > time.time() - 30
        or bool(job.get("pid") and pid_alive(job["pid"]))
    )


def new_job(options):
    started_at = time.time()
    return {
        "status": "running",
        "worker_token": secrets.token_hex(16),
        "started_at": started_at,
        "worker_heartbeat": started_at,
        "run_options": options,
    }


def update_job(project, expected, **changes):
    with job_lock(project):
        current = read_job(project)
        if not same_run(current, expected) or current.get("status") != expected.get("status"):
            return None
        current.update(changes)
        current.pop("control_state", None)
        write_json(Path(project) / "job.json", current)
        return current


def interrupt_job(project, observed, message, *, exit_code=None):
    with job_lock(project):
        job = read_job(project)
        if job.get("status") != "running" or not same_run(job, observed):
            return None
        if exit_code is None and live_job(job):
            return None
        job.update(status="interrupted", message=message)
        job.pop("control_state", None)
        if exit_code is not None:
            job["exit_code"] = exit_code
        write_json(Path(project) / "job.json", job)
        return job


def register_worker(project, token, pid):
    with job_lock(project):
        job = read_job(project)
        if (
            not token
            or job.get("worker_token") != token
            or job.get("status") != "running"
            or job.get("pid")
        ):
            return None
        job.update(pid=pid, worker_heartbeat=time.time())
        job.pop("control_state", None)
        write_json(Path(project) / "job.json", job)
        return job


def spawn(service, rid, token):
    p = service.run_dir(rid)
    log = p / "run/worker.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        # Local CLI exits after dispatch; the project worker must survive its terminal parent.
        kwargs["start_new_session"] = True
    with log.open("ab") as out:
        process = subprocess.Popen(
            [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                str(Path(__file__).with_name("project_worker.py")),
                "--root",
                str(service.root),
                "--project",
                rid,
                "--worker-token",
                token,
                "--env-file",
                str(service.env_file),
            ],
            stdout=out,
            stderr=out,
            **kwargs,
        )
    return process


def unsafe_to_resume(project):
    """An unfinished HTTP call or timed-out POST cannot be blindly reissued."""
    from scene_completion.infrastructure.execution_events import EventStore

    root = Path(project) / "run"
    if not (root / "execution_events.sqlite3").exists():
        return False
    store = EventStore(root)
    with store.connect() as db:
        rows = db.execute(
            "SELECT payload FROM events WHERE kind IN ('request_started','request_finished','request_failed') ORDER BY id DESC LIMIT 200"
        ).fetchall()
    latest = {}
    for (raw,) in rows:
        event = json.loads(raw)
        key = event["data"].get("model_call_id")
        if key:
            latest.setdefault(key, event)
    for e in latest.values():
        if e["kind"] == "request_started":
            return True
        if e["kind"] == "request_failed" and e["data"].get("diagnostic", {}).get(
            "failure_category"
        ) in {"transport_timeout", "stream_incomplete", "connection_failed"}:
            return True
    return False


def restart_if_safe(service, rid, job):
    from scene_completion.workflow_core.storage import run_lock

    project = service.run_dir(rid)
    try:
        with run_lock(project / "dispatch"):
            current = read_job(project)
            if (
                not same_run(current, job)
                or current.get("status") != "interrupted"
                or current.get("reason") in {"user_pause", "user_stop"}
                or unsafe_to_resume(project)
            ):
                return
            marker = project / "worker-restarts.json"
            record = read_json(marker) if marker.exists() else {"count": 0}
            if record["count"] < 1:
                write_json(marker, {**record, "count": record["count"] + 1})
                service._start(rid, current.get("run_options", {}))
    except ValueError:
        return


def monitor(service, rid, process, dispatched):
    p = service.run_dir(rid)
    code = process.wait()
    job = interrupt_job(
        p, dispatched, "执行进程退出，现场已保存；检查不确定请求后再恢复", exit_code=code
    )
    if job is not None:
        from scene_completion.application.recovery_handoff import prepare_handoff

        prepare_handoff(p)
    with service.lock:
        service.active.discard(rid)
    current = read_job(p)
    if same_run(current, dispatched) and current.get("status") == "interrupted":
        restart_if_safe(service, rid, current)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--worker-token", required=True)
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()
    from scene_completion.application.project_service import Workbench

    service = Workbench(args.root, env_file=args.env_file, worker=True)
    project = service.run_dir(args.project)
    stop = threading.Event()
    token = args.worker_token
    job = register_worker(project, token, os.getpid())
    if job is None:
        print("worker 启动身份已过期或已被领取", file=sys.stderr)
        return
    service.active.add(args.project)

    def heartbeat():
        while not stop.wait(1):
            request = project / "worker-stop.json"
            if request.exists() and read_json(request).get("worker_token") == token:
                if update_job(
                    project,
                    job,
                    status="interrupted",
                    reason="user_stop",
                    message="用户停止后台服务，已保留检查点；未决模型请求不会自动重发",
                ):
                    os._exit(0)
                return
            with job_lock(project):
                current = read_job(project)
                if not same_run(current, job) or current.get("status") != "running":
                    return
                write_json(
                    project / "worker-heartbeat.json",
                    {"pid": os.getpid(), "worker_token": token, "at": time.time()},
                )

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        service._execute(args.project, job)
    finally:
        stop.set()
        thread.join(timeout=2)


def stop_workers(service):
    from scene_completion.manager.manager_runtime import stop_managers

    stop_managers(service)
    for path in service.root.glob("*/project.json"):
        p = path.parent
        with job_lock(p):
            job = read_job(p)
            if job.get("status") == "running" and job.get("worker_token"):
                write_json(
                    p / "worker-stop.json", {"worker_token": job["worker_token"], "at": time.time()}
                )


class Guardian:
    """Reattach to heartbeats after web restart without guessing HTTP outcomes."""

    def __init__(self, service):
        self.service = service
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="scene-worker-guardian")
        self.thread.start()

    def close(self):
        self.stop.set()

    def loop(self):
        while not self.stop.wait(5):
            for path in self.service.root.glob("*/project.json"):
                p = path.parent
                job = read_job(p)
                if job.get("status") != "running" or p.name in self.service.active:
                    continue
                if not live_job(job) and (
                    job := interrupt_job(p, job, "进程失联，检查点已保留；仅在无未决模型请求时恢复")
                ):
                    restart_if_safe(self.service, p.name, job)
