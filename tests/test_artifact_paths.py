from pathlib import Path
import pytest
from scene_completion.artifact_paths import relative_artifact_path


@pytest.mark.parametrize('reference', ['proofs/run/result.json', r'proofs\run\result.json', r'proofs\\run\\result.json'])
def test_cross_platform_reference_resolves_same_unchanged_bytes(tmp_path, reference):
    result = tmp_path/'proofs/run/result.json'; result.parent.mkdir(parents=True)
    result.write_bytes(b'{"original_hash_bound_evidence":true}')
    assert relative_artifact_path(tmp_path, reference) == result.resolve()
    assert relative_artifact_path(tmp_path, reference).read_bytes() == result.read_bytes()


@pytest.mark.parametrize('reference', ['../outside.json', r'..\outside.json', '/outside.json',
    r'C:\outside.json', 'C:outside.json', r'\\server\outside.json', 'a/../../outside.json', '', '\x00'])
def test_artifact_reference_cannot_change_roots_or_traverse(tmp_path, reference):
    with pytest.raises(ValueError): relative_artifact_path(tmp_path, reference)


def test_symlink_cannot_escape_root(tmp_path):
    outer=tmp_path/'outside';outer.mkdir();root=tmp_path/'run';root.mkdir()
    try:(root/'escape').symlink_to(outer, target_is_directory=True)
    except OSError:pytest.skip('symlinks not available')
    with pytest.raises(ValueError):relative_artifact_path(root, 'escape/proof.json')
