# 示例输入与离线重建

`online_shopping_seed.json`提供商城的用例定位及系统身份种子，配合项目根目录的RR、SR和测试spec运行 `scene-pipeline`。替换项目时使用自己的用例编号、来源定位与原始材料；不要把旧样例异常作为新项目的生成输入。

[agent_workflow_smoke](agent_workflow_smoke/README.md)提供Agent流程结果快照，可无模型调用重建报告、图和Excel。

其他模型及演示目录是旧协议的兼容资料。旧命令使用 `--protocol legacy`，不要混用旧生成路径与当前RR/SR输入协议。兼容重建脚本为 `verify_demo.py`和 `verify_online_shopping.py`。

全流程配置、续跑及检查命令见[项目README](../README.md)。
