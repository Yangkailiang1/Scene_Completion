"""Register business partitions while the scheduler owns expansion and replacement."""

from copy import deepcopy

from scene_completion.domain.contracts import TASKS
from scene_completion.infrastructure.storage import read_json
from scene_completion.workflow.support import payload
from scene_completion.workflow_core import TaskBlocked
from scene_completion.workflow_core.scheduler import partition_key


def partitioned(self, key, task, deps, build, case):
    """Expand after inputs validate; each child has its own review/cache/retry."""
    from scene_completion.workflow.runtime.task_partitions import merge_parts, split_task

    def waiting(d):
        raise TaskBlocked("dependency_wait", {"reason": "等待子任务展开"})

    self.add(key, task, deps, build=build, transform=waiting, case=case)
    self.scheduler.tasks[key].deferred = True

    def expand():
        inputs = build(
            {
                d: payload(read_json(self.root / self.scheduler.state["tasks"][d]["output_file"]))
                for d in deps
            }
        )
        units = split_task(task, inputs)
        children = []
        for unit, part in units:
            child = partition_key(key, unit)
            children.append(child)
            inherited = {
                m["detail"].get("parent_message_id") for m in self.conversations.list(child)
            }
            for message in self.conversations.list(key):
                if message["kind"] == "guidance" and message["id"] not in inherited:
                    self.conversations.append(
                        child,
                        "guidance",
                        message["text"],
                        {"parent_message_id": message["id"], "parent_task": key},
                    )
            self.add(
                child, task, deps, static=part, build=lambda d, part=part: deepcopy(part), case=case
            )
            self.scheduler.tasks[child].display_label = (
                TASKS.get(task, ("", task))[1] + " · " + unit
            )

        def register_merge():
            self.add(
                key,
                task,
                tuple(children) or deps,
                build=lambda d, inputs=inputs: inputs,
                transform=lambda d, children=children: merge_parts(
                    task,
                    [
                        payload(
                            read_json(self.root / self.scheduler.state["tasks"][c]["output_file"])
                        )
                        for c in children
                    ],
                ),
                case=case,
                skip_review=True,
            )

        self.scheduler.replace_deferred(key, register_merge)

    self.scheduler.defer_expansion(deps, expand)
