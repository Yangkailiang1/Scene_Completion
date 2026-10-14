"""Strict v2 offline replay, cache-only validation and source-bound review."""
from __future__ import annotations
import hashlib
import sys
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from . import concern_gap_batches as b,interaction_batches as old
from .concern_gap import PROTOCOL,merge_units,metrics
from .concern_gap_ranking import rank
from .semantic_backend import read_json,write_json,collect_packets,run_agent_packets
from .sources import fingerprint
from .interaction_protocol import build_ssd,route_mounts,validate_generated
from .interaction_execution_identity import validate_result_execution
from .interaction_evidence import file_hash,junit_counts,deny_resume_network


def verify_bundle(bundle):
    if bundle.get('protocol')!=PROTOCOL:raise ValueError('not a v2 snapshot')
    if bundle.get('result_hash')!=fingerprint({k:v for k,v in bundle.items() if k!='result_hash'}):
        raise ValueError('snapshot/result bundle hash changed')
    ssd=build_ssd(bundle['model'])
    if ssd!=bundle['ssd']:raise ValueError('saved SSD differs from normal model')
    mounts=route_mounts(ssd)
    allowed={'feature_evidence','mount_reason'}
    if [{k:v for k,v in m.items() if k not in allowed} for m in bundle['mounts']]!=mounts:
        raise ValueError('missing/changed concern mounts')
    validate_generated(bundle['source_generated']+bundle['normal'],ssd,bundle['mounts'],bundle['source_index'])
    for collection in ('G','E','T'):
        units=bundle['source_units'][collection]
        if 'dedup' in bundle:
            from .concern_gap_dedup import merge as dedup_merge
            expected=dedup_merge(units,collection+'2',bundle['dedup'][collection])
        else:expected=merge_units(units,collection+'2')
        if collection=='E':
            if expected!=bundle['history']:raise ValueError('historical normalized units changed')
            expected=[u for u in expected if u['use_case_id'] in bundle['scope']['use_case_ids']]
        if expected!=bundle[collection]:raise ValueError('normalized collection changed: '+collection)
        reviews=bundle['reverse_checks'][collection]['reviews']
        if len(reviews)!=len(units) or {r['unit_id'] for r in reviews}!={u['unit_id'] for u in units} or not all(r['passed'] for r in reviews):
            raise ValueError('incomplete/rejected reverse checks')
    candidates=[u for u in bundle['G'] if u['scenario_id'] in bundle['metrics']['missing_ids']]
    saved=bundle['ranking']
    class VectorOnly:
        def model(self,kind):return saved['model']
        def embeddings(self,texts):
            original={__import__('scene_completion.concern_gap_ranking',fromlist=['scene_text']).scene_text(u):saved['vectors'][u['scenario_id']]
                for u in candidates+bundle['history'] if u['scenario_id'] in saved['vectors']}
            return [original[text] for text in texts]
    ranking=rank(candidates,bundle['history'],VectorOnly(),saved['seed'])
    if ranking!=saved:raise ValueError('historical sums/TopN/sampling differ from replay')
    result=metrics(bundle['G'],bundle['E'],bundle['T'],saved['selected_ids'],bundle['relations'])
    if result!=bundle['metrics']:raise ValueError('four metrics or set assignments differ from replay')
    return {'complete':True,'result_hash':bundle['result_hash'],'sets':result['set_sizes']}


def stage_specs(root):
    from .interaction_participants import participant_packets,participant_validator
    from .interaction_audit import checker_audit_packets,checker_audit_validator
    root=Path(root);index=read_json(root/'sources_index.json');base=read_json(root/'generator_base_identity.json')
    bundle=read_json(root/'result_bundle.json');test_index=bundle['test_source_index']
    selected=bundle['scope']['use_case_ids'] if bundle['scope']['kind']=='representative' else None
    from .interaction_scope import assessment_base
    scoped=assessment_base(base,selected)
    model,ssd,mounts,features=bundle['model'],bundle['ssd'],bundle['mounts'],bundle['features']
    specs={
        'interaction-model':(lambda d:old.model_packets(base,index,d),old.model_validator(index)),
        'gap-graph-check':(lambda d:b.graph_packets(model,ssd,index,d),b.graph_validator(index)),
        'interaction-participants':(lambda d:participant_packets(root/'batches/interaction-model',index,d,use_case_ids=selected),participant_validator(index)),
        'gap-features':(lambda d:b.feature_packets(model,ssd,index,d),b.feature_validator(index)),
        'gap-generation':(lambda d:b.generation_packets(ssd,mounts,features,d),b.generation_validator(index)),
        'interaction-checker':(lambda d:old.checker_packets(base,index,d),old.checker_validator(index)),
        'interaction-checker-audit':(lambda d:checker_audit_packets(root/'batches/interaction-checker',index,d),checker_audit_validator(index)),
        'gap-test-extract':(lambda d:b.test_packets(scoped,test_index,d),old.test_validator(test_index))}
    if (root/'ar_sources_index.json').exists():
        ar_index=read_json(root/'ar_sources_index.json')
        specs['gap-ar-trace']=(lambda d:b.ar_packets(ar_index,d),b.ar_validator(ar_index))
    history_ssd=read_json(root/'historical_ssd.json')
    from .concern_gap_normalize_diagnostics import validator as normalize_validator
    from .concern_gap_repair import repair_packets,repair_validator,reverse_validator
    for record in bundle.get('generation_repairs',[]):
        folder=root/'batches'/record['stage_directory']
        first=read_json(folder/'manifest.json')['batches'][0]['batch_id']
        execution_version=read_json(folder/'packets'/(first+'.json'))['input']['repair_tool_version']
        specs[record['stage_directory']]=(lambda d,r=record,v=execution_version:repair_packets(ssd,mounts,features,
            bundle['source_generated_base'],r['rejections'],d,v),repair_validator(index))
    for collection,source,graph,idx in [('G',bundle['source_generated'],ssd,index),('E',bundle['source_existing'],history_ssd,index),('T',bundle['source_tests'],ssd,test_index)]:
        specs['gap-normalize-'+collection]=(lambda d,s=source,g=graph,c=collection,i=idx:b.normalized_packets(s,g,d,c,i),normalize_validator(idx))
        specs['gap-reverse-check-'+collection]=(lambda d,s=source,g=graph,c=collection,i=idx:b.review_packets(bundle['source_units'][c],s,g,d,c,i),reverse_validator)
        if 'dedup' in bundle:
            from .concern_gap_dedup import packets as dedup_packets,validator as dedup_validator
            specs['gap-dedup-'+collection]=(lambda d,c=collection,g=graph:dedup_packets(bundle['source_units'][c],g,c,d),dedup_validator)
        for record in bundle.get('normalization_repairs',{}).get(collection,[]):
            from .concern_gap_inverse_repair import packets as inverse_packets
            specs[record['stage_directory']]=(lambda d,r=record,g=graph,i=idx,c=collection:inverse_packets(r['sources'],g,i,c,
                r['rejections'],r['prior_units'],d),normalize_validator(idx))
    for name,l,r in [('EG',bundle['E'],bundle['G']),('TG',bundle['T'],bundle['G']),('TE',bundle['T'],bundle['E'])]:
        from .concern_gap_comparison import validator as comparison_validator
        specs['gap-ambiguity-'+name]=(lambda d,left=l,right=r,n=name:b.comparison_packets(left,right,d,n),comparison_validator)
    if 'gap-reverse-confirm-G' in read_json(root/'run_manifest.json')['stages']:
        from .concern_gap_review_confirm import packets as confirm_packets,validator as confirm_validator
        specs['gap-reverse-confirm-G']=(lambda d:confirm_packets(bundle['source_units']['G'],bundle['source_generated'],ssd,index,
            bundle['generation_initial_reviews'],d),confirm_validator)
    return specs


def proof_files(root):
    root=Path(root);names=['sources_index.json','generator_base_identity.json','scene_model.json','historical_ssd.json',
        'model_authorization.json','result_bundle.json']
    if read_json(root/'run_manifest.json').get('execution_mode') == 'case-dag':
        names += ['case_tasks.json'] + [str(p.relative_to(root)) for top in ('cases', 'task_outputs', 'task_history')
            for p in sorted((root/top).rglob('*')) if p.is_file() and '.embedding_cache' not in p.parts]
        return {name:file_hash(root/name) for name in names if (root/name).exists()}
    if (root/'ar_sources_index.json').exists():names+=['ar_sources_index.json','ar_trace.json']
    if (root/'generation_repairs.json').exists():
        names+=['generation_repairs.json']+[str(p.relative_to(root)) for p in sorted((root/'repair_evidence').rglob('*')) if p.is_file()]
    names+=[str(p.relative_to(root)) for p in sorted(root.glob('normalization_repairs_*.json'))]
    names+=[str(p.relative_to(root)) for p in sorted((root/'inverse_repair_evidence').rglob('*')) if p.is_file()]
    for folder in sorted((root/'batches').glob('*')):
        if not (folder/'manifest.json').exists():continue
        names.append(str((folder/'manifest.json').relative_to(root)))
        for batch in read_json(folder/'manifest.json')['batches']:
            for key in ('packets','results'):
                names.append(str((folder/key/(batch['batch_id']+'.json')).relative_to(root)))
            # Bind the immutable rejected executions as well as the accepted one.
            names += [str(p.relative_to(root)) for p in sorted((folder/'attempts').glob(batch['batch_id']+'-*.json'))]
    return {name:file_hash(root/name) for name in names}


def replay(root,cache_resume=False):
    root=Path(root);run=read_json(root/'run_manifest.json')
    if run.get('execution_mode') == 'case-dag':
        from .concern_gap_dag_replay import replay as dag_replay
        return dag_replay(root, cache_resume=cache_resume)
    if not run.get('complete') or run.get('protocol')!=PROTOCOL or run.get('versions')!=b.versions():
        raise ValueError('run incomplete, incompatible or tools changed')
    bundle=read_json(root/'result_bundle.json');result=verify_bundle(bundle)
    if result['result_hash']!=run['result_hash']:raise ValueError('run and result hashes disagree')
    records=[];outputs={}
    for name,(prepare,validator) in stage_specs(root).items():
        folder=root/'batches'/name
        with TemporaryDirectory() as tmp:
            expected=prepare(Path(tmp))
            if read_json(folder/'manifest.json')!=expected:
                # Reviewed historical checker imports can retain only an
                # explicitly extraction-neutral report-policy prose difference.
                if name!='interaction-checker' or not run.get('checker_baseline_import'):
                    raise ValueError('stage assignment changed: '+name)
                from .interaction_baseline import checker_extraction_skill
                a=read_json(folder/'manifest.json')['batches'];z=expected['batches']
                if len(a)!=len(z):raise ValueError('checker scope changed')
                for original,current in zip(a,z):
                    p=read_json(folder/'packets'/(original['batch_id']+'.json'))
                    q=read_json(Path(tmp)/'packets'/(current['batch_id']+'.json'))
                    for packet in (p,q):
                        packet.pop('batch_id',None);packet.pop('input_hash',None)
                        packet['input']['checker_skill']=checker_extraction_skill(packet['input']['checker_skill'])
                    if p!=q:raise ValueError('historical checker semantic input changed')
        values,state=collect_packets(folder,validator)
        if not state['complete']:raise ValueError('incomplete semantic stage: '+name)
        outputs[name]=values
        for batch in read_json(folder/'manifest.json')['batches']:
            path=folder/'results'/(batch['batch_id']+'.json');raw=read_json(path)
            identity=validate_result_execution(raw,result_path=path)
            if cache_resume:
                class CacheOnly:
                    config={'allowed_cached_models':[identity['model']],'max_concurrency':1,
                        'thinking':raw['execution_model_evidence'].get('thinking',False),
                        'reasoning_effort':raw['execution_model_evidence'].get('reasoning_effort')}
                    def model(self,kind):return identity['model']
                    def agent(self,p):raise RuntimeError('new model call forbidden during resume')
                resumed=run_agent_packets(folder,CacheOnly(),validator,batch_ids=[batch['batch_id']])
                if not resumed['complete'] or resumed['batches'][0]['status']!='cached':raise ValueError('cache resume failed')
            records.append({'stage':name,'batch_id':batch['batch_id'],'identity':identity,'status':'cached' if cache_resume else 'verified'})
    expected_outputs={'gap-generation':bundle.get('source_generated_base',bundle['source_generated']),'gap-features':bundle['features'],
        'gap-graph-check':bundle['graphs'],'interaction-checker':bundle['source_existing'],'gap-test-extract':bundle['source_tests']}
    from .interaction_cli import merge_model
    from .interaction_scope import assessment_base,select_cases
    index=read_json(root/'sources_index.json');base=read_json(root/'generator_base_identity.json')
    selected=bundle['scope']['use_case_ids'] if bundle['scope']['kind']=='representative' else None
    proven=merge_model(select_cases(outputs['interaction-model'],selected),assessment_base(base,selected),index)
    if proven!=bundle['model'] or build_ssd(merge_model(outputs['interaction-model'],base,index))!=read_json(root/'historical_ssd.json'):
        raise ValueError('normal model/history graph differs from source extraction proof')
    if not all(r['valid'] for r in outputs['gap-graph-check']) or not all(r['passed'] for r in outputs['interaction-participants']) or not all(r['passed'] for r in outputs['interaction-checker-audit']):
        raise ValueError('required source/participant/graph checks rejected')
    for c in ('G','E','T'):
        expected_outputs['gap-normalize-'+c]=bundle.get('base_source_units',bundle['source_units'])[c]
        expected_outputs['gap-reverse-check-'+c]=bundle.get('generation_initial_reviews',bundle['reverse_checks'][c]['reviews']) if c=='G' else bundle['reverse_checks'][c]['reviews']
        if 'dedup' in bundle:expected_outputs['gap-dedup-'+c]=bundle['dedup'][c]
    if 'gap-reverse-confirm-G' in outputs:
        expected_outputs['gap-reverse-confirm-G']=bundle['generation_confirmed_reviews']
        overrides={r['unit_id']:r for r in outputs['gap-reverse-confirm-G']}
        if [overrides.get(r['unit_id'],r) for r in outputs['gap-reverse-check-G']]!=bundle['reverse_checks']['G']['reviews']:
            raise ValueError('confirmed G checks do not resolve actual rejected units')
    for name,values in expected_outputs.items():
        if outputs[name]!=values:raise ValueError('saved bundle differs from actual semantic results: '+name)
    if bundle.get('generation_repairs'):
        from .concern_gap_repair_proof import verify
        if verify(root,bundle['source_generated_base'],bundle['generation_repairs'],outputs)!=bundle['source_generated']:
            raise ValueError('source-only repaired G differs from replay')
    for collection,repair_records in bundle.get('normalization_repairs',{}).items():
        from .concern_gap_inverse_repair import verify as verify_inverse
        if verify_inverse(root,bundle['base_source_units'][collection],repair_records,outputs)!=bundle['source_units'][collection]:
            raise ValueError('same-channel inverse repair differs from actual execution')
    for name,left,right in [('EG',bundle['E'],bundle['G']),('TG',bundle['T'],bundle['G']),('TE',bundle['T'],bundle['E'])]:
        if b.exact_decisions(left,right)+outputs['gap-ambiguity-'+name]!=bundle['relations'][name]:
            raise ValueError('comparison relations differ from actual decisions')
    return {**result,'batches':records}


def check(root):
    root=Path(root);run=read_json(root/'run_manifest.json')
    if run.get('execution_mode') == 'case-dag':
        from .concern_gap_dag_replay import check as dag_check
        return dag_check(root)
    try:
        result=replay(root)
        record={'structurally_valid':True,'complete':True,'result_hash':result['result_hash'],
            'formally_accepted':bool(run.get('accepted')) and not acceptance_reasons(root,result),'pending_stage':None}
        code=0
    except (ValueError,KeyError,OSError,TypeError) as exc:
        record={'structurally_valid':False,'complete':False,'formally_accepted':False,
            'pending_stage':run.get('pending_stage'),'reason':str(exc)};code=2
    write_json(root/'run_checks.json',record)
    (root/'run_checks.md').write_text('# 运行检查\n\n'+str(record)+'\n',encoding='utf8')
    return record,code


def validation_identity():
    repo=Path(__file__).resolve().parents[3]
    return fingerprint({'tools':b.versions(),'tests':{str(p.relative_to(repo)):file_hash(p) for p in sorted((repo/'tests').rglob('*.py'))}})


def validate(root):
    root=Path(root);initial=replay(root);before=proof_files(root);vid=validation_identity()
    if not initial['complete']:
        return initial, 2
    folder=root/'verification';folder.mkdir(exist_ok=True)
    repo=Path(__file__).resolve().parents[3]
    command=[sys.executable,'-m','pytest','-q','--junitxml='+str((folder/'regression.xml').resolve())]
    process=subprocess.run(command,cwd=repo,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=900)
    (folder/'regression.log').write_text(process.stdout+process.stderr,encoding='utf8')
    counts=junit_counts(folder/'regression.xml')
    if process.returncode or not counts['tests'] or any(counts[k] for k in ('failures','errors','skipped')):
        return {'complete':False,'junit_counts':counts},2
    with deny_resume_network() as network:
        final=replay(root,cache_resume=True)
    if network['attempts'] or before!=proof_files(root) or initial['result_hash']!=final['result_hash'] or vid!=validation_identity():
        raise ValueError('resume inputs/metrics/tools/network changed')
    record={'complete':True,'result_hash':initial['result_hash'],'validation_identity':vid,'proof_files':before,
        'junit_counts':counts,'junit_hash':file_hash(folder/'regression.xml'),'log_hash':file_hash(folder/'regression.log'),
        'command':command,'exit_code':process.returncode,'network_calls':network['attempts'],
        'resumed_batches':len(final['batches']),'batches':final['batches']}
    write_json(root/'validation.json',record)
    return record,0


AREAS=['ssd_only_generation','ar_trace_only','graph_checks','feature_inference','reverse_atomicity',
    'exception_identity','gt_framework_derivation','four_metric_denominators','historical_ranking',
    'top_n_sampling','one_to_one_assignment','resume_and_scope']


def prepare_review(root):
    root=Path(root);result=replay(root)
    if not result['complete']:
        return result, 2
    materials={'protocol':PROTOCOL,'result_hash':result['result_hash'],'files':proof_files(root),'areas':AREAS}
    write_json(root/'effect_review_materials.json',materials)
    return {'complete':True,'materials_hash':fingerprint(materials),'result_hash':result['result_hash'],'areas':AREAS},0


def acceptance_reasons(root,result):
    root=Path(root);reasons=[]
    try:
        v=read_json(root/'validation.json')
        counts=junit_counts(root/'verification/regression.xml')
        if (v['result_hash']!=result['result_hash'] or v['validation_identity']!=validation_identity() or v['proof_files']!=proof_files(root)
            or v['network_calls']!=0 or v['exit_code']!=0 or v['junit_counts']!=counts or any(counts[k] for k in ('errors','failures','skipped'))
            or v['junit_hash']!=file_hash(root/'verification/regression.xml') or v['log_hash']!=file_hash(root/'verification/regression.log')):
            reasons.append('regression/resume proof invalid')
        if (v.get('batches')!=[{**r,'status':'cached'} for r in result['batches']]
            or v.get('resumed_batches')!=len(result['batches'])):
            reasons.append('cache-only resume batch identity incomplete')
    except (OSError,KeyError,ValueError):reasons.append('regression/resume proof missing')
    try:
        material={'protocol':PROTOCOL,'result_hash':result['result_hash'],'files':proof_files(root),'areas':AREAS}
        raw=read_json(root/'effect_review_raw.json');meta=read_json(root/'effect_review.json')
        areas=raw['areas']
        from .model_configuration import matches_review_policy
        if (read_json(root/'effect_review_materials.json')!=material or raw['materials_hash']!=fingerprint(material)
            or meta['materials_hash']!=fingerprint(material) or meta['result_hash']!=result['result_hash']
            or meta['raw_review_hash']!=file_hash(root/'effect_review_raw.json') or not matches_review_policy(root, meta)
            or not meta['agent_id'] or meta['passed'] is not True
            or raw['unresolved_findings'] or meta['unresolved_findings'] or len(areas)!=len(AREAS)
            or {a['area'] for a in areas}!=set(AREAS) or not all(a['passed'] is True and a.get('reason')
                and a.get('evidence_files') and set(a['evidence_files'])<=set(material['files']) for a in areas)):
            reasons.append('independent review missing or unresolved')
    except (OSError,KeyError,ValueError):reasons.append('independent review missing')
    return reasons


def evaluate(root):
    from .concern_gap_reports import export
    root=Path(root);result=replay(root)
    if not result['complete']:
        return {**result, 'accepted': False}
    reasons=acceptance_reasons(root,result)
    accepted=not reasons;output={'complete':True,'accepted':accepted,'result_hash':result['result_hash'],'reasons':reasons}
    write_json(root/'acceptance.json',output)
    run=read_json(root/'run_manifest.json');run['accepted']=accepted;write_json(root/'run_manifest.json',run)
    export(root,read_json(root/'result_bundle.json'),accepted=accepted);check(root)
    return output


def export_snapshot(root,path):
    result=replay(root)
    if not result['complete']:
        from .concern_gap_dag_replay import partial_snapshot
        return partial_snapshot(root, path)
    bundle=read_json(Path(root)/'result_bundle.json')
    write_json(path,{'protocol':PROTOCOL,'payload_hash':fingerprint(bundle),'payload':bundle})
    return {'complete':True,'result_hash':result['result_hash']}


def rebuild_snapshot(path,root):
    from .concern_gap_reports import export
    raw=read_json(path);bundle=raw['payload']
    if raw.get('payload_hash')!=fingerprint(bundle):raise ValueError('snapshot payload modified')
    if raw.get('partial'):
        from .concern_gap_dag_replay import rebuild_partial
        return rebuild_partial(bundle, root)
    result=verify_bundle(bundle);export(root,bundle)
    write_json(Path(root)/'assessment_status.json',{'accepted':False,'offline_rebuild':True,'execution_evidence_verified':False})
    return {**result,'execution_evidence_verified':False}
