"""Versioned concern DAG; migration aliases are documentation, not live keys."""
from pathlib import Path
from copy import deepcopy
import json
from functools import lru_cache
from .storage import fingerprint


def validate_registry(value):
    if value.get('version')!='interaction-concerns-v3':raise ValueError('unsupported concern registry version')
    digest=fingerprint({k:v for k,v in value.items() if k!='hash'})
    if value.get('hash')!=digest:raise ValueError('concern registry digest mismatch')
    definitions=value['definitions']
    if not definitions:raise ValueError('empty concern registry')
    visiting=set();done=set()
    def visit(key):
        if key not in definitions:raise ValueError('unknown concern parent/profile target: '+key)
        if key in visiting:raise ValueError('concern inheritance cycle')
        if key in done:return
        d=definitions[key]
        if d['key']!=key:raise ValueError('concern ID/key mismatch')
        visiting.add(key)
        for parent in d['parents']:visit(parent)
        visiting.remove(key);done.add(key)
    for key in definitions:visit(key)
    def profiles(node):
        if isinstance(node,dict):
            for v in node.values():profiles(v)
        else:
            for key in node:visit(key)
    profiles(value['profiles'])
    for old,row in value['legacy_mapping'].items():
        if not row['targets'] and row.get('status')!='retired_by_user_taxonomy':raise ValueError('empty migration target')
        for target in row['targets']:visit(target)
    return value


@lru_cache(maxsize=4)
def _parsed(text):
    return validate_registry(json.loads(text))

def registry():
    return deepcopy(_parsed(Path(__file__).with_name('concern_registry.json').read_text(encoding='utf8')))


def inheritance_paths(key,direction=None,functional_types=None):
    definitions=registry()['definitions']
    def walk(k):
        parents=definitions[k]['parents']
        if not parents:return [[k]]
        return [path+[k] for p in parents for path in walk(p)]
    paths=walk(key)
    if key.startswith('api.data.') and direction:
        root='service.base.response_contract' if direction=='return' else 'service.base.request_data'
        paths=[p for p in paths if p[0]==root]
    if functional_types is not None:
        active=set(functional_types)
        paths=[path for path in paths if all(definitions[k]['layer']!='functional' or definitions[k]['group'] in active for k in path)]
        refined=[path for path in paths if any(definitions[k]['layer']=='functional' for k in path)]
        if refined:paths=refined
    return paths


def failure_family(key):
    return registry()['definitions'].get(key,{}).get('failure_family',key)
