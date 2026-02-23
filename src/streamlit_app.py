"""Streamlit dashboard: pipeline runs, latency, anomalies, engagement."""
import streamlit as st
import pandas as pd

from src.utils.observability import get_pipeline_run_summary, detect_anomalies
from src.db import get_connection, init_analytics_schema

st.set_page_config(page_title="Personalization Platform", layout="wide")
st.title("Personalization Platform — Observability")

try:
    summary = get_pipeline_run_summary(limit=50)
    anomalies = detect_anomalies(summary)
except Exception as e:
    st.error(f"Could not load pipeline data: {e}")
    summary = []
    anomalies = []

# Metrics row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Pipeline runs", len(summary))
with col2:
    st.metric("Anomalies", len(anomalies))
with col3:
    success = sum(1 for r in summary if r.get("status") == "success")
    st.metric("Successful runs", success)
with col4:
    latencies = [r["latency_seconds"] for r in summary if r.get("latency_seconds") is not None]
    avg_lat = round(sum(latencies) / len(latencies), 1) if latencies else None
    st.metric("Avg latency (s)", avg_lat if avg_lat is not None else "—")

# Pipeline latency (simple chart)
if summary and any(r.get("latency_seconds") for r in summary):
    st.subheader("Pipeline latency")
    df = pd.DataFrame([{"run_id": r["run_id"][:8], "latency_seconds": r.get("latency_seconds") or 0} for r in summary])
    st.bar_chart(df.set_index("run_id")["latency_seconds"], height=220)

st.subheader("Recent pipeline runs")
if summary:
    st.dataframe(summary, use_container_width=True)
else:
    st.info("No pipeline runs yet. Run the pipeline to see data.")

st.subheader("Anomalies")
if anomalies:
    st.table(anomalies)
else:
    st.success("No anomalies detected.")

st.subheader("User engagement (top campaigns)")
try:
    conn = get_connection()
    init_analytics_schema(conn)
    cur = conn.execute(
        "SELECT campaign_id, SUM(engagement_count) AS total FROM user_engagement GROUP BY campaign_id ORDER BY total DESC LIMIT 20"
    )
    rows = cur.fetchall()
    if rows:
        st.dataframe([{"campaign_id": r[0], "total_engagement": r[1]} for r in rows], use_container_width=True)
    else:
        st.info("No engagement data yet.")
except Exception as e:
    st.warning(f"Could not load engagement: {e}")

st.caption("Data from SQLite lineage and user_engagement.")
