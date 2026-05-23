"""
NBA Shot Auditor — Streamlit dashboard.

Run with:
    streamlit run src/shot_auditor/app/main.py
"""
import json

import altair as alt
import pandas as pd
import streamlit as st

from shot_auditor import Shot, validate_shot
from shot_auditor.pipeline.synthetic import generate_dataset

st.set_page_config(
    page_title="NBA Shot Auditor",
    page_icon="🏀",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏀 NBA Shot Auditor")
    st.caption("Detect labeling errors in NBA shot records.")
    st.divider()

    source = st.radio(
        "Data source",
        ["Synthetic", "Upload JSON", "NBA API"],
        help="Synthetic: instant demo data. Upload: your own JSON. NBA API: live data (slow).",
    )

    shots_raw: list[dict] = []

    if source == "Synthetic":
        n_shots = st.slider("Shots", 50, 500, 200, step=50)
        fault_rate = st.slider("Fault rate", 0.0, 0.40, 0.10, step=0.05,
                               format="%.0f%%",
                               help="Fraction of shots with injected labeling errors.")
        seed = st.number_input("Seed", value=42, step=1)
        if st.button("Generate", use_container_width=True):
            shots_raw = generate_dataset(n_shots=n_shots, fault_rate=fault_rate, seed=int(seed))
            st.session_state["shots_raw"] = shots_raw
        shots_raw = st.session_state.get("shots_raw", generate_dataset())

    elif source == "Upload JSON":
        uploaded = st.file_uploader("Shot data (.json)", type="json")
        if uploaded:
            shots_raw = json.load(uploaded)
        else:
            st.info("Upload a JSON array of shot dictionaries.")

    else:  # NBA API
        season = st.selectbox("Season", ["2024-25", "2023-24", "2022-23"])
        game_id = st.text_input("Game ID", placeholder="e.g. 0022400001",
                                help="10-digit NBA game ID from stats.nba.com.")
        if st.button("Fetch", use_container_width=True):
            if not game_id.strip():
                st.warning("Enter a game ID first.")
            else:
                with st.spinner("Fetching play-by-play…"):
                    try:
                        from shot_auditor.pipeline.nba import fetch_game_shots
                        shots_raw = fetch_game_shots(game_id.strip())
                        st.session_state["shots_raw"] = shots_raw
                    except Exception as exc:
                        st.error(f"API error: {exc}")
        shots_raw = st.session_state.get("shots_raw", [])
        if shots_raw:
            st.caption(
                "⚠️ `shotClockSeconds` is set to 0 for all NBA API shots — "
                "that field is not available in the standard play-by-play endpoint."
            )

# ── Main ─────────────────────────────────────────────────────────────────────

if not shots_raw:
    st.title("NBA Shot Auditor")
    st.info("Configure a data source in the sidebar to get started.")
    st.stop()

# Validate
records = []
for raw in shots_raw:
    shot = Shot(**raw)
    result = validate_shot(shot)

    fault_types: list[str] = []
    for err in result.errors:
        if "shot clock" in err:
            fault_types.append("Shot Clock")
        elif "game clock" in err:
            fault_types.append("Game Clock")
        elif "points" in err:
            fault_types.append("Points")

    records.append({
        "shotID": shot.shotID,
        "period": shot.period,
        "shotClock": shot.shotClockSeconds,
        "gameClock": shot.gameClockSeconds,
        "fg2": f"{shot.fg2Made}/{shot.fg2Attempted}",
        "fg3": f"{shot.fg3Made}/{shot.fg3Attempted}",
        "ft": f"{shot.ftMade}/{shot.ftAttempted}",
        "points": shot.points,
        "faulty": result.is_faulty,
        "fault_types": fault_types,
        "errors": "; ".join(result.errors),
    })

df = pd.DataFrame(records)
n_total = len(df)
n_faulty = int(df["faulty"].sum())

# ── Metrics ───────────────────────────────────────────────────────────────────

st.title("NBA Shot Auditor")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total shots", f"{n_total:,}")
c2.metric("Faulty shots", f"{n_faulty:,}")
c3.metric("Fault rate", f"{n_faulty / n_total:.1%}" if n_total else "—")
c4.metric("Clean shots", f"{n_total - n_faulty:,}")

st.divider()

tab_log, tab_faults = st.tabs(["Shot Log", "Fault Analysis"])

# ── Shot Log ──────────────────────────────────────────────────────────────────

with tab_log:
    show_faulty_only = st.checkbox("Show faulty shots only")
    display_df = df[df["faulty"]] if show_faulty_only else df
    display_df = display_df.drop(columns=["faulty", "fault_types"])

    def _row_style(row: pd.Series) -> list[str]:
        is_bad = df.loc[row.name, "faulty"]
        bg = "background-color: #ffcccc" if is_bad else ""
        return [bg] * len(row)

    st.dataframe(
        display_df.style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )

# ── Fault Analysis ────────────────────────────────────────────────────────────

with tab_faults:
    faulty_df = df[df["faulty"]].copy()

    if faulty_df.empty:
        st.success("No faulty shots — the dataset is clean.")
    else:
        col_a, col_b = st.columns(2)

        # Fault type breakdown
        with col_a:
            st.subheader("Fault type breakdown")
            ft_series = faulty_df["fault_types"].explode()
            ft_counts = ft_series.value_counts().reset_index()
            ft_counts.columns = ["Fault Type", "Count"]

            chart = (
                alt.Chart(ft_counts)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("Count:Q", title=""),
                    y=alt.Y("Fault Type:N", sort="-x", title=""),
                    color=alt.value("#e63946"),
                    tooltip=["Fault Type", "Count"],
                )
                .properties(height=180)
            )
            st.altair_chart(chart, use_container_width=True)

        # Faulty shots by period
        with col_b:
            st.subheader("Faulty shots by period")
            period_counts = (
                faulty_df["period"]
                .value_counts()
                .sort_index()
                .reset_index()
            )
            period_counts.columns = ["Period", "Count"]

            p_chart = (
                alt.Chart(period_counts)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("Period:O", title="Period"),
                    y=alt.Y("Count:Q", title=""),
                    color=alt.value("#e63946"),
                    tooltip=["Period", "Count"],
                )
                .properties(height=180)
            )
            st.altair_chart(p_chart, use_container_width=True)

        st.subheader("Faulty shot detail")
        st.dataframe(
            faulty_df[["shotID", "period", "shotClock", "gameClock", "points", "errors"]]
            .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
