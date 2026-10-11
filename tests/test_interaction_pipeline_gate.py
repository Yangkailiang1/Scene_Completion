"""Never run downstream participant calls against a rejected normal graph."""
from types import SimpleNamespace

import pytest

from scene_completion import interaction_cli as pipeline
from scene_completion import interaction_model_audit, interaction_origins, interaction_graph_checks
from scene_completion import interaction_participants, role_cli
from scene_completion.semantic_backend import write_json, read_json
from scene_completion.sources import index_sources


@pytest.mark.parametrize('audit_complete', [False, True])
def test_rejected_or_incomplete_source_audit_defers_actors_but_runs_checker(tmp_path, monkeypatch, audit_complete):
    documents = []
    for layer in ('RR', 'SR'):
        path = tmp_path / (layer + '.md')
        path.write_text('# Clinic\n## UC-A\nPatient requests a record.\n', encoding='utf-8')
        documents.append(str(path))
    index = index_sources(documents)
    for document, layer in zip(index['documents'], ('RR', 'SR')):
        document['requirement_layer'] = layer
    base = tmp_path / 'base.json'
    write_json(base, {'use_cases': [{'use_case_id': 'UC-A'}]})
    root = tmp_path / 'run'
    args = SimpleNamespace(model=str(base), output_dir=str(root), agent_mode='packets', rerank=False)
    monkeypatch.setattr(pipeline, 'source_index', lambda args: index)
    monkeypatch.setattr(pipeline, 'versions', lambda: {})
    monkeypatch.setattr(role_cli, '_client', lambda *args: SimpleNamespace(config={}, model=lambda kind: 'ecnu-max'))
    monkeypatch.setattr(pipeline, 'merge_model', lambda *args: {'nodes': [], 'use_cases': [], 'model_gaps': []})
    monkeypatch.setattr(pipeline, 'architecture_proposals', lambda *args: [])
    monkeypatch.setattr(interaction_origins, 'audit_model_origins', lambda *args: {'checks': []})
    monkeypatch.setattr(interaction_graph_checks, 'check_graph_anchors', lambda *args: {'checks': []})
    prepared = []

    def prepare(directory):
        saved = read_json(root / 'run_manifest.json')
        assert saved['source_hash'] and saved['model'] == 'ecnu-max'
        assert saved['complete'] is False and saved['accepted'] is False
        prepared.append(directory.name)
        write_json(directory / 'manifest.json', {'batches': []})

    monkeypatch.setattr(pipeline.batches, 'model_packets', lambda *args: prepare(args[-1]))
    monkeypatch.setattr(pipeline.batches, 'checker_packets', lambda *args: prepare(args[-1]))
    monkeypatch.setattr(interaction_model_audit, 'model_audit_packets', lambda *args, **kwargs: prepare(args[-1]))

    def actors_must_not_run(*args):
        pytest.fail('source audit did not pass, so actor packets must not run')

    monkeypatch.setattr(interaction_participants, 'participant_packets', actors_must_not_run)

    def collect(directory, validator):
        saved = read_json(root / 'run_manifest.json')
        assert saved['stages'][directory.name]['status'] == 'prepared'
        assert saved['stages'][directory.name]['complete'] is False
        if directory.name == 'interaction-model':
            return [{}], {'complete': True}
        if directory.name == 'interaction-model-audit':
            return ([{'passed': False}] if audit_complete else []), {'complete': audit_complete}
        assert directory.name == 'interaction-checker'
        return [], {'complete': False}

    monkeypatch.setattr(pipeline, 'collect_packets', collect)
    manifest, code = pipeline.run(args)
    assert code == 0  # Packet preparation is pending, never accepted.
    assert prepared == ['interaction-model', 'interaction-model-audit', 'interaction-checker']
    assert manifest['pending_participant_checks'] is True
    assert manifest['stages']['interaction-participants']['status'] == 'awaiting_normal_source_audit'
    assert manifest['complete'] is False and manifest['accepted'] is False
