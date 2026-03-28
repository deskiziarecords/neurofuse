import importlib.util
from pathlib import Path
from typing import Dict
from neurofuse_sdk import BasePlugin

class PluginManager:
    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root)
        self._plugins: Dict[str, type[BasePlugin]] = {}

    def load_all(self):
        # Look for plugins in the 'plugins' directory at the repo root
        plugin_base_dir = self.repo_root / "plugins"
        for plugin_dir in plugin_base_dir.glob("*/"):
            if not plugin_dir.is_dir():
                continue
            init_file = plugin_dir / "__init__.py"
            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.is_file():
                continue

            # Use importlib to load the plugin module
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_dir.name}.plugin", plugin_file
            )
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore

            # Expect module to expose a class named `Plugin`
            plugin_cls = getattr(module, "Plugin", None)
            if not isinstance(plugin_cls, type) or not issubclass(plugin_cls, BasePlugin):
                # Optionally log a warning or raise an error
                # For now, we follow the README logic
                # raise ImportError(f"Plugin {plugin_dir.name} does not expose a valid BasePlugin subclass")
                continue
            self._plugins[plugin_dir.name] = plugin_cls

    def get(self, name: str) -> type[BasePlugin]:
        if name not in self._plugins:
            raise KeyError(f"Plugin {name} not found")
        return self._plugins[name]

    def list_names(self):
        return list(self._plugins.keys())
