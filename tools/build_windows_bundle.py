"""Build a self-contained Windows x64 distribution from a pinned wheel set.

Can run on macOS/Linux. Uses CPython's Windows embeddable runtime and only
win_amd64 / universal wheels; never copies the builder's virtualenv.
"""
from pathlib import Path
import argparse,subprocess,sys,urllib.request,zipfile,hashlib,json,shutil
PYTHON_VERSION='3.12.10'
ROOT=Path(__file__).resolve().parents[1]

def download(url,path):
    if not path.exists():
        request=urllib.request.Request(url,headers={'User-Agent':'scene-offline-builder/1.0'})
        with urllib.request.urlopen(request,timeout=90) as r,path.open('wb') as f:shutil.copyfileobj(r,f)

def build(output):
    output=Path(output).resolve();cache=output/'cache';cache.mkdir(parents=True,exist_ok=True)
    wheels=cache/'windows-wheels';wheels.mkdir(exist_ok=True)
    lock=ROOT/'requirements-windows.lock'
    subprocess.run([sys.executable,'-m','pip','download','--index-url','https://pypi.org/simple','--dest',str(wheels),'--platform','win_amd64','--python-version','312','--implementation','cp','--abi','cp312','--abi','abi3','--only-binary=:all:','-r',str(lock)],check=True)
    runtime=cache/f'python-{PYTHON_VERSION}-embed-amd64.zip'
    download(f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip',runtime)
    stage=output/'scene-completion-windows-x64'
    if stage.exists():shutil.rmtree(stage)
    (stage/'python').mkdir(parents=True);(stage/'app').mkdir()
    with zipfile.ZipFile(runtime) as z:z.extractall(stage/'python')
    site=stage/'python/Lib/site-packages'
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--find-links',str(wheels),'--only-binary=:all:','--platform','win_amd64','--python-version','312','--implementation','cp','--abi','cp312','--abi','abi3','--no-compile','--no-deps','--target',str(site),'-r',str(lock)],check=True)
    (stage/'python/python312._pth').write_text('python312.zip\n.\nLib/site-packages\nimport site\n',encoding='utf8')
    if not (ROOT/'web/assets').is_dir() or not (ROOT/'web/third-party-licenses.txt').is_file():
        raise RuntimeError('Build frontend first: npm ci --prefix frontend && npm run build --prefix frontend')
    # Deliberately allow-list runtime sources. No local configuration, original
    # customer documents, caches or Git history enter the distributable.
    for name in ('.cac','web','docs','tests','examples'):
        shutil.copytree(ROOT/name,stage/'app'/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.local.json','.env','scene_completion_output'))
    for name in ('serve.py','README.md','requirements-windows.lock','workflow.config.example.json','requirements.txt','requirements-dev.txt','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name,stage/'app'/name)
    for name in ('start.cmd','check.cmd'):
        shutil.copy2(ROOT/'deployment'/name,stage/name)
    (stage/'使用说明.txt').write_text('解压整个目录。双击start.cmd，浏览器访问 http://127.0.0.1:8765 。无需联网安装Python或依赖。\n在界面配置内网API及客户实际模型标识。业务文档、密钥及运行结果只存本地。\n首次可运行check.cmd检查依赖与离线测试。项目结果通过界面导出。\n',encoding='utf8')
    manifest={'platform':'windows-x64','python':PYTHON_VERSION,'requires_network_install':False,'files':{}}
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
    p=argparse.ArgumentParser();p.add_argument('--output-dir',default=str(ROOT/'dist'));args=p.parse_args();build(args.output_dir)
