"""Run a dynamic task graph with bounded repair and durable task outcomes."""

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import nullcontext
from contextvars import copy_context

from scene_completion.infrastructure.storage import fingerprint

from .admission import concurrency_limit
from .storage import TaskStore
from .task import TaskBlocked, TaskRejected


class SchedulerHooks:
    """Optional integration points for a workflow using the scheduler."""

    def task_registered(self, tasks, task):
        pass

    def status_changed(self, task, record, event):
        pass

    def execution_context(self, task, record):
        return nullcontext()

    def phase(self, name):
        pass

    def priority(self, task, priority_cases):
        return (
            priority_cases.index(task.case) if task.case in priority_cases else len(priority_cases)
        )

    def dependency_value(self, value):
        return value

    def keep_initial_failure(self, task, failure):
        return False

    def before_save(self, task, value):
        pass

    def result_metadata(self, task, value):
        return {}

    def fault(self, task, record):
        pass


def partition_key(parent_key, unit):
    return parent_key + "--part-" + fingerprint(unit)[:10]


class Scheduler:
    def __init__(self, root, concurrency=1, auto_repair="bounded", max_rounds=2, *, hooks=None):
        if max_rounds not in (0, 1, 2):
            raise ValueError("at most two repair rounds")
        self.store = TaskStore(root)
        self.root, self.path, self.state = self.store.root, self.store.path, self.store.state
        self.hooks = hooks if hooks is not None else SchedulerHooks()
        self.tasks = {}
        self.on_update = None
        self.on_result = None
        self.can_recover = None
        self.priority_cases = []
        self.expansions = []
        self.limit = concurrency_limit(concurrency)
        self.rounds = max_rounds if auto_repair == "bounded" else 0

    def save(self):
        self.store.save()

    def add(self, task):
        if task.key in self.tasks:
            raise ValueError("duplicate task key")
        self.tasks[task.key] = task
        self.hooks.task_registered(self.tasks, task)

    def replace_deferred(self, key, register):
        """Register the merge under the deferred parent's original key."""
        if not self.tasks[key].deferred:
            raise ValueError("only a deferred task can be replaced")
        parent = self.tasks.pop(key)
        try:
            register()
        except Exception:
            self.tasks[key] = parent
            raise

    def defer_expansion(self, dependencies, expand):
        self.expansions.append((tuple(dependencies), expand))

    def expand_ready_partitions(self):
        for dependencies, expand in list(self.expansions):
            if self.dependencies_passed(dependencies):
                self.expansions.remove((dependencies, expand))
                expand()

    def dependencies_passed(self, dependencies):
        resolved = getattr(self, "resolved_tasks", ())
        return all(
            key in resolved and self.state["tasks"][key]["status"] == "passed"
            for key in dependencies
        )

    def _event(self, key, event):
        self.state["events"].append({"task": key, "event": event, "at": time.time()})
        self.hooks.status_changed(self.tasks[key], self.state["tasks"].get(key, {}), event)

    def run(self):
        for t in self.tasks.values():
            if any(d not in self.tasks for d in t.deps):
                raise ValueError("unknown dependency")
        remaining = set(self.tasks)
        active = {}
        repair_dispatches = set()
        done = set()
        outputs = {}
        dispatches = {}
        # Historical passed flags are not proof that this execution has
        # revalidated the task's identity, dependencies and cached artifact.
        self.resolved_tasks = done

        def job(t, deps, record):
            fn = t.repair if record["rounds"] else t.execute
            with self.hooks.execution_context(t, record):
                v = (fn or t.execute)(deps, record)
                self.hooks.phase("validating")
                if t.verify:
                    t.verify(v)
                self.hooks.phase("saving")
                return v

        with ThreadPoolExecutor(max_workers=self.limit) as pool:
            while remaining or active:
                if self.store.pause_file.exists():
                    # Finish in-flight work without starting any new task; preserve checkpoints.
                    if not active:
                        break
                    remaining.clear()
                if self.on_update:
                    self.on_update()
                    remaining.update(set(self.tasks) - done - set(active.values()))
                elif self.expansions:
                    self.expand_ready_partitions()
                    remaining.update(set(self.tasks) - done - set(active.values()))
                progressed = False
                order = {key: n for n, key in enumerate(self.tasks)}
                for key in sorted(
                    remaining,
                    key=lambda k: (
                        self.hooks.priority(self.tasks[k], self.priority_cases),
                        dispatches.get(self.tasks[k].stage, 0),
                        order[k],
                    ),
                ):
                    if self.store.pause_file.exists():
                        break
                    t = self.tasks[key]
                    if not set(t.deps) <= done:
                        continue
                    if any(self.state["tasks"][d]["status"] != "passed" for d in t.deps):
                        self.state["tasks"][key] = {
                            "status": "blocked_dependency",
                            "case": t.case,
                            "stage": t.stage,
                            "blocked_by": [
                                d for d in t.deps if self.state["tasks"][d]["status"] != "passed"
                            ],
                        }
                        remaining.remove(key)
                        done.add(key)
                        progressed = True
                        continue
                    if t.deferred:
                        continue
                    deps = {d: outputs[d] for d in t.deps}
                    identity = fingerprint(
                        {
                            "version": t.version,
                            "dependencies": {
                                d: self.hooks.dependency_value(v) for d, v in deps.items()
                            },
                        }
                    )
                    rec = self.state["tasks"].get(key, {})
                    if rec.get("identity") != identity:
                        rec = {
                            "identity": identity,
                            "status": "pending",
                            "rounds": rec.get("rounds", 0)
                            if rec.get("status") == "awaiting_answer"
                            else 0,
                            "case": t.case,
                            "stage": t.stage,
                        }
                        self.state["tasks"][key] = rec
                    if rec.get("status") == "passed":
                        try:
                            v = self.store.load_output(rec)
                            if t.verify:
                                t.verify(v)
                            outputs[key] = v
                            remaining.remove(key)
                            done.add(key)
                            progressed = True
                            continue
                        except (OSError, ValueError, KeyError):
                            rec.update(status="pending", rounds=0)
                    attempt_identity = t.attempt_identity
                    if (
                        attempt_identity
                        and rec.get("attempt_identity") != attempt_identity
                        and rec.get("status") in {"rejected", "failed", "awaiting_configuration"}
                    ):
                        # Explicit provider edits allow a fresh bounded attempt window, not lost history.
                        rec.setdefault("attempt_windows", []).append(
                            {
                                k: rec.get(k)
                                for k in ("attempt_identity", "rounds", "failure", "finished_at")
                            }
                        )
                        rec.update(status="pending", rounds=0)
                        rec.pop("recovery_dispatch", None)
                        rec.pop("failure_signatures", None)
                    rec["attempt_identity"] = attempt_identity
                    # Waiting for a worker slot is not a semantic repair. Do
                    # not consume rounds on every scheduler wake-up while
                    # independent requests are still occupying the pool.
                    if len(active) >= self.limit:
                        continue
                    if rec["status"] in {"rejected", "failed"}:
                        if rec["rounds"] >= self.rounds:
                            if self.can_recover and self.can_recover(t, rec):
                                rec["recovery_dispatch"] = True
                                rec["recovery_calls"] = rec.get("recovery_calls", 0) + 1
                            else:
                                remaining.remove(key)
                                done.add(key)
                                progressed = True
                                continue
                        else:
                            rec["rounds"] += 1
                            repair_dispatches.add(key)
                    elif (
                        rec["status"] == "awaiting_configuration"
                        and self.can_recover
                        and self.can_recover(t, rec)
                    ):
                        rec["recovery_dispatch"] = True
                        rec["recovery_calls"] = rec.get("recovery_calls", 0) + 1
                    previous_failure = rec.get("failure")
                    rec["version"] = t.version
                    rec.update(status="running", started_at=time.time())
                    rec.pop("failure", None)
                    rec.pop("finished_at", None)
                    self._event(key, "repairing" if rec["rounds"] else "started")
                    attempt_record = dict(rec)
                    if previous_failure and (
                        rec["rounds"]
                        or rec.get("recovery_dispatch")
                        or self.hooks.keep_initial_failure(t, previous_failure)
                    ):
                        attempt_record["failure"] = previous_failure
                    future = pool.submit(copy_context().run, job, t, deps, attempt_record)
                    active[future] = key
                    remaining.remove(key)
                    progressed = True
                    dispatches[t.stage] = dispatches.get(t.stage, 0) + 1
                self.save()
                if not active:
                    if remaining and not progressed:
                        raise ValueError("dependency cycle")
                    continue
                finished, _ = wait(active, return_when=FIRST_COMPLETED)
                for f in finished:
                    key = active.pop(f)
                    is_repair = key in repair_dispatches
                    repair_dispatches.discard(key)
                    rec = self.state["tasks"][key]
                    try:
                        v = f.result()
                        task = self.tasks[key]
                        self.hooks.before_save(task, v)
                        file = self.store.save_output(key, rec["identity"], v)
                        rec.update(self.hooks.result_metadata(task, v))
                        rec.update(
                            status="passed",
                            output_file=file,
                            output_hash=fingerprint(v),
                            finished_at=time.time(),
                        )
                        outputs[key] = v
                        done.add(key)
                        self._event(key, "passed")
                    except TaskBlocked as e:
                        if is_repair and e.details.get("semantic_round_not_started"):
                            rec["rounds"] -= 1
                        rec.update(status=e.status, failure=e.details, finished_at=time.time())
                        self._event(key, e.status)
                        if (
                            e.status == "awaiting_configuration"
                            and self.can_recover
                            and self.can_recover(self.tasks[key], rec)
                        ):
                            remaining.add(key)
                        else:
                            done.add(key)
                    except Exception as e:
                        rec.update(
                            finished_at=time.time(),
                            status="rejected"
                            if isinstance(e, (TaskRejected, ValueError))
                            else "failed",
                            failure=getattr(
                                e, "details", {"error": str(e), "type": type(e).__name__}
                            ),
                        )
                        failure = rec["failure"]
                        sig = fingerprint(
                            {
                                k: v
                                for k, v in failure.items()
                                if k
                                not in {
                                    "rejected_output",
                                    "candidate_file",
                                    "path",
                                    "request_id",
                                    "at",
                                }
                            }
                        )
                        history = rec.setdefault("failure_signatures", [])
                        history.append(sig)
                        if (
                            rec["status"] == "failed"
                            or len(history) > 1
                            and history[-1] == history[-2]
                        ):
                            rec["rounds"] = self.rounds
                        self._event(key, rec["status"])
                        remaining.add(key)
                        if rec["status"] == "failed" or rec.get("recovery_dispatch"):
                            self.hooks.fault(self.tasks[key], rec)
                    self.save()
                    if self.on_result:
                        self.on_result()
        return {
            "complete": all(
                self.state["tasks"].get(k, {}).get("status") == "passed" for k in self.tasks
            )
        }
