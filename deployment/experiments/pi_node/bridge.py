"""Run Pi's SDK loop with the *existing* prepared Python tools and model adapter.

The factory substitution is process-local, scoped, and restored even on failure.
Neither runtime gets a filesystem tool, credentials, or another channel's history.
"""

import json
import os
import queue
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    convert_to_messages,
)
from langchain_core.utils.function_calling import convert_to_openai_tool

HERE = Path(__file__).resolve().parent


def to_langchain(messages, system):
    result = [SystemMessage(content=system)]
    for row in messages:
        role = row["role"]
        content = row.get("content", [])
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        text = "\n".join(r.get("text", "") for r in content if r["type"] == "text")
        if role == "user":
            result.append(HumanMessage(content=text))
        elif role == "assistant":
            result.append(
                AIMessage(
                    content=text,
                    tool_calls=[
                        {"name": r["name"], "args": r["arguments"], "id": r["id"]}
                        for r in content
                        if r["type"] == "toolCall"
                    ],
                )
            )
        elif role == "toolResult":
            result.append(ToolMessage(content=text, tool_call_id=row["toolCallId"]))
        elif role != "system":
            raise ValueError("Unsupported Pi message role: " + role)
    return result


def to_pi(message):
    content = []
    if isinstance(message.content, str) and message.content:
        content.append({"type": "text", "text": message.content})
    for call in message.tool_calls:
        content.append(
            {"type": "toolCall", "id": call["id"], "name": call["name"], "arguments": call["args"]}
        )
    usage = message.usage_metadata or {}
    return {
        "role": "assistant",
        "content": content,
        "api": "openai-completions",
        "provider": "scene-experiment",
        "model": "ecnu-max",
        "usage": {
            "input": usage.get("input_tokens", 0),
            "output": usage.get("output_tokens", 0),
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": usage.get("total_tokens", 0),
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0},
        },
        "stopReason": "toolUse" if message.tool_calls else "stop",
        "timestamp": 0,
    }


class PiGraph:
    def __init__(self, *, model, tools, system_prompt, root, baseline_factory, **kwargs):
        self.model = model
        self.tools = {t.name: t for t in tools}
        if set(self.tools) - {"submit_result", "ask_user", "lookup_evidence"}:
            raise ValueError("Pi experiment received an unapproved tool")
        self.system = system_prompt
        self.root = Path(root)
        self.baseline = baseline_factory(
            model=model, tools=tools, system_prompt=system_prompt, **kwargs
        )

    def invoke(self, inputs, config=None):
        transcript = convert_to_messages(inputs["messages"])
        # Deep Agents adds middleware instructions (including loaded Skills)
        # to the factory's system prompt. Capture those exact prepared LC
        # messages without reaching _generate or post: no request, counter,
        # reservation or historical model answer is involved in this probe.
        prepared = []

        class PreparationCaptured(Exception):
            pass

        def capture(_model, messages, **_kwargs):
            prepared.extend(messages)
            raise PreparationCaptured()

        with patch.object(type(self.model), "_generate", capture):
            try:
                self.baseline.invoke(inputs)
            except PreparationCaptured:
                pass
        if not prepared or prepared[0].type != "system":
            raise ValueError("Could not capture the unchanged baseline system message")
        canonical_system = prepared[0].content
        # Only the executable path and locale enter Node. In particular no API
        # keys, model endpoint, provider env, or user-global Pi config enter it.
        env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
        env["PI_CODING_AGENT_DIR"] = str(self.root / "pi-home")
        stderr_path = self.root / "pi-stderr.log"
        self.root.mkdir(parents=True, exist_ok=True)
        with stderr_path.open("a", encoding="utf8") as errors:
            proc = subprocess.Popen(
                ["node", str(HERE / "runner.mjs")],
                cwd=self.root,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=errors,
                text=True,
                encoding="utf8",
                bufsize=1,
            )
            lines = queue.Queue()

            def read_lines():
                for line in proc.stdout:
                    lines.put(line)
                lines.put(None)

            threading.Thread(target=read_lines, daemon=True).start()

            def send(value):
                proc.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
                proc.stdin.flush()

            schemas = [convert_to_openai_tool(t)["function"] for t in self.tools.values()]
            send(
                {
                    "kind": "start",
                    "system": self.system,
                    "prompt": inputs["messages"][-1]["content"],
                    "tools": schemas,
                }
            )
            try:
                while True:
                    try:
                        line = lines.get(timeout=1200)
                    except queue.Empty as exc:
                        raise TimeoutError(
                            "Pi subprocess did not settle within 1200 seconds"
                        ) from exc
                    if line is None:
                        raise RuntimeError(
                            "Pi subprocess exited before delivering a settled result"
                        )
                    event = json.loads(line)
                    kind = event["kind"]
                    if kind == "model":
                        messages = to_langchain(event["messages"], canonical_system)
                        reply = self.model.bind_tools(list(self.tools.values())).invoke(messages)
                        transcript.append(reply)
                        send({"message": to_pi(reply)})
                    elif kind == "tool":
                        name = event["name"]
                        if name not in self.tools:
                            raise ValueError("Pi requested an unapproved tool")
                        # Exceptions intentionally propagate to the SAME outer
                        # repair runner as A. Pi cannot catch/relabel a rejection.
                        value = self.tools[name].invoke(event["args"])
                        send({"text": str(value), "submitted": name == "submit_result"})
                    elif kind == "done":
                        if not event.get("submitted"):
                            raise ValueError("Pi settled without a validated submission")
                        return {"messages": transcript}
                    elif kind == "error":
                        raise RuntimeError("Pi SDK: " + event["error"])
                    else:
                        raise ValueError("Unexpected Pi bridge event")
            finally:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                proc.stdin.close()
                proc.stdout.close()


@contextmanager
def pi_factory(root):
    from deepagents import create_deep_agent

    with patch(
        "deepagents.create_deep_agent",
        side_effect=lambda **kw: PiGraph(root=root, baseline_factory=create_deep_agent, **kw),
    ):
        yield
