# file: pages/2_Architect.py
import streamlit as st
import asyncio
import os
import sys

# Add parent directory of 'src' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.orchestrator import Orchestrator
from src.plugin_manager import PluginManager
from src.config_store import ConfigStore
from src.intelligence.architect import Architect
from src.utils.async_helpers import get_global_loop

_loop = get_global_loop()

st.set_page_config(layout="wide", page_title="Neurofuse Intelligence")
st.title("🤖 AI Architect")

@st.cache_resource
def get_singletons():
    pm = PluginManager(repo_root=".")
    pm.load_all()
    orch = Orchestrator(pm, ConfigStore(), loop=_loop)
    arc = Architect()
    return orch, arc

orch, arc = get_singletons()

st.info("The Architect retrieves context from ChromaDB and generates autonomous system orchestrations.")

query = st.text_area("What orchestration should be written?", placeholder="Sync Ferros and Neurometal for a data fusion cycle.")

if st.button("🏗️ Generate & Load Scenario"):
    with st.spinner("Retrieving memory and writing orchestration..."):
        # Retrieve context from vector store
        memory = asyncio.run_coroutine_threadsafe(arc.retrieve_memory(query), _loop).result()
        st.write("📖 Relevant Memories (from ChromaDB):")
        for m in memory:
            st.caption(f"- {m}")

        # Call simulated architect
        scen = asyncio.run_coroutine_threadsafe(arc.generate_scenario(query, ""), _loop).result()

        # Load into session state for the Sequencer to execute
        if "timeline" not in st.session_state:
            st.session_state.timeline = []
        st.session_state.timeline = scen.timeline
        st.success(f"Scenario '{scen.name}' generated and loaded into the Sequencer!")
        st.write("Next Step: Navigate to the **Sequencer** page to execute.")

st.divider()
st.subheader("System Vector Store Stats")
try:
    import chromadb
    client = chromadb.PersistentClient(path="memory/chroma")
    col = client.get_collection("system_logs")
    st.metric("Total Indexed Logs", col.count())
except:
    st.error("ChromaDB not initialized or empty.")
