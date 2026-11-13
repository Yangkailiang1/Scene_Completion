"""Route SSD and independent analysis imports through their supported services."""

from datetime import datetime, timezone

from scene_completion.compat.standalone.results import prepare
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json


def register(project, bundle, dry_run=False):
    from scene_completion.application import ssd_revision_service as ssd_results
    from scene_completion.domain.ssd.metrics import analyze
    from scene_completion.domain.ssd.validation import VERSION, validate

    if bundle.get("version") == VERSION:
        clean = validate(bundle)
        report = analyze(clean)
        meta = {
            "id": fingerprint(clean),
            "case": clean["case"],
            "scope": "all",
            "metrics": report["metrics"],
            "version": VERSION,
        }
        if dry_run:
            return {**meta, "dry_run": True}
        return {**meta, "revision": ssd_results.publish(project, clean)["revision"]}
    value = prepare(bundle)
    meta = value["metadata"]
    if dry_run:
        return {**meta, "dry_run": True}
    from scene_completion.workflow_core.storage import run_lock

    value.pop("scoped_evaluation")
    path = project / "imported-case-results" / (meta["id"] + ".json")
    with run_lock(path.parent):
        if path.is_file():
            meta = read_json(path)["metadata"]
        else:
            meta["imported_at"] = datetime.now(timezone.utc).isoformat()
            write_json(path, value)
        summary = path.parent / "index" / path.name
        if not summary.is_file():
            write_json(summary, meta)
    from scene_completion.compat.standalone.ssd_adapter import (
        imported_bundle as from_imported_bundle,
    )

    ssd_results.publish(project, from_imported_bundle(bundle))
    return meta


def versions(project):
    path = project / "imported-case-results"
    return sorted(
        (read_json(file) for file in (path / "index").glob("*.json")),
        key=lambda item: (item["imported_at"], item["id"]),
        reverse=True,
    )
