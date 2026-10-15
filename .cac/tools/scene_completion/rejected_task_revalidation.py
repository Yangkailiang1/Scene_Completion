"""Recheck unchanged rejected executions offline after a validator correction."""
import copy
from pathlib import Path
from types import SimpleNamespace

from .case_dag import run_lock
from .semantic_backend import read_json, write_json
from .sources import fingerprint
from .interaction_execution_identity import validate_result_execution
from .response_contract import contract_view


def promote_offline(folder, validator, cache_identity=None):
    """Re-admit preserved raw returns whose only defect was the old validator.

    No model or embedding call happens here. Every promoted result is bound to
    the packet of its own original batch by input hash and is re-checked
    against the caller's current validator, so a stale attempt is skipped
    rather than allowed to stand in for the corrected rule.
    """
    folder = Path(folder)
    if not (folder / 'manifest.json').exists():
        return []
    proofs = []
    for batch in read_json(folder / 'manifest.json')['batches']:
        packet = read_json(folder / 'packets' / (batch['batch_id'] + '.json'))
        if (packet.get('batch_id') != batch['batch_id'] or packet.get('input_hash') != batch['input_hash']
                or fingerprint({k: v for k, v in packet.items() if k not in {'batch_id', 'input_hash'}}) != batch['input_hash']):
            raise ValueError('offline revalidation packet identity changed')
        target = folder / 'results' / (batch['batch_id'] + '.json')
        if target.exists():
            continue
        for attempt in sorted((folder / 'attempts').glob(batch['batch_id'] + '-*.json'),
                key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True):
            history = read_json(attempt)
            raw = history.get('result')
            if not isinstance(raw, dict) or raw.get('batch_id') != batch['batch_id'] or raw.get('input_hash') != batch['input_hash']:
                continue
            try:
                validate_result_execution(raw, result_path=attempt)
                if cache_identity:
                    cache_identity(raw)
                validator(packet, contract_view(packet, raw))
            except (ValueError, TypeError, KeyError):
                continue
            write_json(target, raw)
            proofs.append({'attempt': str(attempt.resolve()), 'attempt_hash': fingerprint(history),
                'original_error': history.get('validation_error'), 'result_hash': fingerprint(raw),
                'batch_id': batch['batch_id'], 'input_hash': batch['input_hash']})
            break
    return proofs


def offline_ready(folder, validator, cache_identity=None):
    """Whether every packet already holds a result that passes the current rule.

    Checked before an offline execute so a folder that is not yet fully provable
    from local files is skipped, instead of paying to regenerate the very return
    that is being re-admitted.
    """
    folder = Path(folder)
    if not (folder / 'manifest.json').exists():
        return False
    for batch in read_json(folder / 'manifest.json')['batches']:
        path = folder / 'results' / (batch['batch_id'] + '.json')
        if not path.exists():
            return False
        try:
            raw = read_json(path)
            validate_result_execution(raw, result_path=path)
            if cache_identity:
                cache_identity(raw)
            packet = read_json(folder / 'packets' / path.name)
            if (packet.get('batch_id') != batch['batch_id'] or packet.get('input_hash') != batch['input_hash']
                    or fingerprint({k: v for k, v in packet.items() if k not in {'batch_id', 'input_hash'}}) != batch['input_hash']):
                return False
            validator(packet, contract_view(packet, raw))
        except (ValueError, TypeError, KeyError):
            return False
    return True


def run(args):
    from .concern_gap_dag import Pipeline, rejected_target
    root = Path(args.output_dir).resolve()
    with run_lock(root):
        previous = read_json(root / 'run_manifest.json')
        saved = read_json(root / 'pipeline_arguments.json')
        saved.update(output_dir=str(root), agent_mode='prepare', auto_repair='off')
        pipeline = Pipeline(SimpleNamespace(**saved))
        try:
            if any(pipeline.manifest.get(k) != previous.get(k) for k in ('protocol', 'source_hash', 'base_hash', 'scope')):
                raise ValueError('offline rejected revalidation cannot change original sources or scope')
            def no_network(*a, **k):
                raise RuntimeError('offline rejected revalidation forbids model and embedding calls')
            for client in (*getattr(pipeline, 'batch_clients', [pipeline.client]), pipeline.embedding,
                    getattr(getattr(pipeline, 'supervisor_packets', None), 'client', None)):
                if client is not None:
                    client.agent = client.post = client.embeddings = no_network
            pipeline.build()
            pipeline.scheduler._refresh()
            cases = args.use_case_id or list(pipeline.contexts)
            results = []
            for case in cases:
                key = pipeline.key(case, args.stage)
                task = pipeline.scheduler.tasks[key]
                record = pipeline.scheduler.state['tasks'][key]
                if record['status'] == 'passed':
                    results.append({'task': key, 'status': 'passed', 'reused': True})
                    continue
                if not pipeline.scheduler._ready(task):
                    raise ValueError('rejected task dependencies must first pass')
                context = pipeline.contexts[case]
                validator = context['validators'][args.stage]
                deps = {k: read_json(root / pipeline.scheduler.state['tasks'][k]['output_file']) for k in task.deps}
                # This checks original allowed evidence and contract, not just
                # the name of a stage or a result found elsewhere on disk.
                task.compatible_failure(deps, record)
                folder = Path(rejected_target(context['root'], args.stage, record.get('failure') or {})['folder'])
                folder.resolve().relative_to(context['root'].resolve())
                # A format fix can also make the complete original batch
                # provable. Prefer that full source-bound execution when it
                # matches today's entire task, rather than binding a partial
                # repair wrapper as if it were the original semantic input.
                original = context['root'] / 'batches' / args.stage
                if task.compatible and original != folder and (original / 'manifest.json').exists():
                    promote_offline(original, validator, pipeline.packets.cache_identity)
                    if offline_ready(original, validator, pipeline.packets.cache_identity):
                        candidate = pipeline.packets.execute(original, validator)
                        try:
                            task.compatible(deps, candidate)
                        except (ValueError, KeyError, TypeError, OSError):
                            pass
                        else:
                            folder = original
                proofs = promote_offline(folder, validator, pipeline.packets.cache_identity)
                if not offline_ready(folder, validator, pipeline.packets.cache_identity):
                    # This entry point is documented as offline. A folder that
                    # cannot be proven from local files is reported back for an
                    # operator decision instead of being re-dispatched, so an
                    # offline recheck can never turn into a silent payment.
                    pipeline.scheduler.state['events'].append({'task': key,
                        'event': 'offline_rejected_revalidation_not_provable', 'round': record['rounds'],
                        'folder': str(folder), 'proofs': proofs})
                    pipeline.scheduler.save()
                    results.append({'task': key, 'status': record['status'], 'offline_ready': False,
                        'dispatched': False, 'proofs': proofs})
                    continue
                output = pipeline.packets.execute(folder, validator)
                if args.stage == 'graphs':
                    output = pipeline.component_records(output)
                write_json(context['root'] / 'active' / (args.stage + '.json'),
                    {'input_hash': record['input_hash'], 'output': output})
                pipeline.scheduler.state['events'].append({'task': key, 'event': 'offline_rejected_execution_revalidation',
                    'round': record['rounds'], 'supervisor_round': record.get('supervisor_rounds', 0), 'proofs': proofs})
                record['status'] = 'pending'
                pipeline.scheduler.save()
                pipeline.scheduler.run(pipeline.progress, allowed=[key])
                results.append({'task': key, 'status': record['status'], 'proofs': proofs})
            result = {'model_calls': 0, 'repair_rounds_preserved': True, 'tasks': results}
            write_json(root / (args.stage + '_rejected_revalidation.json'), result)
            return result, 0 if all(r['status'] == 'passed' for r in results) else 2
        finally:
            if pipeline.profiler:
                pipeline.profiler.finish('offline_rejected_revalidation')
