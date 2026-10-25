from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
import hashlib,json
import pytest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=spec_from_file_location(name,ROOT/path);module=module_from_spec(spec);spec.loader.exec_module(module);return module

def test_portable_integrity_manifest_rejects_changed_private_and_escaping_files(tmp_path):
 verify=load('windows_check','tools/check_windows_bundle.py').verify_files
 file=tmp_path/'app/serve.py';file.parent.mkdir();file.write_text('source')
 manifest={'platform':'windows-x64','requires_network_install':False,'files':{'app/serve.py':hashlib.sha256(file.read_bytes()).hexdigest()}}
 def save(): (tmp_path/'SHA256SUMS.json').write_text(json.dumps(manifest))
 save();assert verify(tmp_path)['platform']=='windows-x64'
 file.write_text('modified')
 with pytest.raises(ValueError,match='digest'):verify(tmp_path)
 manifest['files']={'../escape':'abc'};save()
 with pytest.raises(ValueError,match='escapes'):verify(tmp_path)
 private=tmp_path/'.env';private.write_text('not real credentials')
 manifest['files']={'.env':hashlib.sha256(private.read_bytes()).hexdigest()};save()
 with pytest.raises(ValueError,match='Private'):verify(tmp_path)

def test_portable_launcher_waits_until_ready_before_browser_and_quotes_paths(tmp_path,monkeypatch):
 launcher=load('portable_launcher','deployment/launcher.py');root=tmp_path/'Windows 离线目录';(root/'app').mkdir(parents=True);(root/'app/serve.py').write_text('source')
 events=[];commands=[]
 class Sock:
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def connect_ex(self,*a):return 1
 class Process:
  def poll(self):return None if 'wait' not in events else 0
  def wait(self,**kw):events.append('wait');return 0
  def terminate(self):events.append('terminate')
 class Response:
  status=200
  def __enter__(self):events.append('ready');return self
  def __exit__(self,*a):pass
 monkeypatch.setattr(launcher.socket,'socket',lambda:Sock())
 monkeypatch.setattr(launcher.subprocess,'Popen',lambda cmd,**kw:(commands.append((cmd,kw)) or Process()))
 monkeypatch.setattr(launcher.urllib.request,'urlopen',lambda *a,**kw:Response())
 monkeypatch.setattr(launcher.webbrowser,'open',lambda *a:events.append('browser'))
 assert launcher.run(root)==0 and events==['ready','browser','wait']
 assert str(root/'app/serve.py') in commands[0][0] and str(root/'data') in commands[0][0]
 assert commands[0][1]['cwd']==root.resolve()

def test_portable_launcher_never_kills_existing_port_owner(tmp_path,monkeypatch):
 launcher=load('occupied_launcher','deployment/launcher.py');(tmp_path/'app').mkdir();(tmp_path/'app/serve.py').write_text('source')
 class Sock:
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def connect_ex(self,*a):return 0
 monkeypatch.setattr(launcher.socket,'socket',lambda:Sock())
 monkeypatch.setattr(launcher.subprocess,'Popen',lambda *a,**kw:pytest.fail('Existing port owner must not be replaced'))
 assert launcher.run(tmp_path)==1
