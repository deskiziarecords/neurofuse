# file: src/plugins/base_plugin.py
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
        self._process: asyncio.Task | None = None

    @abstractmethod
    async def start(self) -> None:
        """Launch the system; should run until stop() is called."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shutdown; cancel background tasks."""
        ...

    @abstractmethod
    async def tune(self, **kwargs) -> None:
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

    async def stream_payloads(self) -> AsyncGenerator[Any, None]:
        """Yield Payload objects as they are produced."""
        if False: yield None
