# file: plugins/synthfuse/plugin.py
import asyncio
import random
import uuid
from typing import Dict, Any, AsyncGenerator
from src.plugins.base_plugin import BasePlugin
from src.schemas.payload import Payload
from src.utils.storage import save_artifact

class Plugin(BasePlugin):
    """Synthfuse: Synthetic Data Integration Engine."""

    async def start(self) -> None:
        self._running = True
        self._logs = asyncio.Queue()
        self._metrics = asyncio.Queue()
        self._payload_queue = asyncio.Queue()

        # Initial settings
        self.diversity = self.config.get("settings", {}).get("diversity", 0.5)

        count = 0
        while self._running:
            await asyncio.sleep(4)
            # Emit a fake metric representing data diversity
            score = random.uniform(0.0, self.diversity)
            await self._metrics.put({"name": "synthesis_score", "value": score})
            await self._logs.put(f"[Synthfuse] Synthesizing data batch... score: {score:.3f} (diversity: {self.diversity:.2f})")

            # Emit a mock artifact
            count += 1
            content = f"Synthesized data batch {count}\nDiversity index: {self.diversity}\nScore: {score:.3f}"
            filename = f"batch_{count}.txt"
            uri = await save_artifact(self.name, filename, content)

            payload = Payload(
                id=str(uuid.uuid4())[:8],
                plugin_name=self.name,
                mime_type="text/plain",
                uri=uri,
                metadata={"batch_id": count, "diversity": self.diversity}
            )
            await self._payload_queue.put(payload)

    async def stop(self) -> None:
        self._running = False

    async def tune(self, diversity: float = 0.5) -> None:
        """Apply data diversity tuning."""
        self.diversity = diversity
        self.config.setdefault("settings", {})["diversity"] = diversity
        await self._logs.put(f"[Synthfuse] Diversity level tuned to: {diversity}")

    async def stream_logs(self) -> AsyncGenerator[str, None]:
        while True:
            line = await self._logs.get()
            yield line

    async def stream_metrics(self) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            metric = await self._metrics.get()
            yield metric

    async def stream_payloads(self) -> AsyncGenerator[Payload, None]:
        while True:
            payload = await self._payload_queue.get()
            yield payload
