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
            # keep only last 1000 lines
            self._logs[system] = self._logs[system][-1000:]

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
