"""Explicit project pause/stop/resume; never discard successful artifacts."""

import time

from scene_completion.infrastructure.execution_events import EventStore
from scene_completion.infrastructure.storage import read_json, write_json
from scene_completion.infrastructure.worker_runtime import read_job


def control(service, rid, body):
    if service.review_only:
        raise ValueError("业务审核模式不能控制模型执行")
    p = service.run_dir(rid)
    action = body.get("action")
    job = read_job(p)
    hold = p / "run/pause_requested.json"
    if action not in {"pause", "stop", "resume"}:
        raise ValueError("action必须为pause、stop或resume")
    if body.get("dry_run"):
        return {
            "action": action,
            "saved": False,
            "status": job.get("status"),
            "retains_artifacts": True,
        }
    if action == "resume":
        if job.get("status") == "running" or rid in service.active:
            raise ValueError("请等待当前请求结束并进入暂停／停止状态后继续")
        previous = read_json(hold) if hold.exists() else None
        if hold.exists():
            hold.unlink()
        try:
            return service.start(rid)
        except Exception:
            if previous:
                write_json(hold, previous)
            raise
    write_json(hold, {"by": "user", "action": action, "at": time.time()})
    if action == "stop" and job.get("status") == "running" and job.get("worker_token"):
        write_json(p / "worker-stop.json", {"worker_token": job["worker_token"], "at": time.time()})
    elif job.get("status") != "running":
        job.update(
            status="paused" if action == "pause" else "interrupted",
            reason="user_pause" if action == "pause" else "user_stop",
            message="已保留成功产物及检查点；继续前不会自动派发模型请求",
        )
        write_json(p / "job.json", job)
    EventStore(p / "run").append(
        "execution_control", action=action, status=job.get("status"), retains_artifacts=True
    )
    return {
        "action": action,
        "status": job.get("status"),
        "control_state": action + "ing" if job.get("status") == "running" else job.get("status"),
        "retains_artifacts": True,
        "message": "暂停等待在途请求完成后生效；停止会终止本项目工作进程，未决请求不会自动重发"
        if action == "pause"
        else "正在停止本项目；成功文件保留，未决模型用量继续保守记录",
    }
