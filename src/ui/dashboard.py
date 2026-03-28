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

# ---- refresh loop ----
st_autorefresh(interval=2000, key="main_datarefresh")

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
