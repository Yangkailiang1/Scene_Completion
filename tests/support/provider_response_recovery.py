"""Offline test support extracted without changing builder behavior."""

import io

from scene_completion.domain.contracts import packet


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}


def configuration(tmp_path, **options):
    return {
        "api_key": "private-key-12345",
        "base_url": "http://test.invalid/v1",
        "agent_model": "test-model",
        "run_root": str(tmp_path),
        "max_tokens": 512,
        **options,
    }


def body():
    return {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Current evidence"}],
        "max_tokens": 512,
    }


def crud_packet(**extra):
    p = packet(
        "business-crud",
        {
            "business-entities": {"entities": [], "pending": []},
            "fused-ssd": {"interactions": [], "rr_sr_links": [], "pending": []},
            "normal-documents": [
                {
                    "source_id": "sr",
                    "name": "SR.md",
                    "channel": "normal",
                    "lines": [{"number": 1, "text": "CURRENT_SOURCE_RULE"}],
                }
            ],
        },
        ["G-004"],
    )
    p.update(skill_text="Only classify explicit effects.", **extra)
    return p


__all__ = ["Response", "body", "configuration", "crud_packet"]
