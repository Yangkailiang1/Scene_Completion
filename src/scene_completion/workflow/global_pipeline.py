"""Global G/E reporting precedes independent GT alignment and evaluation."""

from collections import defaultdict
from copy import deepcopy

from scene_completion.domain.contracts import registry
from scene_completion.infrastructure.storage import fingerprint, read_json
from scene_completion.workflow.support import payload


def _cited_documents(records, channel):
    lines = defaultdict(dict)
    for record in records:
        for ref in record.get("source_refs", []):
            parts = ref["quote"].splitlines()
            if len(parts) != ref["line_end"] - ref["line_start"] + 1:
                # A single physical JSON line can contain an embedded multiline
                # string. Preserve it as a single cited source row.
                if ref["line_start"] == ref["line_end"]:
                    parts = [ref["quote"]]
                else:
                    raise ValueError("source citation span does not match retained text")
            for n, text in enumerate(parts, ref["line_start"]):
                old = lines[ref["source_id"]].get(n)
                if old is not None and old != text:
                    raise ValueError("conflicting original source text")
                lines[ref["source_id"]][n] = text
    return [
        {
            "source_id": sid,
            "name": "retained-" + channel + "-citations",
            "channel": channel,
            "lines": [{"number": n, "text": t} for n, t in sorted(rows.items())],
        }
        for sid, rows in lines.items()
    ]


def _schedule_global_analysis(ex, rr, sr, ar, tests):
    from scene_completion.analysis.exception_scopes import (
        canonical_dependencies,
        global_records,
        inverse_dependencies,
        records_from_tests,
    )
    from scene_completion.analysis.global_analysis import (
        compare_concerns,
        compare_scenarios,
        evaluate,
        recommend,
    )
    from scene_completion.analysis.global_idempotency import documents_for, operations, recognized
    from scene_completion.inputs.source_documents import normal_projection

    normal = normal_projection(rr) + normal_projection(sr) + normal_projection(ar)
    groups_cache = {}
    channels = {name: {} for name in ("G_c", "E_c", "GT_c", "G_s", "E_s", "GT_s")}
    anchor_catalogue = {}
    scoped_records = {"E": [], "GT": []}

    def get(key):
        return payload(read_json(ex.root / ex.scheduler.state["tasks"][key]["output_file"]))

    def prepared():
        groups = get("use-case-align")["groups"]
        entities = get("business-entities")["entities"]
        cases = get("rr-use-cases")["cases"] + get("sr-use-cases")["cases"]
        groups_cache.update(groups=groups, entities=entities, cases=cases)
        deps = canonical_dependencies(get("business-dependencies"), groups, cases)["dependencies"]
        ops = (
            operations(get("business-crud-project")["rows"], entities, groups, cases)
            if registry()["definitions"].get("global.idempotency", {}).get("enabled", True)
            else []
        )
        return deps, ops

    def own_records(channel):
        out = []
        for group in groups_cache["groups"]:
            if group["status"] != "confirmed":
                continue
            cid = group["id"]
            scope = get(cid + (":existing-scope" if channel == "E" else ":test-scope"))
            if channel == "E":
                raw = get(cid + ":existing-branches-source")["branches"]
            else:
                # Source records are retained in the scope packet itself and
                # independently re-read here, never recovered from G outputs.
                from scene_completion.analysis.test_alignment import as_records, scoped_tests

                docs, cat = scoped_tests(get("test-inventory"), get("test-case-align"), tests, cid)
                raw = records_from_tests(as_records(cat, docs))
            out += global_records(scope, raw)
        return out

    def active_registry():
        current = registry()
        return {
            **current,
            "definitions": {
                k: v
                for k, v in current["definitions"].items()
                if k.startswith("global.") and v.get("enabled", True)
            },
        }

    def select(records_, anchor, is_operation):
        if is_operation:
            return [
                r
                for r in records_
                if r["scope_unit"]["global_kind"] == "idempotency"
                and anchor["case_id"] in r["scope_unit"]["related_cases"]
                and anchor["entity_id"] in r["scope_unit"]["entity_ids"]
            ]
        return [
            r for r in records_ if any(d["id"] == anchor["id"] for d in inverse_dependencies([r]))
        ]

    def add_channel(anchor, channel, positive=False):
        is_op = "operation" in anchor
        aid = anchor["id"]
        suffix = fingerprint(aid)[:12]
        prefix = "global-" + suffix
        kind = "G" if channel == "G" else channel
        unit_registry = active_registry()
        if is_op:
            unit_registry["definitions"] = {
                k: v for k, v in unit_registry["definitions"].items() if k == "global.idempotency"
            }
        deps = {"dependencies": [] if is_op else [anchor], "pending": []}
        own = select(scoped_records.get(channel, []), anchor, is_op)
        base = {"registry": unit_registry, "business-dependencies": deps}
        if is_op:
            operation_input = (
                anchor
                if channel == "G"
                else {
                    k: anchor[k]
                    for k in (
                        "id",
                        "case_id",
                        "case_aliases",
                        "case_names",
                        "entity_id",
                        "entity_name",
                        "operation",
                    )
                }
            )
            base["business-operations"] = {"operations": [operation_input]}
        if channel == "G":
            from scene_completion.analysis.domain_model import dependency_context

            base["normal-documents"] = (
                documents_for(normal, anchor, "normal")
                if is_op
                else dependency_context(normal, anchor, groups_cache["entities"])
            )
            entity_ids = (
                {anchor["entity_id"]}
                if is_op
                else {anchor["from_entity_id"], anchor["to_entity_id"]}
            )
            base["business-entities"] = {
                "entities": [e for e in groups_cache["entities"] if e["id"] in entity_ids],
                "pending": [],
            }
        else:
            base["existing-documents" if channel == "E" else "test-documents"] = _cited_documents(
                own, "existing" if channel == "E" else "test"
            )
        ckey = prefix + "-" + kind + "_c"
        skey = prefix + "-" + kind + "_s"
        channels[kind + "_c"][aid] = ckey
        channels[kind + "_s"][aid] = skey
        taskc = {
            "G": "global-concerns",
            "E": "global-existing-concerns",
            "GT": "global-test-concerns",
        }[kind]
        tasks = {
            "G": "global-scenarios",
            "E": "global-existing-scenarios",
            "GT": "global-test-scenarios",
        }[kind]
        no_source = (channel == "G" and not positive) or (channel != "G" and not own)
        transform = (
            (lambda d: {"matches": [], "pending": []})
            if no_source
            else (lambda d, a=anchor: recognized(a))
            if is_op and channel == "G"
            else None
        )
        parents = (
            ("business-crud-project", "business-dependencies", "business-entities")
            if channel == "G" and positive
            else tuple(
                g["id"] + (":existing-scope" if channel == "E" else ":test-scope")
                for g in groups_cache["groups"]
                if g["status"] == "confirmed"
            )
            if channel != "G"
            else ()
        )
        if no_source:
            # Empty G channels for inverse-only anchors carry no inverse evidence.
            base = {
                "registry": unit_registry,
                "business-dependencies": {"dependencies": [], "pending": []},
            }
        ex.add(ckey, taskc, parents, static=base, transform=transform)
        ex.add(
            skey,
            tasks,
            (ckey,),
            static=base,
            build=lambda d, b=base, k=ckey: {**deepcopy(b), "identified-concerns": d[k]},
        )
        ex.scheduler.tasks[ckey].display_label = "全局" + kind + "关注点 · " + aid
        ex.scheduler.tasks[skey].display_label = "全局" + kind + "场景 · " + aid

    def merge(d, channel):
        field = "matches" if channel.endswith("_c") else "scenarios"
        return {
            field: [r for k in channels[channel].values() if k in d for r in d[k][field]],
            "pending": [
                r for k in channels[channel].values() if k in d for r in d[k].get("pending", [])
            ],
        }

    def comparisons(purposes):
        result = {}
        for purpose, (left, right) in purposes.items():
            result[purpose] = []
            for aid in sorted(channels[left].keys() & channels[right].keys()):
                a, b = channels[left][aid], channels[right][aid]
                key = "global-match-" + fingerprint([purpose, aid])[:16]
                ex.add(
                    key,
                    "global-scenario-match",
                    (a, b),
                    static={"purpose": purpose},
                    build=lambda d, a=a, b=b, p=purpose: {
                        "left": d[a]["scenarios"],
                        "right": d[b]["scenarios"],
                        "purpose": p,
                    },
                )
                result[purpose].append(key)
        return result

    def aggregate_scenes(d, matched, with_gt):
        return compare_scenarios(
            merge(d, "G_s"),
            merge(d, "E_s"),
            merge(d, "GT_s") if with_gt and tests else None,
            {p: [x for k in keys for x in d[k]["decisions"]] for p, keys in matched.items()},
        )

    def expand_GE():
        deps, ops = prepared()
        scoped_records["E"] = own_records("E")
        positive = {a["id"] for a in deps + ops}
        all_anchors = {a["id"]: a for a in inverse_dependencies(scoped_records["E"]) + deps + ops}
        anchor_catalogue.update(all_anchors)
        for anchor in all_anchors.values():
            add_channel(anchor, "G", anchor["id"] in positive)
            add_channel(anchor, "E")
        ccdeps = tuple(channels["G_c"].values()) + tuple(channels["E_c"].values())
        ex.add(
            "global-concern-compare",
            "global-concern-compare",
            ccdeps,
            build=lambda d: d,
            transform=lambda d: compare_concerns(merge(d, "G_c"), merge(d, "E_c")),
        )
        matched = comparisons({"G_E": ("G_s", "E_s")})
        scenedeps = (
            tuple(channels["G_s"].values())
            + tuple(channels["E_s"].values())
            + tuple(matched["G_E"])
        )
        ex.add(
            "global-scenario-compare",
            "global-scenario-compare",
            scenedeps,
            build=lambda d: d,
            transform=lambda d: aggregate_scenes(d, matched, False),
        )
        ex.add(
            "global-recommend",
            "global-recommend",
            ("global-scenario-compare",),
            build=lambda d: d,
            transform=lambda d: recommend(
                d["global-scenario-compare"]["M"],
                ex.pattern_settings,
                ex.recommendation_history,
                run_id=ex.session_id,
            ),
        )
        ex.add(
            "global-anchor-catalogue",
            "global-anchor-catalogue",
            static={"dependencies": list(all_anchors.values())},
            transform=lambda d: d,
        )
        groups_cache["GE_matches"] = matched

    def expand_GT():
        scoped_records["GT"] = own_records("GT")
        deps, ops = prepared()
        gt_anchors = {a["id"]: a for a in inverse_dependencies(scoped_records["GT"]) + deps + ops}
        for aid, anchor in gt_anchors.items():
            if aid not in anchor_catalogue:
                # An independently evidenced GT dependency can expose a G
                # omission. Its source does not become normal input to G.
                anchor_catalogue[aid] = anchor
                add_channel(anchor, "G", False)
                add_channel(anchor, "E")
            add_channel(anchor, "GT")
        # An E-only relation with no GT still needs an explicit empty GT channel.
        for aid, anchor in anchor_catalogue.items():
            if aid not in channels["GT_c"]:
                add_channel(anchor, "GT")
        cdeps = tuple(k for n in ("G_c", "E_c", "GT_c") for k in channels[n].values())
        ex.add(
            "global-concern-evaluation",
            "global-concern-compare",
            cdeps,
            build=lambda d: d,
            transform=lambda d: compare_concerns(
                merge(d, "G_c"), merge(d, "E_c"), merge(d, "GT_c") if tests else None
            ),
        )
        matched = {
            **groups_cache["GE_matches"],
            **comparisons({"GT_G": ("GT_s", "G_s"), "GT_E": ("GT_s", "E_s")}),
        }
        sdeps = tuple(k for n in ("G_s", "E_s", "GT_s") for k in channels[n].values()) + tuple(
            k for keys in matched.values() for k in keys
        )
        ex.add(
            "global-scenario-evaluation",
            "global-scenario-compare",
            sdeps,
            build=lambda d: d,
            transform=lambda d: aggregate_scenes(d, matched, True),
        )
        ex.add(
            "global-evaluation",
            "global-evaluation",
            ("global-concern-evaluation", "global-scenario-evaluation", "global-recommend")
            + tuple(channels["GT_s"].values()),
            build=lambda d: d,
            transform=lambda d: evaluate(
                d["global-concern-evaluation"],
                d["global-scenario-evaluation"],
                d["global-recommend"],
                merge(d, "GT_s") if tests else None,
            ),
        )

    def schedule():
        ids = [g["id"] for g in get("use-case-align")["groups"] if g["status"] == "confirmed"]
        ex.partitions.append(
            (
                ("business-dependencies", "business-crud-project")
                + tuple(c + ":existing-scope" for c in ids)
                + tuple(c + ":existing-branches-source" for c in ids),
                expand_GE,
            )
        )
        ex.partitions.append(
            (("global-recommend",) + tuple(c + ":test-scope" for c in ids), expand_GT)
        )

    ex.partitions.append((("use-case-align",), schedule))
