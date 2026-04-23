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

st.set_page_config(layout="wide", page_title="neurofuse – The Intelligence Welding Studio", page_icon="🎛️")

# Custom Premium Styling
st.markdown("""
    <style>
    /* Global Styles */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=JetBrains+Mono:wght@400;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Outfit', sans-serif;
        background-color: #0d1117;
        color: #e6edf3;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Titles and Typography */
    h1 {
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
        background: linear-gradient(90deg, #58a6ff, #bc8cff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1.5rem !important;
    }

    .stSubheader {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700 !important;
        text-transform: uppercase;
        color: #1f6feb !important;
        letter-spacing: 0.1em;
    }

    /* Cards and Borders */
    [data-testid="stVerticalBlockBorderWrapper"] > div:first-child {
        background: rgba(22, 27, 34, 0.7);
        border: 1px solid rgba(48, 54, 61, 0.8);
        border-radius: 12px;
        padding: 1.5rem;
        backdrop-filter: blur(8px);
        transition: all 0.3s ease;
    }

    [data-testid="stVerticalBlockBorderWrapper"] > div:first-child:hover {
        border-color: #58a6ff;
        box-shadow: 0 0 20px rgba(88, 166, 255, 0.05);
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        border: 1px solid #30363d !important;
        background-color: #21262d !important;
        color: #c9d1d9 !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        border-color: #8b949e !important;
        background-color: #30363d !important;
    }

    .stButton > button[data-testid="baseButton-secondary"]:active {
        box-shadow: none !important;
    }

    /* Text areas and logs */
    .stText {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
        opacity: 0.8;
    }

    /* Custom Metric Display */
    .metric-val {
        font-size: 2rem;
        font-weight: 600;
        margin-bottom: 0.2rem;
    }
    .metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        opacity: 0.6;
        letter-spacing: 0.05em;
    }
    </style>
""", unsafe_allow_html=True)

# Header Branding
col_logo, col_title, col_mute = st.columns([1, 4, 1])
with col_logo:
    st.image("neuro-all.jpg", use_container_width=True)
with col_title:
    st.title("Neurofuse – Intelligence Welding Studio")
    st.markdown("_The central command for monorepo autonomous systems._")

# ---- singletons (cached across reruns) ----
@st.cache_resource
def get_orchestrator():
    pm = PluginManager(repo_root=".")
    pm.load_all()
    # Pass the global loop during initialization
    orch = Orchestrator(pm, ConfigStore(), loop=_loop)
    return orch

orch = get_orchestrator()

with col_mute:
    st.write("")
    st.write("")
    mute = st.toggle("Master Mute", value=orch.master_mute, help="Safety guardrail: blocks all tuning commands when active.")
    if mute != orch.master_mute:
        orch.master_mute = mute
        st.rerun()

# ---- refresh loop ----
st_autorefresh(interval=2000, key="main_datarefresh")

placeholder = st.empty()
with placeholder.container():
    # Topology Graph
    if orch._telemetry_map:
        with st.expander("System Topology (Live Data Flows)", expanded=True):
            mermaid_code = "graph LR\n"
            for src, targets in orch._telemetry_map.items():
                for tgt in targets:
                    mermaid_code += f"    {src} --> {tgt}\n"
            # Simple Mermaid.js integration via HTML
            import streamlit.components.v1 as components
            html_code = f"""
            <pre class="mermaid">
                {mermaid_code}
            </pre>
            <script type="module">
                import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
            </script>
            """
            components.html(html_code, height=300, scrolling=True)

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
