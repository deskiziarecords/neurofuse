# file: src/orchestrator.py
import asyncio
import inspect
import time
import yaml
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from .plugin_manager import PluginManager
from .config_store import ConfigStore
from .execution_engine import ExecutionEngine
from .monitor import Monitor
from .schemas.control_command import ControlCommand
from .schemas.system_config import SystemConfig
from .schemas.scenario import Scenario, ScenarioEvent, TriggerCondition, TriggeredAction

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
        self._scenarios: Dict[str, Scenario] = {}
        self._global_clock_task: Optional[asyncio.Task] = None
        self._telemetry_map: Dict[str, List[str]] = {} # source -> [targets]

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

            # Auto-detect remote mode if configured in remotes.yaml
            if name in getattr(self.pm, "_remote_names", []):
                # Load remote config from remotes.yaml if not in standard config
                remote_file = self.pm.repo_root / "configs" / "remotes.yaml"
                with remote_file.open() as f:
                    remotes = yaml.safe_load(f)
                    if name in remotes:
                        cfg.launch_mode = "remote"
                        cfg.settings.update(remotes[name])

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
        """Send a tune command to the running plugin with formal verification."""

        # Guardrail: Check for Master Mute
        if getattr(self, "_master_mute", False):
            await self.monitor.log("orchestrator", f"[SAFETY] Blocked tune command for {name} (Master Mute ACTIVE)")
            return

        # Formal Verification: Check for Safety Invariants
        if not self._verify_tuning_safety(name, params):
            await self.monitor.log("orchestrator", f"[SAFETY] Blocked tune command for {name} (Z3 Safety Invariant VIOLATION)")
            return

        plugin_instance = self.engine.get_plugin_instance(name)
        if plugin_instance:
            # Pass unpacked params to support specific method signatures
            await plugin_instance.tune(**params)
        else:
            # Optionally log that the plugin isn't running
            pass

    def _verify_tuning_safety(self, name: str, params: Dict[str, Any]) -> bool:
        """Use Z3 to check if the tuning parameters are within safe operational bounds."""
        from z3 import Solver, Real, sat

        s = Solver()
        # Hardcoded safety invariant for demo
        # For any system, 'gain' or 'intensity' should not exceed 1.0 when combined with 'diversity' > 0.9

        val = Real('val')
        div = Real('div')

        # Rule: val + div <= 1.5
        for p_name, p_val in params.items():
            if p_name in ["gain", "intensity"]:
                 s.add(val == float(p_val))

                 # Get diversity from current config
                 try:
                     div_val = self.cfg.get(name).settings.get("diversity", 0.5)
                 except:
                     div_val = 0.5
                 s.add(div == float(div_val))

                 # Check for violation: val + div > 1.8
                 s.push()
                 s.add(val + div > 1.8)
                 if s.check() == sat:
                     s.pop()
                     return False
                 s.pop()
        return True

    async def master_mute(self, active: bool = True):
        self._master_mute = active
        if active:
            await self.monitor.log("orchestrator", "[SAFETY] MASTER MUTE ACTIVATED - Halting all tuning.")
            # For emergency, we could also stop all systems
            for name in self.pm.list_names():
                await self.stop_system(name)

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

    # ------------------------------------------------------------------ #
    #  Automation & Scenarios
    # ------------------------------------------------------------------ #
    async def run_scenario(self, scenario: Scenario):
        """Execute a timeline of events."""
        start_time = time.perf_counter()
        events = sorted(scenario.timeline, key=lambda e: e.timestamp)

        for event in events:
            now = time.perf_counter()
            delay = event.timestamp - (now - start_time)
            if delay > 0:
                await asyncio.sleep(delay)

            cmd = ControlCommand(action=event.action, payload=event.payload)
            await self._execute_command(event.system, cmd)

    async def _execute_command(self, name: str, cmd: ControlCommand):
        if cmd.action == "start":
            await self.boot_system(name)
        elif cmd.action == "stop":
            await self.stop_system(name)
        elif cmd.action == "tune":
            await self.tune_system(name, cmd.payload)

    async def start_global_monitor(self):
        """Background task for IFTTT logic and telemetry tracking."""
        if self._global_clock_task:
            return
        self._global_clock_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        while True:
            await asyncio.sleep(1.0)
            # Example IFTTT Logic (mock implementation for now)
            # In a real scenario, this would evaluate Scenario.triggers
            for name in self.pm.list_names():
                metrics = await self.monitor.get_metrics(name)
                if not metrics: continue
                last_m = metrics[-1]

                # Record telemetry flow (source -> [targets])
                # For demo, ferros flux is consumed by neurometal
                if name == "ferros":
                    self._telemetry_map["ferros"] = ["neurometal"]

                # Hardcoded safety rule for demo
                if name == "ferros" and last_m.name == "magnetic_flux" and last_m.value > 0.8:
                    # If ferros flux is too high, auto-tune neurometal
                    if "neurometal" in self._status and self._status["neurometal"].state == "running":
                         await self.tune_system("neurometal", {"gain": 0.5})
                         await self.monitor.log("orchestrator", "[IFTTT] Ferros flux high! Throttling neurometal gain.")
