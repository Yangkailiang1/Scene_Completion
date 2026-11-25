"""Structured-input SSD workflow: the single readable source of stage knowledge.

Every stage the structured-input path (``build_structured``) registers is described
here once, so the page labels, the generated user documentation and the stage list
cannot drift apart. Changing a label or a stage's behaviour starts in this file.

Where the other halves live:

- execution order and wiring: ``workflow/ssd/pipeline.py``
- what the model is told for each semantic task, and the output schema:
  ``domain/ssd_contracts.py`` (``SCHEMAS`` / ``ROLE_TEXT``)
- semantic version used for cache identity: ``workflow/task_semantics.json``

This module is documentation-grade metadata only. It never changes a stage name,
a task key, an output path or a semantic version; those stay in their own files.
"""

from __future__ import annotations

# Kinds are deliberately coarse: readers need to know whether a stage spends
# money and whether it can be reproduced deterministically.
SCRIPT = "script"
MODEL = "model"
MODEL_SCRIPT = "model+script"

KIND_LABELS = {
    SCRIPT: "脚本（不调用模型）",
    MODEL: "模型调用",
    MODEL_SCRIPT: "模型调用＋脚本合并",
}


class Stage(dict):
    """A stage description; a plain dict with attribute access for readability."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


def _stage(
    label,
    kind,
    reads,
    writes,
    semantic_tasks,
    depends_on,
    doc,
    *,
    compatible_tasks=(),
    user_visible=True,
):
    return Stage(
        label=label,
        kind=kind,
        kind_label=KIND_LABELS[kind],
        reads=tuple(reads),
        writes=tuple(writes),
        semantic_tasks=tuple(semantic_tasks) + tuple(compatible_tasks),
        default_tasks=tuple(semantic_tasks),
        compatible_tasks=tuple(compatible_tasks),
        depends_on=tuple(depends_on),
        doc=doc,
        user_visible=user_visible,
    )


STAGES = {
    "ssd-prepare": _stage(
        label="建立 SSD 与三方结果",
        kind=SCRIPT,
        reads=("冻结的核心分件或 SysOperation 与配套材料", "关注点注册表"),
        writes=("用例 steps（发送方·接收方·操作·数据）", "G 通道关注点与参考场景", "初始发布版本"),
        semantic_tasks=(),
        depends_on=(),
        doc=(
            "从结构化输入确定性构建步骤与三方结果容器，挂载注册表规则与固定参考"
            "异常模板，生成 G 通道，并发布本用例的第一个版本。"
        ),
    ),
    "ssd-resolve": _stage(
        label="参与者与操作判定、约束挂载与独立识别",
        kind=MODEL,
        reads=("正向主成功事件流、功能树实体约束", "E/GT 各自的原始记录"),
        writes=("操作单元、CRUD、字段与实体约束挂载", "E/GT 各自的来源分类与待定位部分"),
        semantic_tasks=(
            "ssd-participant-classify",
            "ssd-operation-units",
            "ssd-create-path-roles",
            "ssd-entity-inference",
            "ssd-evidence-classify",
        ),
        compatible_tasks=(
            "ssd-entity-classify",
            "ssd-command-classify",
            "ssd-bind",
            "ssd-resolve",
        ),
        depends_on=("ssd-prepare",),
        doc=(
            "先结合参与者声明和原文引文确认角色。默认命令模式接着判操作单元和 CRUD，"
            "再处理未能确定性解析的约束，由脚本建立 G 挂载。"
            "E、GT 分别按本方证据分类，在 compare 才对齐最终 G。旧输入按配置使用其他分类或绑定任务。"
        ),
    ),
    "ssd-generate": _stage(
        label="展开参考异常与业务场景",
        kind=MODEL,
        reads=("G 通道的固定模板场景", "正向用例、步骤、对象、接口、实体"),
        writes=("每个场景的业务分析", "模型补充的适用场景"),
        semantic_tasks=("ssd-generate",),
        depends_on=("ssd-resolve",),
        doc=(
            "只针对 G 通道写业务化分析，可补充同一关注点下明确适用且不重复的场景。"
            "固定模板全部保留；模型看不到 E 与 GT，不从它们补写答案。"
        ),
    ),
    "ssd-compare": _stage(
        label="三方比较与发布",
        kind=MODEL_SCRIPT,
        reads=("最终 G 与 E、GT 各自的来源分类", "候选对、历史判定与人工修订"),
        writes=("逐 G 义务的确认覆盖及独立挂载", "发布基线与有效修订"),
        semantic_tasks=("ssd-ground-align", "ssd-semantic-compare"),
        depends_on=("ssd-generate",),
        doc=(
            "新版命令模式按最终G分别对齐E与GT，无法对应G的异常再按来源独立挂载。"
            "复用未变化的机器判定，再对候选对分批判定。当前口径记录 full/none，旧口径保留 partial。"
            "发布机器基线；若检测到人工修订，再独立复核一次。被任一 GT 确认的 G "
            "计为已覆盖。"
        ),
    ),
    "shared-services-merge": _stage(
        label="合并共用外部服务（脚本）",
        kind=SCRIPT,
        reads=("全部用例的最新修订", "实际外部调用的接收方"),
        writes=("shared_service_results/", "共用服务三方结果与项目指标"),
        semantic_tasks=(),
        depends_on=("ssd-compare",),
        doc=(
            "按实际外部请求的接收方识别服务身份，再按故障类型合并场景，保留每个"
            "调用成员的原记录与出处。服务身份无法确认时保留待定位，不按同名强合并。"
        ),
    ),
}

# The order a single case advances through; each case unlocks its own shared-service merge.
CASE_SEQUENCE = ("ssd-prepare", "ssd-resolve", "ssd-generate", "ssd-compare")
MERGE_STAGE = "shared-services-merge"


def label(stage):
    """Display label for a stage, falling back to the raw name when unknown."""
    description = STAGES.get(stage)
    return description.label if description else stage


def describe(stage):
    return STAGES[stage]


def case_stages():
    return tuple(name for name in CASE_SEQUENCE if STAGES[name].user_visible)


def all_stage_names():
    return tuple(STAGES)
