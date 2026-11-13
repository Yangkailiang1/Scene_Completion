"""Offline test support extracted without changing builder behavior."""

from scene_completion.domain.contracts import packet
from scene_completion.inputs.provenance.indexed_context import task_document_view
from scene_completion.models.clients.deepagents_client import DeepAgentsClient


def document():
    texts = [
        "# 服务调用",
        "正文 " * 2400,
        "```mermaid",
        "sequenceDiagram",
        "participant P as PlatformService",
        "participant A as AdminService",
        "participant C as CloudMapService",
        "actor D as ExternalDatabase",
        "P->>A: POST /mx/v2/instances<br/>创建实例",
        "A->>C: POST /cloudmap/v3/resources<br/>外部服务创建资源",
        "A->>C: DELETE /cloudmap/v3/resources/{resourceID}<br/>删除资源",
        "A->>D: GET /db/v9/records/{recordID}<br/>查询外部数据库",
        "C-->>A: 200 OK",
        "```",
    ]
    return {
        "source_id": "sr-document",
        "name": "sr.md",
        "channel": "normal",
        "lines": [{"number": n, "text": text} for n, text in enumerate(texts, 1)],
    }


def api_packet(layer="SR"):
    p = packet("api-map", {layer: [task_document_view([document()], "api-map")[0]]})
    p.update(skill_text="test skill", node_key=layer.lower() + "-api-map")
    return p


def client(tmp_path, transport, indexed=False):
    return DeepAgentsClient(
        {
            "api_key": "offline-test",
            "base_url": "http://offline.invalid/v1",
            "agent_model": "test",
            "submission_mode": "json_text",
            "max_tokens": 2048,
            "indexed_context": indexed,
            "run_root": str(tmp_path),
        },
        transport=transport,
    )


def external_scope(texts, layer="RR"):
    from scene_completion.inputs.structured.api_boundaries import scope_inputs

    doc = {
        "source_id": layer.lower(),
        "name": layer + ".md",
        "channel": "normal",
        "lines": [{"number": n, "text": text} for n, text in enumerate(texts, 1)],
    }
    components = {
        "components": [
            {"name": n, "composition_type": "外部Actor（系统）", "source_refs": []}
            for n in ("CloudMapService", "GaussDB")
        ]
    }
    return scope_inputs([doc], components, layer, "external")


__all__ = ["api_packet", "client", "document", "external_scope"]
