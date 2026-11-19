"""Native Windows acceptance of the exact shipped interpreter and web app."""

import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


def verify_windows_dependencies(bundle, python_version="3.12.10"):
    """Read wheel metadata without importing Windows extensions on the builder."""
    from importlib import metadata

    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    site = Path(bundle) / "python/Lib/site-packages"
    distributions = list(metadata.distributions(path=[str(site)]))
    if not distributions:
        raise ValueError("No installed Windows dependencies")
    versions = {canonicalize_name(d.metadata["Name"]): d.version for d in distributions}
    env = default_environment()
    env.update(
        os_name="nt",
        sys_platform="win32",
        platform_system="Windows",
        platform_machine="AMD64",
        python_version=".".join(python_version.split(".")[:2]),
        python_full_version=python_version,
        implementation_name="cpython",
        extra="",
    )
    errors = []
    for d in distributions:
        for raw in d.requires or []:
            req = Requirement(raw)
            if req.marker and not req.marker.evaluate(env):
                continue
            version = versions.get(canonicalize_name(req.name))
            if version is None or version not in req.specifier:
                errors.append(f"{d.metadata['Name']} requires {req}; installed={version}")
    if errors:
        raise ValueError("Windows dependency closure failed: " + "; ".join(errors))
    return {
        "windows_distributions": len(distributions),
        "python": python_version,
        "metadata_dependencies": "passed",
    }


def verify_files(bundle):
    bundle = Path(bundle).resolve()
    manifest = json.loads((bundle / "SHA256SUMS.json").read_text(encoding="utf8"))
    assert manifest["platform"] == "windows-x64" and not manifest["requires_network_install"]
    for name, digest in manifest["files"].items():
        path = (bundle / name).resolve()
        if not path.is_relative_to(bundle):
            raise ValueError("Manifest path escapes bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("File digest mismatch: " + name)
    forbidden = {
        ".env",
        ".git",
        ".venv",
        ".workbench",
        "node_modules",
        "model.local.json",
        ".DS_Store",
        "__pycache__",
    }
    for name in manifest["files"]:
        if forbidden.intersection(Path(name).parts):
            raise ValueError("Private or builder-only path in distribution: " + name)
    return manifest


def verify_worker_entrypoints(bundle, executable=None):
    """Start real child scripts independently, not merely the parent web app."""
    bundle = Path(bundle).resolve()
    python = Path(executable) if executable else bundle / "python/python.exe"
    results = []
    for name in ("infrastructure/project_worker.py", "manager/manager_worker.py"):
        script = bundle / "app/src/scene_completion" / name
        process = subprocess.run(
            [str(python), "-I", "-X", "utf8", "-B", str(script), "--help"],
            cwd=bundle.parent,
            capture_output=True,
            encoding="utf8",
            timeout=30,
        )
        if process.returncode or "--project" not in process.stdout:
            raise RuntimeError(
                f"Worker startup failed: {name}; exit={process.returncode}; "
                + process.stderr[-4000:]
            )
        results.append(name)
    return {"worker_entrypoints": results, "worker_startup": "passed"}


def verify_portable_layout(bundle):
    """The shipped suite must not depend on development datasets or test helpers."""
    bundle = Path(bundle)
    app = bundle / "app"
    prompt = bundle / "CODING-AGENT.md"
    prompt_source = app / "deployment/windows/CODING-AGENT.md"
    if not prompt.is_file() or prompt.read_bytes() != prompt_source.read_bytes():
        raise ValueError("Portable Coding Agent prompt missing or inconsistent")
    tests = app / "tests"
    collected = sorted(tests.rglob("test_*.py"))
    if not collected or any(not path.is_relative_to(tests / "portable") for path in collected):
        raise ValueError("The portable bundle must contain only tests/portable test modules")
    for name in (
        "tests/support/paths.py",
        "tests/fixtures/memory_repository/acceptance.json",
        "tests/fixtures/compat/standalone/submitted-bundle.json",
        "tests/fixtures/compat/standalone/prepared-snapshot.json",
        "tests/fixtures/compat/standalone/refined-existing-snapshot.json",
        "deployment/windows/launcher.py",
    ):
        if not (app / name).is_file():
            raise ValueError("Portable resource missing: " + name)
    if (app / "datasets").exists() or (app / "deployment/experiments").exists():
        raise ValueError("Development datasets or experiments must not enter the portable bundle")
    return {"portable_test_modules": len(collected), "portable_resources": "passed"}


def local_cli(work, *args, expected_exit=0):
    cli = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "scene.cmd",
            "--local",
            "--data-dir",
            "data",
            "--env-file",
            ".env",
            *args,
        ],
        cwd=work,
        capture_output=True,
        encoding="utf8",
        timeout=30,
    )
    if cli.returncode != expected_exit:
        raise RuntimeError("Unexpected local CLI exit: " + cli.stdout + cli.stderr)
    return json.loads(cli.stdout)


def verify_deep_materials(work, request):
    source = work.parent / "长路径输入"
    relative = Path("cases") / ("业务 数据" * 20) / ("结构 文件" * 20)
    case = source / relative / "authoring-case.json"
    spec = source / relative / "系统需求_spec.md"
    assert len(str(case)) > 260
    extended = Path("\\\\?\\" + str(case))
    extended.parent.mkdir(parents=True, exist_ok=True)
    quote = "用户读取条目。"
    extended.with_name(spec.name).write_text("# 需求\n" + quote + "\n", encoding="utf8")
    extended.write_text(
        json.dumps(
            {
                "version": "authoring-case-v1",
                "case": {"id": "UC-LONG", "name": "长路径建档"},
                "steps": [
                    {
                        "id": "S1",
                        "order": 1,
                        "sender": {"id": "user", "kind": "external_actor"},
                        "receiver": {"id": "system", "kind": "internal_service"},
                        "operation": {"name": "读取条目", "crud": ["read"]},
                        "source_refs": [
                            {"document": spec.name, "start_line": 2, "end_line": 2, "quote": quote}
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf8",
    )
    if os.environ.get("SCENE_VERIFY_LEGACY_MAX_PATH") == "1":
        try:
            case.read_bytes()
        except OSError as error:
            if getattr(error, "winerror", None) not in {2, 3, 206} and error.errno != 2:
                raise
        else:
            raise AssertionError("The control read did not reproduce the Windows MAX_PATH error")

    web = json.loads(
        request(
            "/api/projects/from-input-bundle",
            {"name": "长路径网页建档", "directory": str(source), "adopt_partial": True},
        )
    )
    cli = local_cli(
        work, "create", "--name", "长路径CLI建档", "--input-dir", str(source), "--adopt-partial"
    )
    assert web["input_bundle"]["saved"] and cli["input_bundle"]["saved"]
    assert local_cli(work, "status", "--project", web["id"])["job"]["status"] == "ready"

    core = work.parent / "长路径核心" / ("核心数据" * 36) / ("转换数据" * 36) / "core"
    assert len(str(core)) > 260
    conversion = local_cli(
        work, "core-input", "convert", "--input", str(source), "--output", str(core)
    )
    assert conversion["case_ids"] == ["UC-LONG"]
    assert local_cli(work, "core-input", "validate", "--input", str(core))["valid"]
    extended_core = extended.parents[4] / core.relative_to(work.parent)
    sidecar = next(extended_core.glob("cases/*/source-map.json"))
    sidecar.unlink()
    invalid = local_cli(work, "core-input", "validate", "--input", str(core), expected_exit=2)
    assert not invalid["valid"] and any(
        "缺少核心分件：source-map.json" in row["reason"] for row in invalid["issues"]
    )

    code = r"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "app/src"))
from scene_completion.infrastructure.storage import io_path, read_json
from scene_completion.application.execution import Execution
from scene_completion.application.ssd_revision_service import editor
from scene_completion.workflow.ssd_pipeline import build_structured, input_directory
for rid in sys.argv[1:3]:
    project = Path.cwd() / "data" / rid
    point = read_json(project / "imports/ssd-input.json")
    assert not Path(point["path"]).anchor
    relative = Path(sys.argv[3])
    frozen = project / point["path"] / relative
    assert len(str(frozen)) > 260 and io_path(frozen).is_file()
    ex = Execution(project / "run", case_ids=["UC-LONG"])
    assert ex.client is None
    assert build_structured(ex, input_directory(ex))
    assert ex.scheduler.run()["complete"]
    task = ex.scheduler.state["tasks"]["UC-LONG:ssd-prepare"]
    assert task["status"] == "passed"
    assert any(
        ref.get("origin", {}).get("start_line") == 2
        for ref in editor(project, "UC-LONG")["bundle"]["steps"][0]["source_refs"]
    )
"""
    result = subprocess.run(
        [
            str(work / "python/python.exe"),
            "-X",
            "utf8",
            "-c",
            code,
            web["id"],
            cli["id"],
            (relative / case.name).as_posix(),
        ],
        cwd=work,
        capture_output=True,
        encoding="utf8",
        timeout=90,
    )
    if result.returncode:
        raise RuntimeError("Deep Windows path failed during SSD preparation: " + result.stderr)
    origin = urllib.parse.quote("origin:" + (relative / spec.name).as_posix(), safe="")
    view = json.loads(
        request(f"/api/projects/{web['id']}/sources/{origin}?start=2&end=2&context=0")
    )
    assert view["lines"] == [{"number": 2, "text": quote}]
    return {
        "long_path_cli_and_web_create": "passed",
        "long_path_core_validate": "passed",
        "long_path_ssd_and_provenance": "passed",
    }


def smoke(bundle):
    if os.name != "nt":
        raise RuntimeError(
            "Native acceptance requires Windows; cross-built files do not prove runtime success"
        )
    bundle = Path(bundle).resolve()
    portable_checks = verify_portable_layout(bundle)
    manifest = verify_files(bundle)
    verify_windows_dependencies(bundle, manifest["python"])
    # Customer paths often contain spaces and non-ASCII characters.
    work = bundle.parent / "Windows 离线验证路径" / bundle.name
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(bundle, work)
    python = work / "python/python.exe"
    worker_checks = verify_worker_entrypoints(work)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log = work.parent / "startup.log"
    with log.open("w", encoding="utf8") as stream:
        process = subprocess.Popen(
            [
                str(python),
                "-X",
                "utf8",
                str(work / "launcher.py"),
                "--no-browser",
                "--port",
                str(port),
            ],
            cwd=work,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"

        def request(path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(
                base + path, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()

        try:
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Launcher failed: " + log.read_text(encoding="utf8"))
                try:
                    request("/api/projects")
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise RuntimeError("Web app did not become ready")
                    time.sleep(0.25)
            assert b"<html" in request("/").lower()
            template = request("/api/test-sources/template")
            expected = (work / "app/examples/tests/mall-exception-tests.xlsx").read_bytes()
            assert template == expected, "Excel template must be shipped intact"
            if (work / "data/.review-mode.json").exists():
                projects = json.loads(request("/api/projects"))
                entries = (
                    projects.get("projects", projects) if isinstance(projects, dict) else projects
                )
                assert entries, "Review package has no project"
                rid = entries[0]["id"]
                view = json.loads(request("/api/projects/" + rid))
                assert view["review_only"]
                assert json.loads(request("/api/projects/" + rid + "/sources"))["documents"]
                try:
                    request("/api/projects/" + rid + "/run", {})
                except urllib.error.HTTPError as error:
                    assert error.code == 403
                else:
                    raise AssertionError("Business package allowed model execution")
                print(
                    json.dumps(
                        {
                            "native_windows": True,
                            "review_only": True,
                            "source_commit": manifest["source_commit"],
                            "portable_sources": "passed",
                            "execution_blocked": "passed",
                            "model_calls": 0,
                            **worker_checks,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                return
            test = {"name": "mall.xlsx", "content_base64": base64.b64encode(template).decode()}
            preview = json.loads(request("/api/test-sources/preview", {"sources": [test]}))
            assert (
                preview["valid"]
                and preview["counts"]["exception"] > 0
                and preview["counts"]["pending"] > 0
            )
            meta = json.loads(
                request(
                    "/api/projects",
                    {
                        "name": "Windows原生离线启动验收",
                        "sources": {
                            "RR": [{"name": "rr.md", "content": "# RR\n离线测试"}],
                            "SR": [{"name": "sr.md", "content": "# SR\n离线测试"}],
                            "test": [test],
                        },
                    },
                )
            )
            view = json.loads(request("/api/projects/" + meta["id"] + "/test-sources"))
            assert view["preview"]["counts"] == preview["counts"]
            assert local_cli(work, "status", "--project", meta["id"])["job"]["status"] == "ready"
            path_checks = verify_deep_materials(work, request)
            print(
                json.dumps(
                    {
                        "native_windows": True,
                        "source_commit": manifest["source_commit"],
                        "python": manifest["python"],
                        "manifest_files": len(manifest["files"]),
                        "unicode_space_path": True,
                        "launcher_and_http": "passed",
                        "local_cli_and_web_share_project": "passed",
                        "xlsx_preview_and_project": "passed",
                        "model_calls": 0,
                        **worker_checks,
                        **portable_checks,
                        **path_checks,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        finally:
            # Only the acceptance process and its child server are terminated.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process.wait(timeout=15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle")
    args = parser.parse_args()
    smoke(args.bundle)
