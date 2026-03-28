# file: src/ui/dashboard.py
import streamlit as st
import asyncio
import os
import sys

# Add the parent directory of 'src' to sys.path so we can import 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from streamlit_autorefresh import st_autorefresh
from src.orchestrator import Orchestrator
from src.plugin_manager import PluginManager
from src.config_store import ConfigStore
from src.utils.async_helpers import get_global_loop

_loop = get_global_loop()

st.set_page_config(layout="wide", page_title="neurofuse – The Intelligence Welding Studio")
st.title("🎛️ Monorepo Autonomous Systems Dashboard")

# ---- singletons (cached across reruns) ----
@st.cache_resource
def get_orchestrator():
    pm = PluginManager(repo_root=".")
    pm.load_all()
    # Pass the global loop during initialization
    orch = Orchestrator(pm, ConfigStore(), loop=_loop)
    return orch

orch = get_orchestrator()

# ---- Sidebar Safety Guardrails ----
with st.sidebar:
    st.header("🛡️ Safety Guardrails")
    if "master_mute" not in st.session_state:
        st.session_state.master_mute = False

    if st.button("🚨 EMERGENCY STOP", type="primary", use_container_width=True):
        st.session_state.master_mute = True
        asyncio.run_coroutine_threadsafe(orch.master_mute(True), _loop)
        st.error("MASTER MUTE ACTIVE")

    if st.session_state.master_mute:
        if st.button("🔓 Release Lock", use_container_width=True):
            st.session_state.master_mute = False
            asyncio.run_coroutine_threadsafe(orch.master_mute(False), _loop)
            st.rerun()

# ---- refresh loop ----
st_autorefresh(interval=2000, key="main_datarefresh")

# ---- Dependency Graph (Mermaid) ----
with st.expander("🕸️ Live System Topology", expanded=False):
    st.write("Current data flow and system interdependencies.")
    mermaid_code = "graph LR\n"
    for system in orch.list_systems():
        status = orch.get_status(system.name)
        color = "green" if status.state == "running" else "gray"
        mermaid_code += f"  {system.name}[{system.name}]:::node_{system.name}\n"
        mermaid_code += f"  classDef node_{system.name} fill:{color},stroke:#333,stroke-width:2px;\n"

    # Add connections from telemetry map
    for source, targets in orch._telemetry_map.items():
        for target in targets:
            # Mock latency heatmap logic: random for demo
            import random
            lat = random.randint(10, 150)
            edge_color = "red" if lat > 100 else "orange" if lat > 50 else "blue"
            mermaid_code += f"  {source} -- \"{lat}ms\" --> {target}\n"
            mermaid_code += f"  linkStyle {mermaid_code.count('-->') - 1} stroke:{edge_color},stroke-width:2px;\n"

    # Note: Using st.markdown for mermaid requires a browser extension or specialized component.
    # For out-of-the-box compatibility without extra components, we'll use an iframe to a mermaid renderer
    # or just show the code. For now, we'll try to use a simple text representation if mermaid doesn't render.
    st.code(mermaid_code, language="mermaid")
    st.info("💡 Tip: Install the 'Mermaid Diagrams' browser extension to see the live graph, or use a custom component.")

placeholder = st.empty()
with placeholder.container():
    systems = orch.list_systems()
    if not systems:
        st.warning("No systems discovered. Please add plugins in the 'plugins' folder.")
    else:
        cols = st.columns(3)
        for i, sys_cfg in enumerate(systems):
            with cols[i % 3]:
                from src.ui.system_controls import render_system_card
                render_system_card(orch, sys_cfg.name)

# Footer
st.divider()
st.caption("neurofuse v0.1.0 • Central Command")
