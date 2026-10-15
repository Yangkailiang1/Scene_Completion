"""Use-case v2 adapter: isolated channels, bounded source-only repairs and final history barrier."""
from __future__ import annotations

import copy
from pathlib import Path
import shutil

from .case_dag import Scheduler, Task, TaskBlocked, TaskRejected, CallGate, quota_error, run_lock
from .semantic_backend import read_json, write_json, collect_packets, run_agent_packets, prepare_packets, SemanticClient
from .sources import fingerprint, index_sources, validate_refs
from .response_contract import contract_view
from . import concern_gap_batches as b, interaction_batches as old
from .concern_gap import PROTOCOL, POLICY, metrics
from .interaction_cli import source_index, merge_model, architecture_proposals, write_pending
from .interaction_protocol import build_ssd, route_mounts, validate_generated
from .interaction_execution_identity import validate_result_execution, copy_execution_sidecars
from .interaction_participants import participant_packets, participant_validator
from .interaction_audit import checker_audit_packets, checker_audit_validator
from .concern_gap_repair import reverse_validator
from .concern_gap_normalize_diagnostics import validator as normalize_validator
from .concern_gap_dedup import packets as dedup_packets, validator as dedup_validator, merge as dedup_merge
from .concern_gap_comparison import validator as comparison_validator
from .concern_gap_ranking import scene_text, rank
from .interaction_scope import assessment_base
from .model_configuration import config_overrides, referenced_env_keys


def case_name(identifier):
    return fingerprint(identifier)[:16]


def contains_id(value, identifiers):
    if isinstance(value, dict):
        return any(contains_id(v, identifiers) for v in value.values())
    if isinstance(value, list):
        return any(contains_id(v, identifiers) for v in value)
    return isinstance(value, str) and value in identifiers


def retain_sidecars(raw, source, destination):
    # In-place migration/repair can already resolve the original portable
    # sidecars through an ancestor. A second copy would make native proof paths
    # ambiguous and needlessly duplicate evidence.
    try:
        validate_result_execution(raw, result_path=destination)
    except ValueError:
        copy_execution_sidecars(raw, source, destination)
        validate_result_execution(raw, result_path=destination)


def diagnosis_validator(packet, result):
    from .diagnosis import validate
    return validate(packet,result)


def proposal_hash(proposal):
    # Stable proposal identity + evidence; unrelated nodes/cases are excluded.
    return fingerprint({k: v for k, v in proposal.items() if k not in ('impact', 'approval_fingerprint')})


def approval_bindings(approval, old_model=None, base=None):
    bindings = dict(approval.get('proposal_bindings', {}))
    if old_model and approval.get('model_hash') == fingerprint(old_model):
        allowed = set(approval.get('approved_proposal_ids', []))
        for item in architecture_proposals(old_model, base):
            if item['proposal_id'] in allowed:
                bindings[item['proposal_id']] = proposal_hash(item)
    return bindings


def verify_execution_output(output):
    for record in output.get('executions', []):
        path = Path(record['result_path'])
        raw = read_json(path)
        if fingerprint(raw) != record['result_hash']:
            raise ValueError('execution output changed')
        validate_result_execution(raw, result_path=path)
        packet = read_json(path.parent.parent / 'packets' / (raw['batch_id'] + '.json'))
        if packet['input_hash'] != raw['input_hash'] or fingerprint({k: v for k, v in packet.items()
                if k not in ('batch_id', 'input_hash')}) != raw['input_hash']:
            raise ValueError('execution packet changed')


def rejected_target(case_root, name, failure):
    """Resolve the exact last rejected packet manifest, including legacy runs."""
    if failure.get('output', {}).get('folder'):
        return failure['output']
    signature = failure.get('input_hash')
    if signature:
        matches = [p.parent for p in (Path(case_root) / 'batches').glob('*/manifest.json')
            if read_json(p).get('input_hash') == signature]
        if len(matches) != 1:
            raise ValueError('last rejected input manifest is missing or ambiguous')
        return {'folder': str(matches[0].resolve())}
    return {'folder': str(Path(case_root) / 'batches' / name)}


class Packets:
    def __init__(self, root, args, client, gate):
        self.root, self.args, self.client, self.gate = Path(root), args, client, gate
        self.client.config['max_concurrency'] = 1
        # Semantic repair budget belongs to the scheduler, not an inner retry loop.
        self.client.config['semantic_max_attempts'] = 1
        self.cache_clients = []
        self.model_pool = None

    def cache_identity(self, raw):
        errors = []
        for client in (self.client, *self.cache_clients):
            try:
                self._cache_identity(raw, client)
                return
            except ValueError as exc:
                errors.append(str(exc))
        raise ValueError('; '.join(errors))

    @staticmethod
    def _cache_identity(raw, client):
        config = client.config
        actual = raw.get('model')
        if actual not in config.get('allowed_cached_models', [client.model('agent')]):
            raise ValueError('cached actual model is not authorized')
        evidence = raw.get('execution_model_evidence', {})
        if evidence.get('thinking_budget') != config.get('thinking_budget'):
            raise ValueError('cached thinking token budget differs from configured request')
        if evidence.get('api_endpoint_hash') and hasattr(client, 'base_url') and evidence['api_endpoint_hash'] != fingerprint(client.base_url):
            raise ValueError('cached endpoint differs from configured endpoint')
        from .model_configuration import request_effort
        effort = request_effort(config)
        authorized_effort = evidence.get('reasoning_effort') in config.get('allowed_cached_reasoning_efforts', [])
        if actual == client.model('agent') and not authorized_effort and (
                evidence.get('thinking') != bool(config.get('thinking')) or evidence.get('reasoning_effort') != effort):
            raise ValueError('cached thinking/effort differs from configured request')

    def import_valid(self, folder, validator):
        reuse = getattr(self.args, 'reuse_run', None)
        stage = read_json(folder / 'manifest.json')['stage']
        checker_input = getattr(self.args, 'checker_input', None)
        if not reuse and not (checker_input and stage in ('interaction-checker', 'interaction-checker-audit')):
            return
        roots = [Path(reuse)] if reuse else []
        if checker_input and stage in ('interaction-checker', 'interaction-checker-audit'):
            roots.append(Path(checker_input).resolve().parent)
        candidates = [candidate for old_root in roots for candidate in
            [old_root / 'batches' / stage, *old_root.glob('cases/*/batches/' + stage)]]
        manifest = read_json(folder / 'manifest.json')
        for previous in candidates:
            if not (previous / 'manifest.json').exists():
                continue
            by_hash = {r['input_hash']: r for r in read_json(previous / 'manifest.json')['batches']}
            for pos, batch in enumerate(manifest['batches']):
                older = by_hash.get(batch['input_hash'])
                if not older:
                    continue
                src = previous / 'results' / (older['batch_id'] + '.json')
                if not src.exists():
                    continue
                packet = read_json(previous / 'packets' / (older['batch_id'] + '.json'))
                current = read_json(folder / 'packets' / (batch['batch_id'] + '.json'))
                if {k: v for k, v in packet.items() if k not in ('batch_id', 'input_hash')} != {
                        k: v for k, v in current.items() if k not in ('batch_id', 'input_hash')}:
                    continue
                try:
                    raw = read_json(src)
                    validate_result_execution(raw, result_path=src)
                    self.cache_identity(raw)
                    validator(packet, contract_view(packet, raw))
                except (ValueError, KeyError, TypeError):
                    continue
                # Adopt ORIGINAL packet identity, never relabel the execution.
                manifest['batches'][pos] = older
                write_json(folder / 'packets' / (older['batch_id'] + '.json'), packet)
                dst = folder / 'results' / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists():
                    shutil.copyfile(src, dst)
                    retain_sidecars(raw, src, dst)
            manifest['input_hash'] = fingerprint(manifest['batches'])
            write_json(folder / 'manifest.json', manifest)

    def execute(self, folder, validator):
        worker_errors = {}
        values, state = collect_packets(folder, validator)
        for batch in read_json(folder / 'manifest.json')['batches']:
            path = folder / 'results' / (batch['batch_id'] + '.json')
            if path.exists():
                try:
                    self.cache_identity(read_json(path))
                except ValueError as exc:
                    state['complete'] = False
                    state['errors'][batch['batch_id']] = str(exc)
        if not state['complete'] and self.args.agent_mode == 'external':
            # Permit one packet at a time, rather than holding a global slot for
            # an entire use case. Offline validation can run after quota failure.
            for batch in read_json(folder / 'manifest.json')['batches']:
                path = folder / 'results' / (batch['batch_id'] + '.json')
                try:
                    if path.exists():
                        self.cache_identity(read_json(path))
                        packet = read_json(folder / 'packets' / path.name)
                        validator(packet, contract_view(packet, read_json(path)))
                        validate_result_execution(read_json(path), result_path=path)
                        continue
                except (ValueError, KeyError, TypeError):
                    pass
                from .model_access import preflight
                if self.model_pool:
                    status = self.model_pool.run_batch(folder, validator, batch['batch_id'])
                else:
                    self.gate.call(preflight, self.client)
                    status = self.gate.call(run_agent_packets, folder, self.client, validator, batch_ids=[batch['batch_id']])
                blocked = [r for r in status.get('batches', []) if r.get('failure_category') in ('model_unavailable','authentication_failed','access_denied')]
                if blocked:
                    raise TaskBlocked('awaiting_configuration', blocked)
                if quota_error(str(status)):
                    raise TaskBlocked('budget_exhausted', 'external quota exhausted')
                if not status['complete']:
                    worker_errors.update({r['batch_id']: r.get('error', 'worker failed') for r in status['batches'] if r['status'] == 'failed'})
                    attempts = sorted((folder / 'attempts').glob(batch['batch_id'] + '-*.json'))
                    if attempts:
                        latest = read_json(attempts[-1])
                        diagnostic = latest.get('response_diagnostic') or {}
                        if latest.get('result') is None and diagnostic.get('failure_category'):
                            raise TaskBlocked('pending', {'transport_failure': latest['response_diagnostic'],
                                'batch_id': batch['batch_id'], 'semantic_round_not_consumed': True})
        values, state = collect_packets(folder, validator)
        state['errors'].update(worker_errors)
        state['complete'] = state['complete'] and not worker_errors
        if not state['complete']:
            if self.args.agent_mode != 'external' and not state['errors']:
                raise TaskBlocked('pending', state)
            raise TaskRejected({**state, 'output': {'folder': str(Path(folder).resolve())}})
        proofs = []
        for batch in read_json(folder / 'manifest.json')['batches']:
            path = folder / 'results' / (batch['batch_id'] + '.json')
            raw = read_json(path)
            validate_result_execution(raw, result_path=path)
            proofs.append({'batch_id': raw['batch_id'], 'input_hash': raw['input_hash'],
                'result_path': str(path.resolve()), 'result_hash': fingerprint(raw), 'model': raw['model']})
        return {'values': values, 'folder': str(folder.resolve()), 'executions': proofs}

    def prepare(self, case_root, name, prepare, validator):
        folder = case_root / 'batches' / name
        previous = read_json(folder / 'manifest.json') if (folder / 'manifest.json').is_file() else None
        prepare(folder)
        if previous:
            from .partial_packet_reuse import reuse
            reuse(folder, previous, validator, self.cache_identity)
        self.import_valid(folder, validator)
        return folder

    def diagnose(self, case_root, name, target, failure, round_number):
        from .diagnosis import quote_catalog, rejection_ids, failure_view, focus_input, share_allowed_inputs
        original = read_json(Path(target['folder']) / 'manifest.json')
        packets = [read_json(Path(target['folder']) / 'packets' / (row['batch_id'] + '.json')) for row in original['batches']]
        errors=set(failure.get('errors',{}))|set(failure.get('pending',[]))
        rejected = rejection_ids(failure, target)
        scoped=[p for p in packets if p['batch_id'] in errors or contains_id(p['input'],rejected) or
            ((Path(target['folder'])/'results'/(p['batch_id']+'.json')).exists() and
                contains_id(read_json(Path(target['folder'])/'results'/(p['batch_id']+'.json')),rejected))]
        if scoped:packets=scoped
        failed_outputs = []
        for row in packets:
            attempts = sorted((Path(target['folder']) / 'attempts').glob(row['batch_id'] + '-*.json'))
            if attempts:
                history = read_json(attempts[-1])
                failed_outputs.append({'batch_id': row['batch_id'], 'validation_error': history.get('validation_error'),
                    'result': history.get('result')})
        # Only the target's original permitted input channel is supplied.
        allowed=share_allowed_inputs([focus_input({k:v for k,v in p['input'].items()
            if k not in ('skill','extraction_skills','execution_versions')}, rejected) for p in packets])
        payload = {'stage': name, 'failure': failure_view(failure), 'allowed_inputs': allowed,
            'evidence_catalog':quote_catalog(allowed),
            'round': round_number, 'repair_policy': 'source-only; preserve successful records; never add unconfirmed model items',
            'failed_outputs_from_same_channel': failed_outputs}
        instructions=[
            'Diagnose the actual rejection using ONLY these allowed stage inputs. Do not ask for other G/E/T collections.',
            'Choose repair for actual format/citation/structure or model defects; recheck for a checker misjudgment supported by the original source; confirm for source conflicts, insufficient evidence or new components/calls/concerns/spec changes.',
            'Explain exact rejected items and targeted changes; preserve unrelated successful items. Unknown information cannot be invented. Quote supplied original evidence for semantic judgments.',
            'Prefer evidence_refs containing supplied DQ IDs; tools resolve their original literal quotes. Do not paraphrase quotes. Direct evidence_quotes must be exact original string fragments, not JSON-escaped representations.',
        ]
        contract={'action':'repair|recheck|confirm','reason':'source-based diagnosis','evidence_refs':[],'evidence_quotes':[],'targets':[]}
        ledger_path=case_root/'diagnosis_format_budget.json'
        ledger=read_json(ledger_path) if ledger_path.exists() else {}
        key=fingerprint([payload,self.client.model('agent'),self.client.config.get('reasoning_effort'),self.client.config.get('thinking')])
        record=ledger.setdefault(key,{'invalid_outputs':0,'feedback':None})
        limit=self.client.config.get('diagnosis_max_format_attempts',2)
        if type(limit) is not int or not 1<=limit<=2:raise ValueError('diagnosis_max_format_attempts must be 1 or 2')
        if record.get('valid_folder'):
            result=self.execute(Path(record['valid_folder']),diagnosis_validator)
            return result['values'][0],result
        if record['invalid_outputs']:
            # A rejection may have come from the checker rule rather than from
            # the return itself. Re-admit the preserved original return offline,
            # under the current rule, instead of paying to regenerate it.
            from .rejected_task_revalidation import offline_ready,promote_offline
            for index in range(record['invalid_outputs']):
                previous=case_root/'batches'/(name+'-diagnosis-'+str(round_number)+('-format-'+str(index) if index else ''))
                promote_offline(previous,diagnosis_validator,self.cache_identity)
                if not offline_ready(previous,diagnosis_validator,self.cache_identity):
                    continue
                result=self.execute(previous,diagnosis_validator)
                record['valid_folder']=str(previous.resolve());write_json(ledger_path,ledger)
                return result['values'][0],result
        while record['invalid_outputs']<limit:
            attempt=record['invalid_outputs']
            folder=case_root/'batches'/(name+'-diagnosis-'+str(round_number)+('-format-'+str(attempt) if attempt else ''))
            data={**payload,**({'diagnosis_format_feedback':record['feedback']} if attempt else {})}
            prepare_packets(folder,'gap-diagnosis',[data],instructions,contract)
            try:result=self.execute(folder,diagnosis_validator)
            except TaskRejected as exc:
                record.update(invalid_outputs=attempt+1,feedback=exc.details)
                write_json(ledger_path,ledger)
            else:
                record['valid_folder']=str(folder.resolve());write_json(ledger_path,ledger)
                return result['values'][0],result
        raise TaskBlocked('diagnosis_blocked',{'failure_category':'diagnosis_protocol','semantic_round_reserved':True,
            'original_stage':name,'original_failure_preserved':True,'invalid_diagnoses':record['invalid_outputs'],
            'reason':'bounded diagnosis-format attempts exhausted; original target was not regenerated'})

    def repaired(self, case_root, name, target, validator, diagnosis, failure, round_number):
        from .diagnosis import rejection_ids, failure_view, repair_input
        source = Path(target['folder'])
        original = read_json(source / 'manifest.json')
        payloads, instructions, contract, retained, preserved_by_prior, preserved_models = [], None, None, [], {}, {}
        ordered_slots = []
        generation_patches = False
        normal_item_patch = False
        rejected_ids = rejection_ids(failure, target) if isinstance(failure, dict) else set()
        allowed_components, allowed_exchanges = set(), set()
        review_folder = failure.get('output', {}).get('folder') if isinstance(failure, dict) else None
        if review_folder and original['stage'] == 'interaction-model':
            review_manifest = read_json(Path(review_folder) / 'manifest.json')
            for review_batch in review_manifest['batches']:
                data = read_json(Path(review_folder) / 'packets' / (review_batch['batch_id'] + '.json'))['input']
                for node in data.get('nodes', []):
                    if node['node_id'] in rejected_ids:
                        allowed_components.update(node.get('source_component_ids', []))
                for exchange in data.get('exchanges', []):
                    if exchange['exchange_id'] in rejected_ids:
                        allowed_exchanges.add(exchange['local_id'])
        for row in original['batches']:
            packet = read_json(source / 'packets' / (row['batch_id'] + '.json'))
            path = source / 'results' / (row['batch_id'] + '.json')
            prior = read_json(path) if path.exists() else None
            prior_attempt = None
            is_comparison = original['stage'].startswith('gap-ambiguity-')
            prior_is_current = False
            if is_comparison and prior is not None:
                # Results can predate the current pair validator. Reuse one
                # only after both its execution identity and current contract
                # still validate; otherwise prefer the latest real semantic
                # attempt over the worker's synthetic cache-revalidation copy.
                try:
                    self.cache_identity(prior)
                    validator(packet, contract_view(packet, prior))
                    validate_result_execution(prior, result_path=path)
                except (ValueError, KeyError, TypeError):
                    pass
                else:
                    prior_is_current = True
            # Failed responses are kept by the semantic worker in attempts.
            # A cache-revalidation snapshot is useful as a last resort, but
            # must not shadow an actual semantic attempt from this packet.
            if is_comparison and (prior is None or not prior_is_current):
                attempts = sorted((source / 'attempts').glob(row['batch_id'] + '-*.json'))
                candidates = []
                for attempt_path in attempts:
                    attempt = read_json(attempt_path)
                    candidate = attempt.get('result')
                    if (not isinstance(candidate, dict)
                            or candidate.get('batch_id') != row['batch_id']
                            or candidate.get('input_hash') != row['input_hash']):
                        continue
                    try:
                        validate_result_execution(candidate)
                        self.cache_identity(candidate)
                    except (ValueError, KeyError, TypeError):
                        continue
                    attempt_number = attempt.get('attempt', -1)
                    if type(attempt_number) is not int:
                        attempt_number = -1
                    candidates.append((bool(attempt.get('cached_result_revalidation')),
                        attempt_path.stat().st_mtime_ns, attempt_number,
                        attempt_path.name, attempt_path, candidate))
                semantic = [candidate for candidate in candidates if not candidate[0]]
                selected = max(semantic or candidates, default=None,
                    key=lambda candidate: candidate[:4])
                if selected is not None:
                    prior_attempt, prior = selected[4], selected[5]
            elif prior is None:
                attempts = sorted((source / 'attempts').glob(row['batch_id'] + '-*.json'))
                if attempts:
                    prior_attempt = attempts[-1]
                    prior = read_json(prior_attempt).get('result')
            # Do not regenerate packets that contain no rejected item. For
            # structural failures, the worker's missing/error IDs identify them.
            errors = set(failure.get('errors', {})) | set(failure.get('pending', [])) if isinstance(failure, dict) else set()
            affected = (not rejected_ids and not errors) or row['batch_id'] in errors or contains_id(packet['input'], rejected_ids) or contains_id(prior, rejected_ids)
            # Raw G responses do not carry the stable IDs assigned by the
            # validator. Resolve that identity before deciding to retain a
            # packet; otherwise a source-level repair silently becomes a no-op.
            if original['stage'] == 'gap-generation' and rejected_ids and prior:
                affected = affected or any(value['scenario_id'] in rejected_ids
                    for value in validator(packet, contract_view(packet, prior)))
            if not affected and path.exists() and (not is_comparison or prior_is_current):
                validator(packet, contract_view(packet, prior))
                validate_result_execution(prior, result_path=path)
                retained.append((row, packet, path))
                ordered_slots.append(('retained', row))
                continue
            if original['stage'].startswith('gap-ambiguity-') and prior_attempt and prior:
                from .comparison_patch import build_comparison_patch
                self.cache_identity(prior)
                patch = build_comparison_patch(source / 'packets' / (row['batch_id'] + '.json'),
                    prior_attempt, validator)
                if patch:
                    ordered_slots.append(('new', len(payloads)))
                    payloads.append(patch['payload'])
                    instructions, contract = patch['instructions'], packet['output_contract']
                    continue
            if original['stage'] == 'interaction-model' and prior_attempt and prior:
                # Repair a cited hierarchy row without asking the supervisor to
                # rewrite an otherwise valid normal model. The original raw
                # execution remains bound to the patch and is checked again.
                from .normal_item_patch import prepare as prepare_normal_patch
                try:
                    validator(packet, contract_view(packet, prior))
                except ValueError as exc:
                    patch = prepare_normal_patch(packet, prior,
                        source / 'packets' / (row['batch_id'] + '.json'),
                        prior_attempt, str(exc), source_index(self.args))
                else:
                    patch = None
                if patch:
                    self.cache_identity(prior)
                    normal_item_patch = True
                    ordered_slots.append(('new', len(payloads)))
                    payloads.append(patch['payload'])
                    instructions, contract = patch['instructions'], patch['contract']
                    continue
            if prior:
                try:
                    for value in validator(packet, contract_view(packet, prior)):
                        identity = value.get('unit_id') or value.get('scenario_id')
                        if identity and rejected_ids and identity not in rejected_ids and value.get('source_scenario_id') not in rejected_ids:
                            preserved_by_prior.setdefault(fingerprint(prior), []).append(copy.deepcopy(value))
                    if original['stage'] == 'interaction-model' and (allowed_components or allowed_exchanges):
                        preserved_models[fingerprint(prior)] = {field: [copy.deepcopy(item) for item in prior[field]
                            if item[id_field] not in allowed] for field, id_field, allowed in
                            [('components', 'component_id', allowed_components), ('exchanges', 'local_id', allowed_exchanges)]}
                except (ValueError, KeyError, TypeError):
                    pass
            repaired_input = repair_input(packet['input'])
            prior_view = prior
            if original['stage'].startswith('gap-reverse-check-') and prior and path.exists() and rejected_ids:
                prior_reviews = validator(packet, contract_view(packet, prior))
                review_ids = {value['unit_id'] for value in prior_reviews
                    if not value['passed'] and value['unit_id'] in rejected_ids}
                if review_ids:
                    repaired_input['units'] = [unit for unit in packet['input']['units'] if unit['unit_id'] in review_ids]
                    source_ids = {unit['source_scenario_id'] for unit in repaired_input['units']}
                    repaired_input['original_scenarios'] = [value for value in packet['input']['original_scenarios']
                        if value['scenario_id'] in source_ids]
                    repaired_input['original_evidence'] = [value for value in packet['input'].get('original_evidence', [])
                        if value['scenario_id'] in source_ids]
                    repaired_input['review_patch'] = {'rejected_unit_ids': sorted(review_ids),
                        'prior_execution': {'result_path': str(path.resolve()), 'result_hash': fingerprint(prior),
                            'packet_path': str((source/'packets'/path.name).resolve()), 'packet_hash': fingerprint(packet)}}
                    prior_view = [value for value in prior_reviews if value['unit_id'] in review_ids]
            if original['stage'] == 'gap-generation' and prior and path.exists():
                validated_prior = validator(packet, contract_view(packet, prior))
                rejected_sources = [value for value in validated_prior if value['scenario_id'] in rejected_ids]
                if rejected_sources:
                    generation_patches = True
                    mounts = {value['mount_id'] for value in rejected_sources}
                    repaired_input['mounts'] = [mount for mount in repaired_input['mounts'] if mount['mount_id'] in mounts]
                    exchanges = {mount['exchange_id'] for mount in repaired_input['mounts']}
                    repaired_input['exchanges'] = [exchange for exchange in repaired_input['exchanges'] if exchange['exchange_id'] in exchanges]
                    if repaired_input.get('skill') == repaired_input.get('generator_skill'):
                        repaired_input.pop('skill', None)
                    if isinstance(repaired_input.get('checked_features'), list):
                        repeated_traits = [trait for mount in repaired_input['mounts']
                            for trait in mount.get('feature_evidence', [])]
                        repaired_input['checked_features'] = [{**value,
                            'traits': [trait for trait in value.get('traits', []) if trait not in repeated_traits],
                            'shared_traits_location': 'mounts[].feature_evidence'}
                            for value in repaired_input['checked_features'] if value['exchange_id'] in exchanges]
                    parties = {value[key] for value in repaired_input['exchanges']
                        for key in ('from_node', 'to_node') if key in value}
                    if parties and isinstance(repaired_input.get('nodes'), list):
                        repaired_input['nodes'] = [value for value in repaired_input['nodes'] if value['node_id'] in parties]
                    repaired_input['directed_patch'] = {'rejected_scenario_ids': [value['scenario_id'] for value in rejected_sources],
                        'prior_execution': {'result_path': str(path.resolve()), 'result_hash': fingerprint(prior),
                            'packet_path': str((source/'packets'/path.name).resolve()), 'packet_hash': fingerprint(packet)}}
                    prior_view = rejected_sources
            rejection_view = failure_view(failure)
            if repaired_input.get('directed_patch'):
                scope = set(repaired_input['directed_patch']['rejected_scenario_ids'])
                rejection_view = {**rejection_view, 'findings': [finding for finding in rejection_view.get('findings', [])
                    if finding.get('source_scenario_id') in scope]}
            ordered_slots.append(('new', len(payloads)))
            payloads.append({**repaired_input, 'bounded_repair': {'diagnosis': diagnosis,
                'rejection': rejection_view, 'prior_output': prior_view, 'round': round_number}})
            instructions, contract = packet['instructions'], packet['output_contract']
        folder = case_root / 'batches' / (name + '-repair-' + str(round_number))
        if generation_patches:
            contract = {'replacements': [{'source_scenario_id': 'exact rejected scenario ID',
                'scenarios': [{'name': 'atomic abnormal condition', 'exception_object': 'object',
                    'operation': 'operation', 'failure_mechanism': 'one actual cause',
                    'trigger_condition': 'specific abnormal condition', 'necessary_conditions': [],
                    'source_refs': [], 'pending_details': []}]}]}
            instructions = [*(instructions or []),
                'DIRECTED PATCH: Return replacements for every directed_patch.rejected_scenario_ids exactly once; no other scenarios or mount items. Repair the specific abnormal cause using its supplied normal SSD/mount and original evidence only. Tools retain all unrelated proven output verbatim. Keep at least one valid atomic scenario per rejected source and preserve its actual mount.']
        if original['stage'].startswith('gap-reverse-check-'):
            instructions = [*(instructions or []),
                'Recheck only the supplied failed units. Tools merge the previous successful reviews unchanged. object_code/cause_code/condition_codes are open semantic snake_case identities, not a closed enum. Type mismatch and format violation are distinct mechanisms; no invented allowed-code list can reject invalid_type. Unknown legal concrete types remain pending, not a reason to change the actual cause. Keep all decisions source-based; valid source-supported conditions may still be rejected for a real defect.']
        if original['stage'].startswith('gap-ambiguity-'):
            instructions = [*(instructions or []),
                'Reassess the actual condition relations, not just output formatting. compatible_conditions means NON-CONTRADICTORY, not complete. Missing checker prerequisites may justify partial with compatible_conditions=true and exact missing evidence. An actual contradiction or different object/operation/cause is unmatched. Never flip flags automatically. For unmatched return only pair IDs, status, and a concrete reason; omit accepted evidence.',
                'Partial never compensates for different objects or operations. If your semantic judgment is same_object=false or same_operation=false, choose unmatched. A partial needs a concrete missing CHECKER condition; same identity with every checker condition supported is full. Answer EVERY supplied expected pair, including unmatched; never return only the promising match. Tools preserve the other previously validated pairs.']
        repair_instructions = list(instructions or [])
        if not normal_item_patch:
            repair_instructions.append('Repair ONLY the actually rejected items, or recheck them from original evidence when diagnosed as a checker error. Preserve all other supplied successful entries. No extra information or new modeling items are authorized. Return the ORIGINAL output contract, with fresh execution proof.')
        prepare_packets(folder, original['stage'], payloads, repair_instructions, contract)
        manifest = read_json(folder / 'manifest.json')
        new_rows = manifest['batches'][:]
        for row, packet, path in retained:
            write_json(folder / 'packets' / path.name, packet)
            destination = folder / 'results' / path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            retain_sidecars(read_json(path), path, destination)
        manifest['batches'] = [value if kind == 'retained' else new_rows[value] for kind, value in ordered_slots]
        manifest['input_hash'] = fingerprint(manifest['batches'])
        write_json(folder / 'manifest.json', manifest)
        def preserve_successful(packet, result):
            values = validator(packet, result)
            prior = packet['input'].get('bounded_repair', {}).get('prior_output')
            prior_hash = (packet['input'].get('directed_patch', {}).get('prior_execution', {}).get('result_hash')
                or packet['input'].get('review_patch', {}).get('prior_execution', {}).get('result_hash') or fingerprint(prior))
            for original in preserved_by_prior.get(prior_hash, []):
                if original not in values:
                    raise ValueError('directed repair changed an unrelated successful scenario/unit')
            for field, originals in preserved_models.get(fingerprint(prior), {}).items():
                for original in originals:
                    if original not in result.get(field, []):
                        raise ValueError('directed normal repair changed an unrelated successful ' + field)
            return values
        return self.execute(folder, preserve_successful)


class Pipeline:
    def __init__(self, args):
        from .role_cli import _client
        from .review import load_ecnu_env_file
        self.args, self.root = copy.copy(args), Path(args.output_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        from .performance import Profiler
        self.profiler = Profiler(self.root) if getattr(args,'profile',False) else None
        previous_path = self.root / 'run_manifest.json'
        previous = read_json(previous_path) if previous_path.exists() else None
        if previous and previous.get('protocol') != PROTOCOL:
            raise ValueError('use a separate directory for a different method protocol')
        if previous and previous.get('execution_mode') != 'case-dag':
            write_json(self.root / 'legacy_stage_barrier_manifest.json', previous)
        if not getattr(self.args, 'reuse_run', None) and (self.root / 'legacy_stage_barrier_manifest.json').exists():
            self.args.reuse_run = str(self.root)
        self.index = source_index(args)
        raw = read_json(args.model)
        self.base = {'use_cases': [{k: u[k] for k in ('use_case_id', 'use_case_name', 'architecture', 'source_use_case_ids') if k in u}
            for u in raw['use_cases']], 'system_composition': {'nodes': raw.get('system_composition', {}).get('nodes', [])}}
        self.selected = {u['use_case_id'] for u in assessment_base(self.base, getattr(args, 'use_case_id', None))['use_cases']}
        self.client = _client(args, self.root)
        self.client.profiler = self.profiler
        self.gate = CallGate(self.client.config.get('max_concurrency', 1), adaptive=self.client.config.get('adaptive_concurrency', True),
            on_change=lambda state: write_json(self.root/'concurrency_status.json', state),
            pause_file=self.root / 'pause_requested.json')
        previous_limit = self.root/'concurrency_status.json'
        if previous_limit.exists():
            old_limit = read_json(previous_limit)
            if old_limit['configured_max'] == self.gate.limit:
                self.gate.effective_limit = min(self.gate.limit, old_limit['effective_max'])
                import time
                self.gate.retry_not_before=time.monotonic()+max(0.,min(300.,old_limit.get('not_before_unix',0)-time.time()))
        path = getattr(args, 'embedding_config', None) or getattr(args, 'config', None)
        config = config_overrides(read_json(path) if path else {}, args)
        if getattr(args, 'env_file', None):
            load_ecnu_env_file(args.env_file, extra_keys=referenced_env_keys(config))
        config['cache_dir'] = str(self.root / '.embedding_cache')
        self.embedding = SemanticClient(config)
        self.embedding.profiler = self.profiler
        embedding_post = self.embedding.post
        embedding_gate = self.gate.budget_scope()
        self.embedding.post = lambda *a, **k: embedding_gate.call(embedding_post, *a, **k)
        embedding_vectors = self.embedding.embeddings
        def checked_vectors(texts):
            from .model_access import with_embedding_preflight
            return with_embedding_preflight(self.embedding, texts, embedding_vectors)
        self.embedding.embeddings = checked_vectors
        self.embedding_lock = __import__('threading').Lock()
        self.packets = Packets(self.root, self.args, self.client, self.gate)
        from .quota_profiles import configured_clients, BatchProfiles
        self.batch_clients = configured_clients(self.args, self.root, self.client)
        self.packets.cache_clients.extend(self.batch_clients[1:])
        if len(self.batch_clients) > 1:
            self.packets.model_pool = BatchProfiles(self.root, self.batch_clients, self.gate)
        self.supervisor_packets = None
        supervisor_config = self.client.config.get('supervisor_config')
        if supervisor_config:
            path = Path(supervisor_config)
            if not path.is_absolute() and not path.exists():
                path = Path(args.config).resolve().parent / path
            supervisor_args = copy.copy(self.args)
            supervisor_args.config = str(path)
            supervisor_args.agent_model = None
            supervisor_args.agent_runtime = None
            supervisor_args.max_concurrency = self.gate.limit
            supervisor = _client(supervisor_args, self.root / 'supervisor')
            supervisor.profiler = self.profiler
            self.supervisor_packets = Packets(self.root, self.args, supervisor, self.gate.budget_scope())
            self.supervisor_packets.cache_clients.extend(self.batch_clients)
            self.packets.cache_clients.append(supervisor)
        self.scheduler = Scheduler(self.root, concurrency=self.gate.limit, profiler=self.profiler,
            auto_repair=getattr(args, 'auto_repair', None) or self.client.config.get('auto_repair', 'bounded'),
            max_rounds=getattr(args, 'max_repair_rounds', None) if getattr(args, 'max_repair_rounds', None) is not None
                else self.client.config.get('max_repair_rounds', 2))
        self.scheduler.resume_external_budget()
        self.history = None
        self.history_run = getattr(args, 'history_run', None)
        self.test_index = index_sources(getattr(args, 'test_spec_document', None) or [])
        for doc in self.test_index['documents']:
            doc['requirement_layer'] = 'TEST'
        if not self.test_index['documents']:
            raise ValueError('test spec is required for provisional GT')
        self.approval = {}
        approval_path = getattr(args, 'architecture_approval', None)
        reuse = Path(self.args.reuse_run) if getattr(self.args, 'reuse_run', None) else None
        if approval_path:
            self.approval = read_json(approval_path)
        elif reuse and (reuse / 'model_authorization.json').exists():
            self.approval = read_json(reuse / 'model_authorization.json')
        old_model = read_json(reuse / 'scene_model.json') if reuse and (reuse / 'scene_model.json').exists() else None
        self.bindings = approval_bindings(self.approval, old_model, self.base)
        ar_paths=getattr(args,'ar_spec_document',None) or []
        if ar_paths:
            self.ar_index=index_sources(ar_paths)
        else:
            from .inline_ar import from_sr
            self.ar_index=from_sr(self.index)
        for doc in self.ar_index['documents']:
            doc['requirement_layer'] = 'AR'
        self.manifest = {'protocol': PROTOCOL, 'policy': POLICY, 'execution_mode': 'case-dag', 'complete': False,
            'accepted': False, 'versions': b.versions(), 'source_hash': fingerprint(self.index), 'base_hash': fingerprint(self.base),
            'scope': {'kind': 'representative' if getattr(args, 'use_case_id', None) else 'full',
                'use_case_ids': sorted(self.selected), 'granularity': 'complete_use_cases'},
            'model': self.client.model('agent'), 'embedding_model': self.embedding.model('embedding'),
            'recommendation_seed': getattr(args, 'recommendation_seed', 42), 'rerank': False,
            'auto_repair': self.scheduler.auto_repair, 'max_repair_rounds': self.scheduler.max_rounds,
            'max_concurrency': self.gate.limit, 'stages': {}}
        from .model_configuration import review_policy
        self.manifest['review_policy'] = review_policy(self.client.config)
        self.manifest['review_execution_required'] = True
        self.manifest['usage_accounting_policy'] = self.client.config.get('usage_accounting_policy', 'strict')
        for name, value in [('sources_index', self.index), ('test_sources_index', self.test_index),
                ('generator_base_identity', self.base), ('run_manifest', self.manifest)]:
            write_json(self.root / (name + '.json'), value)
        write_json(self.root / 'pipeline_arguments.json', {k: v for k, v in vars(self.args).items()
            if isinstance(v, (str, int, float, bool, list, type(None))) and k not in ('api_key', 'key')})
        if self.ar_index['documents']:
            write_json(self.root / 'ar_sources_index.json', self.ar_index)
        self.contexts = {}

    def preflight(self):
        from .model_configuration import review_policy
        self.manifest['review_policy'] = review_policy(self.client.config)
        if self.args.agent_mode != 'external':
            return
        # Existing successful stages need no new capability probe. Only check
        # the backend when an actual external request is about to be needed.
        # The packet worker and vector stage probe lazily, so a fully cached
        # resume does not issue new requests solely to test availability.

    def key(self, case, stage):
        return case + ':' + stage

    def values(self, deps, case, stage):
        return deps[self.key(case, stage)]['values']

    def add(self, case, name, deps, execute, *, repair=None, lane='progress', version=None, verify=None):
        context = self.contexts[case]
        self.scheduler.add(Task(self.key(case, name), case, name, tuple(self.key(case, d) for d in deps),
            version if version is not None else context['version'], lane, execute, repair, verify))

    def semantic(self, case, name, deps, prepare, validator, *, reject=None, repair_target=None, lane='progress', transform=None):
        context, root = self.contexts[case], self.contexts[case]['root']
        def pending_source_correction():
            if name != 'reverse-G' or not (root / 'repair_rounds').exists():
                return None
            generation = self.scheduler.state['tasks'].get(self.key(case, 'G-generate'), {})
            output_file = generation.get('output_file')
            if not output_file:
                return None
            from .source_candidate_recovery import find_pending_source_correction
            return find_pending_source_correction(root,
                read_json(self.scheduler.root / output_file), context['validators'],
                self.packets.cache_identity, case_prefix=case)
        def execute(inputs, record):
            pending = pending_source_correction()
            if pending:
                # A new verdict on the old source cannot discharge a proven
                # outstanding source defect. Continue its real repaired candidate.
                raise TaskRejected(pending['failure'])
            # A successful directed repair is an alternate proven output, not a
            # forged result in the original packet. Reuse only for the same inputs.
            active = root / 'active' / (name + '.json')
            if active.exists():
                saved = read_json(active)
                if saved['input_hash'] == record['input_hash']:
                    verify(saved['output'])
                    output = saved['output']
                else:
                    try:
                        compatible(inputs, saved['output'])
                    except (ValueError, KeyError, OSError, TypeError, TaskBlocked):
                        output = None
                    else:
                        # Deterministic upstream metadata changes can invalidate
                        # this record without changing its permitted source.
                        # Keep the proven directed result, including source-
                        # repair lineage, instead of falling back to the initial
                        # (possibly superseded) packet output.
                        output = saved['output']
            else:
                output = None
            if output is None:
                folder = self.packets.prepare(root, name, lambda d: prepare(inputs, d), validator)
                output = self.packets.execute(folder, validator)
            if transform:
                output = transform(output)
            if reject:
                findings = reject(output['values'])
                if findings:
                    write_json(root / 'rejections' / (name + '.json'), {'findings': findings, 'output': output})
                    raise TaskRejected({'findings': findings, 'output': output})
            return output
        def repair_with(packets, inputs, record, *, supervising=False):
            failure = record.get('failure') or {}
            candidates = failure.get('candidate_replacements', {})
            source_progress = failure.get('candidate_source_repair')
            # Recover a pre-migration rejected repair only from its exact latest
            # journal and complete, validated cached packets. These are still
            # candidates, never promoted to passed before the failed review.
            if name == 'reverse-G' and not candidates and record.get('supervisor_rounds', 0) > 1:
                previous_round = record['supervisor_rounds'] - (1 if supervising else 0)
                journal_path = root / 'repair_rounds' / (name + '-supervisor-' + str(previous_round) + '.json')
                generated_folder = root / 'batches' / ('G-generate-supervisor-repair-' + str(previous_round))
                normalized_folder = root / 'batches' / ('normalize-G-after-source-repair-' + str(record['rounds']))
                if journal_path.exists() and generated_folder.exists() and normalized_folder.exists():
                    journal = read_json(journal_path)
                    rejected_sources = [r.get('source_scenario_id') for r in journal['failure'].get('findings', [])]
                    if rejected_sources and all(rejected_sources):
                        def cached(folder, check):
                            values, status = collect_packets(folder, check)
                            if not status['complete']:
                                raise ValueError('prior repair candidate is incomplete; do not regenerate or promote it')
                            proofs = []
                            for row in read_json(folder / 'manifest.json')['batches']:
                                path = folder / 'results' / (row['batch_id'] + '.json')
                                raw = read_json(path)
                                validate_result_execution(raw, result_path=path)
                                self.packets.cache_identity(raw)
                                proofs.append({'batch_id': raw['batch_id'], 'input_hash': raw['input_hash'],
                                    'result_path': str(path.resolve()), 'result_hash': fingerprint(raw), 'model': raw['model']})
                            return {'values': values, 'folder': str(folder.resolve()), 'executions': proofs}
                        generation = cached(generated_folder, context['validators']['G-generate'])
                        normalization = cached(normalized_folder, context['validators']['normalize-G'])
                        reviewed_ids = {r['unit_id'] for r in failure.get('output', {}).get('values', [])}
                        if reviewed_ids == {r['unit_id'] for r in normalization['values']}:
                            from .directed_patch import validate_generation_progress
                            validate_generation_progress(journal['old_output']['values'], generation['values'], rejected_sources)
                            candidates = {self.key(case, 'G-generate'): generation, self.key(case, 'normalize-G'): normalization}
                            source_progress = {'generation_task': self.key(case, 'G-generate'),
                                'prior_output_hash': fingerprint(journal['old_output']),
                                'corrected_output_hash': fingerprint(generation), 'rejected_source_ids': rejected_sources}
            inputs = {**inputs, **candidates}
            upstream = bool(repair_target and failure.get('findings'))
            target_name = repair_target if upstream else name
            if name == 'reverse-G' and any(not r.get('source_supported', True) or not r.get('atomic', True)
                    for r in failure.get('findings', [])):
                target_name = 'G-generate'
                by_unit = {u['unit_id']: u['source_scenario_id'] for u in self.values(inputs, case, 'normalize-G')}
                failure = {**failure, 'findings': [{**r, 'source_scenario_id': by_unit.get(r.get('unit_id'))}
                    for r in failure['findings']]}
            target_key = self.key(case, target_name)
            if upstream:
                target = inputs[target_key]
                target_validator = context['validators'][target_name]
            else:
                target = failure.get('output')
                if not target:
                    target = rejected_target(root, name, failure)
                target_validator = validator
            if supervising:
                revisions = [r for r in record.get('supervisor_continuations', [])
                    if r['revision_id'] == record.get('active_supervisor_revision')]
                action = revisions[0]['plan'].get('action', 'repair') if revisions else 'repair'
                diagnosis = {'action': action, 'reason': 'Supervisor takeover of the last rejected output. Re-read only the allowed original sources; correct the actual rejection and validate the complete output contract. Preserve all unrelated entries. Do not weaken checks, invent evidence, introduce unapproved modeling items or copy E/GT into normal modeling/G.'}
                # The controller's cross-stage diagnosis is audit evidence only.
                # The semantic repair receives its original allowed inputs and
                # current validator errors, never arbitrary controller prose
                # which could carry checker/test answers into normal/G.
                proof = {'kind': 'supervisor_handoff', 'batch_rounds_preserved': record['rounds'],
                    'supervisor_round': record['supervisor_rounds'], 'model': packets.client.model('agent'),
                    'controller_revision': record.get('active_supervisor_revision')}
            else:
                diagnosis, proof = packets.diagnose(root, name, target, failure, record['rounds'])
            round_label = ('supervisor-' + str(record['supervisor_rounds'])) if supervising else str(record['rounds'])
            write_json(root / 'repair_rounds' / (name + '-' + round_label + '.json'),
                {'diagnosis': diagnosis, 'execution': proof, 'old_output': target, 'failure': failure})
            if diagnosis['action'] == 'confirm':
                raise TaskBlocked('awaiting_confirmation', diagnosis)
            if diagnosis['action'] == 'recheck':
                repair_output = packets.repaired(root, name, failure.get('output', target), validator,
                    diagnosis, failure, record['rounds'])
                if transform:
                    repair_output = transform(repair_output)
                if reject:
                    findings = reject(repair_output['values'])
                    if findings:
                        raise TaskRejected({'findings': findings, 'output': repair_output,
                            'candidate_replacements': candidates, 'candidate_source_repair': source_progress})
                if candidates:
                    repair_output['_replacements'] = candidates
                    repair_output['_source_repair'] = source_progress
                    # Persist the complete checked promotion before any active
                    # pointer can move ahead of the scheduler's task records.
                    self.scheduler.stage_promotion(self.key(case, name), repair_output)
                    for key, value in candidates.items():
                        write_json(root / 'active' / (key.split(':', 1)[1] + '.json'), {
                            'input_hash': self.scheduler.state['tasks'][key]['input_hash'], 'output': value})
                write_json(root / 'active' / (name + '.json'), {'input_hash': record['input_hash'], 'output': repair_output})
                return repair_output
            changed = packets.repaired(root, target_name + ('-supervisor' if supervising else ''), target,
                target_validator, diagnosis, failure, record['supervisor_rounds'] if supervising else record['rounds'])
            source_repair = None
            if name == 'reverse-G' and target_name == 'G-generate':
                from .directed_patch import validate_generation_progress
                rejected = [r['source_scenario_id'] for r in failure['findings']]
                validate_generation_progress(target['values'], changed['values'], rejected)
                source_repair = {'rejected_source_ids': rejected, 'generation_task': target_key,
                    'prior_output_hash': fingerprint(target), 'corrected_output_hash': fingerprint(changed)}
            if upstream:
                # Takeover applies to the rejected semantic output. Independent
                # normalization and review retain the configured batch role and
                # its own execution identity/budget, rather than consuming the
                # controller's repair allowance for unrelated checking work.
                followup_packets = self.packets if supervising else packets
                new_inputs = {**inputs, target_key: changed}
                normalization_replacement = None
                if name == 'reverse-G' and target_name == 'G-generate':
                    normalized_folder = root / 'batches' / ('normalize-G-after-source-repair-' + str(record['rounds']))
                    b.normalized_packets(changed['values'], self.graph(case, new_inputs)[1], normalized_folder, 'G', self.index)
                    from .partial_packet_reuse import reuse_from
                    reuse_from(inputs[self.key(case, 'normalize-G')]['folder'], normalized_folder,
                        context['validators']['normalize-G'], followup_packets.cache_identity)
                    normalization_replacement = followup_packets.execute(normalized_folder, context['validators']['normalize-G'])
                    new_inputs[self.key(case, 'normalize-G')] = normalization_replacement
                # Model repairs are checked against source + approved proposal
                # bindings again; changed/new proposals cannot bypass confirmation.
                if target_name == 'normal':
                    changed_model = self.model(case, changed)
                    new_inputs[self.key(case, 'authorization')] = {'model': changed_model}
                folder = root / 'batches' / (name + '-recheck-' + str(record['rounds']))
                prepare(new_inputs, folder)
                # Changed upstream data need fresh checking; identical valid
                # review packets retain their original execution and budget.
                retained = []
                previous_review = failure.get('output', {}).get('folder')
                if previous_review and Path(previous_review).resolve() != folder.resolve():
                    from .partial_packet_reuse import reuse_from
                    retained = reuse_from(previous_review, folder, validator,
                        followup_packets.cache_identity)['reused_batch_ids']
                # Bind a fresh review to the diagnosis even if input happened
                # to be identical. Do not reuse a prior failed judgment.
                self.salt(folder, diagnosis, record['rounds'], retained=retained)
                checked = followup_packets.execute(folder, validator)
                if transform:
                    checked = transform(checked)
                if reject:
                    findings = reject(checked['values'])
                    if findings:
                        raise TaskRejected({'findings': findings, 'output': checked,
                            'candidate_replacements': {**candidates, target_key: changed,
                                **({self.key(case, 'normalize-G'): normalization_replacement} if normalization_replacement else {})},
                            'candidate_source_repair': source_repair or source_progress})
                checked['_replacements'] = {**candidates, target_key: changed}
                if source_repair or source_progress:
                    checked['_source_repair'] = source_repair or source_progress
                if normalization_replacement:
                    checked['_replacements'][self.key(case, 'normalize-G')] = normalization_replacement
                if target_name == 'normal':
                    checked['_replacements'][self.key(case, 'authorization')] = {'model': changed_model}
                    if name != 'graphs':
                        graph_folder = root / 'batches' / ('graphs-recheck-for-' + name + '-' + str(record['rounds']))
                        self.graph_packets(case, new_inputs, graph_folder)
                        self.salt(graph_folder, diagnosis, record['rounds'])
                        checked_graph = self.component_records(followup_packets.execute(graph_folder, self.graph_validator))
                        if any(not row['valid'] for row in checked_graph['values']):
                            raise TaskRejected({'findings': [row for row in checked_graph['values'] if not row['valid']], 'output': checked_graph})
                        checked['_replacements'][self.key(case, 'graphs')] = checked_graph
                self.scheduler.stage_promotion(self.key(case, name), checked)
                for key, value in checked['_replacements'].items():
                    write_json(root / 'active' / (key.split(':', 1)[1] + '.json'), {
                        'input_hash': self.scheduler.state['tasks'][key]['input_hash'], 'output': value})
                write_json(root / 'active' / (name + '.json'), {'input_hash': record['input_hash'], 'output': checked})
                return checked
            if reject:
                findings = reject(changed['values'])
                if findings:
                    raise TaskRejected({'findings': findings, 'output': changed})
            write_json(root / 'active' / (name + '.json'), {'input_hash': record['input_hash'], 'output': changed})
            return changed
        def verify(output):
            if pending_source_correction():
                raise ValueError('a proven source correction is still awaiting promotion and independent recheck')
            generation_key = self.key(case, 'G-generate')
            if name == 'reverse-G' and output.get('_source_repair'):
                from .directed_patch import validate_generation_progress
                proof = output.get('_source_repair') or {}
                generation_record = self.scheduler.state['tasks'][generation_key]
                changed = read_json(self.root / generation_record['output_file'])
                if (proof.get('generation_task') != generation_key
                        or proof.get('corrected_output_hash') != fingerprint(changed)):
                    raise ValueError('source repair needs a bound proof of actual rejected-item changes')
                validate_generation_progress(None, changed['values'], proof.get('rejected_source_ids'))
            verify_execution_output(output)
            for execution in output.get('executions', []):
                self.packets.cache_identity(read_json(execution['result_path']))
            values, status = collect_packets(output['folder'], validator)
            if not status['complete'] or values != output['values']:
                raise ValueError('cached semantic output changed or no longer validates')
            if reject and reject(values):
                raise ValueError('cached check is rejected')
        context['validators'][name] = validator
        def repair(inputs, record):
            return repair_with(self.packets, inputs, record)
        self.add(case, name, deps, execute, repair=repair, lane=lane, verify=verify)
        if getattr(self, 'supervisor_packets', None) and self.args.agent_mode == 'external':
            self.scheduler.tasks[self.key(case, name)].supervisor = lambda inputs, record: repair_with(
                self.supervisor_packets, inputs, record, supervising=True)
        def compatible(inputs,output):
            # Tool version metadata may change while the actual semantic
            # payload, instructions and contract stay identical. Revalidate
            # the original execution with today's validator in that case.
            from tempfile import TemporaryDirectory
            original = (Path(output['folder']) if name in ('normalize-G', 'reverse-G')
                and output.get('folder') else root/'batches'/name)
            if not (original/'manifest.json').exists():raise ValueError('original packet proof missing')
            revalidation_path = self.root / (name + '_rejected_revalidation.json') if hasattr(self, 'root') else None
            revalidated = False
            if revalidation_path and revalidation_path.exists():
                proof = read_json(revalidation_path)
                bound = {(p['batch_id'], p['input_hash'], p['result_hash'])
                    for task in proof.get('tasks', []) if task.get('task') == self.key(case, name) and task.get('status') == 'passed'
                    for p in task.get('proofs', [])}
                revalidated = bool(output.get('executions')) and all(
                    (e['batch_id'], e['input_hash'], e['result_hash']) in bound for e in output['executions'])
            with TemporaryDirectory(prefix='scene-compatible-packets-') as temporary:
                prepare(inputs,Path(temporary))
                expected=read_json(Path(temporary)/'manifest.json')
                prior=read_json(original/'manifest.json')
                if expected['stage']!=prior['stage'] or len(expected['batches'])!=len(prior['batches']):
                    raise ValueError('semantic batch scope changed')
                def semantic_packet(packet):
                    from .partial_packet_reuse import semantic_packet as execution_neutral_packet
                    packet=execution_neutral_packet(packet)
                    # A failed-unit review patch still covers the exact prior
                    # complete packet through its verified execution binding.
                    # Compare that original evidence to the newly prepared
                    # scope; validation below checks the actual patch lineage.
                    seen = set()
                    while packet.get('input', {}).get('review_patch'):
                        previous_path = packet['input']['review_patch']['prior_execution']['packet_path']
                        if previous_path in seen:
                            raise ValueError('cyclic review patch evidence')
                        seen.add(previous_path)
                        packet = read_json(previous_path)
                    for field in ('batch_id','input_hash'):packet.pop(field,None)
                    for field in ('execution_versions','test_parser_version'):packet['input'].pop(field,None)
                    if revalidated:
                        packet.pop('instructions', None)
                        packet['input'].pop('extraction_skills', None)
                    if name.startswith(('compare-', 'reverse-')):
                        # New citation selectors are an additive output format.
                        # Existing judgments remain usable only if the complete
                        # original scope/input is identical and today's strict
                        # semantic/evidence validator still accepts them below.
                        packet.pop('instructions', None)
                        packet.pop('output_contract', None)
                        packet['input'].pop('fresh_recheck', None)
                        packet['input'].pop('bounded_repair', None)
                    if name=='participants':packet['input'].pop('rule_hash',None)
                    if name=='graphs':
                        # Moving already-checked nodes into the shared registry
                        # is a cache-layout change, not a different graph.
                        _,ssd=self.graph(case,inputs)
                        nodes={node['node_id']:node for node in ssd['nodes']}
                        identities=set(packet['input'].get('component_versions',{}))
                        if not identities:identities={node['node_id'] for node in packet['input']['nodes']}
                        if not identities<=set(nodes):raise ValueError('shared graph identity changed')
                        packet['input']['nodes']=[nodes[key] for key in sorted(identities)]
                        packet['input'].pop('reused_components',None)
                        packet['input'].pop('component_versions',None)
                    return packet
                for batch,previous in zip(expected['batches'],prior['batches']):
                    latest=read_json(Path(temporary)/'packets'/(batch['batch_id']+'.json'))
                    previous=read_json(original/'packets'/(previous['batch_id']+'.json'))
                    if semantic_packet(latest)!=semantic_packet(previous):
                        raise ValueError('semantic packet changed')
            verify(output)
        self.scheduler.tasks[self.key(case,name)].compatible=compatible
        def compatible_failure(inputs, record):
            from tempfile import TemporaryDirectory
            original = root / 'batches' / name
            prior = read_json(original / 'manifest.json')
            with TemporaryDirectory(prefix='scene-failed-context-') as temporary:
                prepare(inputs, Path(temporary))
                expected = read_json(Path(temporary) / 'manifest.json')
                if expected['stage'] != prior['stage'] or len(expected['batches']) != len(prior['batches']):
                    raise ValueError('failed task scope changed')
                for batch, previous in zip(expected['batches'], prior['batches']):
                    latest = read_json(Path(temporary) / 'packets' / (batch['batch_id'] + '.json'))
                    old_packet = read_json(original / 'packets' / (previous['batch_id'] + '.json'))
                    def allowed_input(packet):
                        data = copy.deepcopy(packet['input'])
                        for field in ('execution_versions', 'test_parser_version', 'extraction_skills'):
                            data.pop(field, None)
                        return data
                    if (allowed_input(latest) != allowed_input(old_packet)
                            or (not name.startswith(('compare-', 'reverse-'))
                                and latest['output_contract'] != old_packet['output_contract'])):
                        raise ValueError('failed task original evidence or output contract changed')
            target = rejected_target(root, name, record.get('failure') or {})
            for batch in read_json(Path(target['folder']) / 'manifest.json')['batches']:
                packet = read_json(Path(target['folder']) / 'packets' / (batch['batch_id'] + '.json'))
                if fingerprint({k:v for k,v in packet.items() if k not in ('batch_id','input_hash')}) != batch['input_hash']:
                    raise ValueError('failed original packet changed')
        self.scheduler.tasks[self.key(case, name)].compatible_failure = compatible_failure

    @staticmethod
    def salt(folder, diagnosis, round_number, retained=()):
        manifest = read_json(folder / 'manifest.json')
        packets = [read_json(folder / 'packets' / (row['batch_id'] + '.json')) for row in manifest['batches']]
        pending = [p for p in packets if p['batch_id'] not in set(retained)]
        if pending:
            prepare_packets(folder, manifest['stage'], [{**p['input'], 'fresh_recheck': {
                'diagnosis': diagnosis, 'round': round_number}} for p in pending], pending[0]['instructions'], pending[0]['output_contract'])
            updated = read_json(folder / 'manifest.json')
            replacements = iter(updated['batches'])
            updated['batches'] = [row if row['batch_id'] in retained else next(replacements)
                for row in manifest['batches']]
            updated['input_hash'] = fingerprint(updated['batches'])
            write_json(folder / 'manifest.json', updated)

    def model(self, case, normal):
        context = self.contexts[case]
        model = merge_model(normal['values'], context['base'], self.index)
        proposals = architecture_proposals(model, self.base)
        if self.approval.get('model_hash') == fingerprint(model):
            for proposal in proposals:
                if proposal['proposal_id'] in set(self.approval.get('approved_proposal_ids', [])):
                    self.bindings[proposal['proposal_id']] = proposal_hash(proposal)
        pending = [p for p in proposals if self.bindings.get(p['proposal_id']) != proposal_hash(p)]
        if pending or model['model_gaps']:
            pending = [{**p, 'approval_fingerprint': proposal_hash(p)} for p in pending]
            write_json(context['root'] / 'pending_confirmation.json', {'proposals': pending, 'model_gaps': model['model_gaps']})
            write_pending(context['root'], pending, model['model_gaps'], fingerprint(model))
            raise TaskBlocked('awaiting_confirmation', {'proposals': pending, 'model_gaps': model['model_gaps']})
        return model

    def graph(self, case, inputs):
        model = self.model(case, inputs[self.key(case, 'normal')])
        return model, build_ssd(model)

    def normalize(self, case, collection, raw_name, source_index):
        name = 'normalize-' + collection
        self.semantic(case, name, (raw_name, 'normal', 'graphs'),
            lambda deps, d: b.normalized_packets(self.values(deps, case, raw_name), self.graph(case, deps)[1], d, collection, source_index),
            normalize_validator(source_index))
        reverse = 'reverse-' + collection
        self.semantic(case, reverse, (name, raw_name, 'normal', 'graphs'),
            lambda deps, d: b.review_packets(self.values(deps, case, name), self.values(deps, case, raw_name),
                self.graph(case, deps)[1], d, collection, source_index), reverse_validator,
            reject=lambda rows: [r for r in rows if not r['passed']], repair_target=name)
        self.semantic(case, 'dedup-' + collection, (name, reverse, 'normal', 'graphs'),
            lambda deps, d: dedup_packets(self.values(deps, case, name), self.graph(case, deps)[1], collection, d), dedup_validator)
        def merged_units(deps):
            return {'values':dedup_merge(self.values(deps,case,name),collection+'2',self.values(deps,case,'dedup-'+collection))}
        self.add(case,'units-'+collection,(name,reverse,'dedup-'+collection),lambda deps,_:merged_units(deps))
        def compatible_units(deps,output):
            if merged_units(deps)!=output:raise ValueError('normalized unit inputs changed')
        self.scheduler.tasks[self.key(case,'units-'+collection)].compatible=compatible_units

    def history_version(self):
        from hashlib import sha256
        root = Path(self.history_run)
        files = {}
        for name in ('run_manifest.json', 'result_bundle.json', 'historical_scene_model.json'):
            try:
                files[name] = sha256((root/name).read_bytes()).hexdigest()
            except OSError as exc:
                files[name] = {'unavailable': type(exc).__name__}
        return {'run': str(root.resolve()), 'files': files, 'source': fingerprint(self.index),
            'selected': sorted(self.selected), 'cases': sorted(u['use_case_id'] for u in self.base['use_cases']),
            'embedding_model': self.embedding.model('embedding'), 'endpoint': fingerprint(self.embedding.base_url),
            'rules': fingerprint(Path(__file__).with_name('concern_gap_history.py').read_text(encoding='utf8')),
            'path_rules': fingerprint(Path(__file__).with_name('artifact_paths.py').read_text(encoding='utf8'))}

    def import_history(self):
        from .concern_gap_history import load, copy_vectors
        corpus = load(self.history_run, self.index, self.selected, [u['use_case_id'] for u in self.base['use_cases']])
        corpus['copied_vectors'] = copy_vectors(corpus, self.embedding)
        write_json(self.root/'history_import.json', corpus['binding'])
        return corpus

    def verify_imported_history(self, corpus):
        from .concern_gap_history import verify_binding
        verify_binding(corpus['binding'])
        if (corpus['binding']['excluded_use_case_ids'] != sorted(self.selected)
                or corpus['binding']['corpus_hash'] != fingerprint(corpus['source_units'])):
            raise ValueError('historical corpus scope or contents changed')

    def build(self):
        from .interaction_versions import packet_versions
        positive_versions = {'normal': packet_versions('interaction-model'),
            'semantic': b.packet_versions('gap-graph-check'), 'adapter': fingerprint(Path(__file__).read_text(encoding='utf8')),
            'model': self.client.model('agent'), 'reasoning_effort': self.client.config.get('reasoning_effort'),
            'thinking': self.client.config.get('thinking'), 'endpoint': fingerprint(getattr(self.client, 'base_url', 'native'))}
        if self.history_run:
            self.scheduler.add(Task('@project:history-import', '@project', 'history-import', (),
                self.history_version(), execute=lambda deps, record: self.import_history(),
                verify=self.verify_imported_history))
        for uc in self.base['use_cases']:
            case = uc['use_case_id']
            if self.history_run and case not in self.selected:
                continue
            root = self.root / 'cases' / case_name(case)
            root.mkdir(parents=True, exist_ok=True)
            base = {**self.base, 'use_cases': [uc]}
            self.contexts[case] = {'root': root, 'base': base, 'validators': {},
                'version': {'case': fingerprint(uc), 'sections': fingerprint(old.source_sections(self.index, uc, include_contracts=True)), **positive_versions}}
            # Test edits must not invalidate positive modeling or generation.
            write_json(root / 'case_identity.json', {'use_case_id': case})
            self.semantic(case, 'normal', (), lambda deps, d, base=base: old.model_packets(base, self.index, d), old.model_validator(self.index), lane='discovery')
            if self.ar_index['documents']:
                # AR trace is independent and never becomes an exception input.
                self.semantic(case, 'ar-trace', ('normal',), lambda deps, d, case=case: b.ar_packets(self.ar_index_for_case(case, deps), d),
                    b.ar_validator(self.ar_index))
                task=self.scheduler.tasks[self.key(case,'ar-trace')]
                task.version={'base':self.contexts[case]['version'],'ar_source':fingerprint(self.ar_index),
                    'rules':b.packet_versions('gap-ar-trace')}
                self.scheduler.state['tasks'][task.key]['version']=task.version
            self.semantic(case, 'E-extract', (), lambda deps, d, base=base: old.checker_packets(base, self.index, d), old.checker_validator(self.index), lane='discovery')
            self.semantic(case, 'E-audit', ('E-extract',),
                lambda deps, d, case=case: checker_audit_packets(deps[self.key(case, 'E-extract')]['folder'], self.index, d), checker_audit_validator(self.index),
                reject=lambda rows: [r for r in rows if not r['passed']], repair_target='E-extract')
            self.add(case, 'authorization', ('normal',), lambda deps, _, case=case: {'model': self.model(case, deps[self.key(case, 'normal')])},
                verify=lambda output, case=case: self.authorize(case, output['model']))
            def compatible_authorization(deps,output,case=case):
                if self.model(case,deps[self.key(case,'normal')])!=output['model']:
                    raise ValueError('authorized normal model changed')
            self.scheduler.tasks[self.key(case,'authorization')].compatible=compatible_authorization
            authorization_record = self.scheduler.state['tasks'][self.key(case, 'authorization')]
            if authorization_record['status'] == 'awaiting_confirmation':
                authorization_record['status'] = 'pending'
            self.semantic(case, 'graphs', ('normal', 'authorization'),
                lambda deps, d, case=case: self.graph_packets(case, deps, d), self.graph_validator,
                reject=lambda rows: [r for r in rows if not r['valid']], repair_target='normal', transform=self.component_records)
            self.semantic(case, 'participants', ('normal', 'graphs'),
                lambda deps, d, case=case: participant_packets(deps[self.key(case, 'normal')]['folder'], self.index, d), participant_validator(self.index),
                reject=lambda rows: [r for r in rows if not r['passed']], repair_target='normal')
            self.normalize(case, 'E', 'E-extract', self.index)
            # Include source audit in history readiness, rather than allowing a
            # normalized but unsupported extraction into the historical library.
            self.add(case, 'history-vectors', ('units-E', 'E-audit'),
                lambda deps, _, case=case: self.prefetch(self.values(deps, case, 'units-E')),
                version={'model': self.embedding.model('embedding'), 'endpoint': fingerprint(self.embedding.base_url),
                    'text_rules': fingerprint(__import__('inspect').getsource(scene_text))})
            def compatible_vectors(deps,output,case=case):
                units=self.values(deps,case,'units-E')
                if output.get('model')!=self.embedding.model('embedding'):
                    raise ValueError('historical vector model changed')
                for unit in units:
                    text=scene_text(unit);identifier=unit['scenario_id']
                    cache=Path(self.embedding.config['cache_dir'])/(fingerprint([self.embedding.base_url,self.embedding.model('embedding'),text])+'.json')
                    if output['text_hashes'].get(identifier)!=fingerprint(text) or not cache.exists() or read_json(cache)!=output['vectors'].get(identifier):
                        raise ValueError('historical vector text/endpoint/cache changed')
                if set(output['vectors'])!={u['scenario_id'] for u in units}:raise ValueError('historical vector scope changed')
            self.scheduler.tasks[self.key(case,'history-vectors')].compatible=compatible_vectors
            if case not in self.selected:
                continue
            self.semantic(case, 'features', ('normal', 'graphs', 'participants'),
                lambda deps, d, case=case: b.feature_packets(*self.graph(case, deps), self.index, d), b.feature_validator(self.index))
            self.add(case, 'mounts', ('normal', 'graphs', 'features'), lambda deps, _, case=case: self.mounts(case, deps))
            self.semantic(case, 'G-generate', ('normal', 'graphs', 'features', 'mounts'),
                lambda deps, d, case=case: b.generation_packets(self.graph(case, deps)[1], deps[self.key(case, 'mounts')]['mounts'],
                    self.values(deps, case, 'features'), d), b.generation_validator(self.index))
            self.normalize(case, 'G', 'G-generate', self.index)
            self.semantic(case, 'T-extract', (), lambda deps, d, base=base: b.test_packets(base, self.test_index, d),
                old.test_validator(self.test_index), lane='discovery')
            self.scheduler.tasks[self.key(case, 'T-extract')].version = {'base': self.contexts[case]['version'],
                'test': fingerprint(old.source_sections(self.test_index, uc)), 'rules': b.packet_versions('gap-test-extract')}
            self.scheduler.state['tasks'][self.key(case, 'T-extract')]['version'] = self.scheduler.tasks[self.key(case, 'T-extract')].version
            self.normalize(case, 'T', 'T-extract', self.test_index)
            for name, left, right in [('EG', 'E', 'G'), ('TG', 'T', 'G'), ('TE', 'T', 'E')]:
                self.semantic(case, 'compare-' + name, ('units-' + left, 'units-' + right, 'E-audit'),
                    lambda deps, d, case=case, name=name, left=left, right=right: b.comparison_packets(
                        self.values(deps, case, 'units-' + left), self.values(deps, case, 'units-' + right), d, name), comparison_validator)
            self.add(case, 'case-report', ('normal', 'graphs', 'features', 'mounts', 'G-generate', 'E-extract', 'T-extract',
                'normalize-G', 'normalize-E', 'normalize-T', 'reverse-G', 'reverse-E', 'reverse-T',
                'dedup-G', 'dedup-E', 'dedup-T', 'units-G', 'units-E', 'units-T', 'compare-EG', 'compare-TG', 'compare-TE'),
                lambda deps, _, case=case: self.case_bundle(case, deps))
        dependencies = list(self.scheduler.tasks)
        # Ranking is an explicit global history barrier, not a case barrier.
        self.scheduler.add(Task('@project:historical-ranking', '@project', 'historical-ranking', tuple(dependencies),
            {'embedding_model': self.embedding.model('embedding'), 'endpoint': fingerprint(self.embedding.base_url),
                'seed': self.manifest['recommendation_seed'], 'rules': fingerprint(__import__('inspect').getsource(rank)),
                'versions': self.manifest['versions']},
            execute=lambda deps, record: self.aggregate()[0], verify=self.verify_final))

    def verify_final(self, output):
        from .concern_gap_replay import verify_bundle
        result = verify_bundle(read_json(self.root / 'result_bundle.json'))
        if result['result_hash'] != output['result_hash']:
            raise ValueError('global ranking bundle changed')

    def prefetch(self, history):
        units = sorted([u for u in history if u['mapping_status'] == 'mapped'], key=lambda u: u['scenario_id'])
        texts = [scene_text(u) for u in units]
        # SemanticClient checks disk cache before posting; gate only its actual
        # transport, so cached vectors still work during quota exhaustion.
        with self.embedding_lock:
            values = self.embedding.embeddings(texts)
        if len(values) != len(units):
            raise TaskRejected('incomplete historical embeddings')
        from .concern_gap_ranking import cosine
        for value in values:
            cosine(value, value)
        return {'history_hash': fingerprint(history), 'model': self.embedding.model('embedding'),
            'vectors': {u['scenario_id']: v for u, v in zip(units, values)},
            'text_hashes': {u['scenario_id']: fingerprint(t) for u, t in zip(units, texts)}, 'ranking_published': False}

    def ar_index_for_case(self, case, deps):
        names = [n['name'] for row in self.values(deps, case, 'normal') for n in row['components']]
        index = copy.deepcopy(self.ar_index)
        for doc in index['documents']:
            doc['chapters'] = [c for c in doc['chapters'] if any(name in '\n'.join(doc['text'].splitlines()[c['line_start'] - 1:c['line_end']]) for name in names)]
            doc['text'] = '\n'.join(line if any(c['line_start'] <= n <= c['line_end'] for c in doc['chapters']) else ''
                for n, line in enumerate(doc['text'].splitlines(), 1))
        index['documents'] = [doc for doc in index['documents'] if doc['chapters']]
        return index

    def component_key(self, node):
        return fingerprint({'node': {k: v for k, v in node.items() if k != 'source_component_ids'},
            'source': old.cited_text(node.get('source_refs', []), self.index),
            'check_rules': b.packet_versions('gap-graph-check'), 'skill': b.skill('scene-model-check')})

    def graph_packets(self, case, deps, folder):
        model, ssd = self.graph(case, deps)
        manifest = b.graph_packets(model, ssd, self.index, folder)
        with self.embedding_lock:
            registry_path = self.root / 'component_checks.json'
            registry = read_json(registry_path) if registry_path.exists() else {}
        payloads = []
        for row in manifest['batches']:
            packet = read_json(folder / 'packets' / (row['batch_id'] + '.json'))
            data = packet['input']
            reused = []
            nodes = []
            for node in data['nodes']:
                key = self.component_key(node)
                prior = registry.get(key)
                if prior and prior['check']['valid']:
                    verify_execution_output({'executions': prior['executions']})
                    reused.append(prior)
                else:
                    nodes.append(node)
            payloads.append({**data, 'nodes': nodes, 'reused_components': reused,
                'component_versions': {n['node_id']: self.component_key(n) for n in data['nodes']}})
        if payloads:
            prepare_packets(folder, manifest['stage'], payloads, packet['instructions'], packet['output_contract'])

    def graph_validator(self, packet, result):
        rows = b.graph_validator(self.index)(packet, result)
        for record in packet['input'].get('reused_components', []):
            verify_execution_output({'executions': record['executions']})
            rows.append(record['check'])
        return rows

    def component_records(self, output):
        folder = Path(output['folder'])
        manifest = read_json(folder / 'manifest.json')
        component_versions = {}
        for row in manifest['batches']:
            packet = read_json(folder / 'packets' / (row['batch_id'] + '.json'))
            component_versions.update(packet['input'].get('component_versions', {}))
            for cached in packet['input'].get('reused_components', []):
                output['executions'] += [e for e in cached['executions'] if e not in output['executions']]
        with self.embedding_lock:
            path = self.root / 'component_checks.json'
            registry = read_json(path) if path.exists() else {}
            for check in output['values']:
                if check['kind'] == 'composition' and check['id'] in component_versions:
                    registry[component_versions[check['id']]] = {'node_id': check['id'], 'check': check,
                        'status': 'passed' if check['valid'] else 'rejected', 'executions': output['executions']}
            write_json(path, registry)
        return output

    def authorize(self, case, model):
        # A legacy approval may refer to a historical model hash. Reading that
        # exact approved snapshot does not require importing the historical E
        # corpus, and it never becomes a modeling/normal-generation input.
        if self.history_run and self.approval.get('model_hash'):
            path = Path(self.history_run)/'historical_scene_model.json'
            try:
                self.bindings.update(approval_bindings(self.approval, read_json(path), self.base))
            except (OSError, ValueError):
                pass
        proposals = architecture_proposals(model, self.base)
        pending = [p for p in proposals if self.bindings.get(p['proposal_id']) != proposal_hash(p)]
        if pending or model['model_gaps']:
            raise TaskBlocked('awaiting_confirmation', {'proposals': pending, 'model_gaps': model['model_gaps']})

    def mounts(self, case, deps):
        model, ssd = self.graph(case, deps)
        features = {f['exchange_id']: f for f in self.values(deps, case, 'features')}
        routing = copy.deepcopy(ssd)
        for exchange in routing['exchanges']:
            exchange['operation_kinds'] = next(t['value'] for t in features[exchange['exchange_id']]['traits'] if t['name'] == 'operation_kinds')
        mounts = route_mounts(routing)
        for mount in mounts:
            mount['feature_evidence'] = features[mount['exchange_id']]['traits']
            mount['mount_reason'] = 'checked interaction operation/party/data traits and registered concern routing'
        normal = [copy.deepcopy(s) for u in model['use_cases'] for s in u['normal_scenarios']]
        for scene in normal:
            exchanges = {e['exchange_id'] for e in ssd['exchanges'] if e['requirement_layer'] == scene['requirement_layer']}
            messages = [m for m in ssd['messages'] if m['exchange_id'] in exchanges]
            scene['ssd_message_ids'] = [m['message_id'] for m in messages]
            if scene['scenario_type'] == 'main_success':
                scene['steps'] = [m['text'] for m in messages]
                scene['derivation'] = 'checked_ssd_message_order'
        return {'mounts': mounts, 'normal': normal}

    def case_bundle(self, case, deps):
        model, ssd = self.graph(case, deps)
        mounted = deps[self.key(case, 'mounts')]
        generated = self.values(deps, case, 'G-generate')
        validate_generated(generated + mounted['normal'], ssd, mounted['mounts'], self.index)
        sets = {k: self.values(deps, case, 'units-' + k) for k in ('G', 'E', 'T')}
        relations = {}
        for name, left, right in [('EG', 'E', 'G'), ('TG', 'T', 'G'), ('TE', 'T', 'E')]:
            relations[name] = b.exact_decisions(sets[left], sets[right]) + self.values(deps, case, 'compare-' + name)
        bundle = {'protocol': PROTOCOL, 'model': model, 'ssd': ssd, 'mounts': mounted['mounts'], 'normal': mounted['normal'],
            'features': self.values(deps, case, 'features'), 'graphs': self.values(deps, case, 'graphs'), **sets,
            'source_generated': generated, 'source_existing': self.values(deps, case, 'E-extract'), 'source_tests': self.values(deps, case, 'T-extract'),
            'source_units': {k: self.values(deps, case, 'normalize-' + k) for k in ('G', 'E', 'T')},
            'dedup': {k: self.values(deps, case, 'dedup-' + k) for k in ('G', 'E', 'T')},
            'reverse_checks': {k: {'passed': True, 'reviews': self.values(deps, case, 'reverse-' + k)} for k in ('G', 'E', 'T')},
            'relations': relations, 'project_complete': False, 'formal_metrics': None}
        local = metrics(sets['G'], sets['E'], sets['T'], [], relations)
        bundle['missing_ids'] = local['missing_ids']
        root = self.contexts[case]['root']
        write_json(root / 'case_result.json', bundle)
        from .concern_gap_dag_reports import partial_case
        partial_case(root, bundle)
        return bundle

    def progress(self, scheduler):
        summary = scheduler.summary()
        if not summary['complete'] and (self.root / 'result_bundle.json').exists():
            previous = read_json(self.root / 'result_bundle.json')
            archive = self.root / 'previous_results' / fingerprint(previous)
            archive.mkdir(parents=True, exist_ok=True)
            for name in ('result_bundle.json', 'metrics.json', 'historical_ranking.json', 'scene_assessment.xlsx', 'report.md', 'acceptance.json'):
                path = self.root / name
                if path.exists():
                    shutil.copyfile(path, archive / name)
                    path.unlink()
        final_record = scheduler.state['tasks'].get('@project:historical-ranking', {})
        complete = summary['complete'] and final_record.get('status') == 'passed'
        self.manifest.update(complete=complete, task_summary=summary, pending_stage=None if complete else 'case_tasks')
        if self.packets.model_pool:
            pool = self.packets.model_pool
            self.manifest['batch_model_chain'] = pool.state['profiles']
            self.manifest['active_batch_model'] = pool.current()[1].model('agent')
        if complete:
            bundle = read_json(self.root / 'result_bundle.json')
            self.manifest.update(result_hash=bundle['result_hash'], metric_hash=fingerprint(bundle['metrics']))
        write_json(self.root / 'run_manifest.json', self.manifest)
        from .concern_gap_dag_reports import progress
        progress(self.root, scheduler.state, self.selected)

    def aggregate(self):
        def output(case, stage):
            record = self.scheduler.state['tasks'][self.key(case, stage)]
            return read_json(self.root / record['output_file'])
        if self.history_run:
            record = self.scheduler.state['tasks'].get('@project:history-import', {})
            if record.get('status') != 'passed':
                raise TaskBlocked('pending', 'historical library is not ready; ranking and formal metrics are withheld')
            self.history = read_json(self.root / record['output_file'])
            self.verify_imported_history(self.history)
        cases = [output(case, 'case-report') for case in sorted(self.selected)]
        history = sorted([u for case in sorted(self.contexts) for u in output(case, 'units-E')['values']], key=lambda u: u['scenario_id'])
        raw_history = [u for case in sorted(self.contexts) for u in output(case, 'E-extract')['values']]
        model = merge_model([v for case in sorted(self.selected) for v in output(case, 'normal')['values']],
            assessment_base(self.base, sorted(self.selected)), self.index)
        full_model = merge_model([v for case in sorted(self.contexts) for v in output(case, 'normal')['values']],
            assessment_base(self.base,sorted(self.contexts)), self.index)
        if self.history:
            from .concern_gap_history import verify_binding
            verify_binding(self.history['binding'])
            history=sorted(history+self.history['history'],key=lambda u:u['scenario_id'])
            raw_history+=self.history['source_existing']
            nodes={n['node_id']:n for n in self.history['model']['nodes']}
            nodes.update({n['node_id']:n for n in full_model['nodes']})
            full_model={**full_model,'nodes':list(nodes.values()),'use_cases':full_model['use_cases']+
                [u for u in self.history['model']['use_cases'] if u['use_case_id'] not in self.selected]}
        bundle = {'protocol': PROTOCOL, 'scope': self.manifest['scope'], 'source_index': self.index,
            'test_source_index': self.test_index, 'model': model, 'ssd': build_ssd(model), 'history': history,
            'source_existing': raw_history, 'ar_trace': [v for case in sorted(self.contexts) for v in
                (output(case, 'ar-trace')['values'] if self.ar_index['documents'] else [])],
            'generation_repairs': [], 'normalization_repairs': {k: [] for k in ('G', 'E', 'T')}}
        for key in ('G', 'E', 'T', 'normal', 'features', 'graphs', 'mounts', 'source_generated', 'source_tests'):
            bundle[key] = [row for c in cases for row in c[key]]
        for key in ('G', 'E', 'T'):
            bundle[key].sort(key=lambda u: u['scenario_id'])
        bundle['source_generated_base'] = bundle['source_generated']
        bundle['source_units'], bundle['dedup'], bundle['reverse_checks'] = {}, {}, {}
        for key in ('G', 'E', 'T'):
            ids = sorted(self.contexts) if key == 'E' else sorted(self.selected)
            bundle['source_units'][key] = [r for case in ids for r in output(case, 'normalize-' + key)['values']]
            bundle['dedup'][key] = [r for case in ids for r in output(case, 'dedup-' + key)['values']]
            bundle['reverse_checks'][key] = {'passed': True, 'reviews': [r for case in ids for r in output(case, 'reverse-' + key)['values']]}
        if self.history:
            bundle['history_import']=self.history['binding']
            bundle['source_units']['E']+=self.history['source_units']
            bundle['dedup']['E']+=self.history['dedup']
            bundle['reverse_checks']['E']['reviews']+=self.history['reviews']
        bundle['base_source_units'] = bundle['source_units']
        bundle['generation_initial_reviews'] = bundle['reverse_checks']['G']['reviews']
        bundle['generation_confirmed_reviews'] = []
        bundle['relations'] = {key: [r for c in cases for r in c['relations'][key]] for key in ('EG', 'TG', 'TE')}
        provisional = metrics(bundle['G'], bundle['E'], bundle['T'], [], bundle['relations'])
        missing = [u for u in bundle['G'] if u['scenario_id'] in provisional['missing_ids']]
        # Every history-vector task has passed before reaching this barrier.
        with self.embedding_lock:
            ranking = rank(missing, history, self.embedding, self.manifest['recommendation_seed'])
        bundle['ranking'] = ranking
        bundle['metrics'] = metrics(bundle['G'], bundle['E'], bundle['T'], ranking['selected_ids'], bundle['relations'])
        bundle['result_hash'] = fingerprint(bundle)
        write_json(self.root / 'result_bundle.json', bundle)
        write_json(self.root / 'scene_model.json', model)
        write_json(self.root / 'historical_scene_model.json', full_model)
        write_json(self.root / 'historical_ssd.json', build_ssd(full_model))
        write_json(self.root / 'model_authorization.json', {'proposal_bindings': self.bindings})
        write_json(self.root / 'metrics.json', bundle['metrics'])
        write_json(self.root / 'historical_ranking.json', ranking)
        from .concern_gap_replay import verify_bundle
        verify_bundle(bundle)
        from .concern_gap_reports import export
        export(self.root, bundle)
        self.manifest.update(complete=True, pending_stage=None, result_hash=bundle['result_hash'], metric_hash=fingerprint(bundle['metrics']))
        write_json(self.root / 'run_manifest.json', self.manifest)
        return {'complete': True, 'result_hash': bundle['result_hash'], 'sets': bundle['metrics']['set_sizes']}, 0


def run(args):
    with run_lock(args.output_dir):
        return run_unlocked(args)


def run_unlocked(args):
    if getattr(args, 'rerank', False) or getattr(args, 'exchange_local_id', None):
        raise ValueError('v2 uses complete use cases and historical embedding without rerank')
    pipeline = Pipeline(args)
    try:
        pipeline.preflight()
    except Exception as exc:
        reason = getattr(exc, 'response_diagnostic', {}) or {'failure_category': 'probe_failed'}
        pipeline.manifest.update(pending_stage='model_configuration', configuration_required=reason)
        write_json(pipeline.root/'run_manifest.json', pipeline.manifest)
        return {'complete':False, 'pending_stage':'model_configuration','configuration_required':reason}, 2
    try:
        pipeline.build()
        summary = pipeline.scheduler.run(pipeline.progress)
        pipeline.progress(pipeline.scheduler)
    finally:
        if pipeline.profiler:
            pipeline.profiler.finish('complete' if pipeline.manifest.get('complete') else 'pending')
    if not summary['complete']:
        return summary, 2 if args.agent_mode == 'external' else 0
    record = pipeline.scheduler.state['tasks']['@project:historical-ranking']
    return read_json(pipeline.root / record['output_file']), 0


def repair_selected(args, stages):
    with run_lock(args.output_dir):
        return repair_selected_unlocked(args, stages)


def repair_selected_unlocked(args, stages):
    from types import SimpleNamespace
    root = Path(args.output_dir)
    saved = read_json(root / 'pipeline_arguments.json')
    for name in ('config', 'env_file', 'agent_model'):
        if getattr(args, name, None):
            saved[name] = getattr(args, name)
    saved.update(output_dir=str(root), agent_mode='external', auto_repair='bounded')
    pipeline = Pipeline(SimpleNamespace(**saved))
    pipeline.build()
    cases = set(getattr(args, 'use_case_id', None) or pipeline.contexts)
    if not cases <= set(pipeline.contexts):
        raise ValueError('repair selected unknown use case')
    allowed = {key for key, task in pipeline.scheduler.tasks.items() if task.case in cases and task.stage in stages}
    if getattr(args, 'unit_id', None):
        ids = set(args.unit_id)
        scoped = {key for key in allowed if any(r.get('unit_id') in ids for r in
            pipeline.scheduler.state['tasks'][key].get('failure', {}).get('findings', []) if isinstance(r, dict))}
        if not scoped:
            raise ValueError('selected unit has no active source rejection in the requested DAG stages')
        # Do not silently widen an explicit request to other rejected units.
        for key in scoped:
            task = pipeline.scheduler.tasks[key]
            original = task.repair
            def selected_repair(deps, record, original=original):
                record = {**record, 'failure': {**record['failure'], 'findings': [r for r in record['failure']['findings'] if r.get('unit_id') in ids]}}
                return original(deps, record)
            task.repair = selected_repair
        allowed = scoped
    try:
        summary = pipeline.scheduler.run(pipeline.progress, allowed=allowed)
    finally:
        if pipeline.profiler:pipeline.profiler.finish('targeted_repair_finished')
    return summary, 0 if all(pipeline.scheduler.state['tasks'][key]['status'] == 'passed' for key in allowed) else 2
