"""One explicit release migration, never a blanket acceptance of older results."""
from pathlib import Path
from copy import deepcopy
from .storage import fingerprint,read_json


def migrate(task,record,deps,previous,verify,new_identity):
    if record.get('status')!='passed' or record.get('version') or not previous:return False
    proof=read_json(Path(__file__).with_name('cache_migrations_2aee6cc.json'))['tasks'].get(task.stage)
    if not proof or task.version['code']!=proof['current_code'] or task.version.get('imports'):return False
    legacy=deepcopy(task.version)
    for k in ('cache_contract','imports','import_logic'):legacy.pop(k,None)
    legacy.update(code=proof['legacy_code'],identity=previous.get('execution_identity'),cases=previous.get('run_scope',[]))
    old_identity=fingerprint({'version':legacy,'dependencies':{d:v.get('payload',v) if isinstance(v,dict) else v for d,v in deps.items()}})
    if old_identity!=record.get('identity'):return False
    # Scheduler performs content-hash and all current input/schema/source checks next.
    record.setdefault('cache_migrations',[]).append({'from':old_identity,'to':new_identity,'proof':'2aee6cc exact business implementation + exact inputs + current validation'})
    record.update(identity=new_identity,version=deepcopy(task.version))
    return True
