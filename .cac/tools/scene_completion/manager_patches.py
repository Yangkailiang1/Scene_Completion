"""Isolated code proposals, frozen baseline tests and transactional activation."""
from pathlib import Path
import difflib,shutil,subprocess,sys,os,time,json
from .storage import read_json,write_json,fingerprint
from .manager_store import Journal

PROTECTED={'storage.py','token_budget.py','model_accounts.py','endpoint_admission.py','manager_patches.py','manager_store.py','manager_agent.py','manager_runtime.py','manager_api.py','manager_restart.py','worker_runtime.py'}

def allowed_program(root,path):
 root=Path(root).resolve();target=(root/path).resolve()
 if not target.is_relative_to(root) or target.is_symlink():raise ValueError('路径越出本工具')
 relative=target.relative_to(root).as_posix()
 if target.name in PROTECTED or not (relative.startswith('.cac/tools/scene_completion/') and target.suffix=='.py' or relative in {'serve.py','scene.py'} or relative.startswith('frontend/src/') and target.suffix in {'.ts','.tsx','.css'}):raise ValueError('不能自动修改凭证、账本、守护权限、材料或其他项目；请选择本工具的业务代码')
 return target

def propose(project,program,body):
 journal=Journal(project);changes=body.get('changes',[])
 if not 1<=len(changes)<=12 or not body.get('reason'):raise ValueError('补丁需说明原因，且一次修改1—12个代码文件')
 patch_id=__import__('uuid').uuid4().hex;folder=journal.root/'patches'/patch_id;folder.mkdir(parents=True)
 records=[];diff=[]
 for row in changes:
  target=allowed_program(program,row['path'])
  if not target.is_file():raise ValueError('首版自动修复只修改已有业务代码文件')
  before=target.read_text(encoding='utf8');after=row.get('content')
  if not isinstance(after,str) or len(after.encode())>2000000:raise ValueError('补丁文件过大或无内容')
  if fingerprint(before)!=row.get('expected_hash'):raise ValueError('代码版本已变化，请重新读取')
  if target.suffix=='.py':compile(after,str(target),'exec')
  rel=target.relative_to(program).as_posix();index=len(records)
  (folder/(str(index)+'.before')).write_text(before);(folder/(str(index)+'.after')).write_text(after)
  records.append({'path':rel,'before_hash':fingerprint(before),'after_hash':fingerprint(after)})
  diff+=list(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=rel,tofile=rel))
 (folder/'change.patch').write_text(''.join(diff))
 return journal.put('patch',{'status':'proposed','reason':body['reason'],'changes':records,'created_at':time.time()},patch_id,0)|{'id':patch_id}

def baseline_copy(program,stage):
 def ignore(path,names):return [n for n in names if n in {'__pycache__','node_modules','.git','.workbench','.venv','dist','.env','manager'} or n.endswith(('.local.json','.pyc'))]
 for name in ('.cac','tests','web','docs','examples','frontend/src'):
  source=Path(program)/name
  if source.is_dir():shutil.copytree(source,stage/name,ignore=ignore)
 for name in ('serve.py','scene.py','pytest.ini','README.md','workflow.config.example.json','requirements-windows.lock'):
  if (Path(program)/name).exists():shutil.copy2(Path(program)/name,stage/name)

def test_patch(project,program,patch_id):
 journal=Journal(project);row=journal.get('patch',patch_id)
 if not row or row['status']=='applied':raise ValueError('补丁不存在或已应用')
 if any(not c['path'].endswith('.py') for c in row['changes']):raise ValueError('前端补丁需要研发构建验证；Windows客户无需安装Node，不能直接激活未构建的前端源码')
 folder=journal.root/'patches'/patch_id;stage=folder/'stage'
 if stage.exists():shutil.rmtree(stage)
 stage.mkdir();baseline_copy(program,stage)
 for i,c in enumerate(row['changes']):(stage/c['path']).write_bytes((folder/(str(i)+'.after')).read_bytes())
 # The baseline test suite was copied from the installed program; proposal cannot edit it.
 env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('KEY','TOKEN','SECRET','PASSWORD'))}
 env['PYTHONPATH']=str(stage/'.cac/tools');env['PYTHONDONTWRITEBYTECODE']='1'
 started=time.time()
 try:
  result=subprocess.run([sys.executable,'-m','pytest','tests','-q','--disable-warnings','--maxfail=1'],cwd=stage,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=300)
  text=result.stdout;ok=result.returncode==0
 except subprocess.TimeoutExpired as e:text=str(e);ok=False
 (folder/'test.log').write_text(text)
 return journal.put('patch',{**row,'status':'tested' if ok else 'test_failed','test':{'passed':ok,'seconds':time.time()-started,'summary':text[-5000:],'baseline_suite':'installed frozen tests; model cannot edit'}},patch_id,row['revision'])|{'id':patch_id}

def apply(project,program,patch_id,all_projects,*,confirmed=False,rollback=False):
 from .scheduler import run_lock
 with run_lock(Path(project).parent/'manager-code-activation'):
  return _apply(project,program,patch_id,all_projects,confirmed=confirmed,rollback=rollback)

def _apply(project,program,patch_id,all_projects,*,confirmed=False,rollback=False):
 journal=Journal(project);row=journal.get('patch',patch_id)
 if not row:raise ValueError('未知补丁')
 from .manager_store import settings
 if settings(project)['settings']['mode']!='auto' and not confirmed:raise ValueError('协作模式需要确认补丁')
 if not rollback and (row['status']!='tested' or not row.get('test',{}).get('passed')):raise ValueError('补丁必须通过冻结测试')
 if rollback and row['status']!='applied':raise ValueError('只有已应用补丁可回退')
 if any(read_json(p/'job.json').get('status')=='running' for p in all_projects if (p/'job.json').exists()):
  # Only stop new dispatch in this project; don't terminate requests/other projects.
  write_json(Path(project)/'run/pause_requested.json',{'reason':'等待安全代码应用边界','patch_id':patch_id})
  journal.put('activation',{'patch_id':patch_id,'status':'waiting_safe_boundary','confirmed':confirmed,'rollback':rollback,'requested_at':time.time()},patch_id)
  return {'status':'waiting_safe_boundary','patch_id':patch_id}
 folder=journal.root/'patches'/patch_id
 for c in row['changes']:
  expected=c['after_hash'] if rollback else c['before_hash']
  if fingerprint(allowed_program(program,c['path']).read_text())!=expected:raise ValueError('当前程序已变化，不覆盖新代码')
 applied=[]
 try:
  for i,c in enumerate(row['changes']):
   target=allowed_program(program,c['path']);target.write_bytes((folder/(str(i)+('.before' if rollback else '.after'))).read_bytes());applied.append(i)
   # -B suppresses writes, but Python can still READ an old timestamp/size pyc.
   # Same-size repairs within one second must not boot stale bytecode.
   if target.suffix=='.py':
    for cache in (target.parent/'__pycache__').glob(target.stem+'.*.pyc'):cache.unlink(missing_ok=True)
 except Exception:
  for i in applied:allowed_program(program,row['changes'][i]['path']).write_bytes((folder/(str(i)+('.after' if rollback else '.before'))).read_bytes())
  raise
 (Path(project)/'run/pause_requested.json').unlink(missing_ok=True)
 return journal.put('patch',{**row,'status':'rolled_back' if rollback else 'applied','activated_at':time.time(),'requires_fresh_process':True},patch_id,row['revision'])|{'id':patch_id}
