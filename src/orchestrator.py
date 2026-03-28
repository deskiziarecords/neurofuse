# file: src/orchestrator.py
import asyncio
import inspect
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from .plugin_manager import PluginManager
from .config_store import ConfigStore
from .execution_engine import ExecutionEngine
from .monitor import Monitor
from .schemas.control_command import ControlCommand
from .schemas.system_config import SystemConfig

@dataclass
class SystemStatus:
    name: str
    state: str = "stopped"   # stopped, starting, running, stopping, error
    uptime: float = 0.0
    last_error: Optional[str] = None
    config: Optional[SystemConfig] = None

class Orchestrator:
    def __init__(self, pm: PluginManager, cfg_store: ConfigStore, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.pm = pm
        self.cfg = cfg_store
        self.engine = ExecutionEngine()
        self.monitor = Monitor()
        self.loop = loop or asyncio.get_event_loop()
        self._status: Dict[str, SystemStatus] = {}
        self._start_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    #  Life‑cycle
    # ------------------------------------------------------------------ #
    async def boot_system(self, name: str):
        async with self._lock:
            if name in self._status and self._status[name].state == "running":
                return  # already running
            self._status[name] = SystemStatus(name=name, state="starting")
        try:
            cfg = self.upsert_config(name)  # ensure config exists
            plugin_cls = self.pm.get(name)
            await self.engine.start(name, plugin_cls, cfg.model_dump())
            async with self._lock:
                st = self._status[name]
                st.state = "running"
                st.config = cfg
                self._start_times[name] = time.perf_counter()
        except Exception as exc:
            async with self._lock:
                if name not in self._status:
                     self._status[name] = SystemStatus(name=name)
                self._status[name].state = "error"
                self._status[name].last_error = str(exc)
            raise

    async def stop_system(self, name: str):
        async with self._lock:
            if name not in self._status or self._status[name].state != "running":
                return
            self._status[name].state = "stopping"
        await self.engine.stop(name)
        async with self._lock:
            self._status[name].state = "stopped"
            uptime = time.perf_counter() - self._start_times.pop(name, 0.0)
            self._status[name].uptime = uptime

    # ------------------------------------------------------------------ #
    #  Tuning
    # ------------------------------------------------------------------ #
    async def tune_system(self, name: str, params: Dict[str, Any]):
        """Send a tune command to the running plugin."""
        plugin_instance = self.engine.get_plugin_instance(name)
        if plugin_instance:
            # Pass unpacked params to support specific method signatures
            await plugin_instance.tune(**params)
        else:
            # Optionally log that the plugin isn't running
            pass

    # ------------------------------------------------------------------ #
    #  Introspection
    # ------------------------------------------------------------------ #
    def get_tunable(self, name: str):
        """Return a dict of tunable fields with (type, default) from the plugin's tune signature."""
        plugin_cls = self.pm.get(name)
        sig = inspect.signature(plugin_cls.tune)
        tunable = {}

        # Collect individual parameters
        for pname, param in sig.parameters.items():
            if pname == "self":
                continue
            typ = param.annotation if param.annotation != inspect.Parameter.empty else str
            default = param.default if param.default != inspect.Parameter.empty else None
            tunable[pname] = (typ, default)

        # Heuristic: if 'params' is an argument, pull from config settings
        if "params" in tunable:
             # Try to find values from the current config
             try:
                 cfg = self.cfg.get(name)
                 for key, val in cfg.settings.items():
                     tunable[key] = (type(val), val)
                 # Remove 'params' after expanding settings
                 del tunable["params"]
             except Exception:
                 pass

        # Special case for the 'hello' mock plugin if it doesn't have settings yet
        if not tunable and name == "hello":
             tunable["rate"] = (float, 0.5)

        return tunable

    # ------------------------------------------------------------------ #
    #  Status & Config helpers
    # ------------------------------------------------------------------ #
    def get_status(self, name: str) -> SystemStatus:
        if name not in self._status:
             # Try to load config to see if it exists
             try:
                 cfg = self.cfg.get(name)
                 self._status[name] = SystemStatus(name=name, state="stopped", config=cfg)
             except FileNotFoundError:
                 return SystemStatus(name=name, state="unknown")

        # Update uptime if running
        st = self._status[name]
        if st.state == "running" and name in self._start_times:
            st.uptime = time.perf_counter() - self._start_times[name]
        return st

    def list_systems(self) -> List[SystemConfig]:
        # Systems are those found by plugin manager
        systems = []
        for name in self.pm.list_names():
            systems.append(self.upsert_config(name))
        return systems

    def upsert_config(self, name: str) -> SystemConfig:
        """Load existing config or create a sensible default."""
        try:
            return self.cfg.get(name)
        except FileNotFoundError:
            default = SystemConfig(name=name)
            self.cfg.upsert(default)
            return default

    # ------------------------------------------------------------------ #
    #  Monitoring passthrough
    # ------------------------------------------------------------------ #
    async def stream_logs(self, name: str, limit: int = 200):
        return await self.monitor.get_logs(name, limit)

    async def stream_metrics(self, name: str):
        return await self.monitor.get_metrics(name)

    def send_command(self, name: str, cmd: ControlCommand):
        """Bridge for the UI to send commands easily using the pre-configured loop."""
        if cmd.action == "start":
            asyncio.run_coroutine_threadsafe(self.boot_system(name), self.loop)
        elif cmd.action == "stop":
            asyncio.run_coroutine_threadsafe(self.stop_system(name), self.loop)
        elif cmd.action == "tune":
            asyncio.run_coroutine_threadsafe(self.tune_system(name, cmd.payload), self.loop)
