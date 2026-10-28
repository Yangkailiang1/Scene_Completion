---
name: scene-artifact-import
description: Convert one colleague artifact section to scoped workflow data with exact citations.
---
# 同事产物接入
输入为当前文件的正向章节、文件名及可选的已抽取用例身份目录（case-catalogue）；不访问项目G、E、GT或其他文件。
先返回source_role：artifact、RR、SR、test、unknown。需求原文、测试/逆向测试文档不能伪装成同事正向产物；不属于artifact时artifacts必须为空。混合来源无法安全分离时返回unknown。
识别系统组成、API映射/参数、RR/SR或融合SSD、对象操作。返回artifacts，每项包含task、case_hint、coverage、payload、source_refs；目标字段定义见target_schemas。
只整理文件实际声明的事实，引用提供的evidence_id。测试、已有异常分支及不明材料不得变成正向产物。无可用事实返回空artifacts，并保留待归类状态。
用例归属可根据文件原编号/名称与case-catalogue中的目标和名称唯一对应，写已确认组ID；存在多个可能对应时用null，交由导入预览确认，不能猜对应组。RR/SR层级、请求/返回方向、两次实际调用分别保留。
coverage只有文件明确提供该范围的完整产物时为complete，章节分片/部分接口/缺层SSD均为partial。
payload使用本任务提供的目标JSON Schema字段；未知属性保留null或待确认，不创造方法、路径、组件、约束、调用或返回。不把Schema本身当结果。
