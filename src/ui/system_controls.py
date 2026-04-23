# file: src/ui/system_controls.py
import streamlit as st
import asyncio
from src.orchestrator import Orchestrator
from neurofuse_sdk.schemas.control_command import ControlCommand

def render_system_card(orch: Orchestrator, name: str):
    status = orch.get_status(name)
    
    # State color mapping
    state_colors = {
        "running": "🟢",
        "stopped": "⚪",
        "starting": "🟡",
        "stopping": "🟠",
        "error": "🔴",
        "unknown": "❓"
    }
    indicator = state_colors.get(status.state, "❓")

    with st.container(border=True):
        st.subheader(f"{indicator} {name}")
        
        # Header Metrics Row
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f'<div class="metric-label">Engine State</div><div class="metric-val">{status.state.upper()}</div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-label">Uptime</div><div class="metric-val">{status.uptime:.1f}s</div>', unsafe_allow_html=True)

        if status.last_error:
            st.error(f"Error: {status.last_error}")

        # Metrics Visualization
        if status.state == "running":
            try:
                # Fetch recent metrics for the chart
                fut_metrics = asyncio.run_coroutine_threadsafe(orch.stream_metrics(name), orch.loop)
                metrics = fut_metrics.result(timeout=0.5)
                
                if metrics:
                    # Filter for numeric values and create a small sparkline
                    # We'll take the most recent 50 samples
                    data = [m.value for m in metrics[-50:]]
                    if data:
                        st.markdown(f'<div class="metric-label">{metrics[-1].name} Real-time</div>', unsafe_allow_html=True)
                        st.line_chart(data, height=120, use_container_width=True)
                        st.caption(f"Current: {data[-1]:.4f}")
                else:
                    st.info("Gathering telemetry...")
            except Exception:
                pass

        st.divider()

        # Controls
        ctrl_cols = st.columns([1, 1, 1])
        with ctrl_cols[0]:
            if st.button("▶️ START", key=f"start_{name}", disabled=status.state in ["running", "starting"], use_container_width=True):
                orch.send_command(name, ControlCommand(action="start"))
                st.rerun()

        with ctrl_cols[1]:
            if st.button("⏹️ STOP", key=f"stop_{name}", disabled=status.state not in ["running", "error"], use_container_width=True):
                orch.send_command(name, ControlCommand(action="stop"))
                st.rerun()

        with ctrl_cols[2]:
             st.button("⚙️ TUNE", key=f"tune_trigger_{name}", use_container_width=True)

        # Expanders for detailed inspection
        with st.expander("Diagnostic Inspector"):
            tab1, tab2 = st.tabs(["Logs", "Parameters"])
            
            with tab1:
                if status.state == "running":
                    try:
                        fut_logs = asyncio.run_coroutine_threadsafe(orch.stream_logs(name, limit=15), orch.loop)
                        logs = fut_logs.result(timeout=0.5)
                        if logs:
                            log_text = "\n".join(logs)
                            st.code(log_text, language="text", wrap_lines=True)
                        else:
                            st.text("Awaiting sequence logs...")
                    except Exception as e:
                        st.text(f"Connection pending: {e}")
                else:
                    st.text("System offline.")

            with tab2:
                if orch.master_mute:
                    st.warning("Master Mute is ACTIVE. Tuning disabled.")

                tunables = orch.get_tunable(name)
                new_vals = {}
                for key, (typ, default) in tunables.items():
                    widget_key = f"tune_{name}_{key}_field"
                    if typ == float:
                        new_vals[key] = st.slider(key, 0.0, 5.0, value=float(default or 1.0), key=widget_key, disabled=orch.master_mute)
                    elif typ == int:
                        new_vals[key] = st.number_input(key, value=int(default or 0), step=1, key=widget_key, disabled=orch.master_mute)
                    else:
                        new_vals[key] = st.text_input(key, value=str(default or ""), key=widget_key, disabled=orch.master_mute)

                if st.button("Apply Parameters", key=f"apply_{name}", disabled=orch.master_mute):
                    orch.send_command(name, ControlCommand(action="tune", payload=new_vals))
                    st.success("Warp parameters updated.")
