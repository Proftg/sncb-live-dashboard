import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.kpi_calculator import KPICalculator
from src.gtfs_loader import GTFSLoader
from src.realtime_api import RealtimeAPI

st.set_page_config(
    page_title="SNCB Live - Dashboard Pro",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * {
        font-family: 'Inter', sans-serif;
    }

    .main > div {
        padding-top: 2rem;
    }

    .stMetric {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2a2a4a;
    }

    .stMetric label {
        color: #8892b0 !important;
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .stMetric [data-testid="stMetricValue"] {
        color: #e6f1ff !important;
        font-size: 2rem;
        font-weight: 700;
    }

    .stMetric [data-testid="stMetricDelta"] {
        font-size: 0.9rem;
    }

    .kpi-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #2a2a4a;
        text-align: center;
        margin-bottom: 16px;
    }

    .kpi-card .kpi-label {
        color: #8892b0;
        font-size: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }

    .kpi-card .kpi-value {
        color: #e6f1ff;
        font-size: 2.5rem;
        font-weight: 700;
        line-height: 1;
    }

    .kpi-card .kpi-sub {
        color: #64ffda;
        font-size: 0.85rem;
        margin-top: 8px;
    }

    .kpi-card.warning {
        border-left: 4px solid #f39c12;
    }

    .kpi-card.danger {
        border-left: 4px solid #e74c3c;
    }

    .kpi-card.success {
        border-left: 4px solid #2ecc71;
    }

    .kpi-card.info {
        border-left: 4px solid #3498db;
    }

    .section-title {
        color: #e6f1ff;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 2px solid #2a2a4a;
    }

    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .status-badge.on-time {
        background: rgba(46, 204, 113, 0.2);
        color: #2ecc71;
    }

    .status-badge.delayed {
        background: rgba(243, 156, 18, 0.2);
        color: #f39c12;
    }

    .status-badge.severe {
        background: rgba(231, 76, 60, 0.2);
        color: #e74c3c;
    }

    .alert-banner {
        background: linear-gradient(90deg, rgba(231, 76, 60, 0.15), rgba(231, 76, 60, 0.05));
        border: 1px solid #e74c3c;
        border-radius: 8px;
        padding: 12px 20px;
        margin-bottom: 16px;
        animation: pulse 2s infinite;
    }

    .alert-banner.warning {
        background: linear-gradient(90deg, rgba(243, 156, 18, 0.15), rgba(243, 156, 18, 0.05));
        border: 1px solid #f39c12;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.85; }
    }

    .departure-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        border-bottom: 1px solid #2a2a4a;
        font-size: 0.85rem;
    }

    .departure-row:last-child {
        border-bottom: none;
    }

    div[data-testid="stSidebar"] {
        background: #0f0f1a;
        border-right: 1px solid #2a2a4a;
    }

    div[data-testid="stSidebar"] .stRadio label {
        color: #8892b0;
    }

    div[data-testid="stSidebar"] .stSelectbox label {
        color: #8892b0;
    }

    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    header {
        background: linear-gradient(90deg, #0a0a14 0%, #1a1a2e 50%, #0a0a14 100%);
        border-bottom: 1px solid #2a2a4a;
    }

    h1 {
        color: #e6f1ff !important;
    }

    h2, h3 {
        color: #ccd6f6 !important;
    }

    .stPlotlyChart {
        border-radius: 12px;
        overflow: hidden;
    }

    div[data-baseweb="tabs"] {
        background: #1a1a2e;
        border-radius: 8px;
    }

    div[data-baseweb="tab"] {
        color: #8892b0 !important;
    }

    div[data-baseweb="tab"][aria-selected="true"] {
        color: #64ffda !important;
        background: #16213e !important;
    }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

MAJOR_STATIONS = [
    "Brussels-Central",
    "Gent-Sint-Pieters",
    "Antwerpen-Centraal",
    "Liege-Guillemins",
    "Charleroi-Central",
    "Bruges",
    "Leuven",
    "Namur",
]

DELAY_CATEGORIES = {
    "On-time": {"min": 0, "max": 5, "color": "#2ecc71", "icon": "✓"},
    "Minor": {"min": 5, "max": 15, "color": "#f39c12", "icon": "⚠"},
    "Major": {"min": 15, "max": 30, "color": "#e67e22", "icon": "⚠"},
    "Severe": {"min": 30, "max": float("inf"), "color": "#e74c3c", "icon": "✗"},
}

DELAY_CAUSES = [
    "Signalisation",
    "Problème technique",
    "Conditions météo",
    "Affluence voyageurs",
    "Travaux infrastructure",
    "Incident extérieur",
    "Retard en chaîne",
    "Autre",
]


def generate_historical_data(days=30):
    np.random.seed(42)
    records = []
    base_date = datetime.now() - timedelta(days=days)

    for day in range(days):
        current_date = base_date + timedelta(days=day)
        is_weekend = current_date.weekday() >= 5

        for hour in range(5, 23):
            if is_weekend:
                n_trains = np.random.randint(5, 15)
            else:
                if 7 <= hour <= 9 or 16 <= hour <= 18:
                    n_trains = np.random.randint(20, 40)
                else:
                    n_trains = np.random.randint(8, 20)

            for _ in range(n_trains):
                delay = np.random.exponential(3)
                if np.random.random() < 0.08:
                    delay = np.random.uniform(10, 45)
                if np.random.random() < 0.02:
                    delay = np.random.uniform(30, 90)

                records.append(
                    {
                        "timestamp": current_date.replace(
                            hour=hour, minute=np.random.randint(0, 60)
                        ),
                        "date": current_date.date(),
                        "hour": hour,
                        "station": np.random.choice(MAJOR_STATIONS),
                        "route_id": f"IC-{np.random.randint(1, 20)}",
                        "trip_id": f"TR-{day:02d}-{hour:02d}-{_:04d}",
                        "delay_min": round(delay, 1),
                        "arrival_delay": round(delay, 1),
                        "is_canceled": np.random.random() < 0.01,
                        "delay_cause": np.random.choice(DELAY_CAUSES),
                    }
                )

    return pd.DataFrame(records)


def generate_mock_positions(n=100):
    np.random.seed(42)
    records = []
    for i in range(n):
        delay = np.random.exponential(5)
        if np.random.random() < 0.15:
            delay = np.random.uniform(15, 60)
        records.append(
            {
                "trip_id": f"TR-{i:05d}",
                "route_id": f"IC-{np.random.randint(1, 6)}",
                "latitude": np.random.uniform(49.5, 51.5),
                "longitude": np.random.uniform(2.5, 6.5),
                "departure_delay": round(delay, 1),
                "arrival_delay": round(delay, 1),
                "bearing": round(np.random.uniform(0, 360), 1),
            }
        )
    return pd.DataFrame(records)


def get_delay_category(delay):
    if delay <= 5:
        return "On-time"
    elif delay <= 15:
        return "Minor"
    elif delay <= 30:
        return "Major"
    else:
        return "Severe"


def create_kpi_gauge(value, title, subtitle, color, max_val=100):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": title, "font": {"size": 14, "color": "#8892b0"}},
            number={"font": {"size": 28, "color": "#e6f1ff"}},
            gauge={
                "axis": {"range": [0, max_val], "tickcolor": "#2a2a4a"},
                "bar": {"color": color},
                "bgcolor": "#1a1a2e",
                "borderwidth": 2,
                "bordercolor": "#2a2a4a",
                "steps": [
                    {"range": [0, max_val * 0.6], "color": "#1a1a2e"},
                    {"range": [max_val * 0.6, max_val * 0.8], "color": "#16213e"},
                    {"range": [max_val * 0.8, max_val], "color": "#0f3460"},
                ],
                "threshold": {
                    "line": {"color": color, "width": 4},
                    "thickness": 0.75,
                    "value": value,
                },
            },
        )
    )
    fig.update_layout(
        height=200,
        margin={"l": 20, "r": 20, "t": 30, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#8892b0"},
    )
    return fig


def create_timeline_chart(df):
    daily = df.groupby("date").agg(
        avg_delay=("delay_min", "mean"),
        on_time_pct=("delay_min", lambda x: (x <= 5).mean() * 100),
        total_trains=("delay_min", "count"),
        severe_delays=("delay_min", lambda x: (x > 15).sum()),
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=daily.index,
            y=daily["on_time_pct"],
            name="Ponctualité %",
            line={"color": "#2ecc71", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(46, 204, 113, 0.1)",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=daily.index,
            y=daily["avg_delay"],
            name="Retard moyen (min)",
            line={"color": "#f39c12", "width": 2, "dash": "dash"},
            yaxis="y2",
        )
    )

    fig.update_layout(
        height=350,
        margin={"l": 50, "r": 50, "t": 30, "b": 50},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0a0a14",
        font={"color": "#8892b0"},
        xaxis={
            "gridcolor": "#2a2a4a",
            "title": "Date",
            "title_font": {"color": "#8892b0"},
        },
        yaxis={
            "gridcolor": "#2a2a4a",
            "title": "Ponctualité %",
            "title_font": {"color": "#8892b0"},
            "range": [0, 100],
        },
        yaxis2={
            "overlaying": "y",
            "side": "right",
            "gridcolor": "rgba(0,0,0,0)",
            "title": "Retard moyen (min)",
            "title_font": {"color": "#f39c12"},
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"color": "#8892b0"},
        },
    )
    return fig


def create_hourly_heatmap(df):
    hourly = df.groupby(["date", "hour"]).agg(
        avg_delay=("delay_min", "mean"),
        train_count=("delay_min", "count"),
    )

    pivot = hourly.pivot_table(
        index="hour", columns="date", values="avg_delay", aggfunc="mean"
    )

    x_labels = []
    for col in pivot.columns:
        if hasattr(col, "strftime"):
            x_labels.append(col.strftime("%d/%m"))
        else:
            x_labels.append(str(col))

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=x_labels,
            y=[f"{h}h" for h in pivot.index],
            colorscale=[
                [0, "#2ecc71"],
                [0.3, "#f1c40f"],
                [0.6, "#e67e22"],
                [1, "#e74c3c"],
            ],
            colorbar={
                "title": {"text": "Retard moyen (min)", "font": {"color": "#8892b0"}},
                "tickfont": {"color": "#8892b0"},
            },
            hovertemplate="Date: %{x}<br>Heure: %{y}<br>Retard: %{z:.1f} min<extra></extra>",
        )
    )

    fig.update_layout(
        height=400,
        margin={"l": 60, "r": 30, "t": 30, "b": 50},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0a0a14",
        font={"color": "#8892b0"},
        xaxis={
            "gridcolor": "#2a2a4a",
            "title": "Date",
            "title_font": {"color": "#8892b0"},
        },
        yaxis={
            "gridcolor": "#2a2a4a",
            "title": "Heure",
            "title_font": {"color": "#8892b0"},
        },
    )
    return fig


def create_route_analysis(df):
    route_stats = df.groupby("route_id").agg(
        avg_delay=("delay_min", "mean"),
        total_trains=("delay_min", "count"),
        on_time_pct=("delay_min", lambda x: (x <= 5).mean() * 100),
        severe_delays=("delay_min", lambda x: (x > 15).sum()),
    )

    route_stats = route_stats.sort_values("avg_delay", ascending=False).head(15)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=route_stats.index,
            y=route_stats["avg_delay"],
            name="Retard moyen",
            marker_color=route_stats["avg_delay"].apply(
                lambda x: "#2ecc71" if x <= 5 else ("#f39c12" if x <= 15 else "#e74c3c")
            ),
            text=route_stats["avg_delay"].round(1),
            textposition="outside",
            textfont={"color": "#8892b0"},
        )
    )

    fig.update_layout(
        height=400,
        margin={"l": 50, "r": 30, "t": 30, "b": 100},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0a0a14",
        font={"color": "#8892b0"},
        xaxis={
            "gridcolor": "#2a2a4a",
            "title": "Ligne",
            "title_font": {"color": "#8892b0"},
            "tickangle": -45,
        },
        yaxis={
            "gridcolor": "#2a2a4a",
            "title": "Retard moyen (min)",
            "title_font": {"color": "#8892b0"},
        },
    )
    return fig


def create_station_analysis(df):
    if "station" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="Données de gare non disponibles",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": "#8892b0", "size": 16},
        )
        fig.update_layout(
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0a0a14",
        )
        return fig

    station_stats = df.groupby("station").agg(
        avg_delay=("delay_min", "mean"),
        total_trains=("delay_min", "count"),
        on_time_pct=("delay_min", lambda x: (x <= 5).mean() * 100),
        severe_delays=("delay_min", lambda x: (x > 15).sum()),
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=station_stats["on_time_pct"],
            y=station_stats.index,
            name="Ponctualité %",
            orientation="h",
            marker_color=station_stats["on_time_pct"].apply(
                lambda x: "#2ecc71"
                if x >= 90
                else ("#f39c12" if x >= 70 else "#e74c3c")
            ),
            text=station_stats["on_time_pct"].round(1).astype(str) + "%",
            textposition="outside",
            textfont={"color": "#8892b0"},
        )
    )

    fig.update_layout(
        height=400,
        margin={"l": 150, "r": 50, "t": 30, "b": 50},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0a0a14",
        font={"color": "#8892b0"},
        xaxis={
            "gridcolor": "#2a2a4a",
            "title": "Ponctualité %",
            "title_font": {"color": "#8892b0"},
            "range": [0, 100],
        },
        yaxis={
            "gridcolor": "#2a2a4a",
            "title": "",
            "title_font": {"color": "#8892b0"},
        },
    )
    return fig


def create_delay_distribution(df):
    df["category"] = df["delay_min"].apply(get_delay_category)
    dist = df["category"].value_counts()

    colors = [DELAY_CATEGORIES[cat]["color"] for cat in dist.index]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=dist.index,
                values=dist.values,
                hole=0.5,
                marker_colors=colors,
                textinfo="label+percent",
                textfont={"color": "#e6f1ff", "size": 12},
                hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        height=350,
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#8892b0"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.1,
            "xanchor": "center",
            "x": 0.5,
            "font": {"color": "#8892b0"},
        },
    )
    return fig


def create_map_chart(positions):
    if positions.empty:
        return None

    df = positions.dropna(subset=["latitude", "longitude"]).copy()
    df["color_label"] = df["departure_delay"].apply(get_delay_category)

    fig = px.scatter_map(
        df,
        lat="latitude",
        lon="longitude",
        color="color_label",
        color_discrete_map={
            "On-time": "#2ecc71",
            "Minor": "#f39c12",
            "Major": "#e67e22",
            "Severe": "#e74c3c",
        },
        hover_name="trip_id",
        hover_data={"departure_delay": True, "route_id": True},
        size="departure_delay",
        size_max=15,
        zoom=8,
        center={"lat": 50.8503, "lon": 4.3517},
    )

    fig.update_layout(
        map_style="carto-darkmatter",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def create_delay_cause_chart(df):
    if "delay_cause" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="Données de causes non disponibles",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": "#8892b0", "size": 16},
        )
        fig.update_layout(
            height=350,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0a0a14",
        )
        return fig

    delayed = df[df["delay_min"] > 5].copy()
    if delayed.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Aucun retard enregistré",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": "#8892b0", "size": 16},
        )
        fig.update_layout(
            height=350,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0a0a14",
        )
        return fig

    cause_counts = delayed["delay_cause"].value_counts()
    cause_colors = [
        "#e74c3c",
        "#e67e22",
        "#f39c12",
        "#f1c40f",
        "#3498db",
        "#9b59b6",
        "#1abc9c",
        "#95a5a6",
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=cause_counts.values,
                y=cause_counts.index,
                orientation="h",
                marker_color=cause_colors[: len(cause_counts)],
                text=cause_counts.values,
                textposition="outside",
                textfont={"color": "#8892b0"},
            )
        ]
    )

    fig.update_layout(
        height=350,
        margin={"l": 180, "r": 50, "t": 30, "b": 50},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0a0a14",
        font={"color": "#8892b0"},
        xaxis={
            "gridcolor": "#2a2a4a",
            "title": "Nombre de retards",
            "title_font": {"color": "#8892b0"},
        },
        yaxis={
            "gridcolor": "#2a2a4a",
            "title": "",
            "title_font": {"color": "#8892b0"},
        },
    )
    return fig


def create_comparison_chart(df_current, df_previous):
    metrics = ["Ponctualité %", "Retard moyen (min)", "Retards sévères", "Annulations"]

    if df_current.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Pas de données pour comparaison",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": "#8892b0", "size": 16},
        )
        fig.update_layout(
            height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0a0a14"
        )
        return fig

    current_pct = (
        (df_current["delay_min"] <= 5).mean() * 100
        if "delay_min" in df_current.columns
        else 0
    )
    previous_pct = (
        (df_previous["delay_min"] <= 5).mean() * 100
        if "delay_min" in df_previous.columns
        else 0
    )
    current_avg = (
        df_current["delay_min"].mean() if "delay_min" in df_current.columns else 0
    )
    previous_avg = (
        df_previous["delay_min"].mean() if "delay_min" in df_previous.columns else 0
    )
    current_severe = (
        (df_current["delay_min"] > 15).sum() if "delay_min" in df_current.columns else 0
    )
    previous_severe = (
        (df_previous["delay_min"] > 15).sum()
        if "delay_min" in df_previous.columns
        else 0
    )
    current_cancel = (
        df_current["is_canceled"].sum() if "is_canceled" in df_current.columns else 0
    )
    previous_cancel = (
        df_previous["is_canceled"].sum() if "is_canceled" in df_previous.columns else 0
    )

    current_vals = [current_pct, current_avg, current_severe, current_cancel]
    previous_vals = [previous_pct, previous_avg, previous_severe, previous_cancel]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=metrics,
            y=current_vals,
            name="Période actuelle",
            marker_color="#64ffda",
            text=[f"{v:.1f}" for v in current_vals],
            textposition="outside",
            textfont={"color": "#64ffda"},
        )
    )

    fig.add_trace(
        go.Bar(
            x=metrics,
            y=previous_vals,
            name="Période précédente",
            marker_color="#8892b0",
            text=[f"{v:.1f}" for v in previous_vals],
            textposition="outside",
            textfont={"color": "#8892b0"},
        )
    )

    fig.update_layout(
        height=300,
        margin={"l": 50, "r": 30, "t": 30, "b": 80},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0a0a14",
        font={"color": "#8892b0"},
        barmode="group",
        xaxis={
            "gridcolor": "#2a2a4a",
            "title": "",
            "title_font": {"color": "#8892b0"},
            "tickangle": -30,
        },
        yaxis={
            "gridcolor": "#2a2a4a",
            "title": "",
            "title_font": {"color": "#8892b0"},
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"color": "#8892b0"},
        },
    )
    return fig


def create_departure_board(df, station=None, max_rows=15):
    if station and station != "Toutes les gares":
        board = df[df["station"] == station].copy()
    else:
        board = df.copy()

    if board.empty:
        return pd.DataFrame()

    board = board.sort_values("timestamp", ascending=False).head(max_rows)

    display_cols = []
    if "timestamp" in board.columns:
        display_cols.append("timestamp")
    if "station" in board.columns:
        display_cols.append("station")
    elif "stop_id" in board.columns:
        display_cols.append("stop_id")
    if "route_id" in board.columns:
        display_cols.append("route_id")
    if "trip_id" in board.columns:
        display_cols.append("trip_id")
    delay_col = "delay_min" if "delay_min" in board.columns else "arrival_delay"
    if delay_col in board.columns:
        display_cols.append(delay_col)

    if not display_cols:
        return pd.DataFrame()

    result = board[display_cols].copy()

    if "timestamp" in result.columns:
        result["heure"] = result["timestamp"].apply(
            lambda x: x.strftime("%H:%M") if hasattr(x, "strftime") else str(x)
        )

    if delay_col in result.columns:
        result["statut"] = result[delay_col].apply(
            lambda x: "✓ À l'heure"
            if x <= 5
            else ("⚠ Retard" if x <= 15 else "✗ Sévère")
        )

    return result


def create_alert_banner(severe_df):
    if severe_df.empty:
        return ""
    parts = []
    parts.append('<div style="margin-bottom:16px;">')
    parts.append(
        '<div style="color:#e74c3c;font-size:1.1rem;font-weight:600;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #e74c3c;">🚨 Alertes — Retards Sévères</div>'
    )
    for _, row in severe_df.head(5).iterrows():
        station = str(row.get("station", row.get("stop_id", "N/A")))
        route = str(row.get("route_id", "N/A"))
        delay = float(row.get("delay_min", row.get("arrival_delay", 0)))
        trip = str(row.get("trip_id", "N/A"))
        cause = str(row.get("delay_cause", ""))
        cause_span = ""
        if cause and cause != "nan":
            cause_span = (
                '<span style="color:#8892b0;margin-left:8px;font-size:0.8rem;">('
                + cause
                + ")</span>"
            )
        parts.append(
            '<div style="background:linear-gradient(90deg,rgba(231,76,60,0.15),rgba(231,76,60,0.05));border:1px solid #e74c3c;border-radius:8px;padding:12px 20px;margin-bottom:8px;">'
            '<div style="display:flex;justify-content:space-between;align-items:center;">'
            '<div><strong style="color:#e74c3c;">' + station + "</strong>"
            '<span style="color:#8892b0;margin-left:8px;">' + route + "</span>"
            '<span style="color:#64ffda;margin-left:8px;">' + trip + "</span></div>"
            '<div style="text-align:right;"><span style="color:#e74c3c;font-weight:700;font-size:1.1rem;">+'
            + str(int(delay))
            + " min</span>"
            + cause_span
            + "</div></div></div>"
        )
    parts.append("</div>")
    return "".join(parts)


def create_trend_indicator(current, previous, metric_name):
    if previous == 0:
        return "—", "#8892b0"
    change = ((current - previous) / previous) * 100
    if metric_name in ["Ponctualité %"]:
        if change > 0:
            return f"▲ +{change:.1f}%", "#2ecc71"
        elif change < 0:
            return f"▼ {change:.1f}%", "#e74c3c"
        return "— 0.0%", "#8892b0"
    else:
        if change > 0:
            return f"▲ +{change:.1f}%", "#e74c3c"
        elif change < 0:
            return f"▼ {change:.1f}%", "#2ecc71"
        return "— 0.0%", "#8892b0"


@st.cache_data(ttl=0)
def fetch_live_data():
    api = RealtimeAPI()
    all_departures = []
    for station in MAJOR_STATIONS:
        try:
            df = api.get_liveboard(station=station, arrdep="departure")
            if not df.empty:
                all_departures.append(df)
            time.sleep(0.3)
        except Exception:
            continue
    if not all_departures:
        return None, None
    combined = pd.concat(all_departures, ignore_index=True)
    trip_updates = pd.DataFrame(
        {
            "trip_id": combined["vehicle"],
            "route_id": combined.get("vehicle_shortname", "IC"),
            "stop_id": combined["station"],
            "arrival_delay": combined["delay_min"],
            "departure_delay": combined["delay_min"],
        }
    )
    trip_updates = trip_updates.dropna(subset=["arrival_delay"])
    stations_df = api.get_stations()
    if stations_df.empty:
        positions = generate_mock_positions(len(trip_updates))
    else:
        station_coords = stations_df.set_index("name")[["locationX", "locationY"]]
        positions = []
        for _, row in trip_updates.iterrows():
            station = row["stop_id"]
            if station in station_coords.index:
                lon = station_coords.loc[station, "locationX"]
                lat = station_coords.loc[station, "locationY"]
            else:
                lat = np.random.uniform(49.5, 51.5)
                lon = np.random.uniform(2.5, 6.5)
            positions.append(
                {
                    "trip_id": row["trip_id"],
                    "route_id": row["route_id"],
                    "latitude": lat,
                    "longitude": lon,
                    "departure_delay": row["departure_delay"],
                    "arrival_delay": row["arrival_delay"],
                    "bearing": np.random.uniform(0, 360),
                }
            )
        positions = pd.DataFrame(positions)
    return trip_updates, positions


with st.sidebar:
    st.markdown(
        """
    <div style="text-align: center; padding: 20px 0;">
        <div style="font-size: 2.5rem; margin-bottom: 8px;">🚄</div>
        <div style="color: #e6f1ff; font-size: 1.2rem; font-weight: 700;">SNCB Live</div>
        <div style="color: #64ffda; font-size: 0.75rem; font-weight: 500; letter-spacing: 2px;">OPERATIONS CENTER</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    data_source = st.radio(
        "Source de données",
        ["Temps réel (iRail)", "Données historiques (30j)"],
        index=0,
    )

    st.markdown("---")

    selected_station = st.selectbox(
        "Filtrer par gare",
        ["Toutes les gares"] + MAJOR_STATIONS,
    )

    time_range = st.selectbox(
        "Période",
        ["7 jours", "14 jours", "30 jours"],
        index=2,
    )

    st.markdown("---")

    st.markdown(
        f"""
    <div style="color: #8892b0; font-size: 0.8rem;">
        <div style="margin-bottom: 8px;">📡 Statut API</div>
        <div style="color: #2ecc71;">● Connecté</div>
        <div style="margin-top: 12px;">🕐 Dernière MAJ</div>
        <div style="color: #e6f1ff;">{datetime.now().strftime("%H:%M:%S")}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
    <div>
        <h1 style="margin: 0; color: #e6f1ff; font-size: 1.8rem;">🚄 SNCB Operations Center</h1>
        <p style="margin: 4px 0 0 0; color: #8892b0; font-size: 0.9rem;">Monitoring ponctualité en temps réel — Réseau ferroviaire belge</p>
    </div>
    <div style="text-align: right;">
        <div style="color: #64ffda; font-size: 0.85rem; font-weight: 600;">● LIVE</div>
        <div style="color: #8892b0; font-size: 0.75rem;">"""
    + datetime.now().strftime("%d/%m/%Y %H:%M")
    + """</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

if data_source == "Temps réel (iRail)":
    trip_updates, positions = fetch_live_data()
    if trip_updates is None or trip_updates.empty:
        st.warning("API iRail indisponible, utilisation de données simulées")
        historical_df = generate_historical_data(days=30)
        positions = generate_mock_positions()
    else:
        historical_df = trip_updates.copy()
        now = datetime.now()
        historical_df["timestamp"] = now
        historical_df["date"] = now.date()
        historical_df["hour"] = now.hour
        if (
            "station" not in historical_df.columns
            and "stop_id" in historical_df.columns
        ):
            historical_df["station"] = historical_df["stop_id"]
        if "trip_id" not in historical_df.columns:
            historical_df["trip_id"] = historical_df.index.map(lambda i: f"TR-{i:05d}")
        if (
            "arrival_delay" not in historical_df.columns
            and "delay_min" in historical_df.columns
        ):
            historical_df["arrival_delay"] = historical_df["delay_min"]
        if "is_canceled" not in historical_df.columns:
            historical_df["is_canceled"] = False
        if "route_id" not in historical_df.columns:
            historical_df["route_id"] = "IC"
else:
    days = int(time_range.split()[0])
    historical_df = generate_historical_data(days=days)
    positions = generate_mock_positions()

if selected_station != "Toutes les gares" and "station" in historical_df.columns:
    historical_df = historical_df[historical_df["station"] == selected_station]

if (
    "delay_min" not in historical_df.columns
    and "arrival_delay" in historical_df.columns
):
    historical_df["delay_min"] = historical_df["arrival_delay"]

if "date" in historical_df.columns:
    half = len(historical_df) // 2
    df_current = historical_df.iloc[half:].copy()
    df_previous = historical_df.iloc[:half].copy()
else:
    df_current = historical_df.copy()
    df_previous = pd.DataFrame()

kpi_calc = KPICalculator(historical_df)
kpis = kpi_calc.calculate_all()

total_trains = kpis["total_trains"]
on_time_pct = kpis["on_time_percentage"]
avg_delay = kpis["average_delay"]
severe_count = len(kpis["severe_delays"])
canceled_count = 0
if "is_canceled" in historical_df.columns:
    canceled_count = int(historical_df["is_canceled"].sum())

st.markdown(
    '<div class="section-title">📊 Indicateurs Clés de Performance</div>',
    unsafe_allow_html=True,
)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(
        f"""
    <div class="kpi-card info">
        <div class="kpi-label">Trains surveillés</div>
        <div class="kpi-value">{total_trains:,}</div>
        <div class="kpi-sub">Dernières 24h</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col2:
    color = (
        "#2ecc71"
        if on_time_pct >= 90
        else ("#f39c12" if on_time_pct >= 70 else "#e74c3c")
    )
    st.markdown(
        f"""
    <div class="kpi-card {"success" if on_time_pct >= 90 else "warning" if on_time_pct >= 70 else "danger"}">
        <div class="kpi-label">Ponctualité</div>
        <div class="kpi-value" style="color: {color};">{on_time_pct}%</div>
        <div class="kpi-sub">Objectif: 90%</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col3:
    color = (
        "#2ecc71" if avg_delay <= 3 else ("#f39c12" if avg_delay <= 10 else "#e74c3c")
    )
    st.markdown(
        f"""
    <div class="kpi-card {"success" if avg_delay <= 3 else "warning" if avg_delay <= 10 else "danger"}">
        <div class="kpi-label">Retard moyen</div>
        <div class="kpi-value" style="color: {color};">{avg_delay} min</div>
        <div class="kpi-sub">Médiane: {kpis["median_delay"]} min</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f"""
    <div class="kpi-card {"success" if severe_count == 0 else "danger"}">
        <div class="kpi-label">Retards sévères</div>
        <div class="kpi-value" style="color: {"#e74c3c" if severe_count > 0 else "#2ecc71"};">{severe_count}</div>
        <div class="kpi-sub">{"> 15 min" if severe_count > 0 else "Aucun"}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col5:
    st.markdown(
        f"""
    <div class="kpi-card info">
        <div class="kpi-label">Annulations</div>
        <div class="kpi-value">{canceled_count}</div>
        <div class="kpi-sub">{"0.0%" if total_trains == 0 else f"{canceled_count / total_trains * 100:.1f}%"} du total</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown("---")

st.markdown(
    '<div class="section-title">🎯 Graphiques de Jauge KPI</div>',
    unsafe_allow_html=True,
)

g1, g2, g3, g4 = st.columns(4)

with g1:
    pct_color = (
        "#2ecc71"
        if on_time_pct >= 90
        else ("#f39c12" if on_time_pct >= 70 else "#e74c3c")
    )
    st.plotly_chart(
        create_kpi_gauge(on_time_pct, "Ponctualité", "Objectif: 90%", pct_color),
        use_container_width=True,
    )

with g2:
    delay_color = (
        "#2ecc71" if avg_delay <= 3 else ("#f39c12" if avg_delay <= 10 else "#e74c3c")
    )
    st.plotly_chart(
        create_kpi_gauge(
            avg_delay, "Retard moyen", "Objectif: ≤3 min", delay_color, max_val=30
        ),
        use_container_width=True,
    )

with g3:
    severe_color = "#2ecc71" if severe_count == 0 else "#e74c3c"
    st.plotly_chart(
        create_kpi_gauge(
            severe_count,
            "Retards sévères",
            "Seuil: 0",
            severe_color,
            max_val=max(severe_count * 2, 10),
        ),
        use_container_width=True,
    )

with g4:
    cancel_color = "#2ecc71" if canceled_count == 0 else "#e74c3c"
    st.plotly_chart(
        create_kpi_gauge(
            canceled_count,
            "Annulations",
            "Seuil: 0",
            cancel_color,
            max_val=max(canceled_count * 2, 10),
        ),
        use_container_width=True,
    )

st.markdown("---")

if not df_previous.empty:
    st.markdown(
        '<div class="section-title">📈 Comparaison avec la période précédente</div>',
        unsafe_allow_html=True,
    )

    prev_on_time = (
        (df_previous["delay_min"] <= 5).mean() * 100
        if "delay_min" in df_previous.columns
        else 0
    )
    prev_avg = (
        df_previous["delay_min"].mean() if "delay_min" in df_previous.columns else 0
    )
    prev_severe = (
        (df_previous["delay_min"] > 15).sum()
        if "delay_min" in df_previous.columns
        else 0
    )
    prev_cancel = (
        df_previous["is_canceled"].sum() if "is_canceled" in df_previous.columns else 0
    )

    trend_pct, trend_pct_color = create_trend_indicator(
        on_time_pct, prev_on_time, "Ponctualité %"
    )
    trend_delay, trend_delay_color = create_trend_indicator(
        avg_delay, prev_avg, "Retard moyen"
    )
    trend_severe, trend_severe_color = create_trend_indicator(
        severe_count, prev_severe, "Retards sévères"
    )
    trend_cancel, trend_cancel_color = create_trend_indicator(
        canceled_count, prev_cancel, "Annulations"
    )

    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1:
        st.markdown(
            f"""
        <div class="kpi-card info">
            <div class="kpi-label">Ponctualité</div>
            <div class="kpi-value" style="font-size: 1.8rem;">{on_time_pct}%</div>
            <div class="kpi-sub" style="color: {trend_pct_color};">{trend_pct} vs période préc.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with tc2:
        st.markdown(
            f"""
        <div class="kpi-card info">
            <div class="kpi-label">Retard moyen</div>
            <div class="kpi-value" style="font-size: 1.8rem;">{avg_delay} min</div>
            <div class="kpi-sub" style="color: {trend_delay_color};">{trend_delay} vs période préc.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with tc3:
        st.markdown(
            f"""
        <div class="kpi-card info">
            <div class="kpi-label">Retards sévères</div>
            <div class="kpi-value" style="font-size: 1.8rem;">{severe_count}</div>
            <div class="kpi-sub" style="color: {trend_severe_color};">{trend_severe} vs période préc.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with tc4:
        st.markdown(
            f"""
        <div class="kpi-card info">
            <div class="kpi-label">Annulations</div>
            <div class="kpi-value" style="font-size: 1.8rem;">{canceled_count}</div>
            <div class="kpi-sub" style="color: {trend_cancel_color};">{trend_cancel} vs période préc.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.plotly_chart(
        create_comparison_chart(df_current, df_previous),
        use_container_width=True,
    )

    st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📊 Analyse Temporelle",
        "🗺️ Carte Réseau",
        "📈 Analyse par Ligne",
        "🚉 Analyse par Gare",
    ]
)

with tab1:
    col_chart, col_dist = st.columns([2, 1])

    with col_chart:
        st.markdown(
            '<div class="section-title">Évolution de la ponctualité</div>',
            unsafe_allow_html=True,
        )
        if len(historical_df) > 1:
            st.plotly_chart(
                create_timeline_chart(historical_df), use_container_width=True
            )
        else:
            st.info("Données insuffisantes pour l'analyse temporelle")

    with col_dist:
        st.markdown(
            '<div class="section-title">Distribution des retards</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            create_delay_distribution(historical_df), use_container_width=True
        )

    st.markdown(
        '<div class="section-title" style="margin-top: 24px;">Heatmap horaire des retards</div>',
        unsafe_allow_html=True,
    )
    if len(historical_df) > 10:
        st.plotly_chart(create_hourly_heatmap(historical_df), use_container_width=True)

with tab2:
    st.markdown(
        '<div class="section-title">Position des trains en temps réel</div>',
        unsafe_allow_html=True,
    )
    if not positions.empty:
        map_fig = create_map_chart(positions)
        if map_fig:
            st.plotly_chart(map_fig, use_container_width=True)
    else:
        st.info("Aucune position disponible")

with tab3:
    st.markdown(
        '<div class="section-title">Performance par ligne</div>', unsafe_allow_html=True
    )
    st.plotly_chart(create_route_analysis(historical_df), use_container_width=True)

with tab4:
    st.markdown(
        '<div class="section-title">Ponctualité par gare</div>', unsafe_allow_html=True
    )
    st.plotly_chart(create_station_analysis(historical_df), use_container_width=True)

st.markdown("---")

st.markdown(
    '<div class="section-title">🔍 Analyse des causes de retard</div>',
    unsafe_allow_html=True,
)
st.plotly_chart(create_delay_cause_chart(historical_df), use_container_width=True)

st.markdown("---")

st.markdown(
    '<div class="section-title">🚉 Tableau de bord des départs</div>',
    unsafe_allow_html=True,
)

departure_board = create_departure_board(historical_df, selected_station)
if not departure_board.empty:
    board_cols = []
    if "heure" in departure_board.columns:
        board_cols.append("heure")
    if "station" in departure_board.columns:
        board_cols.append("station")
    elif "stop_id" in departure_board.columns:
        board_cols.append("stop_id")
    if "route_id" in departure_board.columns:
        board_cols.append("route_id")
    if "trip_id" in departure_board.columns:
        board_cols.append("trip_id")
    delay_col = (
        "delay_min" if "delay_min" in departure_board.columns else "arrival_delay"
    )
    if delay_col in departure_board.columns:
        board_cols.append(delay_col)
    if "statut" in departure_board.columns:
        board_cols.append("statut")

    st.dataframe(
        departure_board[board_cols],
        use_container_width=True,
        height=350,
        column_config={
            "heure": st.column_config.TextColumn("Heure"),
            "station": st.column_config.TextColumn("Gare"),
            "stop_id": st.column_config.TextColumn("Gare"),
            "route_id": st.column_config.TextColumn("Ligne"),
            "trip_id": st.column_config.TextColumn("Train"),
            "delay_min": st.column_config.NumberColumn("Retard (min)", format="%.1f"),
            "arrival_delay": st.column_config.NumberColumn(
                "Retard (min)", format="%.1f"
            ),
            "statut": st.column_config.TextColumn("Statut"),
        },
    )
else:
    st.info("Aucun départ à afficher")

st.markdown("---")

severe_alerts = historical_df[historical_df["delay_min"] > 15].sort_values(
    "delay_min", ascending=False
)

if not severe_alerts.empty:
    st.markdown(
        '<div style="color:#e74c3c;font-size:1.1rem;font-weight:600;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #e74c3c;">🚨 Alertes — Retards Sévères</div>',
        unsafe_allow_html=True,
    )
    for _, row in severe_alerts.head(5).iterrows():
        station = str(row.get("station", row.get("stop_id", "N/A")))
        route = str(row.get("route_id", "N/A"))
        delay = float(row.get("delay_min", row.get("arrival_delay", 0)))
        trip = str(row.get("trip_id", "N/A"))
        cause = str(row.get("delay_cause", ""))
        cause_text = f" ({cause})" if cause and cause != "nan" else ""
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown(
                f"**<span style='color:#e74c3c'>{station}</span>**  {route}  {trip}",
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown(
                f"<span style='color:#e74c3c;font-weight:700;font-size:1.1rem;'>+{int(delay)} min</span>{cause_text}",
                unsafe_allow_html=True,
            )
else:
    st.success("✅ Aucun retard sévère détecté — Réseau opérationnel")

st.markdown("---")

st.markdown(
    '<div class="section-title">Derniers événements</div>', unsafe_allow_html=True
)

if "timestamp" in historical_df.columns:
    recent = historical_df.sort_values("timestamp", ascending=False).head(20)
else:
    recent = historical_df.head(20)

cols_to_show = []
if "station" in recent.columns:
    cols_to_show.append("station")
elif "stop_id" in recent.columns:
    cols_to_show.append("stop_id")
if "route_id" in recent.columns:
    cols_to_show.append("route_id")
if "trip_id" in recent.columns:
    cols_to_show.append("trip_id")
if "delay_min" in recent.columns:
    cols_to_show.append("delay_min")
elif "arrival_delay" in recent.columns:
    cols_to_show.append("arrival_delay")

display_df = recent[cols_to_show].copy()

delay_col = "delay_min" if "delay_min" in display_df.columns else "arrival_delay"
display_df["status"] = display_df[delay_col].apply(
    lambda x: '<span class="status-badge on-time">✓ À l\'heure</span>'
    if x <= 5
    else (
        '<span class="status-badge delayed">⚠ Retard</span>'
        if x <= 15
        else '<span class="status-badge severe">✗ Sévère</span>'
    )
)

st.markdown(
    """
<style>
    .dataframe-container {
        background: #1a1a2e;
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #2a2a4a;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.dataframe(
    display_df,
    use_container_width=True,
    height=300,
    column_config={
        "station": st.column_config.TextColumn("Gare"),
        "route_id": st.column_config.TextColumn("Ligne"),
        "trip_id": st.column_config.TextColumn("Train"),
        "delay_min": st.column_config.NumberColumn("Retard (min)", format="%.1f"),
        "status": st.column_config.TextColumn("Statut"),
    },
)

st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #8892b0; font-size: 0.8rem; padding: 20px 0;">'
    "SNCB Operations Center — Dashboard Professionnel — Tahar Guenfoud"
    "</div>",
    unsafe_allow_html=True,
)
