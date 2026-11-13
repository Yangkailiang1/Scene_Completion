"""Offline test support extracted without changing builder behavior."""

from scene_completion.application.project_service import Workbench


def project(tmp_path):
    s = Workbench(tmp_path)
    p = s.create(
        {
            "name": "项目",
            "sources": {
                "RR": [{"name": "rr.md", "content": "# UC-001 浏览商品\n顾客查询商品"}],
                "SR": [{"name": "sr.md", "content": "# SR-01 浏览商品\nCatalog查询列表"}],
            },
        }
    )
    return s, p["id"], s.run_dir(p["id"])


__all__ = ["project"]
