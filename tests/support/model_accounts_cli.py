"""Offline test support extracted without changing builder behavior."""


def source():
    return {
        "name": "CLI project",
        "sources": {
            "RR": [{"name": "rr.md", "content": "# RR"}],
            "SR": [{"name": "sr.md", "content": "# SR"}],
        },
    }


class FakeAPI:
    server = "http://127.0.0.1:8765"

    def __init__(self, client):
        self.client = client
        self.requests = []

    def call(self, path, body=None, method=None):
        self.requests.append((path, body, method))
        r = (
            self.client.request(
                method or ("POST" if body is not None else "GET"), "/api/" + path, json=body
            )
            if body is not None
            else self.client.get("/api/" + path)
        )
        if r.status_code >= 400:
            raise ValueError(r.text)
        return r.json()


__all__ = ["FakeAPI", "source"]
