#!/usr/bin/env python3
"""Validate the checked-in mini dataset using only Python's standard library."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "输入文件"
CASES = dict(
    zip(
        (f"UC-{n:03d}" for n in range(1, 6)),
        ("创建商品", "查询商品列表", "更新商品", "删除商品", "发布商品"),
    )
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate():
    errors = []

    def check(ok, message):
        if not ok:
            errors.append(message)

    for path in ROOT.rglob("*.json"):
        read(path)
    tree = read(ROOT / "功能树.json")
    test = read(ROOT / "recovered_usecases.json")
    apis = read(ROOT / "api_extraction.json")["apis"]
    check({r["ucId"]: r["name"] for r in tree["functions"]} == CASES, "功能树用例不一致")
    check({r["id"]: r["name"] for r in test} == CASES, "测试用例不一致")
    api_ids = {a["API序号"] for a in apis}
    check(len(api_ids) == len(apis) == 10, "需要10个独立RR/SR接口")
    for n, (cid, name) in enumerate(CASES.items(), 1):
        for layer in ("RR", "SR"):
            aid = f"API-{layer}-{n:02d}"
            check(
                any(a["API序号"] == aid and a["接口名称"] == name for a in apis),
                f"{cid}接口映射错误: {aid}",
            )

    counts = {"cases": 0, "operations": 0, "main_interactions": 0, "scenarios": 0}
    for path in sorted((ROOT / "行为模型").glob("*/*/SysOperation.json")):
        value = read(path)
        cid, name = value["use_case_id"], value["use_case"]
        check(CASES.get(cid) == name, f"{path}: 用例身份不符")
        counts["cases"] += 1
        outer = read(path.with_name("SSD.json"))
        operations = value["operations"]
        counts["operations"] += len(operations)

        def sequence(record, label, include_event=False):
            tables = {
                kind: record.get(field, [])
                for kind, field in [
                    ("interaction", "interaction"),
                    ("action", "action"),
                    ("event", "system_event"),
                    ("response", "system_response"),
                ]
            }
            known = {(kind, r["id"]) for kind, rows in tables.items() for r in rows}
            check(len(known) == sum(map(len, tables.values())), f"{label}: 同类型ID重复")
            selected = [(r["kind"], r["ref"]) for r in record["Order"]]
            check(all(k in known for k in selected), f"{label}: Order悬空引用")
            aliases = record["participant"]
            check(all(p.get("name") for p in aliases.values()), f"{label}: participant缺全称")
            for kind, rows in tables.items():
                for r in rows:
                    parties = [r["executor"]] if kind == "action" else [r["sender"], r["receiver"]]
                    check(all(p in aliases for p in parties), f"{label}: 缩写无定义 {parties}")
                    if kind == "interaction":
                        check(r["sender"] != r["receiver"], f"{label}: 普通interaction误为自调用")
                    if r.get("api_id"):
                        check(r["api_id"] in api_ids, f"{label}: 未知接口 {r['api_id']}")
                    check(bool(r.get("source_refs")), f"{label}: 缺来源")
                    for ref in r.get("source_refs", []):
                        doc = {"spec": "系统需求_spec.md", "sr": "功能设计_spec.md"}[
                            ref["document"]
                        ]
                        lines = (ROOT / doc).read_text(encoding="utf-8").splitlines()
                        quote = "\n".join(lines[ref["start_line"] - 1 : ref["end_line"]])
                        check(bool(quote) and quote == ref["quote"], f"{label}: 原文定位不符")
            if include_event:
                selected = (
                    [("event", r["id"]) for r in tables["event"]]
                    + selected
                    + [("response", r["id"]) for r in tables["response"]]
                )
            return list(dict.fromkeys(selected))

        for op_id, op in operations.items():
            seq = sequence(op, op_id, True)
            check(
                op["scenario_kind"] in {"main", "exception", "alternative"}, f"{op_id}: 缺明确类型"
            )
            check(
                op["sourceSSD"] in {s["SSD_ID"] for s in outer["scenarios"].values()},
                f"{op_id}: SSD悬空",
            )
            if op["scenario_kind"] == "main":
                counts["main_interactions"] += len(seq)
                check(
                    seq[0][0] == "event" and seq[-1][0] == "response", f"{op_id}: 缺入口或最终响应"
                )
            if op.get("inherited_operation"):
                check(op["inherited_operation"] in operations, f"{op_id}: 继承悬空")
        for s in outer["scenarios"].values():
            check(
                all(op in operations for op in s["system_operations"]), f"{name}: SSD操作引用悬空"
            )
        for layer in ("IR", "SR"):
            files = list((path.parent / "behaviour" / layer).glob("*.json"))
            check(
                sum(read(f)["scenario_kind"] == "main" for f in files) == 1,
                f"{name}/{layer}: 需要一个主成功场景",
            )
            for f in files:
                r = read(f)
                sequence(r, str(f.relative_to(ROOT)))
                counts["scenarios"] += 1
                if r["scenario_kind"] != "main":
                    check(bool(r.get("guard")), f"{f}: 分支缺触发条件")
                    check(r["extend_at_main"]["scenario"] == "SC_MAIN", f"{f}: 主场景引用不符")
    check(counts["cases"] == 5, "行为用例数量不为5")
    if errors:
        raise ValueError("\n".join(errors))
    return counts


if __name__ == "__main__":
    print(json.dumps({"status": "passed", **validate()}, ensure_ascii=False))
