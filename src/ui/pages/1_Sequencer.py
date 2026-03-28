# file: src/ui/sequencer.py
import streamlit as st
import asyncio
import os
import sys
import time

# Add the parent directory of 'src' to sys.path so we can import 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from streamlit_autorefresh import st_autorefresh
from src.orchestrator import Orchestrator
from src.plugin_manager import PluginManager
from src.config_store import ConfigStore
from src.utils.async_helpers import get_global_loop
from src.schemas.scenario import Scenario, ScenarioEvent

_loop = get_global_loop()

st.set_page_config(layout="wide", page_title="Neurofuse Sequencer")
st.title("🎬 Scenario Sequencer")

@st.cache_resource
def get_orchestrator():
    pm = PluginManager(repo_root=".")
    pm.load_all()
    orch = Orchestrator(pm, ConfigStore(), loop=_loop)
    # Start the global monitor for IFTTT
    asyncio.run_coroutine_threadsafe(orch.start_global_monitor(), _loop)
    return orch

orch = get_orchestrator()

st_autorefresh(interval=3000, key="sequencer_refresh")

st.info("Automate multi-system choreography through time-based timelines.")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Scenario Builder")
    name = st.text_input("Scenario Name", value="Fusion Cycle 1")

    systems = [s.name for s in orch.list_systems()]
    system = st.selectbox("System", systems)
    action = st.selectbox("Action", ["start", "stop", "tune"])
    offset = st.number_input("Time Offset (s)", min_value=0.0, value=5.0)

    if st.button("Add to Timeline"):
        if "timeline" not in st.session_state:
            st.session_state.timeline = []
        st.session_state.timeline.append(ScenarioEvent(timestamp=offset, system=system, action=action))
        st.success("Event added.")

with col2:
    st.subheader("Current Timeline")
    timeline = st.session_state.get("timeline", [])
    if not timeline:
        st.write("Timeline is empty.")
    else:
        for idx, event in enumerate(sorted(timeline, key=lambda e: e.timestamp)):
            st.write(f"T+{event.timestamp}s: **{event.system}** → *{event.action}*")
            if st.button(f"Remove Event {idx}", key=f"remove_{idx}"):
                st.session_state.timeline.pop(idx)
                st.rerun()

    if st.button("🚀 Execute Scenario", disabled=not timeline):
        scen = Scenario(name=name, timeline=timeline)
        asyncio.run_coroutine_threadsafe(orch.run_scenario(scen), orch.loop)
        st.success(f"Scenario '{name}' execution started!")

# Global Orchestrator Logs
st.divider()
st.subheader("Global Control Logs")
try:
    fut = asyncio.run_coroutine_threadsafe(orch.stream_logs("orchestrator", limit=20), orch.loop)
    logs = fut.result(timeout=0.5)
    for line in logs:
        st.text(line)
except:
    st.text("Loading logs...")
