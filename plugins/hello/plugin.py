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

        while self._running:
            await asyncio.sleep(1)
            # Emit a fake metric
            await self._metrics.put({"name": "dummy_value", "value": random.random()})
            await self._logs.put(f"[{self.name}] tick")

    async def stop(self) -> None:
        self._running = False

    async def tune(self, params: Dict[str, Any]) -> None:
        self.config["settings"].update(params)
        await self._logs.put(f"[{self.name}] tuned with {params}")

    async def stream_logs(self) -> AsyncGenerator[str, None]:
        while True:
            line = await self._logs.get()
            yield line

    async def stream_metrics(self) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            metric = await self._metrics.get()
            yield metric
