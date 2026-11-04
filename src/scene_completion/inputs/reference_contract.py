"""Model citation formats are explicit; document and program identities differ."""

import json

from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.source_documents import documents_in, evidence_refs


class ReferenceContractError(ValueError):
    def __init__(self, category, path, mode, received, allowed=()):
        self.details = {
            "category": category,
            "path": path,
            "reference_mode": mode,
            "received": received,
            "allowed_evidence_count": len(allowed),
            "allowed_evidence_examples": list(allowed)[:8],
        }
        label = "unknown evidence_id" if category == "unknown_evidence_id" else category
        super().__init__(label + ": " + json.dumps(self.details, ensure_ascii=False))


def validate_raw_references(value, path=""):
    """Report raw-vs-indexed mistakes before the generic business Schema."""
    if isinstance(value, dict):
        for key, v in value.items():
            location = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key == "source_refs":
                if not isinstance(v, list) or any(not isinstance(r, dict) for r in v):
                    raise ReferenceContractError("reference_format_mismatch", location, "raw", v)
            else:
                validate_raw_references(v, location)
    elif isinstance(value, list):
        for n, v in enumerate(value):
            validate_raw_references(v, path + "/" + str(n))


def instructions(indexed):
    if indexed:
        return (
            "本次启用indexed_context。source_refs只填写本任务给定的evidence_id字符串列表；"
            "可用lookup_evidence查证。不得生成新ID或混用完整引用对象。"
        )
    return (
        "本次未启用indexed_context；没有evidence_catalog或evidence_id，也没有lookup_evidence工具。"
        "source_refs必须是包含source_id、line_start、line_end、quote的对象列表；"
        "只复制当前允许材料的来源身份、真实行号和逐字引文，不填写ID字符串、不臆造新来源。"
        "需要核对时读取/input/sources/对应文件。程序Git提交版本不属于文档source_id。"
    )


def summary(inputs, indexed=None):
    docs = documents_in(inputs)
    refs = evidence_refs(inputs)
    sources = sorted({d["source_id"] for d in docs} | {r["source_id"] for r in refs})
    return {
        "mode": "indexed" if indexed is not None else "raw",
        "evidence_count": len(indexed.pool) if indexed is not None else None,
        "evidence_fingerprint": fingerprint(indexed.pool) if indexed is not None else None,
        "source_ids": sources,
        "documents": [
            {
                "source_id": d["source_id"],
                "name": d["name"],
                "channel": d["channel"],
                "line_count": len(d["lines"]),
                "projection_hash": fingerprint(d["lines"]),
            }
            for d in docs
        ],
        "note": "source_id标识文档；projection_hash标识本次取片，不是程序source_commit。",
    }
