"""Build a self-contained Windows x64 distribution from a pinned wheel set.

Can run on macOS/Linux. Uses CPython's Windows embeddable runtime and only
win_amd64 / universal wheels; never copies the builder's virtualenv.
"""
from pathlib import Path
import argparse,subprocess,sys,urllib.request,zipfile,hashlib,json,shutil
from datetime import datetime,timezone
PYTHON_VERSION='3.12.10'
ROOT=Path(__file__).resolve().parents[1]

def download(url,path):
    if not path.exists():
        request=urllib.request.Request(url,headers={'User-Agent':'scene-offline-builder/1.0'})
        with urllib.request.urlopen(request,timeout=90) as r,path.open('wb') as f:shutil.copyfileobj(r,f)

def build(output,offline=False):
    output=Path(output).resolve();cache=output/'cache';cache.mkdir(parents=True,exist_ok=True)
    wheels=cache/'windows-wheels';wheels.mkdir(exist_ok=True)
    lock=ROOT/'requirements-windows.lock'
    source=['--no-index','--find-links',str(wheels)] if offline else ['--index-url','https://pypi.org/simple']
    subprocess.run([sys.executable,'-m','pip','download',*source,'--dest',str(wheels),'--platform','win_amd64','--python-version','312','--implementation','cp','--abi','cp312','--abi','abi3','--only-binary=:all:','-r',str(lock)],check=True)
    runtime=cache/f'python-{PYTHON_VERSION}-embed-amd64.zip'
    if offline and not runtime.is_file():raise RuntimeError('Offline build requires the cached Windows embeddable Python ZIP')
    download(f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip',runtime)
    stage=output/'scene-completion-windows-x64'
    if stage.exists():shutil.rmtree(stage)
    (stage/'python').mkdir(parents=True);(stage/'app').mkdir()
    with zipfile.ZipFile(runtime) as z:z.extractall(stage/'python')
    site=stage/'python/Lib/site-packages'
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--find-links',str(wheels),'--only-binary=:all:','--platform','win_amd64','--python-version','312','--implementation','cp','--abi','cp312','--abi','abi3','--no-compile','--no-deps','--target',str(site),'-r',str(lock)],check=True)
    from check_windows_bundle import verify_windows_dependencies
    verify_windows_dependencies(stage,PYTHON_VERSION)
    (stage/'python/python312._pth').write_text('python312.zip\n.\nLib/site-packages\nimport site\n',encoding='utf8')
    if not (ROOT/'web/assets').is_dir() or not (ROOT/'web/third-party-licenses.txt').is_file():
        raise RuntimeError('Build frontend first: npm ci --prefix frontend && npm run build --prefix frontend')
    # Deliberately allow-list runtime sources. No local configuration, original
    # customer documents, caches or Git history enter the distributable.
    for name in ('.cac','web','docs','tests','examples','tools','deployment'):
        shutil.copytree(ROOT/name,stage/'app'/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.local.json','.env','.DS_Store','scene_completion_output'))
    for name in ('serve.py','scene.py','README.md','pytest.ini','requirements-windows.lock','workflow.config.example.json','requirements.txt','requirements-dev.txt','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,stage/'app'/name)
    shutil.copy2(ROOT/'deployment/launcher.py',stage/'launcher.py')
    shutil.copy2(ROOT/'deployment/env.example',stage/'.env.example')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    version={'source_commit':commit,'platform':'windows-x64','python':PYTHON_VERSION,'built_at':datetime.now(timezone.utc).isoformat(),'dependency_lock_sha256':hashlib.sha256(lock.read_bytes()).hexdigest(),'requires_node':False,'requires_network_install':False}
    (stage/'VERSION.json').write_text(json.dumps(version,indent=2)+'\n',encoding='utf8')
    for name in ('start.cmd','status.cmd','stop.cmd','check.cmd','scene.cmd'):
        shutil.copy2(ROOT/'deployment'/name,stage/name)
    (stage/'使用说明.txt').write_text('解压整个目录。双击start.cmd，浏览器访问 http://127.0.0.1:8765 。无需联网安装Python或依赖。start.cmd后台启动；status.cmd查看状态；stop.cmd停止。关闭浏览器或启动窗口不停止服务。\n在界面配置内网API及客户实际模型标识，也可复制根目录.env.example为.env后填写。业务文档、密钥及运行结果只存本地data目录。\n支持Windows 10/11 x64，不需要安装Node、Python或pip。请不要在ZIP预览窗口中直接运行。\nExcel测试示例在app/examples/tests/mall-exception-tests.xlsx。\n首次可运行check.cmd检查依赖与离线测试。项目结果通过界面导出。\n',encoding='utf8')
    manifest={**version,'files':{}}
    for f in stage.rglob('*'):
        if f.is_file():manifest['files'][str(f.relative_to(stage)).replace('\\','/')]=hashlib.sha256(f.read_bytes()).hexdigest()
    (stage/'SHA256SUMS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    target=output/'scene-completion-windows-x64.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in stage.rglob('*'):
            if f.is_file():z.write(f,str(Path(stage.name)/f.relative_to(stage)))
    (output/(target.name+'.sha256')).write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
    print(target)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',default=str(ROOT/'dist'));p.add_argument('--offline',action='store_true',help='Use cached Windows wheels and Python runtime only; fail if anything is missing');args=p.parse_args();build(args.output_dir,offline=args.offline)
