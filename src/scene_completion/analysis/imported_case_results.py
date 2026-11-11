"""Validate and present an independent, single-use-case Code Agent result."""

from copy import deepcopy
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

from scene_completion.analysis.concern_alignment import VERSION as MATCHING_VERSION
from scene_completion.analysis.concern_alignment import attach_report, compare, index_elements
from scene_completion.analysis.evaluation_scope import report_view
from scene_completion.analysis.exception_comparison import compare_report, missing_report
from scene_completion.analysis.interaction_enrichment import display_parameters
from scene_completion.analysis.interaction_identity import canonical_fused
from scene_completion.analysis.recommendation import evaluate, rank
from scene_completion.analysis.result_views import ResultView
from scene_completion.analysis.scenario_patterns import normalize_settings
from scene_completion.domain.concern_registry import registry_scope
from scene_completion.domain.contracts import schema
from scene_completion.domain.interaction_types import classify
from scene_completion.domain.schema_definitions import (
    DOCUMENT,
    MATCH,
    REFS,
    SCENARIO,
    S,
    arr,
    enum,
    obj,
)
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.source_documents import evidence_refs

VERSION = "scene-case-analysis-v1"
PAIRS = {"G_E": ("G", "E"), "GT_G": ("GT", "G"), "GT_E": ("GT", "E")}
CHANNEL = obj(
    status=enum("ready", "partial", "missing"),
    source_refs=REFS,
    concerns=arr(MATCH),
    scenarios=arr(SCENARIO),
    pending=arr(S),
)
SETTINGS = {"type": "object"}
BUNDLE = obj(
    version=enum(VERSION),
    case=obj(id=S, name=S, source_ids=arr(S)),
    ssd=schema("fused-ssd"),
    api_map=schema("api-map"),
    api_parameters=schema("api-parameters"),
    sources=arr(DOCUMENT),
    channels=obj(G=CHANNEL, E=CHANNEL, GT=CHANNEL),
    decisions=obj(
        **{name: schema("semantic-compare")["properties"]["decisions"] for name in PAIRS}
    ),
    registry=SETTINGS,
    recommendation_settings=SETTINGS,
    history=arr(SETTINGS),
    scope=enum("SR", "RR", "all"),
    pending=arr(S),
)
# Optional submitted ranking is checked against the frozen, server-derived result.
BUNDLE["properties"]["recommendation_ids"] = arr(S)
BUNDLE["properties"]["metrics"] = SETTINGS


def _unique(rows, key, label):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(label + " ID 重复")
    return result


def _check_refs(value, sources, allowed, required=False):
    refs = evidence_refs(value)
    if required and not refs:
        raise ValueError("已确认记录缺少来源依据")
    for ref in refs:
        source = sources.get(ref["source_id"])
        if source is None or source[0] not in allowed:
            raise ValueError("引用的来源不存在或超出当前材料通道")
        lines = source[1]
        start, end = ref["line_start"], ref["line_end"]
        if not 0 <= end - start < len(lines):
            raise ValueError("来源行范围无效")
        span = [lines.get(n) for n in range(start, end + 1)]
        if None in span or ref["quote"] not in "\n".join(span):
            raise ValueError("引用原文与提交的来源行不一致")


def _channels(bundle, sources, material):
    elements = index_elements(material)
    lookup = {
        (
            e["interaction_id"],
            e["target"],
            e["object"],
            e["data_location"],
            e.get("operation_index"),
        ): e
        for e in elements
    }
    rows = {i["id"]: i for i in material["enriched-interactions"]["interactions"]}
    output = {}
    for channel, channel_data in bundle["channels"].items():
        own = {"G": "normal", "E": "existing", "GT": "test"}[channel]
        allowed = {own, "normal"}
        _check_refs(
            channel_data["source_refs"], sources, {own}, required=channel_data["status"] == "ready"
        )
        if channel_data["status"] == "missing" and (
            channel_data["concerns"] or channel_data["scenarios"]
        ):
            raise ValueError("缺失材料通道不能包含已确认记录")
        matches = {}
        for concern in channel_data["concerns"]:
            concern = deepcopy(concern)
            _check_refs(concern, sources, allowed, required=True)
            if not any(sources[ref["source_id"]][0] == own for ref in concern["source_refs"]):
                raise ValueError("关注点缺少本通道证据")
            iid = concern["interaction_id"]
            key = concern["concern_key"]
            definition = bundle["registry"]["definitions"].get(key, {})
            if definition.get("kind") != "check" or not definition.get("enabled", True):
                raise ValueError("关注点未注册、未启用或仅用于分类：" + key)
            if key.startswith("global.") or key.endswith(".idempotency"):
                raise ValueError("交互结果不能包含全局关注点：" + key)
            anchor = lookup.get(
                (
                    iid,
                    concern["target"],
                    concern["object"],
                    concern.get("data_location"),
                    concern.get("operation_index"),
                )
            )
            if anchor is None:
                raise ValueError("关注点未绑定到本用例真实交互或字段：" + iid)
            ident = "concern-" + fingerprint([anchor["element_id"], key])[:24]
            concern.update(
                binding_id=ident,
                element_id=anchor["element_id"],
                direction=anchor["direction"],
                case_id=anchor["case_id"],
                status="applicable",
                scope=anchor["scope"],
            )
            previous = matches.setdefault(ident, concern)
            previous["source_refs"] = list(
                {
                    fingerprint(r): r for r in previous["source_refs"] + concern["source_refs"]
                }.values()
            )
        scenarios = _unique(channel_data["scenarios"], "id", "场景")
        for s in scenarios.values():
            iid = s["interaction_id"]
            step = rows.get(iid)
            if (
                not step
                or s["case_id"] != step["case_id"]
                or s["layer"] != step["layer"]
                or s.get("canonical_interaction_id", iid) != iid
                or s["operation"] != step["operation"]["name"]
            ):
                raise ValueError("场景不属于本用例的实际交互：" + s["id"])
            if s.get("scenario_type", "exception") != "exception":
                raise ValueError("正常、备选和待确认项请放入待确认说明")
            _check_refs(s, sources, allowed, required=True)
            if not any(sources[ref["source_id"]][0] == own for ref in s["source_refs"]):
                raise ValueError("场景缺少本通道证据")
            candidates = [
                row["binding_id"]
                for row in matches.values()
                if row["interaction_id"] == iid
                and row["concern_key"] == s["concern_key"]
                and row["object"] == s["object"]
                and (
                    row["target"] != "data"
                    or (
                        row.get("data_location") == s.get("data_location")
                        and s["field"] == row["object"]
                    )
                )
            ]
            if len(candidates) != 1:
                raise ValueError("场景没有唯一的同通道关注点绑定：" + s["id"])
            if s.get("coverage_kind", "exact") != "exact" and (
                channel != "E" or not s.get("original_branch_id")
            ):
                raise ValueError("宽泛覆盖需要 E 的原分支")
            if any(
                key not in bundle["registry"]["definitions"] for key in s.get("concern_origins", [])
            ):
                raise ValueError("场景引用未注册的关注点")
            s.update(concern_binding_ids=candidates, matching_version=MATCHING_VERSION)
        output[channel] = {"matches": list(matches.values()), "scenarios": list(scenarios.values())}
    return output


def _decisions(decisions, channels):
    for purpose, (left, right) in PAIRS.items():
        first = {s["id"]: s for s in channels[left]["scenarios"]}
        second = {s["id"]: s for s in channels[right]["scenarios"]}
        seen = set()
        for row in decisions[purpose]:
            pair = row["left_id"], row["right_id"]
            a, b = first.get(pair[0]), second.get(pair[1])
            if not a or not b or pair in seen:
                raise ValueError("匹配判定含无效或重复的场景引用：" + purpose)
            seen.add(pair)
            if row["status"] == "full" and not set(a["concern_binding_ids"]) & set(
                b["concern_binding_ids"]
            ):
                raise ValueError("完整匹配必须具有同一交互和关注点绑定")


def _history(rows):
    for r in rows:
        if (
            r.get("human_reviewed") is not True
            or r.get("source_channel") not in {"business_review", "business_adoption"}
            or r.get("decision") not in {"adopt", "not_needed"}
            or not all(
                isinstance(r.get(k), str) and r[k]
                for k in ("id", "pattern_id", "run_id", "library_version", "pattern_hash", "source")
            )
            or not isinstance(r.get("context"), dict)
            or type(r.get("reviewed_at")) not in (float, int)
        ):
            raise ValueError("推荐历史只接受有来源的已审核业务记录")
        for k, value in r["context"].items():
            if k in {"functional_types", "technologies"}:
                if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                    raise ValueError("推荐历史功能或技术类型格式错误")
            elif k in {"actual_operation", "boundary", "direction", "timeliness"}:
                if value is not None and not isinstance(value, str):
                    raise ValueError("推荐历史特征格式错误")
    _unique(rows, "id", "推荐历史")
    return rows


def _derive(value):
    cid = value["case"]["id"]
    source_rows = _unique(value["sources"], "source_id", "来源")
    sources = {
        key: (
            source["channel"],
            {n: row["text"] for n, row in _unique(source["lines"], "number", "来源行").items()},
        )
        for key, source in source_rows.items()
    }
    if not set(value["case"]["source_ids"]) <= {
        key for key, (channel, _) in sources.items() if channel == "normal"
    }:
        raise ValueError("用例引用必须来自正向材料")
    ssd = value["ssd"]
    raw = _unique(ssd["interactions"], "id", "SSD")
    if not raw or not value["case"]["source_ids"]:
        raise ValueError("导入需要可校验的SSD与用例来源")
    for row in raw.values():
        _check_refs(row, sources, {"normal"}, required=True)
        parent = row.get("parent_id")
        if row["case_id"] != cid or parent == row["id"] or (parent and parent not in raw):
            raise ValueError("SSD含跨用例或未知的上游交互")
        if row["direction"] == "return" and parent and raw[parent]["direction"] != "request":
            raise ValueError("返回必须指向请求")
        allowed = (
            {"response", "business"}
            if row["direction"] == "return"
            else {"header", "path", "query", "body", "business"}
        )
        keys = [
            (p["location"], p["name"].casefold() if p["location"] == "header" else p["name"])
            for p in row["data"]["sequence"]
        ]
        if len(set(keys)) != len(keys) or any(location not in allowed for location, _ in keys):
            raise ValueError("SSD字段位置与方向冲突或字段重复")
    for link in ssd["rr_sr_links"]:
        if raw.get(link["rr_id"], {}).get("layer") != "RR" or any(
            raw.get(sid, {}).get("layer") != "SR" for sid in link["sr_ids"]
        ):
            raise ValueError("SSD跨层引用无效")
    _check_refs(ssd, sources, {"normal"})
    for item in ("api_map", "api_parameters"):
        _check_refs(value[item], sources, {"normal"})
    apis = _unique(value["api_parameters"]["apis"], "id", "接口契约")
    for api in apis.values():
        _check_refs(api["source_refs"], sources, {"normal"}, required=True)
        for iid in api.get("bound_interaction_ids", []):
            step = raw.get(iid)
            if (
                not step
                or step["layer"] != api.get("source_layer")
                or step.get("step_kind") == "action"
            ):
                raise ValueError("接口契约绑定了未知、跨层或本地交互")
        for response in api.get("responses", []):
            code = response["status_code"]
            if any(p["location"] != "response" for p in response["parameters"]) or (
                code is not None
                and (
                    len(code) != 3
                    or not code.isascii()
                    or not code.isdigit()
                    or (code.startswith("2") != (response["kind"] == "success"))
                )
            ):
                raise ValueError("响应契约字段或状态码无效")
    for interface in (a for s in value["api_map"]["services"] for a in s["interfaces"]):
        if interface["id"] not in apis or any(
            interface.get(k) != apis[interface["id"]].get(k)
            for k in ("source_layer", "method", "address")
        ):
            raise ValueError("接口映射与契约引用不一致")
    material = {"api-map": value["api_map"], "api-parameters": value["api_parameters"]}
    enriched = display_parameters(canonical_fused(ssd, material), material)
    for step in enriched["interactions"]:
        step["classification"] = classify(step, enriched["interactions"])
    material["enriched-interactions"] = enriched
    channels = _channels(value, sources, material)
    _decisions(value["decisions"], channels)

    g, e, gt = (channels[k] for k in ("G", "E", "GT"))
    g_ready, e_ready, gt_ready = (
        value["channels"][k]["status"] == "ready" for k in ("G", "E", "GT")
    )
    comparisons = g_ready and e_ready
    evaluated = comparisons and gt_ready
    gc = compare(g, e, gt if gt_ready else None)
    if not comparisons:
        gc["M_c"] = []
        for row in gc["rows"]:
            row["missing"] = False
    if not evaluated:
        gc["metrics"] = {}
    ge, tg, te = (value["decisions"][k] for k in PAIRS)
    report = missing_report(g["scenarios"], e["scenarios"], ge) if comparisons else {}
    settings = normalize_settings(value["recommendation_settings"])
    history = _history(value["history"])
    patterns = {p["id"]: p for p in settings["library"]["patterns"]}
    for scenario in g["scenarios"]:
        if not scenario.get("pattern_id"):
            continue
        pid = scenario["pattern_id"]
        linked = scenario.get("linked_pattern_ids", [pid])
        if (
            not scenario.get("confidence")
            or pid not in linked
            or pid not in patterns
            or any(key not in patterns for key in linked)
            or scenario["concern_key"] not in patterns[pid]["concern_keys"]
        ):
            raise ValueError("G场景缺少有效模式或有据置信度：" + scenario["id"])
    if report:
        recommendation = rank(
            report["M"], {}, settings, history, case_id=cid, run_id=fingerprint(ssd)
        )
    else:
        recommendation = {"enabled": False, "status": "待补材料", "Q": [], "ranked": []}
    if "recommendation_ids" in value and value["recommendation_ids"] != [
        s["id"] for s in recommendation["Q"]
    ]:
        raise ValueError("提交的推荐顺序与冻结设置计算结果不一致")
    evaluation = {}
    if evaluated:
        scores = compare_report(g["scenarios"], e["scenarios"], gt["scenarios"], ge, tg, te)
        evaluation = attach_report(evaluate(scores, recommendation), gc)
        evaluation["test_set"] = "original"

    payloads = {
        **material,
        "fused-ssd": ssd,
        "enriched-view": enriched,
        "concern-match": g,
        "concern-compare": gc,
        "gap-recommend": recommendation,
        "gap-compare": {"decisions": ge},
        "GT_G": {"decisions": tg},
        "GT_E": {"decisions": te},
        "exception-generate": g,
        "existing-extract": e,
        "test-ground-truth": gt,
        "missing-report": report,
        "exception-evaluation": evaluation,
    }
    if evaluated:
        payloads["concern-evaluation"] = gc
    return payloads, evaluated


def prepare(bundle):
    errors = sorted(
        Draft202012Validator(BUNDLE).iter_errors(bundle), key=lambda e: str(e.json_path)
    )
    if errors:
        raise ValueError(
            "结果格式错误：" + "；".join(f"{e.json_path}: {e.message}" for e in errors[:8])
        )
    value = deepcopy(bundle)
    try:
        with registry_scope(value["registry"]):
            payloads, evaluated = _derive(value)
            scoped = (
                report_view(
                    payloads["exception-evaluation"],
                    payloads["concern-evaluation"],
                    payloads,
                    value["scope"],
                )
                if evaluated
                else {}
            )
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("结果中存在不完整的定义或引用：" + str(error)) from error
    metrics = scoped.get("metrics", {})
    if "metrics" in bundle and bundle["metrics"] != metrics:
        raise ValueError("提交的指标与服务端按冻结范围计算的结果不一致")
    metadata = {
        "id": fingerprint(bundle),
        "metrics": metrics,
        "version": VERSION,
        "case": value["case"],
        "scope": value["scope"],
        "matching_version": MATCHING_VERSION,
        "registry_hash": value["registry"]["hash"],
        "evaluation_complete": evaluated,
        "counts": {
            k: {
                "concerns": len(value["channels"][k]["concerns"]),
                "scenarios": len(value["channels"][k]["scenarios"]),
            }
            for k in ("G", "E", "GT")
        },
        "channels": {k: v["status"] for k, v in value["channels"].items()},
        "pending": value["pending"]
        + [f"{k} · {note}" for k, v in value["channels"].items() for note in v["pending"]],
    }
    return {
        "metadata": metadata,
        "bundle": bundle,
        "payloads": payloads,
        "scoped_evaluation": scoped,
    }


def register(project, bundle, dry_run=False):
    value = prepare(bundle)
    meta = value["metadata"]
    if dry_run:
        return {**meta, "dry_run": True}
    from scene_completion.workflow_core.storage import run_lock

    value.pop("scoped_evaluation")
    path = project / "imported-case-results" / (meta["id"] + ".json")
    with run_lock(path.parent):
        if path.is_file():
            meta = read_json(path)["metadata"]
        else:
            meta["imported_at"] = datetime.now(timezone.utc).isoformat()
            write_json(path, value)
        summary = path.parent / "index" / path.name
        if not summary.is_file():
            write_json(summary, meta)
    return meta


def versions(project):
    path = project / "imported-case-results"
    return sorted(
        (read_json(file) for file in (path / "index").glob("*.json")),
        key=lambda item: (item["imported_at"], item["id"]),
        reverse=True,
    )


class ImportedCaseView(ResultView):
    """Render a snapshot with the normal result presenters, without task state."""

    def __init__(self, project, import_id, evaluation_scope=None):
        from scene_completion.analysis.evaluation_scope import validate_scope

        if len(import_id) != 64 or any(c not in "0123456789abcdef" for c in import_id):
            raise ValueError("无效导入结果版本")
        self.project = project
        path = project / "imported-case-results" / (import_id + ".json")
        if not path.is_file():
            raise ValueError("导入结果版本不存在")
        self.snapshot = read_json(path)
        self.state = {}
        self.root = path.parent / import_id
        self.test_source_changed = False
        self.meta = self.snapshot["metadata"]
        self.cid = self.meta["case"]["id"]
        self.evaluation_scope = validate_scope(evaluation_scope or self.meta["scope"])
        self.manifest = {
            "matching_version": MATCHING_VERSION,
            "registry_hash": self.meta["registry_hash"],
            "complete": self.meta["evaluation_complete"],
            "supplement_tests": False,
            "recommendation": self.snapshot["payloads"]["gap-recommend"],
        }
        self._scope_inputs_cache = {}

    def definitions(self):
        return self.snapshot["bundle"]["registry"]["definitions"]

    def payload(self, key):
        if key.startswith(self.cid + ":"):
            key = key[len(self.cid) + 1 :]
        return self.snapshot["payloads"].get(key, {})

    def scoped(self, cid, report, concerns=None):
        with registry_scope(self.snapshot["bundle"]["registry"]):
            return super().scoped(cid, report, concerns)

    def cases(self):
        return [
            {
                "id": self.cid,
                "name": self.meta["case"]["name"],
                "analysis_complete": self.meta["channels"]["G"] == "ready",
                "evaluation_complete": self.meta["evaluation_complete"],
                "evaluation_ready": self.meta["evaluation_complete"],
            }
        ]

    def catalog(self):
        return []

    def index(self, include_artifacts=True):
        return {**super().index(include_artifacts), "imported_result": self.meta}

    def detail(self, cid, test_set="original", evaluation_override=None):
        self._require_original(test_set)
        return {
            **super().detail(cid, test_set, evaluation_override),
            "imported_result": self.meta,
            "recommendations": self.payload("gap-recommend"),
        }

    def metrics(self, test_set="original", case_id=None):
        self._require_original(test_set)
        value = super().metrics(test_set, case_id)
        value["truth_source"] = "Code Agent 整理的原始异常测试"
        if not self.meta["evaluation_complete"]:
            value["metrics"] = {}
            for row in value["cases"]:
                row["metrics"] = {}
                row["status"] = "未评测"
        return value

    def scenario(self, cid, channel, sid, test_set="original"):
        self._require_original(test_set)
        if cid != self.cid:
            raise ValueError("未知结果用例")
        return super().scenario(cid, channel, sid, test_set)

    @staticmethod
    def _require_original(test_set):
        if test_set != "original":
            raise ValueError("此导入结果仅包含原始测试集")
