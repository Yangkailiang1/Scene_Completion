"""Versioned reference failure variants, independent of documents and models.

These are reviewable failure conditions, not claims about an undocumented HTTP
code, token format, timeout or recovery implementation. Concrete field limits
are instantiated by deterministic rules from the actual positive contract.
"""

from copy import deepcopy

from scene_completion.domain.ssd import llm_responses

TEMPLATE_VERSION = "three-scope-reference-v1"

_AUTHENTICATION = [
    ("missing_credential", "无凭证访问", "调用时未提供身份凭证", "拒绝未认证调用"),
    ("malformed_credential", "无效格式凭证", "身份凭证格式不符合认证协议", "拒绝格式无效的凭证"),
    ("empty_credential", "空凭证访问", "已提供凭证字段但其内容为空", "拒绝空凭证"),
    ("invalid_token", "Token 无效", "Token 格式有效但身份认证校验不通过", "拒绝无效 Token"),
    ("expired_token", "Token 过期", "Token 已过期", "拒绝过期 Token"),
]
_AUTHORIZATION = [
    ("horizontal_escalation", "水平越权", "调用方访问属于其他用户或隔离域的资源", "拒绝越权访问"),
    ("vertical_escalation", "垂直越权", "调用方执行超出其角色权限的操作", "拒绝越权操作"),
]

_VARIANTS = {
    "human.authentication": _AUTHENTICATION,
    "service_relation.authentication": _AUTHENTICATION,
    "human.authorization": _AUTHORIZATION,
    "service_relation.authorization": _AUTHORIZATION,
    "api.data.completeness": [
        (
            "missing_required",
            "必填数据缺失",
            "必填数据未提供",
            "拒绝不完整的输入或识别不完整的返回",
        ),
        ("empty_body", "请求体为空", "要求请求体的调用未提供请求体内容", "拒绝空请求体"),
    ],
    "api.data.type": [("wrong_type", "数据类型不符", "字段类型与接口定义不符", "识别类型不匹配")],
    "api.data.format": [
        ("invalid_format", "数据格式不符", "字段不满足声明的格式规范", "识别格式不匹配")
    ],
    "api.data.length": [
        ("invalid_length", "数据长度越界", "字段长度超出声明的范围", "识别长度越界")
    ],
    "api.data.size": [
        ("oversized_payload", "数据大小超限", "文件或请求体超过声明的大小限制", "识别大小超限")
    ],
    "api.data.range": [
        ("outside_range", "数据范围越界", "字段超出声明的范围或允许枚举", "识别范围越界")
    ],
    "api.data.validity": [
        ("missing_reference", "引用资源不存在", "输入字段引用的业务资源不存在", "拒绝无效资源引用"),
        (
            "deleted_reference",
            "引用资源已删除",
            "输入字段仍引用已删除的业务资源",
            "拒绝失效资源引用",
        ),
    ],
    "service.business_attribute_constraint": [
        (
            "duplicate_value",
            "字段唯一约束",
            "字段值违反所属业务范围内的唯一约束",
            "拒绝冲突的业务变更",
        ),
        (
            "immutable_attribute",
            "字段不可修改",
            "操作改变了不允许修改的实体属性",
            "拒绝不允许的属性变更",
        ),
        (
            "attribute_combination",
            "字段组合约束",
            "实体属性组合违反业务规则",
            "拒绝不满足规则的业务变更",
        ),
    ],
    "service.query_retrieval.resource_existence": [
        (
            "missing_resource",
            "资源不存在",
            "查询指定的业务资源不存在",
            "按接口约定处理不存在的资源",
        ),
    ],
    "service.query_retrieval.data_visibility": [
        (
            "invisible_resource",
            "数据不可见",
            "查询返回了当前调用方不可见的数据",
            "返回结果遵守当前调用方的数据可见范围",
        ),
    ],
    "service.display_interaction.display_correctness": [
        ("truncated_content", "内容截断", "界面内容被错误截断", "按显示要求完整呈现内容"),
        (
            "incorrect_effect",
            "显示效果错误",
            "界面效果或呈现结果与显示要求不符",
            "按显示要求正确呈现",
        ),
    ],
    "service.display_interaction.device_adaptation": [
        (
            "orientation_layout",
            "设备布局异常",
            "设备或横竖屏变化导致布局错乱",
            "保持适用设备下的正确布局",
        ),
    ],
    "service.analysis_generation.execution_deadline": [
        (
            "execution_timeout",
            "执行超时",
            "分析或生成操作未在适用的执行时限内完成",
            "按执行时限要求处理超时",
        ),
    ],
    "service.release_activation.prerequisite": [
        (
            "incomplete_configuration",
            "发布前置条件不满足",
            "发布所需配置或业务前置条件不完整",
            "阻止不满足前置条件的发布",
        ),
    ],
    "service.release_activation.result_consistency": [
        (
            "stale_release",
            "发布结果未更新",
            "配置变更后生效内容仍为旧版本",
            "生效内容与应发布的配置保持一致",
        ),
    ],
    "service.release_activation.failure_recovery": [
        (
            "partial_release_remains",
            "发布失败残留",
            "发布失败后遗留部分生效配置",
            "失败后恢复到约定的一致状态",
        ),
    ],
    "database.uniqueness": [
        (
            "unique_conflict",
            "名称或唯一键冲突",
            "同一唯一约束范围内写入重复名称或唯一键",
            "保持数据库唯一约束",
        ),
    ],
    "database.referential_integrity": [
        (
            "orphaned_child",
            "关联对象残留",
            "父对象删除后子对象关联残留或失效",
            "保持声明的关联完整性",
        ),
    ],
    "database.query_performance": [
        ("query_timeout", "查询超时", "数据库查询未满足适用的查询时限", "按性能要求处理超时"),
    ],
    "database.special_characters": [
        (
            "sql_injection",
            "SQL 注入",
            "数据中的 SQL 片段被错误当作可执行语句",
            "数据内容不得改变数据库执行语义",
        ),
        (
            "html_injection",
            "HTML 注入",
            "存储的 HTML 内容在后续处理中被错误解释执行",
            "按约定安全处理 HTML 内容",
        ),
        (
            "wide_characters",
            "宽字符处理异常",
            "宽字符在存储或查询中被错误处理",
            "按字段约定保留并处理宽字符",
        ),
        (
            "emoji_characters",
            "emoji 处理异常",
            "emoji 在存储或查询中被错误处理",
            "按字段约定保留并处理 emoji",
        ),
    ],
    "database.storage_validity": [
        (
            "stored_missing_field",
            "存量记录缺字段",
            "存量记录缺少存储模型要求的字段",
            "识别并按约定处理不完整记录",
        ),
        (
            "stored_invalid_content",
            "存量内容不符",
            "存量记录内容不满足存储模型要求",
            "识别并按约定处理无效记录",
        ),
    ],
    llm_responses.KEY: [
        (
            llm_responses.GENERIC,
            "响应无法解析",
            "外部大模型返回的响应无法解析",
            "按约定处理解析失败，避免将无法解析的响应作为成功结果使用",
        ),
        (
            llm_responses.JSON,
            "响应 JSON 解析失败",
            "外部大模型返回的响应不符合约定的 JSON 语法，无法解析",
            "按约定处理无效响应，避免使用解析失败的数据",
        ),
        (
            llm_responses.REQUIRED,
            "响应缺少必填字段",
            "外部大模型响应缺少响应契约规定的必填字段",
            "按约定处理不完整的响应，避免使用缺少必填字段的数据",
        ),
    ],
    "llm.grounding": [
        (
            "fabricated_fact",
            "幻觉或事实错误",
            "生成了与给定事实依据不符的内容",
            "输出遵循给定事实依据",
        ),
        (
            "task_semantic_mismatch",
            "任务语义不符",
            "生成结果不符合本次任务要求",
            "生成符合任务语义的结果",
        ),
    ],
    "llm.instruction_following": [
        ("ignored_constraint", "忽略任务约束", "生成过程忽略了任务中明确的约束", "遵守任务约束"),
        ("omitted_step", "遗漏必要步骤", "生成过程遗漏任务要求的必要步骤", "完成必要步骤"),
        ("wrong_task", "执行不符任务", "执行了与明确指令不符的任务", "遵循任务指令"),
    ],
    "llm.prompt_security": [
        (
            "prompt_injection",
            "提示词注入",
            "输入中的指令企图改变可信任务指令",
            "不将不可信输入提升为控制指令",
        ),
        (
            "instruction_escalation",
            "指令越权",
            "输入诱导模型执行超出授权范围的操作",
            "保持任务授权边界",
        ),
        (
            "system_prompt_leak",
            "系统提示词泄露",
            "输入诱导模型泄露系统提示词或内部信息",
            "不泄露受保护的内部信息",
        ),
    ],
    "llm.context_sufficiency": [
        ("context_limit", "上下文超限", "任务上下文超过可用容量", "按约定处理上下文容量限制"),
        ("truncated_context", "上下文截断", "任务所需内容在传递时被截断", "保持任务所需上下文完整"),
        ("lost_history", "历史信息丢失", "关键历史要求在后续处理时丢失", "保留任务所需历史信息"),
    ],
    "llm.output_stability": [
        (
            "inconsistent_repetition",
            "相同条件结果不一致",
            "相同输入及条件产生互相不一致的结果",
            "满足约定的重复执行稳定性",
        ),
        (
            "changed_judgment",
            "关键判断变化",
            "相同依据下关键判断发生矛盾变化",
            "关键判断保持约定的一致性",
        ),
    ],
    "service_relation.data_isolation": [
        (
            "cross_service_data",
            "跨服务数据隔离",
            "不同 service-id 或隔离域的业务链路访问了彼此的数据",
            "保持链路各环节的数据隔离",
        ),
    ],
    "global.dependency_consistency": [
        (
            "one_sided_success",
            "链路部分成功",
            "业务链路一侧成功而关联侧失败",
            "保持关联操作结果一致",
        ),
        (
            "stale_dependency",
            "链路版本不一致",
            "上游修改成功而下游仍保留旧版本",
            "保持关联数据版本一致",
        ),
    ],
    "global.call_order": [
        (
            "unfinished_prerequisite",
            "前置未完成",
            "前置操作未完成就执行后续操作",
            "先满足声明的前置操作条件",
        ),
        (
            "reversed_order",
            "调用顺序颠倒",
            "实际调用颠倒了声明的业务依赖顺序",
            "遵循声明的依赖顺序",
        ),
    ],
    "global.cascade_operation": [
        ("missed_cascade", "级联漏操作", "主操作完成后遗漏应级联的对象操作", "完成声明的级联义务"),
        (
            "wrong_cascade",
            "级联误操作",
            "级联操作影响了不应处理的对象",
            "只处理声明范围内的关联对象",
        ),
        ("failed_cascade", "级联失败", "应执行的级联操作未成功完成", "按约定处理级联失败"),
    ],
    "service.base.availability": [
        (
            "service_unavailable",
            "外部服务不可用",
            "依赖的外部服务不可达或无法提供服务",
            "识别并按约定处理外部服务不可用",
        ),
    ],
}

for _operation, _label in (("create", "创建"), ("update", "更新"), ("delete", "删除")):
    _VARIANTS[f"service.crud.{_operation}.concurrency_consistency"] = [
        (
            "concurrent_conflict",
            "并发操作冲突",
            f"并发{_label}导致业务对象结果冲突",
            "保持并发执行的一致性",
        ),
        (
            "concurrent_deletion",
            "并发删除冲突",
            f"{_label}过程中关联业务资源被并发删除",
            "按约定处理并发删除冲突",
        ),
    ]
    _VARIANTS[f"service.crud.{_operation}.idempotency"] = [
        (
            "repeated_effect",
            "重复请求异常",
            f"相同业务{_label}请求重复执行产生额外业务影响",
            "重复执行不产生额外业务影响",
        ),
    ]
    _VARIANTS[f"service.crud.{_operation}.resource_existence"] = [
        (
            "missing_resource",
            "对象资源不存在",
            f"{_label}所依赖或操作的业务资源不存在",
            "按约定处理不存在的业务资源",
        ),
    ]


def scenario_metadata(key, variant_id="derived_constraint", origin="deterministic_constraint"):
    return {
        "template_id": f"{key}:{variant_id}",
        "variant_id": variant_id,
        "template_version": TEMPLATE_VERSION,
        "generation_origin": origin,
    }


def templates_for(key):
    return [
        {
            **scenario_metadata(key, variant, "reference_template"),
            "label": label,
            "condition": condition,
            "expected": expected,
        }
        for variant, label, condition, expected in deepcopy(_VARIANTS.get(key, []))
    ]


def reference_catalog():
    return {"version": TEMPLATE_VERSION, "by_key": {key: templates_for(key) for key in _VARIANTS}}
