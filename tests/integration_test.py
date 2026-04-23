import asyncio
import sys
import os

# Add repo root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.orchestrator import Orchestrator
from src.plugin_manager import PluginManager
from src.config_store import ConfigStore

async def main():
    print("Starting integration test...")
    pm = PluginManager(repo_root=".")
    pm.load_all()

    orch = Orchestrator(pm, ConfigStore())

    print("Booting synthfuse...")
    await orch.boot_system("synthfuse")

    print("Booting ferros...")
    await orch.boot_system("ferros")

    # Wait for some metrics to be emitted and routed
    print("Waiting for telemetry routing (5 seconds)...")
    await asyncio.sleep(5)

    # Check if ferros received data from synthfuse
    # We can check the logs of ferros
    logs = await orch.stream_logs("ferros", limit=50)
    found_modulation = False
    for line in logs:
        if "MODULATION: Synthfuse score" in line:
            print(f"Success! Found modulation log in ferros: {line}")
            found_modulation = True
            break

    if not found_modulation:
        print("Failure: Modulation log not found in ferros.")
        sys.exit(1)

    # Check telemetry map
    if "synthfuse" in orch._telemetry_map and "ferros" in orch._telemetry_map["synthfuse"]:
        print("Success! Telemetry map correctly tracked synthfuse -> ferros.")
    else:
        print(f"Failure: Telemetry map incorrect: {orch._telemetry_map}")
        sys.exit(1)

    print("Stopping systems...")
    await orch.stop_system("synthfuse")
    await orch.stop_system("ferros")
    print("Integration test passed!")

if __name__ == "__main__":
    asyncio.run(main())
