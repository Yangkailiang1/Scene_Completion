---
name: scene-composition-render
description: 将已验证系统组成JSON绘制为分区式参与关系图，保留用例椭圆、Actor小人和节点来源。
---

# 系统组成绘图
读取components任务的JSON结果，使用composition_drawing.render_composition或CLI render-composition导出SVG与layout.json。布局沿用历史scene-assemble的分区参与关系设计：人类Actor、UI/前端、系统内部用例及服务、外部系统，下方展示资源及明确的设备部署信息。只画输入已有节点和有证据关系，不恢复旧CRUD依赖推导、部署推断或自动前端映射。用例保持椭圆，人类Actor旁有小人；SVG中文字和图形可编辑。抽取与绘图是两个职责，重绘不会调用模型。
