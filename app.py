"""mission-control — one dashboard over all 15 AI projects.

Run:  streamlit run app.py
Set MISSION_ROOT if your projects live somewhere other than the parent folder.
"""

from __future__ import annotations

import time

import streamlit as st

from scanner import ROOT, scan

st.set_page_config(page_title="Mission Control", page_icon="🎛️", layout="wide")

st.title("🎛️ Mission Control")
st.caption(f"Scanning **{ROOT}** · artifacts read in place — no agents were modified to report here")

statuses = scan()
business = [s for s in statuses if s.tier == "business"]
papers = [s for s in statuses if s.tier == "paper"]

# ---------------------------------------------------------------- headline
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Projects", len(statuses))
c2.metric("Verified", sum(1 for s in statuses if s.verified))
c3.metric("Fresh (<24h)", sum(1 for s in statuses if s.state == "fresh"))
c4.metric("Idle / never", sum(1 for s in statuses if s.state in ("idle", "never run")))
p1 = next((s for s in statuses if s.name == "ticket-triage-ai"), None)
c5.metric("Triage pending", (p1.metric.split()[0] if p1 and p1.metric[0].isdigit() else "—"))

if st.button("↻ Rescan"):
    st.rerun()

STATE_BADGE = {"fresh": "🟢", "recent": "🟡", "idle": "⚪", "never run": "⚫"}


def render(group: list, title: str) -> None:
    st.subheader(title)
    cols = st.columns(2)
    for i, s in enumerate(group):
        with cols[i % 2]:
            with st.container(border=True):
                badge = STATE_BADGE.get(s.state, "⚪")
                check = " ✅" if s.verified else ""
                st.markdown(f"{badge} **{s.name}**{check} · *{s.purpose}*")
                st.markdown(f"`{s.state}` · last activity **{s.last_human}**")
                st.markdown(f"**{s.metric}**")
                if s.artifacts:
                    st.caption("artifacts: " + " · ".join(s.artifacts[:4]))


render(business, "Business systems")
render(papers, "Paper implementations")

# ---------------------------------------------------------------- activity
st.subheader("Recent activity")
recent = sorted((s for s in statuses if s.last_ts), key=lambda s: s.last_ts, reverse=True)
for s in recent[:8]:
    st.markdown(f"- **{s.name}** — {s.metric} `({s.last_human})`")

st.caption(f"Rendered {time.strftime('%Y-%m-%d %H:%M:%S')} · "
           "✅ = passed its end-to-end verification run")
