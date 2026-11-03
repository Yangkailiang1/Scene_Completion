"""Global Pipeline for the current workflow."""

from copy import deepcopy

from scene_completion.domain.contracts import registry
from scene_completion.infrastructure.storage import fingerprint, read_json
from scene_completion.inputs.source_documents import normal_projection
from scene_completion.workflow.support import payload


def _schedule_global_analysis(ex, rr, sr, ar, tests):
    """Expand global tasks only after the evidenced business graph is saved."""
    from scene_completion.analysis.domain_model import dependency_context, existing_branch_context
    from scene_completion.analysis.global_analysis import (
        compare_concerns,
        compare_scenarios,
        evaluate,
        recommend,
    )
    from scene_completion.inputs.source_documents import current_projection
    from scene_completion.inputs.test_sources import exception_documents

    def expand():
        state = ex.scheduler.state["tasks"]

        def get(key):
            return payload(read_json(ex.root / state[key]["output_file"]))

        dependencies = get("business-dependencies")["dependencies"]
        entities = get("business-entities")["entities"]
        active = {
            k: v
            for k, v in registry()["definitions"].items()
            if k.startswith("global.") and v.get("enabled", True)
        }
        limited_registry = {
            "version": registry()["version"],
            "hash": registry()["hash"],
            "definitions": active,
        }
        normal = normal_projection(rr) + normal_projection(sr) + normal_projection(ar)
        raw = current_projection(rr) + current_projection(sr) + current_projection(ar)
        branches = get("existing-branches")["branches"]
        test = exception_documents(tests)
        keys = {k: [] for k in ("G_c", "E_c", "GT_c", "G_s", "E_s", "GT_s")}
        for dependency in dependencies:
            suffix = fingerprint(dependency["id"])[:12]
            one = {"dependencies": [dependency], "pending": []}
            subset = [
                e
                for e in entities
                if e["id"] in {dependency["from_entity_id"], dependency["to_entity_id"]}
            ]
            normal_docs = dependency_context(normal, dependency, entities)
            existing_docs = existing_branch_context(raw, branches, dependency, entities)
            test_docs = dependency_context(test, dependency, entities)
            names = {
                "G_c": ("global-concerns", ()),
                "E_c": ("global-existing-concerns", ()),
                "GT_c": ("global-test-concerns", ()),
                "G_s": ("global-scenarios", ("G_c",)),
                "E_s": ("global-existing-scenarios", ("E_c",)),
                "GT_s": ("global-test-scenarios", ("GT_c",)),
            }
            for channel, (task, depends_on) in names.items():
                key = "global-" + suffix + "-" + channel
                keys[channel].append(key)
                parents = ("business-dependencies",) + tuple(
                    "global-" + suffix + "-" + x for x in depends_on
                )
                if channel == "G_c":
                    inputs = {
                        "business-dependencies": one,
                        "business-entities": {"entities": subset, "pending": []},
                        "registry": limited_registry,
                        "normal-documents": normal_docs,
                    }
                elif channel == "E_c":
                    inputs = {
                        "existing-documents": existing_docs,
                        "business-dependencies": one,
                        "registry": limited_registry,
                    }
                elif channel == "GT_c":
                    inputs = {
                        "test-documents": test_docs,
                        "business-dependencies": one,
                        "registry": limited_registry,
                    }
                else:
                    inputs = {"business-dependencies": one, "registry": limited_registry}
                    if channel == "G_s":
                        inputs["business-entities"] = {"entities": subset, "pending": []}
                    else:
                        inputs["existing-documents" if channel == "E_s" else "test-documents"] = (
                            existing_docs if channel == "E_s" else test_docs
                        )

                def build(d, inputs=inputs, depends_on=depends_on, suffix=suffix):
                    value = deepcopy(inputs)
                    if depends_on:
                        value["identified-concerns"] = d["global-" + suffix + "-" + depends_on[0]]
                    return value

                inactive = (
                    (channel in {"E_c", "E_s"} and not existing_docs)
                    or (channel in {"GT_c", "GT_s"} and not test_docs)
                    or (
                        channel in {"G_s", "E_s", "GT_s"}
                        and not get("business-dependencies")["dependencies"]
                    )
                )

                def empty(d, channel=channel):
                    return {"matches" if channel.endswith("_c") else "scenarios": [], "pending": []}

                ex.add(key, task, parents, build=build, transform=empty if inactive else None)
                ex.scheduler.tasks[key].display_label = (
                    {
                        "G_c": "全局关注点识别",
                        "E_c": "全局已有关注点",
                        "GT_c": "全局测试关注点",
                        "G_s": "全局场景展开",
                        "E_s": "全局已有场景",
                        "GT_s": "全局测试场景",
                    }[channel]
                    + " · "
                    + dependency["id"]
                )

        def merged(d, channel):
            list_key = "matches" if channel.endswith("_c") else "scenarios"
            return {
                list_key: [row for key in keys[channel] for row in d[key][list_key]],
                "pending": [row for key in keys[channel] for row in d[key].get("pending", [])],
            }

        concern_deps = tuple(keys["G_c"] + keys["E_c"] + keys["GT_c"])
        ex.add(
            "global-concern-compare",
            "global-concern-compare",
            concern_deps,
            build=lambda d: d,
            transform=lambda d: compare_concerns(
                merged(d, "G_c"),
                merged(d, "E_c"),
                merged(d, "GT_c")
                if any(keys["GT_c"] and d[k]["matches"] for k in keys["GT_c"])
                else None,
            ),
        )
        scenario_deps = tuple(keys["G_s"] + keys["E_s"] + keys["GT_s"])
        ex.add(
            "global-scenario-compare",
            "global-scenario-compare",
            scenario_deps,
            build=lambda d: d,
            transform=lambda d: compare_scenarios(
                merged(d, "G_s"),
                merged(d, "E_s"),
                merged(d, "GT_s") if any(d[k]["scenarios"] for k in keys["GT_s"]) else None,
            ),
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
            "global-evaluation",
            "global-evaluation",
            ("global-concern-compare", "global-scenario-compare", "global-recommend")
            + tuple(keys["GT_s"]),
            build=lambda d: d,
            transform=lambda d: evaluate(
                d["global-concern-compare"],
                d["global-scenario-compare"],
                d["global-recommend"],
                merged(d, "GT_s") if any(d[k]["scenarios"] for k in keys["GT_s"]) else None,
            ),
        )

    ex.partitions.append((("business-dependencies", "existing-branches"), expand))
