"""V2 pipeline: checked graphs, independent inverse units and historical ranks."""
from __future__ import annotations
import copy
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from . import concern_gap_batches as b, interaction_batches as old
from .concern_gap import PROTOCOL, POLICY, merge_units, metrics
from .interaction_cli import source_index, merge_model, architecture_proposals, write_pending
from .interaction_protocol import build_ssd, route_mounts, validate_generated, baseline
from .interaction_scope import assessment_base, select_cases
from .interaction_participants import participant_packets, participant_validator, write_participants
from .interaction_execution_identity import validate_result_execution, copy_execution_sidecars
from .semantic_backend import read_json, write_json, collect_packets, run_agent_packets
from .sources import fingerprint,index_sources
from .concern_gap_inverse_repair import ledger as inverse_ledger
from .model_configuration import config_overrides, referenced_env_keys


def copy_compatible(folder,reuse):
    """Copy byte-identical packets/results, never retag an old semantic result."""
    if not reuse: return 0
    source=Path(reuse)/'batches'/folder.name
    if not (source/'manifest.json').exists(): return 0
    previous={r['input_hash']:r for r in read_json(source/'manifest.json')['batches']}
    copied=0
    for batch in read_json(folder/'manifest.json')['batches']:
        if batch['input_hash'] not in previous:continue
        old_batch=previous[batch['input_hash']]
        src=source/'results'/(old_batch['batch_id']+'.json')
        dst=folder/'results'/(batch['batch_id']+'.json')
        if not src.exists() or dst.exists():continue
        if read_json(source/'packets'/(old_batch['batch_id']+'.json')) != read_json(folder/'packets'/(batch['batch_id']+'.json')):
            continue
        raw=read_json(src);validate_result_execution(raw,result_path=src)
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        copy_execution_sidecars(raw,src,dst);copied+=1
    return copied


def run(args):
    config = read_json(args.config) if getattr(args, 'config', None) else {}
    mode = getattr(args, 'execution_mode', None) or config.get('execution_mode', 'case-dag')
    if mode not in ('case-dag', 'stage-barrier'):
        raise ValueError('execution_mode must be case-dag or stage-barrier')
    if mode == 'case-dag':
        from .concern_gap_dag import run as run_dag
        return run_dag(args)
    if getattr(args,'profile',False) or getattr(args,'history_run',None):
        raise ValueError('profile and history-run require v2 case-dag execution')
    return run_stage_barrier(args)


def run_stage_barrier(args):
    from .role_cli import _client
    from .concern_gap_reports import export
    from .concern_gap_ranking import rank
    if getattr(args,'rerank',False):raise ValueError('v2 historical recommendation does not use rerank')
    if getattr(args,'exchange_local_id',None):raise ValueError('v2 run selects complete use cases, not partial chains')
    root=Path(args.output_dir).resolve();root.mkdir(parents=True,exist_ok=True)
    prior=read_json(root/'run_manifest.json') if (root/'run_manifest.json').exists() else None
    if prior and prior.get('protocol')!=PROTOCOL:raise ValueError('use a separate v2 directory')
    index=source_index(args)
    base=read_json(args.model)
    base={'use_cases':[{k:u[k] for k in ('use_case_id','use_case_name','architecture','source_use_case_ids') if k in u} for u in base['use_cases']],
        'system_composition':{'nodes':base.get('system_composition',{}).get('nodes',[])}}
    selected=getattr(args,'use_case_id',None);scoped=assessment_base(base,selected)
    from .model_configuration import concurrency_limit, review_policy
    client=_client(args,root);client.config['max_concurrency']=concurrency_limit(client.config.get('max_concurrency',1))
    from .review import load_ecnu_env_file
    from .semantic_backend import SemanticClient
    embedding_path=getattr(args,'embedding_config',None) or getattr(args,'config',None)
    embedding_config=config_overrides(read_json(embedding_path) if embedding_path else {}, args)
    if getattr(args,'env_file',None):load_ecnu_env_file(args.env_file, extra_keys=referenced_env_keys(embedding_config))
    embedding_config['cache_dir']=str(root/'.embedding_cache')
    embedding_client=SemanticClient(embedding_config)
    if args.agent_mode=='external':
        from .interaction_execution_identity import validate_client_execution_model
        validate_client_execution_model(client)
    reuse=getattr(args,'reuse_run',None)
    manifest={'protocol':PROTOCOL,'policy':POLICY,'complete':False,'accepted':False,
        'source_hash':fingerprint(index),'base_hash':fingerprint(base),'versions':b.versions(),
        'scope':{'kind':'representative' if selected else 'full','use_case_ids':[u['use_case_id'] for u in scoped['use_cases']],
            'granularity':'complete_use_cases'},'model':client.model('agent'),'stages':{},
        'recommendation_seed':getattr(args,'recommendation_seed',42),'rerank':False,
        'embedding_model':embedding_client.model('embedding'),'recommendation_backend':'historical_embedding',
        'source_quality_gate':getattr(args,'source_quality_gate','strict')}
    manifest['review_policy'] = review_policy({**client.config, 'agent_model': client.model('agent')})
    write_json(root/'sources_index.json',index);write_json(root/'generator_base_identity.json',base)
    write_json(root/'run_manifest.json',manifest)
    for name in ('acceptance.json','assessment_status.json','scene_assessment.xlsx','report.md'):
        (root/name).unlink(missing_ok=True)

    def stage(name,prepare,validator):
        folder=root/'batches'/name;prepare(folder)
        imported=copy_compatible(folder,reuse)
        manifest['stages'][name]={'complete':False,'imported':imported,'status':'prepared'}
        write_json(root/'run_manifest.json',manifest)
        if args.agent_mode=='external':run_agent_packets(folder,client,validator)
        rows,state=collect_packets(folder,validator)
        proofs=[]
        if state['complete']:
            for batch in read_json(folder/'manifest.json')['batches']:
                p=folder/'results'/(batch['batch_id']+'.json')
                proofs.append(validate_result_execution(read_json(p),result_path=p))
        manifest['stages'][name]={**state,'imported':imported,'execution_proofs':proofs}
        write_json(root/'run_manifest.json',manifest)
        print(name+': '+('complete' if state['complete'] else 'pending'),flush=True)
        if not state['complete']:raise Pending(name)
        return rows

    try:
        # Keep compatible full normal packets, allowing a full-project historical
        # library without re-extracting successful normal models.
        values=stage('interaction-model',lambda d:old.model_packets(base,index,d),old.model_validator(index))
        full_model=merge_model(values,base,index)
        model=merge_model(select_cases(values,selected),scoped,index)
        full_ssd=build_ssd(full_model);ssd=build_ssd(model)
        write_json(root/'scene_model.json',model);write_json(root/'historical_scene_model.json',full_model)
        write_json(root/'diagrams/ssd.json',ssd);write_json(root/'historical_ssd.json',full_ssd)
        proposals=architecture_proposals(model,base);model_hash=fingerprint(model)
        approval_file=getattr(args,'architecture_approval',None)
        if not approval_file and reuse and (Path(reuse)/'model_authorization.json').exists():
            approval=read_json(Path(reuse)/'model_authorization.json')
        else:approval=read_json(approval_file) if approval_file else {}
        approved=set(approval.get('approved_proposal_ids',[])) if approval.get('model_hash')==model_hash else set()
        pending=[p for p in proposals if p['proposal_id'] not in approved]
        write_pending(root,pending,model['model_gaps'],model_hash)
        if pending or model['model_gaps']:
            manifest['pending_architecture_confirmation']=pending;manifest['model_gaps']=model['model_gaps']
            raise Pending('architecture_confirmation')
        write_json(root/'model_authorization.json',{'model_hash':model_hash,'approved_proposal_ids':sorted(approved),'proposals':proposals})
        ar_trace=[]
        if getattr(args,'ar_spec_document',None):
            ar_index=index_sources(args.ar_spec_document)
            for doc in ar_index['documents']:doc['requirement_layer']='AR'
            write_json(root/'ar_sources_index.json',ar_index)
            ar_trace=stage('gap-ar-trace',lambda d:b.ar_packets(ar_index,d),b.ar_validator(ar_index))
            write_json(root/'ar_trace.json',ar_trace)
        # Independent source graph checks precede success/feature/mount outputs.
        checks=stage('gap-graph-check',lambda d:b.graph_packets(model,ssd,index,d),b.graph_validator(index))
        write_json(root/'graph_checks.json',{'checks':checks,'passed':all(r['valid'] for r in checks)})
        if not all(r['valid'] for r in checks):raise Pending('graph_checks_rejected')
        actors=stage('interaction-participants',lambda d:participant_packets(root/'batches/interaction-model',index,d,use_case_ids=selected),participant_validator(index))
        write_participants(root,actors)
        if not all(r['passed'] for r in actors):raise Pending('participant_checks_rejected')
        features=stage('gap-features',lambda d:b.feature_packets(model,ssd,index,d),b.feature_validator(index))
        write_json(root/'interaction_features.json',features)
        normal=[copy.deepcopy(s) for u in model['use_cases'] for s in u['normal_scenarios']]
        for s in normal:
            xs={e['exchange_id']:e for e in ssd['exchanges'] if e['use_case_id']==s['use_case_id'] and e['requirement_layer']==s['requirement_layer']}
            messages=[m for m in ssd['messages'] if m['exchange_id'] in xs]
            s['ssd_message_ids']=[m['message_id'] for m in messages]
            if s['scenario_type']=='main_success':
                s['steps']=[m['text'] for m in messages]
                s['derivation']='checked_ssd_message_order'
        write_json(root/'main_success_scenarios.json',{'scenarios':normal,'ssd_hash':fingerprint(ssd)})
        routing_ssd=copy.deepcopy(ssd)
        by_features={f['exchange_id']:f for f in features}
        for exchange in routing_ssd['exchanges']:
            exchange['operation_kinds']=next(t['value'] for t in by_features[exchange['exchange_id']]['traits'] if t['name']=='operation_kinds')
        mounts=route_mounts(routing_ssd)
        for m in mounts:
            m['feature_evidence']=by_features[m['exchange_id']]['traits']
            m['mount_reason']='checked interaction operation/party/data traits and registered concern routing'
        write_json(root/'concern_mounts.json',mounts)
        g_raw=stage('gap-generation',lambda d:b.generation_packets(ssd,mounts,features,d),b.generation_validator(index))
        write_json(root/'generated_scenarios_base.json',{'scenarios':g_raw})
        from .concern_gap_repair import apply_repairs,reverse_validator
        from .concern_gap_repair_proof import preserve
        repair_ledger=preserve(root)
        g_base=copy.deepcopy(g_raw)
        g_raw=apply_repairs(root,g_raw)
        validate_generated(g_raw+normal,ssd,mounts,index)
        write_json(root/'generated_scenarios.json',{'protocol':PROTOCOL,'llm_review_used':False,'scenarios':g_raw+normal})
        # Original exceptions follow an independent extraction channel. No G
        # or feature-inferred exception is provided to the original extractor.
        if getattr(args,'checker_input',None):
            from .interaction_baseline import import_baseline
            manifest['checker_baseline_import']=import_baseline(args.checker_input,root,index,base,retain_source_packets=True)
        e_raw=stage('interaction-checker',lambda d:read_json(d/'manifest.json') if manifest.get('checker_baseline_import') else old.checker_packets(base,index,d),old.checker_validator(index))
        from .interaction_audit import checker_audit_packets,checker_audit_validator
        audit=stage('interaction-checker-audit',lambda d:checker_audit_packets(root/'batches/interaction-checker',index,d),checker_audit_validator(index))
        write_json(root/'checker_source_audit.json',{'items':audit,'passed':all(r['passed'] for r in audit)})
        if not all(r['passed'] for r in audit):raise Pending('checker_source_review')
        write_json(root/'existing_scenarios.json',{'scenarios':e_raw,'source_hash':fingerprint(index)})

        def normalize(source,graph,source_index,collection):
            from .concern_gap_normalize_diagnostics import validator as normalize_validator
            units=stage('gap-normalize-'+collection,lambda d:b.normalized_packets(source,graph,d,collection,source_index),normalize_validator(source_index))
            write_json(root/('base_source_units_'+collection+'.json'),units)
            from .concern_gap_inverse_repair import apply as apply_inverse
            units=apply_inverse(units,inverse_ledger(root,collection))
            write_json(root/('source_units_'+collection+'.json'),units)
            review=stage('gap-reverse-check-'+collection,lambda d:b.review_packets(units,source,graph,d,collection,source_index),reverse_validator)
            if collection=='G':write_json(root/'reverse_checks_G_initial.json',{'reviews':review})
            if collection=='G' and (not all(r['passed'] for r in review) or (root/'batches/gap-reverse-confirm-G/manifest.json').exists()):
                from .concern_gap_review_confirm import packets as confirm_packets,validator as confirm_validator
                confirmed=stage('gap-reverse-confirm-G',lambda d:confirm_packets(units,source,graph,source_index,review,d),confirm_validator)
                write_json(root/'reverse_checks_G_confirmed.json',{'reviews':confirmed})
                replacements={r['unit_id']:r for r in confirmed}
                review=[replacements.get(r['unit_id'],r) for r in review]
            write_json(root/('reverse_checks_'+collection+'.json'),{'reviews':review,'passed':all(r['passed'] for r in review)})
            if not all(r['passed'] for r in review):raise Pending('reverse_checks_'+collection)
            from .concern_gap_dedup import packets as dedup_packets,validator as dedup_validator,merge as dedup_merge
            dedup=stage('gap-dedup-'+collection,lambda d:dedup_packets(units,graph,collection,d),dedup_validator)
            write_json(root/('dedup_'+collection+'.json'),dedup)
            merged=dedup_merge(units,collection+'2',dedup)
            write_json(root/('units_'+collection+'.json'),merged)
            write_json(root/('source_units_'+collection+'.json'),units)
            return merged

        g=normalize(g_raw,ssd,index,'G')
        history=normalize(e_raw,full_ssd,index,'E')
        e=select_cases(history,selected)
        tests=getattr(args,'test_spec_document',None) or []
        if not tests:raise ValueError('test spec is required for provisional GT')
        test_index=index_sources(tests)
        for doc in test_index['documents']:doc['requirement_layer']='TEST'
        write_json(root/'test_sources_index.json',test_index)
        t_raw=stage('gap-test-extract',lambda d:b.test_packets(scoped,test_index,d),old.test_validator(test_index))
        write_json(root/'test_conditions.json',{'scenarios':t_raw,'gt_status':'provisional_test_spec'})
        t=normalize(t_raw,ssd,test_index,'T')
        relations={}
        from .concern_gap_comparison import validator as comparison_validator
        for name,left,right in [('EG',e,g),('TG',t,g),('TE',t,e)]:
            ambiguous=stage('gap-ambiguity-'+name,lambda d,l=left,r=right,n=name:b.comparison_packets(l,r,d,n),comparison_validator)
            relations[name]=b.exact_decisions(left,right)+ambiguous
        provisional=metrics(g,e,t,[],relations)
        missing=[u for u in g if u['scenario_id'] in provisional['missing_ids']]
        # Historical ranking never reads T. Same model/text cache reused by the
        # standard embedding client; no rerank or confidence proxy is used.
        ranking=rank(missing,history,embedding_client,manifest['recommendation_seed'])
        write_json(root/'historical_ranking.json',ranking)
        evaluated=metrics(g,e,t,ranking['selected_ids'],relations)
        write_json(root/'relations.json',relations);write_json(root/'metrics.json',evaluated)
        bundle={'protocol':PROTOCOL,'scope':manifest['scope'],'source_index':index,'test_source_index':test_index,
            'model':model,'ssd':ssd,'mounts':mounts,'features':features,'graphs':checks,
            'normal':normal,'G':g,'E':e,'history':history,'T':t,'ranking':ranking,'relations':relations,'metrics':evaluated,
            'source_generated':g_raw,'source_existing':e_raw,'source_tests':t_raw,
            'source_generated_base':g_base,'generation_repairs':repair_ledger,
            'source_units':{k:read_json(root/('source_units_'+k+'.json')) for k in ('G','E','T')},
            'base_source_units':{k:read_json(root/('base_source_units_'+k+'.json')) for k in ('G','E','T')},
            'normalization_repairs':{k:inverse_ledger(root,k) for k in ('G','E','T')},
            'ar_trace':ar_trace,
            'generation_initial_reviews':read_json(root/'reverse_checks_G_initial.json')['reviews'],
            'generation_confirmed_reviews':read_json(root/'reverse_checks_G_confirmed.json')['reviews'] if 'gap-reverse-confirm-G' in manifest['stages'] else [],
            'dedup':{k:read_json(root/('dedup_'+k+'.json')) for k in ('G','E','T')},
            'reverse_checks':{k:read_json(root/('reverse_checks_'+k+'.json')) for k in ('G','E','T')}}
        bundle['result_hash']=fingerprint(bundle)
        write_json(root/'result_bundle.json',bundle)
        export(root,bundle)
        manifest.update(complete=True,result_hash=bundle['result_hash'],metric_hash=fingerprint(evaluated))
        write_json(root/'run_manifest.json',manifest)
        return {'complete':True,'result_hash':bundle['result_hash'],'sets':evaluated['set_sizes']},0
    except Pending as exc:
        manifest['pending_stage']=str(exc);write_json(root/'run_manifest.json',manifest)
        return {'complete':False,'pending_stage':str(exc),'stages':manifest['stages']},2 if args.agent_mode=='external' else 0
    except Exception as exc:
        manifest['error']=str(exc);write_json(root/'run_manifest.json',manifest)
        raise


class Pending(Exception):
    pass
