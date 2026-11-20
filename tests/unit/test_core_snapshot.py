import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from scene_completion.analysis.ssd import core_snapshot
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json

BUNDLE = {"case": {"id": "UC-SNAPSHOT"}}


def write_core(_inputs, output, bundles):
    write_json(output / "architecture.json", {"elements": []})
    case = output / "cases/snapshot"
    write_json(case / "main-success.json", bundles[0])
    for file in core_snapshot.REQUIRED:
        write_json(case / file, {})
    (output / "test.md").write_text("冻结的原文", encoding="utf-8")


def access_denied():
    error = PermissionError(13, "access denied")
    error.winerror = 5
    return error


def test_core_index_retries_access_denied_without_renaming_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(core_snapshot, "write_core", write_core)
    delays, attempts = [], []
    monkeypatch.setattr(core_snapshot.time, "sleep", delays.append)

    def register(path, value):
        attempts.append(path)
        if len(attempts) == 1:
            raise access_denied()
        write_json(path, value)

    def rename(*args):
        raise AssertionError("核心快照不能依赖整目录重命名")

    monkeypatch.setattr(core_snapshot, "write_json", register)
    monkeypatch.setattr(Path, "rename", rename)
    relative = core_snapshot.pin_core(tmp_path, tmp_path, BUNDLE)
    assert delays == [0.1] and len(attempts) == 2
    assert read_json(attempts[0])["directory"] == Path(relative).name
    assert core_snapshot.pin_core(tmp_path, tmp_path, BUNDLE) == relative
    core_snapshot.verify_core_snapshot(tmp_path, {**BUNDLE, "core_snapshot": relative})

    source_map = next((tmp_path / relative).glob("cases/*/source-map.json"))
    source_map.unlink()
    with pytest.raises(ValueError, match="快照缺失或不完整"):
        core_snapshot.verify_core_snapshot(tmp_path, {**BUNDLE, "core_snapshot": relative})
    replacement = core_snapshot.pin_core(tmp_path, tmp_path, BUNDLE)
    assert replacement != relative and (tmp_path / relative).exists()


def test_unregistered_core_cannot_be_reused_after_access_denied(tmp_path, monkeypatch):
    monkeypatch.setattr(core_snapshot, "write_core", write_core)
    monkeypatch.setattr(core_snapshot.time, "sleep", lambda _: None)

    def register(*args):
        raise access_denied()

    monkeypatch.setattr(core_snapshot, "write_json", register)
    with pytest.raises(PermissionError) as rejected:
        core_snapshot.pin_core(tmp_path, tmp_path, BUNDLE)
    error = rejected.value.response_diagnostic
    assert error["operation"] == "register_core_snapshot"
    assert error["winerror"] == 5 and error["retries"] == 2
    assert error["relative_path"] == "structured-cores/" + fingerprint(BUNDLE) + ".json"
    assert not list((tmp_path / "structured-cores/.snapshots").iterdir())


def test_partial_or_invalid_index_is_ignored_and_old_complete_core_is_reused(tmp_path, monkeypatch):
    root = tmp_path / "structured-cores"
    identity = fingerprint(BUNDLE)
    legacy = root / identity[:24]
    write_json(legacy / "architecture.json", {})
    # Simulate interruption before any index commit, and then an invalid index.
    orphan = root / ".snapshots" / (identity[:24] + "-orphan")
    write_json(orphan / "architecture.json", {})
    index = root / (identity + ".json")
    write_json(index, {"identity": identity, "directory": "../wrong", "files": {}})
    monkeypatch.setattr(core_snapshot, "write_core", write_core)
    used = core_snapshot.pin_core(tmp_path, tmp_path, BUNDLE)
    assert tmp_path / used not in {legacy, orphan}
    assert legacy.is_dir() and orphan.is_dir()

    index.unlink()
    write_core(tmp_path, legacy, [BUNDLE])
    assert (
        core_snapshot.pin_core(tmp_path, tmp_path, BUNDLE)
        == legacy.relative_to(tmp_path).as_posix()
    )
    assert (tmp_path / used).is_dir()


def test_simultaneous_core_publications_keep_both_valid_paths(tmp_path, monkeypatch):
    barrier = Barrier(2)

    def delayed(*args):
        write_core(*args)
        barrier.wait(timeout=5)

    monkeypatch.setattr(core_snapshot, "write_core", delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = list(
            pool.map(lambda _: core_snapshot.pin_core(tmp_path, tmp_path, BUNDLE), range(2))
        )
    assert len(set(paths)) == 2
    assert core_snapshot.pin_core(tmp_path, tmp_path, BUNDLE) in paths
    for path in paths:
        main = next((tmp_path / path).glob("cases/*/main-success.json"))
        assert json.loads(main.read_text(encoding="utf8")) == BUNDLE
