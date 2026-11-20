"""Render the structured-input workflow document from workflow/ssd_stages.py.

The document is generated, never hand-written: hand-maintained flow docs go stale,
which is exactly how the superseded project-scope stages kept appearing as current
behaviour. ``--check`` fails when the committed file no longer matches the code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TARGET = ROOT / "docs/current/structured-input-workflow.md"

HEADER = """# 结构化输入工作流（自动生成）

本文件由 `tools/render_workflow_doc.py` 从 `src/scene_completion/workflow/ssd_stages.py`
生成，请勿手工编辑。改动阶段说明请改代码后运行：

```sh
python tools/render_workflow_doc.py
```

`make check` 会校验本文件与代码一致。触发条件与分支判定见
[SSD工作流与审核](ssd-case-workflow.md)，语义提示词见 `domain/ssd_contracts.py`。

## 触发条件

结构化输入分支在 `workflow/planning.py::build_pipeline()` 中判定：`workflow_mode`
为 `ssd`（默认），且 `input_directory()` 返回目录，且 `build_structured()` 在该目录下
至少找到一个 `SysOperation.json`。三者任一不满足，不会报错，而是继续走文档抽取分支。

## 单个用例的推进顺序

```
{sequence}
```

用例之间并行。每个用例完成比较后触发对应的共用服务合并节点。
"""

FOOTER = """
## 阶段来源

- 阶段定义与顺序：`src/scene_completion/workflow/ssd_stages.py`
- 执行装配见 `src/scene_completion/workflow/ssd/pipeline.py`
- 按阶段阅读代码及输入映射见[架构与代码导览](../architecture/code-guide.md#按顺序阅读-ssd)
- 模型提示词与输出 Schema：`src/scene_completion/domain/ssd_contracts.py`
- 缓存用的语义版本：`src/scene_completion/workflow/task_semantics.json`
"""


def render():
    """Build the document text from the stage declarations."""
    from scene_completion.workflow.ssd_stages import CASE_SEQUENCE, KIND_LABELS, MERGE_STAGE, STAGES

    sequence = " → ".join(CASE_SEQUENCE)
    lines = [HEADER.format(sequence=sequence)]
    lines.append("## 阶段总表\n")
    lines.append("| 阶段 | 页面标签 | 类型 | 对应语义任务 | 依赖 |")
    lines.append("|---|---|---|---|---|")
    for name, stage in STAGES.items():
        tasks = "、".join(stage.semantic_tasks) or "—"
        deps = "、".join(stage.depends_on) or "（起点）"
        lines.append(f"| `{name}` | {stage.label} | {KIND_LABELS[stage.kind]} | {tasks} | {deps} |")
    lines.append("")
    lines.append("## 逐阶段说明\n")
    for name, stage in STAGES.items():
        lines.append(f"### `{name}` · {stage.label}\n")
        lines.append(f"- **类型**：{KIND_LABELS[stage.kind]}")
        lines.append(f"- **读取**：{'；'.join(stage.reads)}")
        lines.append(f"- **产出**：{'；'.join(stage.writes)}")
        semantic = "、".join(stage.semantic_tasks) or "不调用模型"
        lines.append(f"- **语义任务**：{semantic}")
        deps = "、".join(stage.depends_on) or "无（用例起点）"
        lines.append(f"- **依赖**：{deps}")
        lines.append(f"\n{stage.doc}\n")
    lines.append(f"> 合并阶段 `{MERGE_STAGE}` 依赖对应的用例比较节点。")
    lines.append(FOOTER)
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="只校验已提交文件与代码一致，不写入",
    )
    args = parser.parse_args()
    text = render()
    if args.check:
        if not TARGET.exists():
            print(f"缺少生成文档：{TARGET.relative_to(ROOT)}", file=sys.stderr)
            return 1
        current = TARGET.read_text(encoding="utf8")
        if current != text:
            print(
                "结构化输入工作流文档已过期，请运行 python tools/render_workflow_doc.py",
                file=sys.stderr,
            )
            return 1
        print("结构化输入工作流文档与代码一致")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text, encoding="utf8")
    print(f"已生成 {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
