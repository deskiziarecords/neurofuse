# file: src/execution_engine.py
import asyncio
from typing import Dict, Optional, Any
from .plugins.base_plugin import BasePlugin
from .utils.async_helpers import create_plugin_task
from .monitor import Monitor

class ExecutionEngine:
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._forward_tasks: Dict[str, asyncio.Task] = {}
        self._instances: Dict[str, BasePlugin] = {}

    async def start(self, name: str, plugin_cls: type[BasePlugin], config: dict):
        """Instantiate and run the plugin."""
        plugin = plugin_cls(name=name, config=config)
        self._instances[name] = plugin

        # Start the main plugin task
        task = asyncio.create_task(create_plugin_task(plugin.start()))
        self._tasks[name] = task

        # Start log/metric forwarding task
        forward_task = asyncio.create_task(self._forward(plugin, name))
        self._forward_tasks[name] = forward_task

    async def stop(self, name: str):
        # Stop and cleanup the main plugin task
        task = self._tasks.get(name)
        if task:
            # Let the plugin stop itself gracefully first
            plugin = self._instances.get(name)
            if plugin:
                await plugin.stop()

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._tasks[name]

        # Stop and cleanup forwarding task
        forward_task = self._forward_tasks.get(name)
        if forward_task:
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass
            del self._forward_tasks[name]

        # Remove plugin instance
        if name in self._instances:
            del self._instances[name]

    def get_plugin_instance(self, name: str) -> Optional[BasePlugin]:
        return self._instances.get(name)

    async def _forward(self, plugin: BasePlugin, name: str):
        """Pipe logs/metrics to the monitor."""
        monitor = Monitor()
        try:
            # We concurrently stream logs and metrics
            log_task = asyncio.create_task(self._forward_logs(plugin, name, monitor))
            metric_task = asyncio.create_task(self._forward_metrics(plugin, name, monitor))
            await asyncio.gather(log_task, metric_task)
        except asyncio.CancelledError:
            pass
        except Exception:
            # Optionally log errors in forwarding
            pass

    async def _forward_logs(self, plugin: BasePlugin, name: str, monitor: Monitor):
        async for line in plugin.stream_logs():
            await monitor.log(name, line)

    async def _forward_metrics(self, plugin: BasePlugin, name: str, monitor: Monitor):
        async for metric in plugin.stream_metrics():
            from .schemas.metric_sample import MetricSample
            if isinstance(metric, dict):
                sample = MetricSample(system=name, **metric)
            else:
                sample = metric
            await monitor.metric(name, sample)
