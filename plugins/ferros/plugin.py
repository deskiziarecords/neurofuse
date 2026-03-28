# file: plugins/ferros/plugin.py
import asyncio
import random
from typing import Dict, Any, AsyncGenerator
from src.plugins.base_plugin import BasePlugin

class Plugin(BasePlugin):
    """Ferros: The Magnetic Data Fusion System."""

    async def start(self) -> None:
        self._running = True
        self._logs = asyncio.Queue()
        self._metrics = asyncio.Queue()

        # Initial settings
        self.intensity = self.config.get("settings", {}).get("intensity", 0.7)

        while self._running:
            await asyncio.sleep(2)
            # Emit a fake metric representing magnetic flux
            flux = random.uniform(0.1, self.intensity)
            await self._metrics.put({"name": "magnetic_flux", "value": flux})
            await self._logs.put(f"[Ferros] Aligning magnetic domains... flux: {flux:.3f} (intensity: {self.intensity:.2f})")

    async def stop(self) -> None:
        self._running = False

    async def tune(self, intensity: float = 0.7) -> None:
        """Apply magnetic intensity tuning."""
        self.intensity = intensity
        self.config.setdefault("settings", {})["intensity"] = intensity
        await self._logs.put(f"[Ferros] Intensity tuned to: {intensity}")

    async def stream_logs(self) -> AsyncGenerator[str, None]:
        while True:
            line = await self._logs.get()
            yield line

    async def stream_metrics(self) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            metric = await self._metrics.get()
            yield metric

    async def receive_data(self, source: str, data: Dict[str, Any]) -> None:
        """Modulate intensity based on incoming synthesis data."""
        if source == "synthfuse" and data.get("name") == "synthesis_score":
            score = data.get("value", 0.5)
            # Higher synthesis score boosts magnetic alignment intensity
            new_intensity = min(1.0, 0.5 + score)
            if abs(new_intensity - self.intensity) > 0.05:
                self.intensity = new_intensity
                await self._logs.put(f"[Ferros] MODULATION: Synthfuse score {score:.2f} detected. Intensity shifted to {self.intensity:.2f}")
