"""Discover and assemble independent SSD cases from supplier and core inputs."""

import json
from copy import deepcopy
from pathlib import Path

from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.current_scope import (
    COMMAND_OPERATION_PROFILE,
    COMMAND_PROFILES,
    STRUCTURED_PROFILES,
)
from scene_completion.domain.ssd.construction import (
    channel,
    ident,
    pending,
    unique,
)
from scene_completion.infrastructure.storage import io_path
from scene_completion.inputs.provenance.ssd_sources import (
    Sources,
    api_contracts,
    entities_for,
)
from scene_completion.inputs.structured.case_names import candidates as case_candidates
from scene_completion.workflow.ssd.generate.fixed import generate_g
from scene_completion.workflow.ssd.input_conversion import function_tree
from scene_completion.workflow.ssd.input_conversion.provenance import (
    cited_origins,
    origin_documents,
)
from scene_completion.workflow.ssd.input_conversion.sys_operation import _steps
from scene_completion.workflow.ssd.shared.step_bindings import RULE_VERSION, VERSION


def _input_root(directory):
    root = io_path(directory).resolve()
    return root / "输入文件" if (root / "输入文件").is_dir() else root


def case_identity(file, directory, raw=None):
    """Shared scheduler/builder identity, independent of an absolute checkout path.

    Pass the already decoded raw object when discovering cases. Passing an empty
    mapping returns a stable fallback identity even for a malformed source file.
    """
    root = _input_root(directory)
    file = Path(file)
    if not file.is_absolute():
        file = root / file
    file = io_path(file).resolve()
    relative = file.parent.relative_to(root)
    if raw is None:
        raw = json.loads(file.read_text(encoding="utf-8-sig"))
    inferred = None
    if raw.get("use_case") and not raw.get("use_case_id") and (root / "功能树.json").is_file():
        tree = json.loads((root / "功能树.json").read_text(encoding="utf-8-sig"))
        ids = [
            row.get("functionId") or row.get("ucId")
            for _, row in case_candidates(
                tree.get("functions", []),
                raw["use_case"],
                raw.get("resource") or file.parent.parent.name,
            )
        ]
        if len(ids) == 1:
            inferred = ids[0]
    return {
        "id": raw.get("use_case_id") or inferred or ident("case", relative.as_posix()),
        "name": raw.get("use_case") or file.parent.name,
    }


def build_cases(directory, case_ids=None, *, case_files=None, generate=True, profile=None):
    """Build independent bundles; an explicit file list isolates worker failures.

    Shared API/entity documents are read once, but only the selected SysOperation
    files are decoded when ``case_files`` is supplied by a case worker.
    """
    from scene_completion.inputs.structured import authoring_cases

    root = _input_root(directory)
    if case_files is None:
        entries = list(authoring_cases.discover(root, case_identity))
    else:
        if isinstance(case_files, (str, Path)):
            case_files = [case_files]
        entries = []
        for value in case_files:
            file = Path(value)
            file = io_path(file if file.is_absolute() else root / file).resolve()
            if (
                not file.is_relative_to(root)
                or file.name not in authoring_cases.FILES
                or not file.is_file()
            ):
                raise ValueError("用例文件必须是输入目录内的 SysOperation.json：" + str(value))
            if file not in [entry[0] for entry in entries]:
                entries.append((file, None, None))
    if not entries:
        raise ValueError("目录中没有 SysOperation.json；原始输入须先转换为用例 SSD")
    origins = origin_documents(root)
    sources = Sources(root, origins)
    tree_path = root / "功能树.json"
    tree = json.loads(tree_path.read_text(encoding="utf-8-sig")) if tree_path.exists() else None
    contracts = api_contracts(sources, tree, tree_path)
    selections = {case_ids} if isinstance(case_ids, str) else set(case_ids or [])
    bundles = []
    from scene_completion.workflow.ssd.input_conversion.requirements import existing_channel
    from scene_completion.workflow.ssd.input_conversion.test_evidence import test_channel

    for file, discovered_case, error in entries:
        if discovered_case and selections and not selections.intersection(discovered_case.values()):
            continue
        if error:
            raise ValueError(error)
        value = authoring_cases.read(file, root)
        authored = authoring_cases.is_authoring(value)
        if authored:
            # Rendered in memory: literal values stay as supplied and only the
            # step references are re-pointed. The folder name is presentation.
            raw = authoring_cases.sys_operation(value)
            case = authoring_cases.case_identity(value)
        else:
            raw = value
            case = case_identity(file, root, raw)
        if selections and not selections.intersection(case.values()):
            continue
        name = sources.add(file) if Path(file).is_relative_to(root) else None
        tree_link = raw.get("function_tree") or {}
        active_profile = profile or raw.get("analysis_profile")
        entity_only = active_profile in STRUCTURED_PROFILES
        command_mode = active_profile in COMMAND_PROFILES
        case_entity = raw.get("resource") or (file.parent.parent.name if not authored else None)
        local_tree_path, local_tree, local_contracts, tree_case, tree_hits = function_tree.for_case(
            root,
            sources,
            (tree_path, tree, contracts),
            tree_link,
            case,
            case_entity,
            active_profile,
        )
        steps, missing = _steps(
            raw, sources, name, local_contracts, root=root, entity_only=entity_only
        )
        bundle = {
            "version": VERSION,
            "coverage_policy": "coverage-any-confirmed-v2",
            "case": case,
            **({"analysis_profile": active_profile} if active_profile else {}),
            "function_tree_case_id": tree_case,
            **({"case_entity": case_entity} if case_entity else {}),
            "function_tree_path": local_tree_path.relative_to(root).as_posix()
            if local_tree
            else None,
            "steps": steps,
            "channels": {key: channel() for key in ("G", "E", "GT")},
            "documents": [],
            "decisions": [],
            "pending": [],
            "entities": entities_for(
                sources,
                local_tree,
                tree_case,
                case["name"],
                local_tree_path,
                entity_only=entity_only,
                selected=tree_hits if active_profile == COMMAND_OPERATION_PROFILE else None,
            ),
            # Retain the project catalogue so a reviewer can select another
            # declared API. G still uses only the actual step's bound fields.
            "apis": [] if entity_only else deepcopy(list(local_contracts.values())),
            "registry": default_registry(),
            "rule_version": RULE_VERSION,
        }
        if active_profile == COMMAND_OPERATION_PROFILE and len(tree_hits) != 1:
            bundle["pending"].append(
                pending(
                    ident("case-tree-gap", case["id"]),
                    "功能树用例无法唯一对应",
                    reason="功能树用例无法唯一对应",
                    case_match_gap=True,
                    candidates=[row.get("functionId") or row.get("ucId") for _, row in tree_hits],
                )
            )
        if command_mode:
            from scene_completion.workflow.ssd.shared.command_bindings import attach

            attach(bundle, local_contracts)
        if entity_only and not command_mode:
            bundle["operation_hints"] = function_tree.operation_hints(
                local_tree, tree_case, case["name"]
            )
        if missing:
            bundle["pending"].append(
                pending(
                    ident("pending", case["id"], "order"),
                    "Order 未引用的步骤已保留，请确认顺序：" + ", ".join(missing),
                    [sources.ref(name)] if name else [],
                )
            )
        from scene_completion.analysis.interactions.field_anchors import anchors

        bundle["field_anchors"] = anchors(bundle)
        for step in steps:
            if "parent_candidates" in step:
                bundle["pending"].append(
                    pending(
                        ident("pending", case["id"], "response", step["id"]),
                        "响应未能唯一关联到请求",
                        step["source_refs"],
                        step_id=step["id"],
                        candidate_step_ids=step["parent_candidates"],
                    )
                )
        if generate:
            bundle["channels"]["G"] = generate_g(bundle)
        bundle["channels"]["E"] = existing_channel(
            bundle,
            file.parent,
            sources,
            supplied=authoring_cases.supplied_exceptions(raw, sources, file, "E")
            if authored
            else (),
            raw=raw if not authored else None,
        )
        if authored:
            # The supplied extension mapping is the test case's own binding; keep
            # it visible for review instead of re-deriving it.
            bundle["extension_mapping"] = deepcopy(
                (raw.get("extension-mapping") or {}).get("items", [])
            )
        bundle["channels"]["GT"] = test_channel(
            bundle,
            sources,
            supplied=authoring_cases.supplied_exceptions(raw, sources, file, "GT")
            if authored
            else (),
            mapping=raw.get("extension-mapping") if authored else None,
            mapping_source=(
                (file.with_name("extension-mapping.json"), "")
                if file.name == authoring_cases.LEGACY_MAIN
                else (file, "/extension_mapping")
            )
            if authored and (raw.get("extension-mapping") or {}).get("items")
            else None,
        )
        bundle["documents"] = deepcopy(list(sources.documents.values()))
        bundle["origin_documents"] = cited_origins(bundle, origins)
        bundle["source_documents"] = unique(
            [
                {"path": d["source_path"], "role": d["role"], "aliases": d["configured_aliases"]}
                for d in origins
            ]
        )
        bundles.append(bundle)
    if selections:
        found = {value for bundle in bundles for value in bundle["case"].values()}
        unknown = selections - found
        if unknown:
            raise ValueError("未知用例：" + ", ".join(sorted(unknown)))
    return bundles
