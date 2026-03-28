# file: src/ui/system_controls.py
import streamlit as st
import asyncio
from src.orchestrator import Orchestrator
from src.schemas.control_command import ControlCommand

def render_system_card(orch: Orchestrator, name: str):
    status = orch.get_status(name)
    with st.container(border=True):
        st.subheader(name)
        st.caption(f"State: {status.state} • Uptime: {status.uptime:.1f}s")
        if status.last_error:
            st.error(f"Last error: {status.last_error}")

        c1, c2, c3 = st.columns(3)
        if c1.button("▶️ Start", key=f"start_{name}", disabled=status.state == "running"):
            orch.send_command(name, ControlCommand(action="start"))
            st.rerun()

        if c2.button("⏹️ Stop", key=f"stop_{name}", disabled=status.state != "running"):
            orch.send_command(name, ControlCommand(action="stop"))
            st.rerun()

        if c3.button("⚙️ Tune", key=f"tune_btn_{name}"):
            with st.expander("Tuning Params", expanded=True):
                tunables = orch.get_tunable(name)
                new_vals = {}
                for key, (typ, default) in tunables.items():
                    # Use unique keys for each system's widgets
                    widget_key = f"tune_{name}_{key}"
                    if typ == float:
                        new_vals[key] = st.slider(key, 0.0, 1.0, value=float(default or 0.0), key=widget_key)
                    elif typ == int:
                        new_vals[key] = st.number_input(key, value=int(default or 0), step=1, key=widget_key)
                    else:
                        new_vals[key] = st.text_input(key, value=str(default or ""), key=widget_key)

                if st.button("Apply Tune", key=f"apply_{name}"):
                    orch.send_command(name, ControlCommand(action="tune", payload=new_vals))
                    st.success(f"Tuning command sent for {name}")

        # Real-time logs preview (simple tail)
        if status.state == "running":
            with st.expander("Recent Logs"):
                # Use threadsafe call to get logs
                try:
                    fut = asyncio.run_coroutine_threadsafe(orch.stream_logs(name, limit=10), orch.loop)
                    logs = fut.result(timeout=0.5)
                    if logs:
                        for line in logs:
                            st.text(line)
                    else:
                        st.text("No logs yet...")
                except Exception as e:
                    st.text(f"Waiting for logs... ({e})")
