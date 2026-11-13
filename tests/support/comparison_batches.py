"""Offline test support extracted without changing builder behavior."""


class Client:
    base_url = "http://offline/v1"

    def __init__(self):
        self.calls = []

    def model(self, kind):
        return "test"

    def agent(self, p):
        self.calls.append(p["input"])
        pairs = {(r["left_id"], r["right_id"]) for r in p["input"].get("candidate_pairs", [])}
        return {
            "decisions": [
                {
                    "left_id": a["id"],
                    "right_id": b["id"],
                    "status": "full" if a["cause"] == b["cause"] else "unmatched",
                    "reason": "fixture semantic decision",
                }
                for a in p["input"]["left"]
                for b in p["input"]["right"]
                if not pairs or (a["id"], b["id"]) in pairs
            ]
        }


__all__ = ["Client"]
