"""Current protocol business objects and task JSON schemas."""

from copy import deepcopy


def obj(**properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def arr(items):
    return {"type": "array", "items": items}


def enum(*values):
    return {"enum": list(values)}


S = {"type": "string", "minLength": 1}
STR = {"type": "string"}
NULL_S = {"type": ["string", "null"]}
INT = {"type": "integer"}
REF = obj(
    source_id=S,
    line_start={"type": "integer", "minimum": 1},
    line_end={"type": "integer", "minimum": 1},
    quote=S,
)
DOCUMENT = obj(
    source_id=S,
    name=S,
    channel=enum("normal", "existing", "test"),
    lines=arr(obj(number={"type": "integer", "minimum": 1}, text=STR)),
)
REFS = arr(REF)
VALUE = {
    "anyOf": [
        {"type": "string"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "null"},
        arr({"anyOf": [{"type": "string"}, {"type": "number"}]}),
    ]
}
CONSTRAINT = obj(
    id=S,
    kind=enum("type", "enum", "minimum", "maximum", "format", "length", "size", "pattern", "other"),
    value=VALUE,
    status=enum("explicit", "pending"),
    source_refs=REFS,
)
PARAMETER = obj(
    name=S,
    location=enum("header", "path", "query", "body", "response", "business"),
    data_type=NULL_S,
    required={"type": ["boolean", "null"]},
    default=VALUE,
    constraints=arr(CONSTRAINT),
    source_refs=REFS,
)
API_PARAMETERS = obj(id=S, name=S, address=NULL_S, parameters=arr(PARAMETER), source_refs=REFS)
# Optional extension preserves compatibility with historical parameter artifacts.
API_PARAMETERS["properties"].update(source_layer=enum("RR", "SR"), declared_id=S, method=NULL_S)
INTERFACE_CONSTRAINT = obj(
    kind=enum("authentication", "signature", "authorization", "transport", "other"),
    requirement=S,
    source_refs=REFS,
)
API_PARAMETERS["properties"].update(
    interface_scope=enum("system", "external"),
    interface_constraints=arr(INTERFACE_CONSTRAINT),
)
API_PARAMETERS["properties"]["responses"] = arr(
    obj(
        kind=enum("success", "error"),
        status_code=NULL_S,
        parameters=arr(PARAMETER),
        source_refs=REFS,
    )
)
PARTY = obj(name=S, position=S, source_refs=REFS)
INTERACTION = obj(
    id=S,
    case_id=S,
    sequence={"type": "integer", "minimum": 1},
    parent_id=NULL_S,
    layer=enum("RR", "SR"),
    sender=PARTY,
    receiver=PARTY,
    operation=obj(
        name=S,
        kinds=arr(
            enum(
                "read",
                "create",
                "update",
                "delete",
                "display",
                "process",
                "publish",
                "external_call",
            )
        ),
        sequence=arr(S),
        optional=arr(S),
        source_refs=REFS,
    ),
    data=obj(sequence=arr(PARAMETER)),
    direction=enum("request", "return"),
    api_id=NULL_S,
    source_refs=REFS,
)
INTERACTION["properties"]["step_kind"] = enum("interaction", "action")
COMPONENT = obj(
    id=S,
    name=S,
    composition_type=enum(
        "外部Actor（人类）",
        "外部Actor（系统）",
        "系统边界",
        "UI/前端",
        "内部服务",
        "用例",
        "内部数据库",
        "外部数据库",
        "内部资源",
        "外部资源",
        "连接设备",
        "部署硬件",
        "运行环境",
        "AI模型",
    ),
    parent_id=NULL_S,
    source_status=enum("explicit", "inferred"),
    source_refs=REFS,
)
INTERFACE = obj(id=S, name=S, method=NULL_S, address=NULL_S, source_refs=REFS)
INTERFACE["properties"].update(source_layer=enum("RR", "SR"), declared_id=S)
INTERFACE["properties"].update(
    interface_scope=enum("system", "external"),
    interface_constraints=arr(INTERFACE_CONSTRAINT),
)
SCENARIO = obj(
    id=S,
    case_id=S,
    interaction_id=S,
    layer=enum("RR", "SR"),
    object=S,
    operation=S,
    cause=S,
    conditions=arr(S),
    concern_key=S,
    field=NULL_S,
    rule_id=NULL_S,
    source_status=enum("explicit", "framework_inferred"),
    derivation=STR,
    source_refs=REFS,
    steps=obj(
        normal_context=arr(S), trigger=S, documented_follow_up=arr(obj(action=S, source_refs=REFS))
    ),
)
PENDING = obj(interaction_id=S, object=S, concern_key=S, reason=S, source_refs=REFS)
DECISION = obj(left_id=S, right_id=S, status=enum("full", "partial", "unmatched"), reason=S)
MATCH = obj(
    interaction_id=S,
    target=enum("sender", "receiver", "operation", "data"),
    object=S,
    concern_key=S,
    basis=S,
    concrete_rule=NULL_S,
    source_refs=REFS,
)

MATCH["properties"].update(
    policy_id=S,
    operation_index={"type": ["integer", "null"], "minimum": 0},
    source_unit_ids=arr(S),
    source_branch_ids=arr(S),
    coverage_kind=enum("exact", "input_parameters", "authentication", "authorization"),
    api_id=NULL_S,
    api_source_layer={"anyOf": [{"type": "null"}, enum("RR", "SR")]},
    element_id=S,
    binding_id=S,
    case_id=S,
    direction=enum("request", "return"),
    identification=S,
    classification_origin=S,
    caller=S,
    callee=S,
    element_origin={"type": "object"},
)

ACTIVATION = obj(
    kind=enum(
        "data",
        "authentication",
        "authorization",
        "availability",
        "result",
        "compatibility",
        "timing",
        "device",
        "resource_limit",
        "business",
        "persistence",
        "concurrency",
        "idempotency",
        "release",
        "recovery",
        "resource_lookup",
        "storage_field",
        "unique",
        "reference",
        "transaction",
        "isolation",
        "grounding",
        "instruction",
        "context",
        "prompt_security",
        "stability",
        "relation",
        "technology",
    ),
    condition=S,
    value=VALUE,
    unit=NULL_S,
    status=enum("explicit", "pending"),
    source_refs=REFS,
)
ACTIVATION["properties"].update(
    field=NULL_S,
    constraint_kind={
        "anyOf": [
            {"type": "null"},
            enum(
                "required",
                "type",
                "enum",
                "minimum",
                "maximum",
                "format",
                "length",
                "size",
                "pattern",
                "other",
            ),
        ]
    },
)
MATCH["properties"].update(
    status=enum("applicable", "pending", "not_applicable"),
    status_reason=S,
    inheritance_paths=arr(arr(S)),
    activation_evidence=arr(ACTIVATION),
    scope=enum("interface", "storage", "context", "service", "relation", "environment"),
    data_location={
        "anyOf": [
            {"type": "null"},
            enum("header", "path", "query", "body", "response", "business", "storage"),
        ]
    },
    service=NULL_S,
    functional_types=arr(
        enum(
            "display_interaction",
            "query_retrieval",
            "create",
            "update",
            "delete",
            "resource_mutation",
            "analysis_generation",
            "release_activation",
        )
    ),
    technologies=arr(enum("database", "llm")),
)
SCENARIO["properties"].update(
    policy_id=S,
    concern_origins=arr(S),
    concern_paths=arr(arr(S)),
    scope=enum("interface", "storage", "context", "service", "relation", "environment"),
    data_location=NULL_S,
)

# Alignment metadata is optional for generated rules, mandatory on new inverse tasks.
SCENARIO["properties"].update(
    concern_binding_ids=arr(S), element_anchors=arr({"type": "object"}), matching_version=S
)
SCENARIO["properties"].update(
    original_branch_id=NULL_S,
    coverage_kind=enum("exact", "input_parameters", "authentication", "authorization"),
    canonical_interaction_id=S,
    interaction_type=enum("actor_system", "service_service", "undetermined"),
)
SCENARIO["properties"].update(
    resolution=enum("explicit", "conditional"),
    executable={"type": "boolean"},
    pending_details=arr(S),
    normalization_origin=obj(interaction_id=S, object=S, field=NULL_S, data_location=NULL_S),
    source_scenario_id=S,
)
SCENARIO["properties"].update(source_unit_ids=arr(S), quality_notes=arr(S))
SCENARIO["properties"]["activation_evidence"] = arr(ACTIVATION)
SCENARIO["properties"]["scenario_type"] = enum("exception", "normal", "optional", "pending")
FAILURE_RULE = obj(kind=S, value=VALUE)
SCENARIO["properties"]["failure_rule"] = FAILURE_RULE
SCENARIO["properties"].update(
    pattern_id=S,
    linked_pattern_ids=arr(S),
    confidence=obj(
        score={"type": "number", "minimum": 0, "maximum": 1},
        basis=S,
        calibrated_probability=enum(False),
    ),
    risk=obj(
        level=enum("low", "normal", "high", "critical"),
        score={"type": "number"},
        reason=S,
        source=enum("project_override", "pattern_default"),
    ),
    scenario_context={"type": "object"},
    pattern_versions={"type": "object", "additionalProperties": S},
    predicate={"type": "object"},
)
DECISION["properties"].update(
    concern_alignment=enum("same", "different"), follow_up_comparison=enum("not_scored")
)
NORMAL_RULE = obj(
    id=S,
    interaction_id=S,
    owner_service=S,
    concern_key=S,
    condition=S,
    violation=S,
    fields=arr(S),
    functional_kinds=arr(
        enum("read", "create", "update", "delete", "display", "process", "publish", "external_call")
    ),
    resolution=enum("explicit", "conditional"),
    pending_details=arr(S),
    source_refs=REFS,
)
BRANCH = obj(
    id=S, case_hint=STR, description=S, operation_hint=STR, party_hint=STR, source_refs=REFS
)
BRANCH["properties"]["scenario_type"] = enum("exception", "normal", "optional", "pending")
BINDING = obj(
    branch_id=S,
    interaction_id=NULL_S,
    status=enum("confirmed", "pending", "not_this_case"),
    basis=S,
    source_refs=REFS,
)

# Strict nested enrichment contracts keep arbitrary side-channel material out.
RESOURCE_SERVICE = obj(
    node_id=S,
    name=S,
    kind=enum("internal_service"),
    service_role=enum("resource_service"),
    physical_resource_id=S,
    logical_only=enum(True),
    resource_origin=enum("internal", "external"),
    source_refs=REFS,
)
ENRICHED_PARTY = obj(
    **PARTY["properties"],
    component_id=NULL_S,
    resource_service={"anyOf": [{"type": "null"}, RESOURCE_SERVICE]},
    supported_operations=arr(obj(name=S, source_refs=REFS)),
    concerns=arr(MATCH),
)
LINK = obj(rr_id=S, sr_ids=arr(S), status=enum("confirmed", "pending"), basis=S, source_refs=REFS)
CLASSIFICATION = obj(
    kind=enum("actor_system", "service_service", "undetermined"),
    caller=S,
    provider=S,
    caller_location=S,
    provider_location=S,
)
ENRICHED_INTERACTION = obj(
    **{
        **INTERACTION["properties"],
        "sender": ENRICHED_PARTY,
        "receiver": ENRICHED_PARTY,
        "data": obj(sequence=arr(PARAMETER), concerns=arr(MATCH)),
        "operation": {
            **deepcopy(INTERACTION["properties"]["operation"]),
            "properties": {
                **deepcopy(INTERACTION["properties"]["operation"]["properties"]),
                "concerns": arr(MATCH),
            },
        },
    },
    associated_api=NULL_S,
    classification=CLASSIFICATION,
)
ENRICHED_INTERACTION["required"].remove("step_kind")
ENRICHED_INTERACTION["properties"]["source_views"] = arr(
    obj(id=S, layer=enum("RR", "SR"), api_id=NULL_S, operation=S, source_refs=REFS)
)
ENRICHED_INTERACTION["properties"]["parameter_requirement_sources"] = arr(
    obj(
        name=S,
        location=S,
        sources=arr(
            obj(
                origin=enum("SSD", "API"),
                **{
                    k: deepcopy(PARAMETER["properties"][k])
                    for k in ("data_type", "required", "default", "constraints", "source_refs")
                },
            )
        ),
    )
)
ENRICHED = obj(
    interactions=arr(ENRICHED_INTERACTION),
    rr_sr_links=arr(LINK),
    pending=arr(obj(interaction_id=S, reason=S, source_refs=REFS)),
    resource_mappings=arr(obj(physical_resource_id=S, logical_service_id=S, source_refs=REFS)),
)

SCHEMAS = {
    "artifact-convert": obj(
        source_role=enum("artifact", "RR", "SR", "test", "unknown"),
        artifacts=arr(
            obj(
                task=enum(
                    "components",
                    "api-map",
                    "api-parameters",
                    "rr-ssd",
                    "sr-ssd",
                    "fused-ssd",
                    "object-operations",
                    "business-entities",
                ),
                case_hint=NULL_S,
                coverage=enum("complete", "partial"),
                payload={"type": "object"},
                source_refs=REFS,
            )
        ),
    ),
    "normal-rules": obj(
        rules=arr(NORMAL_RULE), pending=arr(obj(interaction_id=S, reason=S, source_refs=REFS))
    ),
    "components": obj(
        components=arr(COMPONENT),
        relations=arr(obj(from_id=S, to_id=S, relation=S, source_refs=REFS)),
    ),
    "rr-ssd": obj(interactions=arr(INTERACTION)),
    "sr-ssd": obj(interactions=arr(INTERACTION)),
    "object-operations": obj(
        objects=arr(obj(name=S, supported_operations=arr(obj(name=S, source_refs=REFS))))
    ),
    "api-map": obj(services=arr(obj(name=S, interfaces=arr(INTERFACE), source_refs=REFS))),
    "api-index": obj(
        apis=arr(
            {
                **obj(
                    id=S,
                    name=S,
                    source_ranges=arr(obj(source_id=S, start=INT, end=INT)),
                    source_refs=REFS,
                ),
                "properties": {
                    **obj(
                        id=S,
                        name=S,
                        source_ranges=arr(obj(source_id=S, start=INT, end=INT)),
                        source_refs=REFS,
                    )["properties"],
                    "source_layer": enum("RR", "SR"),
                    "declared_id": S,
                    "interface_scope": enum("system", "external"),
                },
            }
        )
    ),
    "api-parameters": obj(apis=arr(API_PARAMETERS)),
    "concern-match": obj(matches=arr(MATCH), pending=arr(PENDING)),
    "existing-concerns": obj(matches=arr(MATCH), pending=arr(PENDING)),
    "test-concerns": obj(matches=arr(MATCH), pending=arr(PENDING)),
    "exception-generate": obj(scenarios=arr(SCENARIO), pending=arr(PENDING)),
    "existing-branches": obj(branches=arr(BRANCH)),
    "existing-bind": obj(bindings=arr(BINDING)),
    "existing-extract": obj(scenarios=arr(SCENARIO)),
    "test-ground-truth": obj(scenarios=arr(SCENARIO)),
    "gap-compare": obj(decisions=arr(DECISION), missing=arr(SCENARIO)),
    "semantic-compare": obj(decisions=arr(DECISION)),
    "interaction-align": obj(
        aliases=arr(obj(name=S, component_id=S, source_refs=REFS)),
        links=arr(
            obj(
                rr_id=S,
                sr_ids=arr(S),
                status=enum("confirmed", "pending"),
                basis=S,
                source_refs=REFS,
            )
        ),
    ),
    "gap-recommend": {
        "oneOf": [
            obj(enabled=enum(False), status=enum("未启用")),
            {
                "type": "object",
                "required": [
                    "enabled",
                    "status",
                    "Q",
                    "ranked",
                    "critical_review",
                    "settings_hash",
                    "history_hash",
                ],
                "properties": {"enabled": enum(True), "Q": arr(SCENARIO)},
            },
        ]
    },
    "test-operation-project": obj(
        objects=arr(obj(name=S, supported_operations=arr(obj(name=S, source_refs=REFS))))
    ),
}

# V5 project-wide products. A global binding has a dependency identity and no
# interaction_id; it cannot be scored again for every associated use case.
DOMAIN_PENDING = obj(object=S, reason=S, source_refs=REFS)
BUSINESS_ATTRIBUTE = obj(
    name=S,
    data_type=NULL_S,
    required={"type": ["boolean", "null"]},
    operation=enum("create", "read", "update", "delete", "any"),
    constraints=arr(CONSTRAINT),
    source_refs=REFS,
)
BUSINESS_ATTRIBUTE["properties"].update(case_ids=arr(S), case_names=arr(S))
BUSINESS_RULE = obj(
    id=S,
    description=S,
    operation=enum("create", "read", "update", "delete", "any"),
    fields=arr(S),
    condition=S,
    source_refs=REFS,
)
BUSINESS_ENTITY = obj(
    id=S,
    name=S,
    attributes=arr(BUSINESS_ATTRIBUTE),
    business_rules=arr(BUSINESS_RULE),
    source_refs=REFS,
)
CRUD_ROW = obj(
    case_id=S,
    interaction_id=S,
    entity_id=S,
    service=S,
    operation=enum("create", "read", "update", "delete"),
    api_id=NULL_S,
    basis=S,
    source_refs=REFS,
)
CRUD_ROW["properties"].update(
    execution_mode=enum("direct", "delegated"),
    delegate_interaction_ids=arr(S),
)
FIELD_MAPPING = obj(
    api_id=S,
    direction=enum("request", "return"),
    location=enum("header", "path", "query", "body", "response"),
    field_path=S,
    entity_id=S,
    attribute=S,
    basis=S,
    source_refs=REFS,
)
DATA_ENTITY = obj(id=S, name=S, fields=arr(S), source_refs=REFS)
DATA_RELATION = obj(
    id=S, from_entity_id=S, to_entity_id=S, relation=S, fields=arr(S), source_refs=REFS
)
DATA_FLOW = obj(
    id=S,
    producer_service=S,
    consumer_service=S,
    entity_id=S,
    fields=arr(S),
    interaction_id=S,
    source_refs=REFS,
)
BUSINESS_DEPENDENCY = obj(
    id=S,
    from_case_id=S,
    to_case_id=S,
    from_entity_id=S,
    to_entity_id=S,
    dependency_type=enum("order", "consistency", "cascade", "other"),
    condition=S,
    obligation=S,
    cascade_group=NULL_S,
    source_refs=REFS,
)
GLOBAL_BINDING = obj(id=S, dependency_id=NULL_S, concern_key=S, object=S, basis=S, source_refs=REFS)
GLOBAL_BINDING["properties"].update(business_operation_id=S, policy_id=S)
GLOBAL_SCENARIO = obj(
    id=S,
    dependency_id=NULL_S,
    concern_key=S,
    object=S,
    cause=S,
    conditions=arr(S),
    source_status=enum("explicit", "framework_inferred"),
    resolution=enum("explicit", "conditional"),
    executable={"type": "boolean"},
    source_refs=REFS,
)
GLOBAL_SCENARIO["properties"].update(business_operation_id=S)
SCHEMAS.update(
    {
        "global-scenario-match": obj(decisions=arr(DECISION)),
        "business-entities": obj(entities=arr(BUSINESS_ENTITY), pending=arr(DOMAIN_PENDING)),
        "business-crud": obj(rows=arr(CRUD_ROW), pending=arr(DOMAIN_PENDING)),
        "business-attribute-map": obj(mappings=arr(FIELD_MAPPING), pending=arr(DOMAIN_PENDING)),
        "data-dependencies": obj(
            entities=arr(DATA_ENTITY),
            relations=arr(DATA_RELATION),
            flows=arr(DATA_FLOW),
            pending=arr(DOMAIN_PENDING),
        ),
        "business-dependencies": obj(
            dependencies=arr(BUSINESS_DEPENDENCY), pending=arr(DOMAIN_PENDING)
        ),
        "global-concerns": obj(matches=arr(GLOBAL_BINDING), pending=arr(DOMAIN_PENDING)),
        "global-existing-concerns": obj(matches=arr(GLOBAL_BINDING), pending=arr(DOMAIN_PENDING)),
        "global-test-concerns": obj(matches=arr(GLOBAL_BINDING), pending=arr(DOMAIN_PENDING)),
        "global-scenarios": obj(scenarios=arr(GLOBAL_SCENARIO), pending=arr(DOMAIN_PENDING)),
        "global-existing-scenarios": obj(
            scenarios=arr(GLOBAL_SCENARIO), pending=arr(DOMAIN_PENDING)
        ),
        "global-test-scenarios": obj(scenarios=arr(GLOBAL_SCENARIO), pending=arr(DOMAIN_PENDING)),
        "global-concern-compare": obj(
            rows=arr({"type": "object"}),
            G_count=INT,
            E_count=INT,
            M_count=INT,
            M_ids=arr(S),
            pending=arr(DOMAIN_PENDING),
            metrics={"type": "object"},
        ),
        "global-scenario-compare": obj(
            rows=arr({"type": "object"}),
            G_count=INT,
            E_count=INT,
            GT_count={"type": ["integer", "null"]},
            M=arr(GLOBAL_SCENARIO),
            pending=arr(DOMAIN_PENDING),
        ),
        "global-recommend": obj(
            Q=arr(GLOBAL_SCENARIO),
            ranked=arr({"type": "object"}),
            settings={"type": "object"},
            history_count=INT,
            run_id=S,
        ),
        "global-evaluation": obj(
            granularity=enum("global"),
            metrics={"type": "object"},
            concern_count=INT,
            scenario_count=INT,
            missing_count=INT,
            recommendation_count=INT,
            formula_notes={"type": "object"},
        ),
    }
)

# Each actual request needs an explicit decision, rather than treating a
# database-only matrix as proof that the receiving service was reviewed.
SCHEMAS["business-crud"]["properties"]["reviews"] = arr(
    obj(
        interaction_id=S,
        decision=enum("crud", "not_crud", "pending"),
        basis=S,
        source_refs=REFS,
    )
)

SCHEMAS["pattern-applicability"] = obj(
    instances=arr(
        obj(id=S, pattern_id=S, status=enum("accepted", "pending", "excluded"), scenario=SCENARIO)
    ),
    settings_hash=S,
    library_version=S,
    threshold={"type": "number", "minimum": 0, "maximum": 1},
    issues=arr(PENDING),
)

SCHEMAS["test-ground-truth"]["properties"]["pending"] = arr(PENDING)
SCHEMAS["existing-extract"]["properties"]["pending"] = arr(PENDING)
SUPPLEMENT_TEST = obj(
    interaction_id=S,
    concern_key=S,
    field=NULL_S,
    scope=enum("interface", "service", "storage", "relation", "context"),
    data_location=NULL_S,
    preconditions=arr(S),
    trigger=S,
    test_data=S,
    steps=arr(S),
    expected_result=S,
    source_refs=REFS,
    executable={"type": "boolean"},
    pending_details=arr(S),
)
SCHEMAS["test-supplement"] = obj(tests=arr(SUPPLEMENT_TEST))
SCHEMAS["test-supplement"]["properties"]["pending"] = arr(PENDING)
SUPPLEMENT_TEST["properties"]["failure_rule"] = FAILURE_RULE
SUPPLEMENT_TEST["properties"]["normal_rule_id"] = NULL_S
EXCLUSION = obj(
    original_id=S, scenario_type=enum("normal", "optional", "pending"), reason=S, source_refs=REFS
)
EXCLUSION["properties"].update(interaction_id=S, object=S, concern_key=S)
SCHEMAS["pattern-applicability"]["properties"]["excluded"] = arr(EXCLUSION)
for task in (
    "test-ground-truth",
    "existing-extract",
    "exception-generate",
    "test-concerns",
    "existing-concerns",
    "concern-match",
):
    SCHEMAS[task]["properties"]["excluded"] = arr(EXCLUSION)
SCHEMAS["existing-branches"]["properties"]["excluded"] = arr(EXCLUSION)

SCHEMAS["global-scenario-compare"]["properties"]["full_matches"] = {"type": "object"}
SCHEMAS["global-scenario-compare"]["properties"]["decisions"] = {"type": "object"}
