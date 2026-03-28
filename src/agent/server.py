# file: src/agent/server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import json
import os
import sys

# Add parent to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.plugin_manager import PluginManager
from src.plugins.base_plugin import BasePlugin
from src.schemas.system_config import SystemConfig

app = FastAPI(title="Neurofuse Remote Agent")

# Global state for the agent
pm = PluginManager(repo_root=".")
pm.load_all()
instances: Dict[str, BasePlugin] = {}
tasks: Dict[str, asyncio.Task] = {}

class StartRequest(BaseModel):
    name: str
    plugin_type: Optional[str] = None
    config: Dict[str, Any]

@app.post("/start")
async def start_plugin(req: StartRequest):
    if req.name in instances:
        return {"status": "already_running"}

    # Use plugin_type if provided, otherwise fallback to name
    target_type = req.plugin_type or req.name
    try:
        plugin_cls = pm.get(target_type)
    except KeyError:
        return {"status": "error", "message": f"Plugin type {target_type} not found on agent"}

    if plugin_cls is None:
        return {"status": "error", "message": f"Plugin type {target_type} is marked as remote on agent itself"}

    plugin = plugin_cls(name=req.name, config=req.config)
    instances[req.name] = plugin

    # We don't use ExecutionEngine here to avoid circularity;
    # the agent is a mini execution engine itself.
    task = asyncio.create_task(plugin.start())
    tasks[req.name] = task
    return {"status": "started"}

@app.post("/stop/{name}")
async def stop_plugin(name: str):
    if name not in instances:
        return {"status": "not_running"}

    plugin = instances[name]
    await plugin.stop()
    tasks[name].cancel()
    del instances[name]
    del tasks[name]
    return {"status": "stopped"}

@app.post("/tune/{name}")
async def tune_plugin(name: str, params: Dict[str, Any]):
    if name not in instances:
        return {"status": "error", "message": "not_running"}
    await instances[name].tune(**params)
    return {"status": "tuned"}

@app.websocket("/ws/{name}")
async def stream_data(websocket: WebSocket, name: str):
    await websocket.accept()
    if name not in instances:
        await websocket.close(code=1000)
        return

    plugin = instances[name]

    async def forward_logs():
        async for line in plugin.stream_logs():
            await websocket.send_json({"type": "log", "data": line})

    async def forward_metrics():
        async for metric in plugin.stream_metrics():
            await websocket.send_json({"type": "metric", "data": metric})

    async def forward_payloads():
        async for payload in plugin.stream_payloads():
            # Convert Payload model to dict
            await websocket.send_json({"type": "payload", "data": payload.model_dump()})

    try:
        await asyncio.gather(forward_logs(), forward_metrics(), forward_payloads())
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()
