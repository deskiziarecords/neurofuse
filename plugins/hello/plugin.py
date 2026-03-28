# file: plugins/hello/plugin.py
from src.plugins.base_plugin import BasePlugin
import asyncio
import random
from typing import Dict, Any, AsyncGenerator

class Plugin(BasePlugin):
    async def start(self) -> None:
        self._running = True
        self._logs = asyncio.Queue()
        self._metrics = asyncio.Queue()
        self.rate = self.config.get("settings", {}).get("rate", 0.5)

        while self._running:
            await asyncio.sleep(1)
            # Emit a fake metric
            await self._metrics.put({"name": "dummy_value", "value": random.random() * self.rate})
            await self._logs.put(f"[{self.name}] tick (rate: {self.rate:.2f})")

    async def stop(self) -> None:
        self._running = False

    async def tune(self, rate: float = 0.5) -> None:
        self.rate = rate
        self.config.setdefault("settings", {})["rate"] = rate
        await self._logs.put(f"[{self.name}] rate tuned to {rate}")

    async def stream_logs(self) -> AsyncGenerator[str, None]:
        while True:
            line = await self._logs.get()
            yield line

    async def stream_metrics(self) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            metric = await self._metrics.get()
            yield metric
