# file: src/monitor.py
import asyncio
from typing import Dict, List, Optional, Any
from .schemas.metric_sample import MetricSample
from .schemas.payload import Payload

class Monitor:
    _instance: Optional["Monitor"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logs: Dict[str, List[str]] = {}
            cls._instance._metrics: Dict[str, List[MetricSample]] = {}
            cls._instance._payloads: Dict[str, List[Payload]] = {}
            cls._instance._lock: Optional[asyncio.Lock] = None
        return cls._instance

    def _get_lock(self) -> asyncio.Lock:
        """Lazily initialize the lock for the current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def log(self, system: str, line: str):
        async with self._get_lock():
            self._logs.setdefault(system, []).append(line)
            # keep only last 1000 lines
            self._logs[system] = self._logs[system][-1000:]

    async def metric(self, system: str, sample: MetricSample):
        async with self._get_lock():
            self._metrics.setdefault(system, []).append(sample)
            self._metrics[system] = self._metrics[system][-500:]  # keep recent

    async def get_logs(self, system: str, limit: int = 200) -> List[str]:
        async with self._get_lock():
            return list(self._logs.get(system, [])[-limit:])

    async def get_metrics(self, system: str) -> List[MetricSample]:
        async with self._get_lock():
            return list(self._metrics.get(system, []))

    async def payload(self, system: str, payload: Payload):
        async with self._get_lock():
            self._payloads.setdefault(system, []).append(payload)
            self._payloads[system] = self._payloads[system][-100:]

    async def get_payloads(self, system: str) -> List[Payload]:
        async with self._get_lock():
            return list(self._payloads.get(system, []))
