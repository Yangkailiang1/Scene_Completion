"""Input-bound review versions; approved edits are revalidated before consumption."""
from pathlib import Path
from datetime import datetime,timezone
from copy import deepcopy
from .storage import fingerprint,read_json,write_json
from .scheduler import TaskBlocked
from .validation import validate_result
from .contracts import SCHEMAS

REVIEW_TASKS={'test-inventory','test-case-align','existing-concerns','test-concerns','existing-branches','existing-bind','use-case-extract','use-case-align','components','api-map','api-parameters','fused-ssd','object-operations','concern-match','exception-generate','existing-extract','gap-compare'}
class Reviews:
    def __init__(self,root,mode='auto'):
        if mode not in {'auto','manual'}:raise ValueError('review mode must be auto or manual')
        self.root=Path(root)/'reviews';self.mode=mode
    def path(self,key):return self.root/(fingerprint(key)+'.json')
    def read(self,key):
        p=self.path(key);return read_json(p) if p.exists() else None
    def revision(self,key):
        v=self.read(key);return v.get('revision',0) if v else 0
    def cached(self,key,task,inputs,identity=None):
        v=self.read(key)
        if not v or v['input_hash']!=fingerprint(inputs):return None
        if v.get('execution_identity')!=identity:return None
        if v['status']=='regenerate':return None
        if v['status']=='rejected':raise TaskBlocked('awaiting_review',{'review':key,'reason':'业务已驳回，可修改结果或重新生成'})
        if self.mode=='manual' and v['status']!='approved':raise TaskBlocked('awaiting_review',{'review':key})
        if task in SCHEMAS:validate_result(task,v['payload'],inputs)
        return deepcopy(v['payload'])
    def propose(self,key,task,inputs,value,identity=None):
        if task not in REVIEW_TASKS:return value
        old=self.read(key);rev=old.get('revision',0)+1 if old else 0
        from .execution_events import phase,emit
        phase('saving')
        from .artifact_exports import export_task
        preview=self.root/'previews'/fingerprint(key)
        export_task(preview,task,value,artifact_name=(task if ':' in key else key).replace(':','--'))
        entry={'key':key,'task':task,'input_hash':fingerprint(inputs),'inputs':inputs,'payload':value,
          'execution_identity':identity,'status':'draft' if self.mode=='manual' else 'auto','revision':rev,'updated_at':datetime.now(timezone.utc).isoformat()}
        # Immutable history is separate from replaceable rendering artifacts.
        write_json(self.root/'versions'/(fingerprint(entry)+'.json'),entry);write_json(self.path(key),entry)
        emit('artifacts_saved',files=[str(p.relative_to(self.root.parent)).replace('\\','/') for p in preview.iterdir() if p.is_file()])
        if self.mode=='manual':raise TaskBlocked('awaiting_review',{'review':key})
        return value
    def decide(self,key,action,*,expected_revision,expected_input_hash,value=None,comment=''):
        from .scheduler import run_lock
        with run_lock(self.root.parent):
            return self._decide(key,action,expected_revision=expected_revision,expected_input_hash=expected_input_hash,value=value,comment=comment)
    def _decide(self,key,action,*,expected_revision,expected_input_hash,value=None,comment=''):
        old=self.read(key)
        if not old:raise ValueError('unknown review item')
        if old['revision']!=expected_revision or old['input_hash']!=expected_input_hash:raise ValueError('review item changed; refresh before saving')
        if action not in {'approve','reject','regenerate'}:raise ValueError('unknown review decision')
        new=deepcopy(old)
        if value is not None:
            if action!='approve':raise ValueError('edited payload requires approve')
            validate_result(old['task'],value,old['inputs']);new['payload']=value
        new.update(status={'approve':'approved','reject':'rejected','regenerate':'regenerate'}[action],
            revision=old['revision']+1,comment=comment,updated_at=datetime.now(timezone.utc).isoformat())
        write_json(self.root/'versions'/(fingerprint(new)+'.json'),new);write_json(self.path(key),new)
        return new
