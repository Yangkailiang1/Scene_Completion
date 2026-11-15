"""Verified batch checkpoints survive failures elsewhere in a multi-batch task."""

from scene_completion.analysis.validation import validate_result
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.workflow.recovery.node_repair import binding


def location(ex, packet):
    identity = {
        "binding": binding(packet, ex.conversations.revision(packet["node_key"])),
        "mode": ex.mode,
        "artifact_identity": getattr(ex, "artifact_identity", {}),
    }
    return ex.root / "semantic_batches" / (fingerprint(identity) + ".json"), identity


def load(ex, packet):
    path, identity = location(ex, packet)
    if not path.exists():
        return None
    row = read_json(path)
    if row.get("identity") != identity or row.get("hash") != fingerprint(
        [row.get("payload"), row.get("proof")]
    ):
        return None
    validate_result(packet["task"], row["payload"], packet["input"])
    return row["payload"], {
        "provider": "verified_batch_checkpoint",
        "semantic_response_reused": True,
        "original_execution": row["proof"],
    }


def save(ex, packet, payload, proof):
    path, identity = location(ex, packet)
    write_json(
        path,
        {
            "identity": identity,
            "payload": payload,
            "proof": proof,
            "hash": fingerprint([payload, proof]),
        },
    )
