# neurofuse
The Intelligence Welding Studio
[neurofuse](https://github.com/deskiziarecords/neurofuse/blob/main/neuro-all.jpg)


##  Table of Contents  

<details>
  <summary>Click to expand</summary>

- [1. High‑Level Architecture](#1-high-level-architecture)  
- [2. Core Modules & Responsibilities](#2-core-modules--responsibilities)  
- [3. Plugin Interface (the contract each repo must obey)](#3-plugin-interface-the-contract-each-repo-must-obey)  
- [4. Data Models & Persistence](#4-data-models--persistence)  
- [5. Streamlit UI Layers](#5-streamlit-ui-layers)  - [6. Key Functions & API Endpoints](#6-key-functions--api-endpoints)  - [7. Concurrency, Safety & Observability](#7-concurrency-safety--observability)  
- [8. Deployment & DevOps Tips](#8-deployment--devops-tips)  
- [9. Minimal Working Example (Skeleton)](#9-minimal-working-example-skeleton)  

</details>  

---  

## 1. High‑Level Architecture  

```
+-------------------+      +----------------------+      +-------------------+
|   Streamlit UI    |<---> |   Central Orchestrator|<--->|   Plugin Registry |
| (pages, widgets) |      |  (state, scheduler)  |      | (discovery, load) |
+-------------------+      +----------------------+      +-------------------+
          ^                         ^                         ^
          |                         |                         |
          |                         |                         v
          |                 +-------------------+   +-------------------+
          |                 |   Config Store    |   |   Execution Engine|
          |                 | (YAML/JSON/DB)    |   | (subprocess/async)|
          |                 +-------------------+   +-------------------+
          |                         ^                         ^
          |                         |                         |
          +-------------------------+-------------------------+
                                    |
                           +-------------------+
                           |   Monitoring &    |
                           |   Logging Service |
                           +-------------------+
```

* **Streamlit UI** – the only user‑facing layer; built from reusable components.  
* **Central Orchestrator** – holds the *runtime state* of every plug‑in (booted, stopped, config, metrics).  
* **Plugin Registry** – scans the monorepo for valid plug‑ins, loads them dynamically, and exposes a uniform API.  
* **Config Store** – persists per‑plug‑in configuration (versioned, supports hot‑reload).  
* **Execution Engine** – launches each plug‑in in an isolated process / async task, streams stdout/stderr, and forwards control commands (start, stop, pause, tune).  
* **Monitoring & Logging** – aggregates logs, metrics, and health‑checks; feeds back to the UI for dashboards/alerts.  

---  

## 2. Core Modules & Responsibilities  

| Module (file) | Primary Responsibility | Key Public Functions / Classes |
|---------------|------------------------|--------------------------------|
| `orchestrator.py` | Global state machine, life‑cycle management | `Orchestrator`, `boot_system(name)`, `stop_system(name)`, `get_status()` |
| `plugin_manager.py` | Discovery, dynamic import, versioning | `PluginManager`, `load_plugins(path)`, `get_plugin(name)` |
| `config_store.py` | Load/save YAML/JSON, schema validation, hot‑reload | `ConfigStore`, `get_config(name)`, `update_config(name, patch)` |
| `execution_engine.py` | Spawn subprocesses / asyncio tasks, stream I/O | `ExecutionEngine`, `run(name, args)`, `send_command(name, cmd)`, `terminate(name)` |
| `monitor.py` | Collect logs, metrics, health checks | `Monitor`, `subscribe(name)`, `publish_metric(name, metric)` |
| `ui/` (folder) | Streamlit pages & reusable widgets | `dashboard.py`, `system_controls.py`, `log_viewer.py`, `config_editor.py` |
| `schemas/` | Pydantic models for config, commands, metrics | `SystemConfig`, `ControlCommand`, `MetricSample` |
| `utils/` | Helpers (logging, version parsing, git utils) | `get_git_revision()`, `deep_merge()` |

---  

## 3. Plugin Interface (the contract each repo must obey)  

Every plug‑in (e.g., `synth-fuse`) must expose a **Python package** with the following structure:

```
my_plugin/
├─ __init__.py          # exposes Plugin class
├─ plugin.py            # implements BasePlugin
├─ config_schema.yaml   # optional JSON‑Schema for validation
└─ README.md
```

### 3.1 Base Plugin (abstract)

```python
# file: plugins/base_plugin.py
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator
import asyncio

class BasePlugin(ABC):
    """
    All autonomous systems must subclass this.
    The orchestrator treats the instance as a black‑box that can:
      - be started/stopped,
      - receive tune commands,
      - emit async logs/metrics.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self._process: asyncio.Task | None = None    @abstractmethod
    async def start(self) -> None:
        """Launch the system; should run until stop() is called."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shutdown; cancel background tasks."""
        ...

    @abstractmethod
    async def tune(self, params: Dict[str, Any]) -> None:
        """Apply runtime tuning parameters (e.g., learning rate, gain)."""
        ...

    @abstractmethod
    async def stream_logs(self) -> AsyncGenerator[str, None]:
        """Yield log lines as they appear."""
        ...

    @abstractmethod
    async def stream_metrics(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield metric dicts (e.g., loss, throughput)."""
        ...
```

*Each repo only needs to implement the five async methods.*  
The orchestrator will wrap the instance in a task and pipe its streams to the monitoring service.

---  

## 4. Data Models & Persistence  ### 4.1 Pydantic Schemas (`schemas/`)

```python
# file: schemas/system_config.py
from pydantic import BaseModel, Field
from typing import Optional, Literal

class SystemConfig(BaseModel):
    name: str = Field(..., description="Unique identifier, matches repo folder name")
    version: str = Field("0.1.0", description="Semantic version of the plug‑in")
    enabled: bool = True
    # free‑form plug‑in specific settings – validated against its own JSON‑Schema if present
    settings: Dict[str, Any] = Field(default_factory=dict)
    # execution preferences
    launch_mode: Literal["subprocess", "asyncio"] = "subprocess"
    env: Dict[str, str] = Field(default_factory=dict)
```

```python
# file: schemas/control_command.py
from pydantic import BaseModel
from typing import Literal, Anyclass ControlCommand(BaseModel):
    action: Literal["start", "stop", "tune", "pause", "resume"]
    payload: Dict[str, Any] = Field(default_factory=dict)
```

```python
# file: schemas/metric_sample.py
from pydantic import BaseModel
from datetime import datetime
from typing import Any

class MetricSample(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    system: str
    name: str                     # e.g., "loss", "fps"
    value: float
    tags: Dict[str, str] = Field(default_factory=dict)
```

### 4.2 Config Store (simple file‑based, can be swapped for SQLite/Postgres)

```python
# file: config_store.py
import yaml, json, os
from pathlib import Path
from .schemas.system_config import SystemConfig

CONFIG_DIR = Path(__file__).parent / "configs"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

class ConfigStore:
    def _path(self, name: str) -> Path:
        return CONFIG_DIR / f"{name}.yaml"

    def get(self, name: str) -> SystemConfig:
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"No config for {name}")
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return SystemConfig(**data)

    def upsert(self, cfg: SystemConfig) -> None:
        path = self._path(cfg.name)
        with path.open("w") as f:
            yaml.dump(cfg.dict(), f, sort_keys=False)

    def list_all(self) -> list[SystemConfig]:
        return [self.get(p.stem) for p in CONFIG_DIR.glob("*.yaml")]
```

---  

## 5. Streamlit UI Layers  

### 5.1 Page Structure (`ui/`)

```
ui/
├─ __init__.py├─ dashboard.py          # landing page – grid of system cards
├─ system_controls.py    # modal/drawer for start/stop/tune
├─ log_viewer.py         # real‑time log tail (st.autorefresh)
├─ metric_charts.py      # Plotly/D3 charts from metric stream
└─ config_editor.py      # YAML/JSON editor with schema validation
```

### 5.2 Reusable Component Example (`system_controls.py`)

```python
# file: ui/system_controls.py
import streamlit as st
from ..orchestrator import Orchestrator
from ..schemas.control_command import ControlCommand

def render_system_card(orch: Orchestrator, name: str):
    status = orch.get_status(name)
    with st.container():
        st.subheader(name)
        st.caption(f"Status: {status.state} • Uptime: {status.uptime:.1f}s")

        col1, col2, col3 = st.columns(3)
        if col1.button("▶️ Start", disabled=status.state == "running"):
            orch.send_command(name, ControlCommand(action="start"))
        if col2.button("⏹️ Stop", disabled=status.state != "running"):
            orch.send_command(name, ControlCommand(action="stop"))
        if col3.button("⚙️ Tune"):
            with st.expander("Tuning Params", expanded=False):
                # Example: pull tunable fields from config schema
                tunables = orch.get_tunable(name)
                new_vals = {}
                for key, (typ, default) in tunables.items():
                    if typ == "float":
                        new_vals[key] = st.slider(key, 0.0, 1.0, default)
                    elif typ == "int":
                        new_vals[key] = st.number_input(key, value=default, step=1)
                if st.button("Apply Tune"):
                    orch.send_command(name,
                                      ControlCommand(action="tune", payload=new_vals))
```

### 5.3 Main Dashboard (`dashboard.py`)

```python
# file: ui/dashboard.pyimport streamlit as st
from orchestrator import Orchestrator
from plugin_manager import PluginManager
from config_store import ConfigStore

st.set_page_config(layout="wide", title="Monorepo DAW – Central Command")
st.title("🎛️ Monorepo Autonomous Systems Dashboard")

# ---- singletons (cached across reruns) ----
@st.cache_resourcedef get_orchestrator():
    pm = PluginManager(repo_root=".")
    pm.load_all()
    orch = Orchestrator(pm, ConfigStore())
    return orch

orch = get_orchestrator()

# ---- refresh loop ----
placeholder = st.empty()
with placeholder.container():
    cols = st.columns(3)
    for i, sys_cfg in enumerate(orch.list_systems()):
        with cols[i % 3]:
            from ui.system_controls import render_system_card            render_system_card(orch, sys_cfg.name)

# Auto‑refresh every 2 seconds to poll status/logs
st.autorefresh(interval=2000, key="datarefresh")
```

---  

## 6. Key Functions & API Endpoints  

Although Streamlit runs a single process, we expose an **internal async API** that the UI calls. Think of it as a thin service layer; you could later replace it with FastAPI if you need external HTTP access.

| Function (in `orchestrator.py`) | Description | Parameters | Return |
|---------------------------------|-------------|------------|--------|
| `async def boot_system(self, name: str)` | Load plugin, merge config, start execution task | `name` | `None` |
| `async def stop_system(self, name: str)` | Request graceful stop, wait for task termination | `name` | `None` |
| `async def tune_system(self, name: str, params: dict)` | Send tune command to running plugin | `name`, `params` | `None` |
| `def get_status(self, name: str) -> SystemStatus` | Snapshot of state, uptime, last error | `name` | `SystemStatus` (dataclass) |
| `def list_systems(self) -> list[SystemConfig]` | All known plug‑ins with config | – | list |
| `def get_tunable(self, name: str) -> dict[str, tuple[type, Any]]` | Introspect plugin’s `tune` signature (via `inspect`) | `name` | mapping |
| `async def stream_logs(self, name: str) -> AsyncGenerator[str, None]` | Forward plugin’s log stream | `name` | lines |
| `async def stream_metrics(self, name: str) -> AsyncGenerator[MetricSample]` | Forward plugin’s metric stream | `name` | metric objects |

**Internal message bus** (optional): use `asyncio.Queue` per system to decouple UI from engine.

---  

## 7. Concurrency, Safety & Observability  

| Concern | Solution |
|---------|----------|
| **Isolation** | Each plug‑in runs in its own `asyncio.Task` (if `launch_mode="asyncio"`) **or** a dedicated `subprocess.Popen` (stdout/stderr piped to logs). This prevents a crash from taking down the dashboard. |
| **Thread‑safety** | Streamlit is single‑threaded; all orchestrator methods are `async` and called via `await` inside callbacks (`st.button` triggers a callback that runs `asyncio.create_task`). Use `asyncio.Lock` around mutable shared state (e.g., the system registry). |
| **Config Hot‑Reload** | `ConfigStore` watches file timestamps (`watchdog` or simple polling). On change, it emits a `CONFIG_UPDATED` event; orchestrator merges and, if the system is running, sends a `tune` command with the diff. |
| **Logging** | Central `logging.Logger` named `"monorepo_daw"` with a `QueueHandler` that pushes records to an async queue; a background task writes to rotating files and also pushes to UI via `st.experimental_rerun` or `st.empty().write`. |
| **Metrics** | Use `prometheus_client` optionally; each plug‑in can expose a `/metrics` endpoint; the orchestrator scrapes and feeds a time‑series DB (e.g., InfluxDB) for charting. |
| **Error Boundaries** | Wrap each plugin’s `start()`/`stop()` in a `try/except`; capture traceback, store in `SystemStatus.last_error`, and display an error badge in the UI. |
| **Security** | Validate any incoming `payload` against the plugin’s JSON‑Schema before applying. Only allow `tune` actions on running systems. |

---  

## 8. Deployment & DevOps Tips  

1. **Repository Layout**  

```
monorepo-daw/
├─ plugins/                 # git submodules or folder copies of synth-fuse, ferros, …
│   ├─ synth-fuse/
│   ├─ ferros/
│   └─ …
├─ src/                     # all code above (orchestrator, ui, etc.)
│   ├─ __init__.py
│   ├─ orchestrator.py
│   ├─ plugin_manager.py
│   ├─ config_store.py
│   ├─ execution_engine.py
│   ├─ monitor.py
│   ├─ schemas/
│   ├─ utils/
│   └─ ui/
├─ configs/                 # generated at runtime, version‑controlled optionally├─ requirements.txt
├─ Dockerfile└─ README.md
```

2. **Dockerfile (minimal)**  

```dockerfile
FROM python:3.12-slimWORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src
COPY plugins/ ./plugins   # or mount as volume at runtime
EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "src/ui/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

3. **CI/CD**  

* Use GitHub Actions to run `pytest` on the orchestrator and plugin contracts.  
* On push to `main`, build the Docker image and push to a registry (e.g., GHCR).  
* Deploy to a cheap VM, Cloud Run, or Kubernetes; expose port 8501 behind an auth proxy (e.g., OAuth2‑proxy) if needed.

4. **Versioning Plug‑ins**  

* Each plug‑in folder should contain a `VERSION` file or use its git tag.  
* The `PluginManager` reads this and stores it in `SystemConfig.version`.  
* UI can show a “Update Available” badge when the local tag lags behind remote.

---  

## 9. Minimal Working Example (Skeleton)  

Below is a **runnable skeleton** you can copy into a fresh repo. It does **not** yet contain the real plug‑ins (`synth-fuse`, etc.) but shows how they would be plugged in.

```bash
# 1️⃣ Create the repo
mkdir monorepo-daw && cd monorepo-daw
git init

# 2️⃣ Scaffold folders
mkdir -p src/ui src/schemas src/utils plugins
touch src/__init__.py src/ui/__init__.py

# 3️⃣ requirements.txt
cat > requirements.txt <<'EOF'
streamlit>=1.35
pydantic>=2.6
pyyaml>=6.0
watchdog>=4.0
aiofiles>=23.0
EOF

# 4️⃣ Install
pip install -r requirements.txt
```

### 9.1 `src/schemas/system_config.py` (as shown earlier)

### 9.2 `src/schemas/control_command.py` & `metric_sample.py` (copy from section 4)

### 9.3 `src/plugins/base_plugin.py` (copy from section 3.1)

### 9.4 `src/plugin_manager.py`

```python# file: src/plugin_manager.py
import importlib.util
from pathlib import Path
from typing import Dict
from .plugins.base_plugin import BasePlugin

class PluginManager:
    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root)
        self._plugins: Dict[str, type[BasePlugin]] = {}

    def load_all(self):
        for plugin_dir in self.repo_root.glob("plugins/*/"):
            init_file = plugin_dir / "__init__.py"
            if not init_file.is_file():
                continue
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_dir.name}.plugin", plugin_dir / "plugin.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore
            # Expect module to expose a class named `Plugin`
            plugin_cls = getattr(module, "Plugin", None)
            if not isinstance(plugin_cls, type) or not issubclass(plugin_cls, BasePlugin):
                raise ImportError(f"Plugin {plugin_dir.name} does not expose a valid BasePlugin subclass")
            self._plugins[plugin_dir.name] = plugin_cls    def get(self, name: str) -> type[BasePlugin]:
        return self._plugins[name]

    def list_names(self):
        return list(self._plugins.keys())
```

### 9.5 `src/execution_engine.py`

```python
# file: src/execution_engine.pyimport asyncio
from typing import AsyncGeneratorfrom .plugins.base_plugin import BasePlugin

class ExecutionEngine:
    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    async def start(self, name: str, plugin_cls, config: dict):
        """Instantiate and run the plugin."""
        plugin = plugin_cls(name=name, config=config)
        task = asyncio.create_plugin_task(plugin.start())  # we define helper below
        self._tasks[name] = task        # start background log/metric forwarding
        asyncio.create_task(self._forward(plugin, name))

    async def stop(self, name: str):
        task = self._tasks.get(name)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._tasks[name]

    async def _forward(self, plugin: BasePlugin, name: str):
        """Pipe logs/metrics to the monitor (stubbed)."""
        try:
            async for line in plugin.stream_logs():
                await Monitor.instance().log(name, line)
            async for metric in plugin.stream_metrics():
                await Monitor.instance().metric(name, metric)
        except asyncio.CancelledError:
            pass
```

> **Helper** – add to `src/utils/async_helpers.py`  

```python
# file: src/utils/async_helpers.pyimport asyncio

async def create_plugin_task(coro):
    """Wraps a plugin coroutine so we can catch exceptions."""
    try:
        await coro
    except Exception as exc:
        # let the orchestrator record the error
        raise exc
```

### 9.6 `src/monitor.py` (very simple in‑memory broker)

```python
# file: src/monitor.py
import asyncio
from typing import Dict, List
from .schemas.metric_sample import MetricSample

class Monitor:
    _instance: "Monitor" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logs: Dict[str, List[str]] = {}
            cls._instance._metrics: Dict[str, List[MetricSample]] = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def log(self, system: str, line: str):
        async with self._lock:
            self._logs.setdefault(system, []).append(line)
            # keep only last 1000 lines            self._logs[system] = self._logs[system][-1000:]

    async def metric(self, system: str, sample: MetricSample):
        async with self._lock:
            self._metrics.setdefault(system, []).append(sample)
            self._metrics[system] = self._metrics[system][-500:]  # keep recent

    async def get_logs(self, system: str, limit: int = 200) -> List[str]:
        async with self._lock:
            return list(self._logs.get(system, [])[-limit:])

    async def get_metrics(self, system: str) -> List[MetricSample]:
        async with self._lock:
            return list(self._metrics.get(system, []))
```

### 9.7 `src/orchestrator.py` (core)

```python
# file: src/orchestrator.py
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from .plugin_manager import PluginManager
from .config_store import ConfigStore
from .execution_engine import ExecutionEngine
from .monitor import Monitor
from .schemas.control_command import ControlCommand
from .schemas.system_config import SystemConfig

@dataclassclass SystemStatus:
    name: str
    state: str = "stopped"   # stopped, starting, running, stopping, error    uptime: float = 0.0
    last_error: Optional[str] = None
    config: Optional[SystemConfig] = None

class Orchestrator:
    def __init__(self, pm: PluginManager, cfg_store: ConfigStore):
        self.pm = pm
        self.cfg = cfg_store
        self.engine = ExecutionEngine()
        self.monitor = Monitor()
        self._status: Dict[str, SystemStatus] = {}
        self._start_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    #  Life‑cycle    # ------------------------------------------------------------------ #
    async def boot_system(self, name: str):
        async with self._lock:
            if name in self._status and self._status[name].state == "running":
                return  # already running
            self._status[name] = SystemStatus(name=name, state="starting")
        try:
            cfg = self.upsert_config(name)  # ensure config exists
            plugin_cls = self.pm.get(name)
            await self.engine.start(name, plugin_cls, cfg.dict())
            async with self._lock:
                st = self._status[name]
                st.state = "running"
                st.config = cfg
                self._start_times[name] = asyncio.get_event_loop().time()
        except Exception as exc:
            async with self._lock:
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
            self._status[name].uptime = asyncio.get_event_loop().time() - self._start_times.pop(name, 0.0)

    # ------------------------------------------------------------------ #
    #  Tuning
    # ------------------------------------------------------------------ #
    async def tune_system(self, name: str, params: Dict[str, Any]):
        """Send a tune command to the running plugin."""
        plugin_cls = self.pm.get(name)
        # Instantiate a temporary object just to call its tune method
        plugin = plugin_cls(name=name, config={})
        await plugin.tune(params)

    # ------------------------------------------------------------------ #
    #  Introspection
    # ------------------------------------------------------------------ #
    def get_tunable(self, name: str):
        """Return a dict of tunable fields with (type, default) from the plugin's tune signature."""
        import inspect
        plugin_cls = self.pm.get(name)
        sig = inspect.signature(plugin_cls.tune)
        tunable = {}
        for pname, param in sig.parameters.items():
            if pname == "self":
                continue            # Default to str if no annotation; you can enrich with metadata later
            typ = param.annotation if param.annotation != inspect.Parameter.empty else str            default = param.default if param.default != inspect.Parameter.empty else None
            tunable[pname] = (typ, default)
        return tunable

    # ------------------------------------------------------------------ #
    #  Status & Config helpers
    # ------------------------------------------------------------------ #
    def get_status(self, name: str) -> SystemStatus:
        return self._status.get(name, SystemStatus(name=name, state="unknown"))

    def list_systems(self) -> list[SystemConfig]:
        return [self.cfg.get(n) for n in self.pm.list_names()]

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
```

### 9.8 `src/ui/dashboard.py` (copy from section 5.3 – adjust import paths)

```python
# file: src/ui/dashboard.py
import streamlit as st
from ..orchestrator import Orchestrator
from ..plugin_manager import PluginManager
from ..config_store import ConfigStore

st.set_page_config(layout="wide", title="Monorepo DAW – Central Command")
st.title("🎛️ Monorepo Autonomous Systems Dashboard")

@st.cache_resourcedef get_orchestrator():
    pm = PluginManager(repo_root="..")
    pm.load_all()
    return Orchestrator(pm, ConfigStore())

orch = get_orchestrator()

placeholder = st.empty()
with placeholder.container():
    cols = st.columns(3)
    for i, sys_cfg in enumerate(orch.list_systems()):
        with cols[i % 3]:
            from .system_controls import render_system_card
            render_system_card(orch, sys_cfg.name)

st.autorefresh(interval=2000, key="datarefresh")
```

### 9.9 `src/ui/system_controls.py` (copy from section 5.2)

```python
# file: src/ui/system_controls.py
import streamlit as st
from ..orchestrator import Orchestrator
from ..schemas.control_command import ControlCommand

def render_system_card(orch: Orchestrator, name: str):
    status = orch.get_status(name)
    with st.container():
        st.subheader(name)
        st.caption(f"State: {status.state} • Uptime: {status.uptime:.1f}s")
        if status.last_error:
            st.error(f"Last error: {status.last_error}")

        c1, c2, c3 = st.columns(3)
        if c1.button("▶️ Start", disabled=status.state == "running"):
            # fire‑and‑forget async call
            async def _start():
                await orch.boot_system(name)
            st.session_state.setdefault("_tasks", []).append(
                st.experimental_run(_start())  # pseudo – replace with proper async handling in prod
            )
        if c2.button("⏹️ Stop", disabled=status.state != "running"):
            async def _stop():
                await orch.stop_system(name)
            st.session_state.setdefault("_tasks", []).append(st.experimental_run(_stop()))
        if c3.button("⚙️ Tune"):
            with st.expander("Tuning Params", expanded=False):
                tunables = orch.get_tunable(name)
                new_vals = {}
                for key, (typ, default) in tunables.items():
                    if typ == float:
                        new_vals[key] = st.slider(key, 0.0, 1.0, value=float(default or 0.0))
                    elif typ == int:
                        new_vals[key] = st.number_input(key, value=int(default or 0), step=1)
                    else:
                        new_vals[key] = st.text_input(key, value=str(default or ""))
                if st.button("Apply Tune"):
                    async def _tune():
                        await orch.tune_system(name, new_vals)
                    st.session_state.setdefault("_tasks", []).append(st.experimental_run(_tune()))
```

> **Note** – The stub `st.experimental_run` is just illustrative. In a real implementation you’d use `asyncio.create_task` inside a Streamlit callback (e.g., `st.button`’s `on_click`) and keep a reference to the task for cancellation.

### 9.10 Run it```bash
streamlit run src/ui/dashboard.py
```

You should see a blank grid (no plug‑ins yet). To test, add a dummy plug‑in:

```bash
mkdir -p plugins/hello
cat > plugins/hello/__init__.py <<'EOF'
# empty
EOFcat > plugins/hello/plugin.py <<'EOF'
from ..base_plugin import BasePlugin
import asyncio
import random

class Plugin(BasePlugin):
    async def start(self):
        self._running = True
        while self._running:
            await asyncio.sleep(1)
            # Emit a fake metric
            await self._emit_metric("dummy_value", random.random())
            await self._emit_log(f"[{self.name}] tick")

    async def stop(self):
        self._running = False

    async def tune(self, params):
        self._tune_params = params        await self._emit_log(f"[{self.name}] tuned with {params}")

    # Helper methods (you could also inherit from a mixin)
    async def _emit_log(self, line):
        # In a real system you'd push to a queue; here we just print.
        print(line)

    async def _emit_metric(self, name, value):
        from ..schemas.metric_sample import MetricSample
        from datetime import datetime        await Monitor.instance().metric(self.name, MetricSample(timestamp=datetime.utcnow(),
                                                               name=name,
                                                               value=value,
                                                               tags={}))
EOF
```

Now refresh the dashboard – you should see a **“hello”** card you can start/stop/tune, with logs and metrics appearing in the console (or you could wire the monitor to stream back to the UI via `st.empty()`).

---

2. **Implement each real plug‑in** (`synth-fuse`, `ferros`, `neutometal`, `tungsten`) by subclassing `BasePlugin` and placing its code under `plugins/<name>/`.  
3. Ensure each plug‑in exposes a `plugin.py` that defines a class named `Plugin`.  
4. (Optional) Add a `config_schema.yaml` in each plug‑in folder; the `ConfigStore` can validate against it using `jsonschema` if you want stricter checks.  
5. Run `pip install -r requirements.txt` and launch the dashboard with `streamlit run src/ui/dashboard.py`.  
6. For production, Dockerise (see Dockerfile) and deploy behind a reverse proxy with authentication if needed.  

That’s the full spec—plug‑in contract, state management, execution isolation, UI components, and observability hooks—all ready for Jules to turn into a working “DAW‑for‑autonomous‑systems” control center.
