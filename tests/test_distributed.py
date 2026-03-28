# file: tests/test_distributed.py
import pytest
import asyncio
import httpx
from src.orchestrator import Orchestrator
from src.plugin_manager import PluginManager
from src.config_store import ConfigStore
from src.execution_engine import RemotePluginProxy

@pytest.fixture
def orchestrator():
    pm = PluginManager(".")
    pm.load_all()
    orch = Orchestrator(pm, ConfigStore())
    return orch

@pytest.mark.asyncio
async def test_remote_proxy_initialization(orchestrator):
    config = {"remote_url": "http://localhost:9999", "settings": {"plugin_type": "hello"}}
    proxy = RemotePluginProxy("remote_hello", config)
    assert proxy.url == "http://localhost:9999"
    assert proxy.ws_url == "ws://localhost:9999/ws/remote_hello"
    assert proxy._running is False

@pytest.mark.asyncio
async def test_chromadb_retrieval(orchestrator):
    from src.intelligence.architect import Architect
    arc = Architect()

    # Push test log
    await orchestrator.monitor.log("test_system", "Critical overheating in the fusion core.")
    await asyncio.sleep(2) # Wait for async push to Chroma

    # Retrieve
    mem = await arc.retrieve_memory("overheating")
    assert any("fusion core" in m.lower() for m in mem)
