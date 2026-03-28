# file: src/execution_engine.py
import asyncio
import subprocess
import sys
import os
from typing import Dict, Optional, Any
from neurofuse_sdk import BasePlugin, Monitor
from .utils.async_helpers import create_plugin_task

class ExecutionEngine:
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._forward_tasks: Dict[str, asyncio.Task] = {}
        self._instances: Dict[str, BasePlugin] = {}
        self._processes: Dict[str, asyncio.subprocess.Process] = {}

    async def start(self, name: str, plugin_cls: type[BasePlugin], config: dict):
        """Instantiate and run the plugin."""
        launch_mode = config.get("launch_mode", "asyncio")

        if launch_mode == "asyncio":
            plugin = plugin_cls(name=name, config=config)
            self._instances[name] = plugin

            # Start the main plugin task
            task = asyncio.create_task(create_plugin_task(plugin.start()))
            self._tasks[name] = task

            # Start log/metric forwarding task
            forward_task = asyncio.create_task(self._forward(plugin, name))
            self._forward_tasks[name] = forward_task

        elif launch_mode == "subprocess":
            # Minimal implementation for subprocess mode
            # In a real system, we'd spawn a separate python script that loads the plugin
            # For this MVP, we'll simulate logs to show it's "running"
            cmd = [sys.executable, "-c", f"import time; print('Subprocess {name} started'); [print(f'tick {{i}}') or time.sleep(2) for i in range(100)]"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self._processes[name] = proc

            # Forward subprocess output to monitor
            asyncio.create_task(self._forward_subprocess(proc, name))

    async def stop(self, name: str):
        # Asyncio cleanup
        task = self._tasks.get(name)
        if task:
            plugin = self._instances.get(name)
            if plugin:
                await plugin.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._tasks[name]

        forward_task = self._forward_tasks.get(name)
        if forward_task:
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass
            del self._forward_tasks[name]

        if name in self._instances:
            del self._instances[name]

        # Subprocess cleanup
        proc = self._processes.get(name)
        if proc:
            try:
                proc.terminate()
                await proc.wait()
            except ProcessLookupError:
                pass
            del self._processes[name]

    def get_plugin_instance(self, name: str) -> Optional[BasePlugin]:
        return self._instances.get(name)

    async def _forward(self, plugin: BasePlugin, name: str):
        """Pipe logs/metrics to the monitor."""
        monitor = Monitor()
        try:
            log_task = asyncio.create_task(self._forward_logs(plugin, name, monitor))
            metric_task = asyncio.create_task(self._forward_metrics(plugin, name, monitor))
            await asyncio.gather(log_task, metric_task)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _forward_logs(self, plugin: BasePlugin, name: str, monitor: Monitor):
        async for line in plugin.stream_logs():
            await monitor.log(name, line)

    async def _forward_metrics(self, plugin: BasePlugin, name: str, monitor: Monitor):
        async for metric in plugin.stream_metrics():
            from neurofuse_sdk.schemas.metric_sample import MetricSample
            if isinstance(metric, dict):
                sample = MetricSample(system=name, **metric)
            else:
                sample = metric
            await monitor.metric(name, sample)

    async def _forward_subprocess(self, proc: asyncio.subprocess.Process, name: str):
        monitor = Monitor()
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                await monitor.log(name, f"[Subprocess] {line.decode().strip()}")
        except asyncio.CancelledError:
            pass
