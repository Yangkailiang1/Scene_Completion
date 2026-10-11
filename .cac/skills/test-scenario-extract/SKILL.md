---
name: test-scenario-extract
description: 将 test_spec.md 中有来源的测试场景解析为稳定 ID 的结构化参考测试集。
title: Test Scenario Extract
version: 2.0.0
---

# Test Scenario Extract

RR/SR 协议中的 interaction-test-conditions 在 G、C 和推荐集合固定后，独立读取测试 spec 的每个原始条目，提取其中实际异常条件；不得读取 G、C 或用已有推荐反推测试异常。此阶段供全部待推荐异常的采纳评估，测试不区分RR/SR，不改变生成、系统/设计覆盖匹配、漏报率或推荐集合。

保留每个原始测试 ID、类型和来源。正常条目及普通可选成功流程返回 conditions=[]；标为可选的条目若明确描述重复请求、失败或非法输入，可提取对应异常。不同对象/失败机制/触发条件拆成原子记录。原文明示条件保留直接依据；泛指异常允许按既有框架展开可能原因，必须标为推导测试单元并说明依据，不能从正常操作臆测异常。测试中的响应、错误码与恢复不参与异常识别。

use_case_id 必须来自该测试条目的明确需求关联，保留 API/业务操作定位；不假定 RR/SR 编号一一对应。每个测试 ID 均须返回，条件引用只能落在对应条目，requirement_layer=TEST表示独立测试来源，不是SR或RR层级。工具保留原始标签，由interaction-adoption以test_all对全部待推荐异常×全部测试异常条件逐对比较，不按RR/SR或用例编号筛掉候选对；不同业务对象、操作、机制或矛盾条件判未匹配。推荐先沿真实RR/SR映射语义去重为交互关注点异常单元；测试按同一粒度独立拆分。每个单元仅一个concern_key、具体interaction_location及原始条件引句；不同可能因果关注点拆为多条。用户允许对泛指异常按框架展开可能原因，source_basis=framework_derived，保存derivation_reason；明确原因使用explicit。普通正常条目不能推导异常。完整逐对语义判断后工具一一分配，采纳分母为去重推荐单元数，分子为已分配推荐单元数；原文明示与框架推导贡献分列，零分母null。普通正常操作相同不能算重合。

当前编排工具实际加载本 Skill 文本，并将测试解析器版本及原始条目纳入输入哈希。下述 extract-test-scenarios/validate-test-scenarios 为兼容的结构化解析接口，不自动产生本协议的异常识别或采纳结论。

## 历史兼容：结构化测试记录

旧接口仅负责读取 `test_spec.md` 并将每条测试场景解析到 `reference_test_scenarios.json`；不得修改生成侧 `test_scenarios.json`。保持测试场景编号、用例/需求/API 关联、场景类型、前置条件、触发条件、目标、预期结果和来源定位。缺字段或重复 ID 时显式失败，不推断缺失测试行为。

使用 `python .cac/tools/scene_completion.py extract-test-scenarios --input test_spec.md --output reference_test_scenarios.json`，再运行 `validate-test-scenarios`。格式见 `references/format.md`。本 Skill 不调用其他 Skill。

用户进一步确认：同一实际原因跨RR/SR只有关注点编码/分析视角不同，仍合并一个推荐因果单元并保留全部原始关注点标签；不同实际原因才拆分。测试每个拆分单元有一个因果关注点，匹配按具体原因，不能以标签相等替代机制判断，也不能仅因标签不同拒绝同一原因。
