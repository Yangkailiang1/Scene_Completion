"""Configured model clients shared by CLI, HTTP and background workers."""

from pathlib import Path


def client_for(config, root, env_file=None):
    from scene_completion.models.configuration.model_configuration import referenced_env_keys
    from scene_completion.models.transport.http_transport import load_ecnu_env_file

    if env_file and Path(env_file).exists():
        load_ecnu_env_file(env_file, referenced_env_keys(config))
    config = dict(config)
    config.setdefault("cache_dir", str(root / "model_cache"))
    if config.get("agent_runtime") == "deepagents":
        from scene_completion.models.clients.deepagents_client import DeepAgentsClient

        config["run_root"] = str(root)
        config.setdefault("indexed_context", True)
        return DeepAgentsClient(config)
    if config.get("agent_runtime") == "luna-subprocess":
        from scene_completion.models.clients.native_client import NativeClient

        config.update(native_run_root=str(root), native_run_dir=str(root / "native"))
        return NativeClient(config)
    from scene_completion.models.clients.model_client import SemanticClient

    return SemanticClient(config)
