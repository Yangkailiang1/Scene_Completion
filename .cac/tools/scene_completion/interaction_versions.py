"""Version semantic packets by their actual dependencies, not unrelated reports."""
import inspect
from pathlib import Path

from .sources import fingerprint


def packet_versions(stage):
    from . import interaction_batches as b, interaction_protocol as p, semantic_backend as s
    from . import review
    root = Path(__file__).parent
    common = {name: fingerprint((root / name).read_text(encoding='utf-8')) for name in
              ('sources.py', 'document_extract.py', 'schemas.py', 'interaction_hierarchy.py', 'model_configuration.py', 'response_contract.py', 'evidence_refs.py')}
    common.update(protocol=p.PROTOCOL, taxonomy=fingerprint(p.baseline()),
        transport=fingerprint(inspect.getsource(s.SemanticClient.agent)),
        semantic_request=fingerprint(inspect.getsource(s.SemanticClient._agent)),
        transport_setup=fingerprint(inspect.getsource(s.SemanticClient.__init__)),
        endpoint_request=fingerprint(inspect.getsource(s.SemanticClient.post)),
        model_resolution=fingerprint(inspect.getsource(s.SemanticClient.model)),
        environment_resolution=fingerprint(inspect.getsource(review._resolve_env_reference)),
        content_parser=fingerprint(inspect.getsource(review._content_from_response)),
        http_transport=fingerprint(inspect.getsource(review._post_chat_completions)),
        version_rule=fingerprint(inspect.getsource(packet_versions)))
    groups = {
        'interaction-model': [b.model_packets, b.model_validator, b.source_sections, b.cited_text,
            b.source_identifier_supported, b.bound_contract_refs, p.reject_generation_bypass,
            p.validate_exchange_fields, p.build_ssd, p.normalize_resource_services],
        'interaction-checker': [b.checker_packets, b.checker_validator, b.checker_extraction_version,
            b.validate_checker_binding, b.source_sections, b.cited_text, b.source_identifier_supported,
            p.validate_identification, p.normalized_conditions],
        'interaction-generation': [b.generation_packets, b.generation_validator, b.bound_contract_refs,
            p.validate_identification, p.normalized_conditions],
        'interaction-recommendation': [b.recommendation_packets, b.recommendation_validator],
        'interaction-test-conditions': [b.test_packets, b.test_validator],
    }
    if stage in {'interaction-matching', 'interaction-verification', 'interaction-adoption'}:
        functions = [b.pair_packets, b.pair_validator, p.same_comparison_scope, p.identification]
    elif stage == 'interaction-checker-audit':
        from .interaction_audit import checker_audit_packets, checker_audit_validator
        functions = [checker_audit_packets, checker_audit_validator, b.checker_validator,
            b.validate_checker_binding, b.cited_text]
    else:
        functions = groups.get(stage, [])
    common['functions'] = {f.__name__: fingerprint(inspect.getsource(f)) for f in functions}
    if stage == 'interaction-model':
        common['exchange_fields'] = fingerprint(sorted(p.EXCHANGE_FIELDS))
        common['operation_kinds'] = fingerprint(sorted(p.OPERATION_KINDS))
    return common


def replay_versions(values):
    """Presentation-only edits do not invalidate semantic evidence."""
    return {k: v for k, v in values.items() if k != 'interaction_reports.py'}
