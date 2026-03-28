# file: tests/test_neurofuse.py
import pytest
import asyncio
from src.orchestrator import Orchestrator
from src.plugin_manager import PluginManager
from src.config_store import ConfigStore
from src.schemas.scenario import Scenario, ScenarioEvent
from src.schemas.payload import Payload

@pytest.fixture
def orchestrator():
    pm = PluginManager(repo_root=".")
    pm.load_all()
    # Use a dummy loop or fresh loop for testing
    loop = asyncio.new_event_loop()
    orch = Orchestrator(pm, ConfigStore(), loop=loop)
    return orch

@pytest.mark.asyncio
async def test_z3_safety_invariant(orchestrator):
    # Setup: mock a system with high diversity
    name = "synthfuse"
    cfg = orchestrator.upsert_config(name)
    cfg.settings["diversity"] = 0.95
    orchestrator.cfg.upsert(cfg)

    # Rule: intensity + diversity > 1.8 is unsafe
    # intensity 0.9 + diversity 0.95 = 1.85 (UNSAFE)
    assert orchestrator._verify_tuning_safety(name, {"intensity": 0.9}) is False

    # intensity 0.5 + diversity 0.95 = 1.45 (SAFE)
    assert orchestrator._verify_tuning_safety(name, {"intensity": 0.5}) is True

@pytest.mark.asyncio
async def test_master_mute(orchestrator):
    await orchestrator.master_mute(True)
    assert orchestrator._master_mute is True

    # Try to tune when muted
    await orchestrator.tune_system("hello", {"rate": 0.1})
    logs = await orchestrator.monitor.get_logs("orchestrator")
    assert any("Blocked tune command" in line for line in logs)

@pytest.mark.asyncio
async def test_scenario_execution(orchestrator):
    scenario = Scenario(
        name="Test Scenario",
        timeline=[
            ScenarioEvent(timestamp=0.1, system="hello", action="start"),
            ScenarioEvent(timestamp=0.2, system="hello", action="tune", payload={"rate": 0.8})
        ]
    )

    # Mock boot_system to avoid full plugin launch for simple unit test
    async def mock_boot(name):
        from src.orchestrator import SystemStatus
        orchestrator._status[name] = SystemStatus(name=name, state="running")
    orchestrator.boot_system = mock_boot

    await orchestrator.run_scenario(scenario)
    # Check if commands were reached (this is simplified)
    assert "hello" in orchestrator._status
