import importlib.util
import os

from PyQt5.QtWidgets import QDockWidget

class PluginManager:
    def __init__(self, host_window):
        self.host_window = host_window
        self.modules = []
        self.instances = []

    def _log(self, message):
        try:
            self.host_window.set_status(message)
        except Exception:
            pass

    def _plugin_dirs(self, runtime_base_dir):
        candidates = [
            os.path.join(runtime_base_dir, "Plugins"),
            os.path.join(runtime_base_dir, "plugins"),
            os.path.join(runtime_base_dir, "Resource", "Plugins"),
            os.path.join(runtime_base_dir, "Resource", "plugins"),
        ]
        seen = set()
        unique = []
        for path in candidates:
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen:
                continue
            seen.add(norm)
            unique.append(path)
        return unique

    def load_plugins(self, runtime_base_dir):
        self.modules = []
        self.instances = []
        loaded_count = 0
        loaded_names = set()

        for plugin_dir in self._plugin_dirs(runtime_base_dir):
            if not os.path.isdir(plugin_dir):
                continue

            for filename in sorted(os.listdir(plugin_dir)):
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue
                file_key = filename.lower()
                if file_key in loaded_names:
                    continue
                full_path = os.path.join(plugin_dir, filename)
                module_key = os.path.splitext(filename)[0]
                module_name = f"neopyxel_plugin_{module_key}_{loaded_count}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, full_path)
                    if not spec or not spec.loader:
                        self._log(f"Plugin skipped (invalid spec): {filename}")
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self.modules.append(module)

                    initialized = False
                    if hasattr(module, "register") and callable(module.register):
                        result = module.register(self.host_window)
                        if result is not None:
                            self.instances.append(result)
                            if isinstance(result, QDockWidget):
                                self.host_window.register_plugin_dock(result)
                        initialized = True
                    elif hasattr(module, "setup") and callable(module.setup):
                        # Backward-compatible entry point used by some external plugins.
                        result = module.setup(self.host_window)
                        if result is not None:
                            self.instances.append(result)
                            if isinstance(result, QDockWidget):
                                self.host_window.register_plugin_dock(result)
                        initialized = True
                    elif hasattr(module, "Plugin"):
                        instance = module.Plugin()
                        self.instances.append(instance)
                        if isinstance(instance, QDockWidget):
                            self.host_window.register_plugin_dock(instance)
                        initialized = True

                    if not initialized:
                        self._log(
                            f"Plugin skipped (no entry point): {filename} "
                            f"(expected register(app), setup(app), or class Plugin)"
                        )
                        continue

                    loaded_names.add(file_key)
                    loaded_count += 1
                    self._log(f"Plugin loaded: {filename}")
                except Exception as exc:
                    self._log(f"Plugin load failed: {filename} ({exc})")

        self._log(f"Plugin system ready: {loaded_count} plugin(s)")

    def emit(self, hook_name, *args, **kwargs):
        for module in self.modules:
            try:
                hook = getattr(module, hook_name, None)
                if callable(hook):
                    hook(*args, **kwargs)
            except Exception as exc:
                self._log(f"Plugin hook error: {module.__name__}.{hook_name} ({exc})")

        for instance in self.instances:
            try:
                hook = getattr(instance, hook_name, None)
                if callable(hook):
                    hook(*args, **kwargs)
            except Exception as exc:
                self._log(
                    f"Plugin hook error: {instance.__class__.__name__}.{hook_name} ({exc})"
                )

