# Windows x64离线包

下载对应GitHub Release中的scene-completion-windows-x64.zip，完整解压至可写目录后双击start.cmd。包中自带CPython 3.12.10、已安装的Windows依赖和编译后的网页，客户无需安装Python、Node或pip，无需联网下载环境。模型权重不在包内，调用客户现有内网模型。

启动器等待本地服务就绪后打开浏览器。默认地址为http://127.0.0.1:8765，端口占用时运行`start.cmd --port 8766`。仅监听本机，不自动开放局域网端口。

在网页配置内网模型地址、实际模型名称和密钥，也可复制包根目录.env.example为.env后填写。不要把填写后的.env上传到GitHub。新项目、上传文档、审核记录和运行结果保存在包根目录data中。升级前保留原包和data，源码提交见VERSION.json。

- start.cmd：启动本地工作台，服务就绪后打开浏览器。
- check.cmd：使用包内Python检查依赖并运行离线测试，不调用付费模型。
- .env.example：空白模型配置模板。
- app/examples/tests/mall-exception-tests.xlsx：可编辑测试集示例。
- VERSION.json：源码提交、Python版本和依赖锁摘要。
- SHA256SUMS.json：包内文件摘要；ZIP的.sha256附件用于下载校验。

GitHub Windows工作流在发布前分别运行系统Python测试、包内嵌入式Python测试、中文及空格路径下的启动器、网页HTTP和Excel导入验收。仅当这些检查通过后才上传Release附件；macOS的交叉打包结果不能代替Windows原生验证。包内不含开发机.env、凭证、.workbench运行数据、虚拟环境或node_modules。
