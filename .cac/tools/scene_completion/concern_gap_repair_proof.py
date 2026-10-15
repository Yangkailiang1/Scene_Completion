"""Preserve and verify actual source-only rejection and replacement executions."""
from copy import deepcopy
from pathlib import Path
from .semantic_backend import read_json,write_json
from .sources import fingerprint
from .interaction_execution_identity import validate_result_execution,copy_execution_sidecars
from .concern_gap_repair import reverse_validator,apply_repairs
from .artifact_paths import relative_artifact_path


def preserve(root):
    root=Path(root);path=root/'generation_repairs.json'
    if not path.exists():return []
    ledger=read_json(path)
    for record in ledger:
        evidence=record.setdefault('rejection_evidence',{})
        for rejection in record['rejections']:
            key=rejection['review_result_hash']
            if key in evidence:continue
            folder=root/'batches'/rejection.get('review_stage_directory','gap-reverse-check-G')
            source=folder/'results'/(rejection['review_batch_id']+'.json')
            raw=read_json(source)
            if fingerprint(raw)!=key:raise ValueError('source rejection execution changed before preservation')
            destination=root/'repair_evidence'/key/'result.json'
            write_json(destination,raw);copy_execution_sidecars(raw,source,destination)
            packet=read_json(folder/'packets'/(rejection['review_batch_id']+'.json'))
            write_json(destination.with_name('packet.json'),packet)
            evidence[key]={'result_path':destination.relative_to(root).as_posix(),
                'packet_path':destination.with_name('packet.json').relative_to(root).as_posix()}
    write_json(path,ledger)
    return ledger


def verify(root,base,ledger,outputs):
    root=Path(root)
    if ledger!=read_json(root/'generation_repairs.json'):raise ValueError('repair ledger changed')
    source_by_id={s['scenario_id']:s for s in base}
    for record in ledger:
        if record['source_set_hash']!=fingerprint(base):raise ValueError('repair source-set fingerprint changed')
        for rejection in record['rejections']:
            paths=record['rejection_evidence'][rejection['review_result_hash']]
            packet=read_json(relative_artifact_path(root,paths['packet_path']))
            result_path=relative_artifact_path(root,paths['result_path']);raw=read_json(result_path)
            if fingerprint(raw)!=rejection['review_result_hash']:raise ValueError('rejection result changed')
            if raw['input_hash']!=packet['input_hash'] or raw['batch_id']!=packet['batch_id']:
                raise ValueError('rejection packet execution does not agree')
            validate_result_execution(raw,result_path=result_path)
            row=next(r for r in reverse_validator(packet,deepcopy(raw)) if r['unit_id']==rejection['unit_id'])
            unit=next(u for u in packet['input']['units'] if u['unit_id']==rejection['unit_id'])
            source=next(s for s in packet['input']['original_scenarios'] if s['scenario_id']==rejection['source_scenario_id'])
            if (row!=rejection['review'] or row['passed'] or unit['source_scenario_id']!=source['scenario_id']
                or source!=source_by_id[source['scenario_id']]
                or not (any(row[k] is False for k in ('source_supported','atomic','mapping_correct')) or row.get('defect_origin')=='generated_identification')):
                raise ValueError('repair is not backed by actual rejected source identification')
        if outputs[record['stage_directory']]!=record['replacements']:
            raise ValueError('replacement scenes differ from actual generator repair execution')
        manifest=read_json(root/'batches'/record['stage_directory']/'manifest.json')
        if manifest['input_hash']!=record['input_hash']:raise ValueError('repair input changed')
    return apply_repairs(root,base)
