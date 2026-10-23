"""Offline integrity inspection; it never submits inference requests."""
from .storage import read_json,fingerprint
from .contracts import PROTOCOL,SCHEMAS,validate

def inspect_run(root):
    errors=[]
    try:
        manifest=read_json(root/'run_manifest.json');state=read_json(root/'workflow_tasks.json')
        if manifest.get('protocol')!=PROTOCOL:errors.append('wrong protocol')
        for k,status in manifest['tasks'].items():
            record=state['tasks'][k]
            if record['status']!=status:errors.append(k+': manifest/state mismatch')
            if status!='passed':continue
            value=read_json(root/record['output_file'])
            if value.get('protocol')!=PROTOCOL or fingerprint(value)!=record['output_hash']:errors.append(k+': cache identity mismatch')
            if value['task'] in SCHEMAS:validate(value['task'],value['payload'])
        return {'valid':not errors,'complete':manifest['complete'],'analysis_by_case':manifest.get('analysis_by_case',{}),'errors':errors}
    except (ValueError,OSError,KeyError) as e:return {'valid':False,'errors':errors+[str(e)]}
