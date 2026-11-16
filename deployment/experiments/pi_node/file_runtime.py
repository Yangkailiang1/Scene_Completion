"""Three isolated experimental loops over one metered JSON transport and submit closure."""

import json
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from bridge import PiGraph
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, convert_to_messages
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from scene_completion.application.runtime_settings import request_options
from scene_completion.infrastructure.execution_events import emit, fields
from scene_completion.models.clients.deepagents_client import _AGENT_SESSION
from scene_completion.models.transport.request_context import prepare


class ExperimentModel(BaseChatModel):
    scene_client: Any
    task_stage: str
    workspace: Any = None
    tools_offered: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "experiment-shared-metered-json"

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=[convert_to_openai_tool(t) for t in tools])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        session = _AGENT_SESSION.get()
        if session["count"] >= 5:
            raise ValueError("five-request node budget exhausted")
        session["count"] += 1
        tools = [t["function"] for t in kwargs["tools"]]
        # The fifth and final request has only submission/question tools in every arm.
        if session["count"] >= 5:
            tools = [t for t in tools if t["name"] in ("submit_result", "ask_user")]
        schema = next(
            t["parameters"]["properties"]["payload"] for t in tools if t["name"] == "submit_result"
        )
        notice = (
            "实验统一JSON接口：直接输出符合产物Schema的根业务JSON，或输出 "
            '{"tool":"允许的工具名","arguments":{对应参数}} 调用一个工具。'
            "所有查阅、文件操作、修复与提交合计最多五次模型请求；没有隐藏重试。"
            "最终产物只能经submit_result提交并通过同一格式、身份、引用、挂载及固定项校验，"
            "写文件、JSON可解析或自称完成都不代表交付。不能读取其他通道或旧答案。"
            "\n产物Schema："
            + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
            + "\n本次允许工具："
            + json.dumps(tools, ensure_ascii=False, separators=(",", ":"))
        )
        if self.workspace is not None:
            notice += (
                "\n文件能力仅限input/task.json、input/schema.json与work/*.json。"
                "完整材料已在当前消息，文件不是额外信息。可将候选结果写入work/candidate.json，"
                "读取复核，按需精确修改；文件工具可用于组织和修复，不要求为使用工具而重复读取。"
                "不得访问绝对路径、上级目录、源码、凭证、账本或其他会话；没有Shell或网络工具。"
                "最终仍提交完整业务JSON，不能用文件路径替代payload。"
            )
        converted = []
        for m in messages:
            row = {
                "role": {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}[
                    m.type
                ],
                "content": m.content,
            }
            if m.type == "tool":
                row["tool_call_id"] = m.tool_call_id
            if m.type == "ai" and m.tool_calls:
                # These calls originated from JSON text, not native wire tool calls.
                row["content"] = json.dumps(
                    {"tool": m.tool_calls[0]["name"], "arguments": m.tool_calls[0]["args"]},
                    ensure_ascii=False,
                )
            if m.type == "tool":
                # JSON-text APIs use ordinary messages for the same tool feedback.
                row = {"role": "user", "content": "工具反馈：" + str(m.content)}
            converted.append(row)
        converted[0] = {**converted[0], "content": str(converted[0]["content"]) + "\n" + notice}
        client = self.scene_client
        body = {
            "model": client.model("agent"),
            "messages": converted,
            "max_tokens": client.output_limit(self.task_stage),
            "stream": client.config.get("stream", True),
            "response_format": {"type": "json_object"},
        }
        if body["stream"] and client.config.get("stream_usage", True):
            body["stream_options"] = {"include_usage": True}
        body = request_options(body, client.config, self.task_stage)
        with fields(model_call_id=uuid4().hex):
            prepare(client, body, self.task_stage)
            emit(
                "request_started",
                requested_model=body["model"],
                experiment_transport="common-json-v1",
            )
            response = client.post("/chat/completions", body)
            emit(
                "request_finished",
                requested_model=body["model"],
                provider_model=response.get("model"),
                usage=response.get("usage"),
            )
        if response["choices"][0].get("finish_reason") == "length":
            raise ValueError("candidate truncated; not delivered")
        raw = response["choices"][0]["message"]
        if raw.get("tool_calls"):
            raise ValueError("unexpected native tool call in frozen JSON-text transport")
        decoded = json.loads(raw.get("content") or "")
        allowed = {t["name"] for t in tools}
        if isinstance(decoded, dict) and set(decoded) == {"tool", "arguments"}:
            name, args = decoded["tool"], decoded["arguments"]
        elif isinstance(decoded, dict) and set(decoded) == {"clarification"}:
            name, args = "ask_user", decoded["clarification"]
        elif (
            isinstance(decoded, dict)
            and "result" in decoded
            and set(decoded) <= {"result", "review_questions"}
        ):
            name, args = (
                "submit_result",
                {
                    "payload": decoded["result"],
                    "review_questions": decoded.get("review_questions", []),
                },
            )
        else:
            name, args = "submit_result", {"payload": decoded}
        if name not in allowed or not isinstance(args, dict):
            raise ValueError("unavailable tool or invalid argument object")
        usage = response.get("usage") or {}
        ai = AIMessage(
            content=raw.get("content") or "",
            tool_calls=[{"name": name, "args": args, "id": "exp-" + uuid4().hex}],
            response_metadata={"provider_model": response.get("model"), "usage": usage},
            usage_metadata={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )
        return ChatResult(generations=[ChatGeneration(message=ai)])


class FilePiGraph(PiGraph):
    def __init__(self, *, model, workspace=None, **kwargs):
        research = ExperimentModel(
            scene_client=model.scene_client, task_stage=model.task_stage, workspace=workspace
        )
        kwargs["root"] = kwargs["root"] / "sdk-runtime"
        kwargs["root"].mkdir(parents=True, exist_ok=True)
        (kwargs["root"] / ".git").mkdir(exist_ok=True)
        super().__init__(model=research, sandboxed=True, **kwargs)
        if workspace:
            self.tools.update({t.name: t for t in workspace.tools()})


class PlainGraph(FilePiGraph):
    """Ordinary sequential LLM/interface loop, no Agent SDK, no file tools."""

    def invoke(self, inputs, config=None):
        prepared = []

        class Captured(Exception):
            pass

        def capture(_model, messages, **kwargs):
            prepared.extend(messages)
            raise Captured()

        with patch.object(type(self.model), "_generate", capture):
            try:
                self.baseline.invoke(inputs)
            except Captured:
                pass
        if not prepared or prepared[0].type != "system":
            raise ValueError("unchanged baseline prompt capture failed")
        messages = [
            SystemMessage(content=prepared[0].content),
            *convert_to_messages(inputs["messages"]),
        ]
        while True:
            reply = self.model.bind_tools(list(self.tools.values())).invoke(messages)
            messages.append(reply)
            if not reply.tool_calls:
                raise ValueError("LLM did not submit a tool result")
            for call in reply.tool_calls:
                value = self.tools[call["name"]].invoke(call["args"])
                if call["name"] == "submit_result":
                    return {"messages": messages}
                messages.append(ToolMessage(content=str(value), tool_call_id=call["id"]))


@contextmanager
def runtime_factory(root, arm, workspace=None):
    from deepagents import create_deep_agent

    cls = PlainGraph if arm == "D" else FilePiGraph
    with patch(
        "deepagents.create_deep_agent",
        side_effect=lambda **kw: cls(
            root=root, workspace=workspace, baseline_factory=create_deep_agent, **kw
        ),
    ):
        yield
