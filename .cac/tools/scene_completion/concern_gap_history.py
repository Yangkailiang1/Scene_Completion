"""Read-only import of a proved E corpus, never a normal/G/T reuse channel."""
from pathlib import Path
import copy
import shutil
from .semantic_backend import read_json, collect_packets
from .sources import fingerprint
from .concern_gap_replay import verify_bundle
from .interaction_execution_identity import validate_result_execution


def source_versions(index):
    return sorted((d['document'], fingerprint(d['text'])) for d in index['documents'])


def load(root, index, selected, cases):
    root=Path(root).resolve()
    manifest=read_json(root/'run_manifest.json')
    if not manifest.get('complete'):
        raise ValueError('history run is incomplete; no automatic project rerun')
    bundle=read_json(root/'result_bundle.json')
    verify_bundle(bundle)
    if source_versions(bundle['source_index'])!=source_versions(index):
        raise ValueError('history source documents changed; prepare a compatible history run explicitly')
    model=read_json(root/'historical_scene_model.json')
    if {u['use_case_id'] for u in model['use_cases']}!=set(cases):
        raise ValueError('history use-case universe differs')
    from . import interaction_batches as old
    from .interaction_audit import checker_audit_validator
    from .concern_gap_normalize_diagnostics import validator as normalize_validator
    from .concern_gap_repair import reverse_validator
    from .concern_gap_dedup import validator as dedup_validator
    validators={'interaction-checker':old.checker_validator(index),
        'interaction-checker-audit':checker_audit_validator(index),
        'gap-normalize-E':normalize_validator(index), 'gap-reverse-check-E':reverse_validator,
        'gap-dedup-E':dedup_validator}
    proofs={}
    outputs={}
    def collect(folder, validator):
        values,status=collect_packets(folder,validator)
        if not status['complete']:raise ValueError('history execution incomplete: '+str(folder))
        path=folder/'manifest.json';proofs[str(path)]=fingerprint(read_json(path))
        for batch in read_json(path)['batches']:
            packet=folder/'packets'/(batch['batch_id']+'.json')
            result=folder/'results'/(batch['batch_id']+'.json')
            raw=read_json(result);validate_result_execution(raw,result_path=result)
            if raw['input_hash']!=batch['input_hash'] or read_json(packet)['input_hash']!=batch['input_hash']:
                raise ValueError('history batch identity differs')
            for p in (packet,result):proofs[str(p)]=fingerprint(read_json(p))
        return values
    if manifest.get('execution_mode')=='case-dag':
        # Validate the existing local task proofs without requiring a new model.
        from .concern_gap_dag_replay import replay
        replay(root)
        state=read_json(root/'case_tasks.json')
        proofs[str(root/'case_tasks.json')]=fingerprint(state)
        for task in state['tasks'].values():
            if task['status']!='passed':raise ValueError('historical case task is incomplete')
            path=root/task['output_file'];output=read_json(path);proofs[str(path)]=fingerprint(output)
            for execution in output.get('executions',[]):
                result=Path(execution['result_path'])
                packet=result.parent.parent/'packets'/result.name
                for path in (packet,result):proofs[str(path)]=fingerprint(read_json(path))
    else:
        for stage,validator in validators.items():outputs[stage]=collect(root/'batches'/stage,validator)
        if outputs['interaction-checker']!=bundle['source_existing']:
            raise ValueError('history E differs from independent extraction')
        if not all(row['passed'] for row in outputs['interaction-checker-audit']):
            raise ValueError('history independent source audit rejected')
        initial=outputs['gap-normalize-E']
        if initial!=bundle.get('base_source_units',bundle['source_units'])['E']:
            raise ValueError('history normalization differs from proof')
        repairs=bundle.get('normalization_repairs',{}).get('E',[])
        repair_outputs={}
        for record in repairs:
            stage=record['stage_directory'];repair_outputs[stage]=collect(root/'batches'/stage,normalize_validator(index))
        if repairs:
            from .concern_gap_inverse_repair import verify
            initial=verify(root,initial,repairs,repair_outputs)
        if initial!=bundle['source_units']['E'] or outputs['gap-reverse-check-E']!=bundle['reverse_checks']['E']['reviews'] or outputs['gap-dedup-E']!=bundle['dedup']['E']:
            raise ValueError('history inverse/dedup proof differs')
    for name in ('result_bundle.json','run_manifest.json','historical_scene_model.json','historical_ssd.json'):
        proofs[str(root/name)]=fingerprint(read_json(root/name))
    excluded=set(selected)
    units=[u for u in bundle['source_units']['E'] if u['use_case_id'] not in excluded]
    ids={u['unit_id'] for u in units}
    corpus={
        'history':[u for u in bundle['history'] if u['use_case_id'] not in excluded],
        'source_existing':[u for u in bundle['source_existing'] if u['use_case_id'] not in excluded],
        'source_units':units,
        'dedup':[r for r in bundle['dedup']['E'] if r['left_unit_id'] in ids and r['right_unit_id'] in ids],
        'reviews':[r for r in bundle['reverse_checks']['E']['reviews'] if r['unit_id'] in ids],
        'model':model,
        'binding':{'run':str(root),'result_hash':bundle['result_hash'],'proofs':proofs,
            'excluded_use_case_ids':sorted(excluded),'corpus_hash':fingerprint(units)}}
    return copy.deepcopy(corpus)


def verify_binding(binding):
    for path,hashed in binding['proofs'].items():
        if fingerprint(read_json(path))!=hashed:raise ValueError('imported historical proof changed: '+path)


def copy_vectors(corpus, client):
    from .concern_gap_ranking import scene_text,cosine
    root=Path(corpus['binding']['run']);cache=Path(client.config['cache_dir'])
    copied=0
    for unit in corpus['history']:
        key=fingerprint([client.base_url,client.model('embedding'),scene_text(unit)])
        source=root/'.embedding_cache'/(key+'.json')
        if source.exists():
            vector=read_json(source);cosine(vector,vector)
            target=cache/source.name
            if not target.exists():
                cache.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);copied+=1
    return copied
