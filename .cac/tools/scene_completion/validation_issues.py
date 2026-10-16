"""Machine-readable validation failures; never a semantic acceptance shortcut."""
from .sources import fingerprint


class ValidationFailure(ValueError):
    def __init__(self, message, issues):
        super().__init__(message)
        self.validation_diagnostic = {'schema': 'scene-validation-issues-v1', 'issues': issues}


def normalization_issue(source, error):
    fields = {
        'every necessary condition needs a semantic code': ['condition_codes'],
        'unique canonical conditions required': ['condition_codes'],
        'canonical semantic code required: object_code': ['object_code'],
        'canonical semantic code required: cause_code': ['cause_code'],
        'normalization needs exact original abnormal scenario evidence': ['evidence_quote'],
    }
    changed = fields.get(str(error), [])
    return {'item_id': source['scenario_id'], 'category': 'output_contract' if changed else 'semantic_or_source',
        'fields': changed, 'message': str(error), 'directed_repair_safe': bool(changed),
        'allowed_evidence': source.get('source_refs', []),
        'immutable_fields': ['source_scenario_id', 'source_refs', 'exchange_id', 'mount_id']}


def direct_plan(failure):
    diagnostics = failure.get('validation_diagnostics', {})
    errors = set(failure.get('errors', {}))
    if (not errors or set(diagnostics) != errors or failure.get('findings')
            or set(failure.get('pending', [])) - errors):
        return None
    issues = [i for d in diagnostics.values() for i in d.get('issues', [])]
    if not issues or not all(i.get('directed_repair_safe') and i.get('fields') and i.get('item_id') for i in issues):
        return None
    plan = {'action': 'repair', 'reason': 'Repair the validator-identified fields from their own permitted source; preserve successful rows and all immutable fields.',
        'targets': [i['item_id'] + '.' + f for i in issues for f in i['fields']],
        'evidence_quotes': [], 'validation_issues': issues}
    return plan, {'kind': 'deterministic_validation_plan', 'failure_hash': fingerprint(failure),
        'issues_hash': fingerprint(issues), 'model_calls': 0}
