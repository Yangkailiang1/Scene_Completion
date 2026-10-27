"""Native Windows acceptance of the exact shipped interpreter and web app."""
from pathlib import Path
import argparse,base64,hashlib,json,os,shutil,socket,subprocess,time,urllib.request


def verify_windows_dependencies(bundle,python_version='3.12.10'):
    """Read wheel metadata without importing Windows extensions on the builder."""
    from importlib import metadata
    from packaging.requirements import Requirement
    from packaging.markers import default_environment
    from packaging.utils import canonicalize_name
    site=Path(bundle)/'python/Lib/site-packages'
    distributions=list(metadata.distributions(path=[str(site)]))
    if not distributions:raise ValueError('No installed Windows dependencies')
    versions={canonicalize_name(d.metadata['Name']):d.version for d in distributions}
    env=default_environment();env.update(os_name='nt',sys_platform='win32',platform_system='Windows',platform_machine='AMD64',python_version='.'.join(python_version.split('.')[:2]),python_full_version=python_version,implementation_name='cpython',extra='')
    errors=[]
    for d in distributions:
        for raw in d.requires or []:
            req=Requirement(raw)
            if req.marker and not req.marker.evaluate(env):continue
            version=versions.get(canonicalize_name(req.name))
            if version is None or version not in req.specifier:errors.append(f'{d.metadata["Name"]} requires {req}; installed={version}')
    if errors:raise ValueError('Windows dependency closure failed: '+'; '.join(errors))
    return {'windows_distributions':len(distributions),'python':python_version,'metadata_dependencies':'passed'}


def verify_files(bundle):
    bundle=Path(bundle).resolve();manifest=json.loads((bundle/'SHA256SUMS.json').read_text(encoding='utf8'))
    assert manifest['platform']=='windows-x64' and not manifest['requires_network_install']
    for name,digest in manifest['files'].items():
        path=(bundle/name).resolve()
        if not path.is_relative_to(bundle):raise ValueError('Manifest path escapes bundle')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('File digest mismatch: '+name)
    forbidden={'.env','.git','.venv','.workbench','node_modules','model.local.json','.DS_Store','__pycache__'}
    for name in manifest['files']:
        if forbidden.intersection(Path(name).parts):raise ValueError('Private or builder-only path in distribution: '+name)
    return manifest


def smoke(bundle):
    if os.name!='nt':raise RuntimeError('Native acceptance requires Windows; cross-built files do not prove runtime success')
    bundle=Path(bundle).resolve();manifest=verify_files(bundle);verify_windows_dependencies(bundle,manifest['python'])
    # Customer paths often contain spaces and non-ASCII characters.
    work=bundle.parent/'Windows 离线验证路径'/bundle.name
    if work.exists():shutil.rmtree(work)
    shutil.copytree(bundle,work);python=work/'python/python.exe'
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    log=work.parent/'startup.log'
    with log.open('w',encoding='utf8') as stream:
        process=subprocess.Popen([str(python),'-X','utf8',str(work/'launcher.py'),'--no-browser','--port',str(port)],cwd=work,stdout=stream,stderr=subprocess.STDOUT)
        base=f'http://127.0.0.1:{port}'
        def request(path,body=None):
            data=json.dumps(body).encode() if body is not None else None
            req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=10) as response:return response.read()
        try:
            deadline=time.monotonic()+60
            while True:
                if process.poll() is not None:raise RuntimeError('Launcher failed: '+log.read_text(encoding='utf8'))
                try:request('/api/projects');break
                except OSError:
                    if time.monotonic()>deadline:raise RuntimeError('Web app did not become ready')
                    time.sleep(.25)
            assert b'<html' in request('/').lower()
            template=request('/api/test-sources/template')
            expected=(work/'app/examples/tests/mall-exception-tests.xlsx').read_bytes()
            assert template==expected,'Excel template must be shipped intact'
            test={'name':'mall.xlsx','content_base64':base64.b64encode(template).decode()}
            preview=json.loads(request('/api/test-sources/preview',{'sources':[test]}))
            assert preview['valid'] and preview['counts']['exception']>0 and preview['counts']['pending']>0
            meta=json.loads(request('/api/projects',{'name':'Windows原生离线启动验收','sources':{'RR':[{'name':'rr.md','content':'# RR\n离线测试'}],'SR':[{'name':'sr.md','content':'# SR\n离线测试'}],'test':[test]}}))
            view=json.loads(request('/api/projects/'+meta['id']+'/test-sources'))
            assert view['preview']['counts']==preview['counts']
            print(json.dumps({'native_windows':True,'source_commit':manifest['source_commit'],'python':manifest['python'],'manifest_files':len(manifest['files']),'unicode_space_path':True,'launcher_and_http':'passed','xlsx_preview_and_project':'passed','model_calls':0},ensure_ascii=False),flush=True)
        finally:
            # Only the acceptance process and its child server are terminated.
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            process.wait(timeout=15)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle');args=parser.parse_args();smoke(args.bundle)
