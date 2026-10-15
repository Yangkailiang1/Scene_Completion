"""Validate canonical v2 scope, reusing strict v1 identification evidence checks."""
from copy import deepcopy
from .concern_gap import eligible
from .interaction_batches import pair_validator


def format_hint():
    """Clarify the existing validation schema without choosing semantic values."""
    return {
        'accepted_pair_requirements': {
            'specific_shared_condition': 'nonempty concrete common abnormal cause',
            'generated_evidence': 'exact nonempty generated identification excerpt',
            'checker_evidence': 'exact nonempty checker identification excerpt',
            'condition_evidence': [{'checker_condition': 'EXACT checker necessary_conditions item',
                'relation': 'supported|missing', 'generated_quote': 'COMPLETE generated condition if supported, otherwise empty',
                'reason': 'specific semantic reason; required'}],
            'missing_condition_details': ['EXACT missing checker condition, never an explanation'],
            'missing_condition_evidence': [{'detail': 'same EXACT string as missing_condition_details entry',
                'checker_field': 'trigger_condition|necessary_conditions',
                'checker_quote': 'same EXACT string as detail', 'generated_gap_reason': 'explanation'}]},
        'rules': 'Every necessary condition needs one evidence row, including ordinary context. '
                 'Partial requires exact missing quotes. Full has no missing detail. Unmatched needs no accepted-pair evidence. '
                 'Judge semantics independently; do not invent support or change a decision to satisfy formatting.'}


def validator(packet,result):
    binding = packet.get('input', {}).get('comparison_patch_binding')
    if binding:
        from .comparison_patch import apply_comparison_patch
        return apply_comparison_patch(binding['source_packet_path'], binding['prior_attempt_path'],
            packet, result, _base_validator)
    return _base_validator(packet, result)


def _base_validator(packet,result):
    from .comparison_evidence_refs import resolve_comparison_evidence
    result = resolve_comparison_evidence(packet, result)
    metadata=packet['input']['canonical_metadata']
    left=packet['input']['checker'];right=packet['input']['generated']
    ids={s['scenario_id'] for s in left+right}
    if set(metadata)!=ids:raise ValueError('canonical comparison metadata incomplete')
    def unit(scene):return {**scene,**metadata[scene['scenario_id']],'mapping_status':'mapped'}
    if any(not eligible(unit(l),unit(r)) for l in left for r in right):
        raise ValueError('canonical comparison has unrelated use case/location/concern')
    for decision in result.get('pairs', []):
        if (decision.get('status') == 'unmatched' and decision.get('same_causal_facet') is True
                and decision.get('compatible_conditions') is True):
            raise ValueError('Unmatched contradicts same_causal_facet=true and compatible_conditions=true '
                             'at this same actual interaction. Re-evaluate the original object/operation/actual '
                             'cause and conditions; response, successful handling, reuse, returned result or '
                             'hypothetical handling failure embedded in failure_mechanism cannot distinguish '
                             'exception identity. Repeated requests remain abnormal triggers even when correctly '
                             'handled. Do not simply flip flags to bypass this guard: distinct actual objects or '
                             'causes need concrete causal source evidence; identical cause with missing conditions '
                             'requires partial evidence. Preserve a semantic decision, not a format-driven match.')
    # Validation view only: the historical adapter enforces causal facets and
    # every necessary-condition quote. Actual packet/proof identities stay intact.
    view=deepcopy(packet);view['stage']='interaction-adoption';view['input']['comparison_scope']='test_all'
    try:
        return pair_validator(view,result)
    except ValueError as exc:
        if str(exc) == 'matched pair has incompatible identification':
            invalid = [{'checker_scenario_id': row.get('checker_scenario_id'),
                'generated_scenario_id': row.get('generated_scenario_id'),
                'incompatible_fields': [field for field in ('same_object', 'same_operation',
                    'same_mechanism', 'compatible_conditions') if row.get(field) is not True]}
                for row in result.get('pairs', []) if row.get('status') in ('full', 'partial')
                and any(row.get(field) is not True for field in ('same_object', 'same_operation',
                    'same_mechanism', 'compatible_conditions'))]
            raise ValueError(str(exc) + '. compatible_conditions means non-contradictory, not complete. '
                             'Missing checker conditions can support partial with exact missing evidence; '
                             'contradictory conditions or different object/operation/cause require unmatched. '
                             'Partial cannot compensate for a different object or operation. '
                             'Reassess the supplied originals; do not automatically flip any semantic flag. '
                             'Rejected pairs: ' + repr(invalid)) from exc
        if not any(word in str(exc) for word in ('condition', 'evidence', 'detail')):
            raise
        # Diagnostic input, never a replacement semantic decision. Preserve exact
        # conditions so retry workers can satisfy the strict evidence contract.
        obligations = [{'checker_scenario_id': l['scenario_id'],
                        'necessary_conditions': l.get('necessary_conditions', []),
                        'generated_support_choices': {
                            r['scenario_id']: [r['trigger_condition'], r['failure_mechanism'],
                                               *r.get('necessary_conditions', [])] for r in right}}
                       for l in left]
        import json
        raise ValueError(str(exc) + '. STRICT accepted-pair format: specific_shared_condition must be a '
                         'nonempty concrete common cause. generated_evidence/checker_evidence must be nonempty '
                         'exact excerpts of the respective identification (trigger_condition is allowed). '
                         'condition_evidence row keys MUST be checker_condition, relation, generated_quote, reason '
                         '(not condition/checker_quote; reason required); cover every exact checker necessary condition. '
                         'Supported generated_quote is one COMPLETE supplied generated condition. For partial: '
                         'missing_condition_evidence.detail MUST equal checker_quote and an exact '
                         'missing_condition_details entry, NOT an explanation; put explanation in generated_gap_reason. '
                         'Never invent support or change semantic decisions to satisfy format. Required conditions: '
                         + json.dumps(obligations, ensure_ascii=False)) from exc
