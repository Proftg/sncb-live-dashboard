import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.kpi_calculator import KPICalculator
from src.realtime_api import RealtimeAPI

st.set_page_config(
    page_title="SNCB Live - Dashboard Pro",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Auto-refresh: use streamlit-autorefresh if available, fallback to fragment
# ---------------------------------------------------------------------------
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .main > div { padding-top: 1rem; }
    .kpi-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px; padding: 20px; border: 1px solid #2a2a4a;
        text-align: center; margin-bottom: 12px;
    }
    .kpi-card .kpi-label {
        color: #8892b0; font-size: 0.8rem; font-weight: 500;
        text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;
    }
    .kpi-card .kpi-value {
        color: #e6f1ff; font-size: 2.2rem; font-weight: 700; line-height: 1;
    }
    .kpi-card .kpi-sub { color: #64ffda; font-size: 0.85rem; margin-top: 8px; }
    .kpi-card.warning { border-left: 4px solid #f39c12; }
    .kpi-card.danger  { border-left: 4px solid #e74c3c; }
    .kpi-card.success { border-left: 4px solid #2ecc71; }
    .kpi-card.info    { border-left: 4px solid #3498db; }
    .section-title {
        color: #e6f1ff; font-size: 1.1rem; font-weight: 600;
        margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #2a2a4a;
    }
    div[data-testid="stSidebar"] { background: #0f0f1a; border-right: 1px solid #2a2a4a; }
    header { background: linear-gradient(90deg, #0a0a14 0%, #1a1a2e 50%, #0a0a14 100%); border-bottom: 1px solid #2a2a4a; }
    h1 { color: #e6f1ff !important; }
    h2, h3 { color: #ccd6f6 !important; }
    .stPlotlyChart { border-radius: 12px; overflow: hidden; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAJOR_STATIONS = [
    "Brussels-Central", "Brussels-South", "Brussels-North",
    "Gent-Sint-Pieters", "Antwerpen-Centraal", "Liege-Guillemins",
    "Charleroi-Central", "Bruges", "Leuven", "Namur",
    "Mons", "Mechelen", "Hasselt", "Kortrijk", "Ostend",
    "Ottignies", "Denderleeuw", "Schaerbeek",
    "Liege-Saint-Lambert", "Arlon",
]

DELAY_CATEGORIES = {
    "On-time": {"min": 0, "max": 5, "color": "#2ecc71"},
    "Minor":   {"min": 5, "max": 15, "color": "#f39c12"},
    "Major":   {"min": 15, "max": 30, "color": "#e67e22"},
    "Severe":  {"min": 30, "max": float("inf"), "color": "#e74c3c"},
}

REFRESH_INTERVALS = {"30s": 30, "60s": 60, "2 min": 120, "5 min": 300}


def get_delay_category(delay):
    if delay <= 5:
        return "On-time"
    elif delay <= 15:
        return "Minor"
    elif delay <= 30:
        return "Major"
    return "Severe"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
@st.cache_resource
def get_api():
    return RealtimeAPI()


def fetch_live_data(api_instance):
    """Fetch liveboards for all major stations in parallel + station coords."""
    combined = api_instance.get_liveboards_parallel(MAJOR_STATIONS)
    if combined.empty:
        return None, None, None

    trip_updates = pd.DataFrame({
        "trip_id": combined["vehicle"],
        "route_id": combined.get("vehicle_shortname", pd.Series(["IC"] * len(combined))),
        "stop_id": combined["station"],
        "arrival_delay": combined["delay_min"],
        "departure_delay": combined["delay_min"],
        "destination": combined.get("destination", ""),
        "platform": combined.get("platform", ""),
        "canceled": combined.get("canceled", 0),
        "scheduled_datetime": combined.get("scheduled_datetime", pd.NaT),
    })
    trip_updates = trip_updates.dropna(subset=["arrival_delay"])
    now = datetime.now()
    trip_updates["timestamp"] = now
    trip_updates["date"] = now.date()
    trip_updates["hour"] = now.hour
    trip_updates["station"] = trip_updates["stop_id"]
    trip_updates["is_canceled"] = trip_updates["canceled"].astype(str).isin(["1", "True"])
    trip_updates["delay_min"] = trip_updates["arrival_delay"]

    stations_df = api_instance.get_stations()
    positions = _build_positions(trip_updates, stations_df)
    disturbances = api_instance.get_disturbances()

    return trip_updates, positions, disturbances


def _build_positions(trip_updates, stations_df):
    """Map trains to real station coordinates with jitter to avoid overlap."""
    if stations_df.empty or trip_updates.empty:
        return pd.DataFrame()

    station_coords = stations_df.set_index("name")[["locationX", "locationY"]]

    # Count trains per station for jitter spread
    station_counts = trip_updates.groupby("stop_id").cumcount()

    positions = []
    for idx, (_, row) in enumerate(trip_updates.iterrows()):
        station = row["stop_id"]
        if station not in station_coords.index:
            continue
        lon = float(station_coords.loc[station, "locationX"])
        lat = float(station_coords.loc[station, "locationY"])

        # Jitter: spread trains around the station in a small circle
        count_at_station = station_counts.iloc[idx]
        if count_at_station > 0:
            angle = (count_at_station * 137.508) % 360  # golden angle for even spread
            radius = 0.008 + 0.003 * (count_at_station // 8)  # ~800m base, grows per ring
            lat += radius * np.cos(np.radians(angle))
            lon += radius * np.sin(np.radians(angle))

        positions.append({
            "trip_id": row["trip_id"],
            "route_id": row["route_id"],
            "latitude": lat,
            "longitude": lon,
            "departure_delay": row["departure_delay"],
            "arrival_delay": row["arrival_delay"],
            "destination": row.get("destination", ""),
            "station": station,
        })
    return pd.DataFrame(positions)


# ---------------------------------------------------------------------------
# Session state: accumulate history for trends
# ---------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "prev_kpis" not in st.session_state:
    st.session_state.prev_kpis = None
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0a0a14",
    font=dict(color="#8892b0"),
)


def create_kpi_gauge(value, title, subtitle, color, max_val=100):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": title, "font": {"size": 14, "color": "#8892b0"}},
        number={"font": {"size": 28, "color": "#e6f1ff"}},
        gauge={
            "axis": {"range": [0, max_val], "tickcolor": "#2a2a4a"},
            "bar": {"color": color}, "bgcolor": "#1a1a2e",
            "borderwidth": 2, "bordercolor": "#2a2a4a",
            "steps": [
                {"range": [0, max_val * 0.6], "color": "#1a1a2e"},
                {"range": [max_val * 0.6, max_val * 0.8], "color": "#16213e"},
                {"range": [max_val * 0.8, max_val], "color": "#0f3460"},
            ],
            "threshold": {"line": {"color": color, "width": 4}, "thickness": 0.75, "value": value},
        },
    ))
    fig.update_layout(height=200, margin={"l": 20, "r": 20, "t": 30, "b": 10}, **CHART_LAYOUT)
    return fig


def create_delay_distribution(df):
    df = df.copy()
    df["category"] = df["delay_min"].apply(get_delay_category)
    dist = df["category"].value_counts()
    colors = [DELAY_CATEGORIES[cat]["color"] for cat in dist.index if cat in DELAY_CATEGORIES]
    fig = go.Figure(data=[go.Pie(
        labels=dist.index, values=dist.values, hole=0.5,
        marker_colors=colors, textinfo="label+percent",
        textfont={"color": "#e6f1ff", "size": 12},
    )])
    fig.update_layout(height=350, margin={"l": 20, "r": 20, "t": 30, "b": 20}, **CHART_LAYOUT,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5, font={"color": "#8892b0"}))
    return fig


def create_route_analysis(df):
    route_stats = df.groupby("route_id").agg(
        avg_delay=("delay_min", "mean"),
        total_trains=("delay_min", "count"),
        on_time_pct=("delay_min", lambda x: (x <= 5).mean() * 100),
    )
    route_stats = route_stats.sort_values("avg_delay", ascending=False).head(15)
    fig = go.Figure(go.Bar(
        x=route_stats.index, y=route_stats["avg_delay"], name="Retard moyen",
        marker_color=route_stats["avg_delay"].apply(
            lambda x: "#2ecc71" if x <= 5 else ("#f39c12" if x <= 15 else "#e74c3c")
        ),
        text=route_stats["avg_delay"].round(1), textposition="outside", textfont={"color": "#8892b0"},
    ))
    fig.update_layout(height=400, margin={"l": 50, "r": 30, "t": 30, "b": 100}, **CHART_LAYOUT,
                      xaxis=dict(gridcolor="#2a2a4a", title="Ligne", tickangle=-45),
                      yaxis=dict(gridcolor="#2a2a4a", title="Retard moyen (min)"))
    return fig


def create_station_analysis(df):
    if "station" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="Donnees gare non disponibles", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font={"color": "#8892b0", "size": 16})
        fig.update_layout(height=400, **CHART_LAYOUT)
        return fig
    station_stats = df.groupby("station").agg(
        avg_delay=("delay_min", "mean"),
        total_trains=("delay_min", "count"),
        on_time_pct=("delay_min", lambda x: (x <= 5).mean() * 100),
    )
    fig = go.Figure(go.Bar(
        x=station_stats["on_time_pct"], y=station_stats.index, orientation="h",
        marker_color=station_stats["on_time_pct"].apply(
            lambda x: "#2ecc71" if x >= 90 else ("#f39c12" if x >= 70 else "#e74c3c")
        ),
        text=station_stats["on_time_pct"].round(1).astype(str) + "%",
        textposition="outside", textfont={"color": "#8892b0"},
    ))
    fig.update_layout(height=max(300, len(station_stats) * 30), margin={"l": 150, "r": 50, "t": 30, "b": 50}, **CHART_LAYOUT,
                      xaxis=dict(gridcolor="#2a2a4a", title="Ponctualite %", range=[0, 100]),
                      yaxis=dict(gridcolor="#2a2a4a"))
    return fig


def create_map_chart(positions):
    if positions.empty:
        return None
    df = positions.dropna(subset=["latitude", "longitude"]).copy()
    if df.empty:
        return None
    df["delay_cat"] = df["departure_delay"].apply(get_delay_category)
    df["marker_size"] = df["departure_delay"].clip(lower=2, upper=40)
    df["hover_label"] = df.apply(
        lambda r: f"{r['route_id']} | {r['station']} → {r['destination']} | +{r['departure_delay']:.0f}min", axis=1
    )

    fig = px.scatter_map(
        df, lat="latitude", lon="longitude", color="delay_cat",
        color_discrete_map={"On-time": "#2ecc71", "Minor": "#f39c12", "Major": "#e67e22", "Severe": "#e74c3c"},
        category_orders={"delay_cat": ["On-time", "Minor", "Major", "Severe"]},
        hover_name="hover_label",
        hover_data={"delay_cat": False, "latitude": False, "longitude": False, "marker_size": False,
                    "departure_delay": ":.1f", "route_id": True, "station": True, "destination": True},
        size="marker_size", size_max=18, zoom=7,
        center={"lat": 50.5, "lon": 4.35},
    )
    fig.update_layout(
        map_style="carto-darkmatter",
        margin={"l": 0, "r": 0, "t": 0, "b": 0}, height=550,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(title="Statut", orientation="v", yanchor="top", y=0.98, xanchor="left", x=0.01,
                    bgcolor="rgba(26,26,46,0.8)", font=dict(color="#e6f1ff")),
    )
    return fig


def create_history_chart(history):
    """Line chart of KPI evolution over time from accumulated snapshots."""
    if len(history) < 2:
        return None
    df = pd.DataFrame(history)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["on_time_pct"], name="Ponctualite %",
        line=dict(color="#2ecc71", width=2), fill="tozeroy", fillcolor="rgba(46,204,113,0.1)",
    ))
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["avg_delay"], name="Retard moyen (min)",
        line=dict(color="#f39c12", width=2, dash="dash"), yaxis="y2",
    ))
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["total_trains"], name="Trains surveilles",
        line=dict(color="#3498db", width=1, dash="dot"), yaxis="y2",
    ))
    fig.update_layout(
        height=300, **CHART_LAYOUT,
        margin=dict(l=50, r=50, t=10, b=30),
        xaxis=dict(gridcolor="#2a2a4a"),
        yaxis=dict(gridcolor="#2a2a4a", title="Ponctualite %", range=[0, 100]),
        yaxis2=dict(overlaying="y", side="right", gridcolor="rgba(0,0,0,0)", title="Retard / Trains"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#8892b0")),
    )
    return fig


def create_trend_indicator(current, previous, metric_name):
    if previous is None or previous == 0:
        return "—", "#8892b0"
    change = ((current - previous) / abs(previous)) * 100
    if metric_name in ["Ponctualite %"]:
        if change > 0:
            return f"▲ +{change:.1f}%", "#2ecc71"
        elif change < 0:
            return f"▼ {change:.1f}%", "#e74c3c"
    else:
        if change > 0:
            return f"▲ +{change:.1f}%", "#e74c3c"
        elif change < 0:
            return f"▼ {change:.1f}%", "#2ecc71"
    return "— 0.0%", "#8892b0"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
api = get_api()

with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:20px 0;">
        <div style="font-size:2.5rem;margin-bottom:8px;">🚄</div>
        <div style="color:#e6f1ff;font-size:1.2rem;font-weight:700;">SNCB Live</div>
        <div style="color:#64ffda;font-size:0.75rem;font-weight:500;letter-spacing:2px;">OPERATIONS CENTER</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    refresh_label = st.selectbox("Rafraichissement", list(REFRESH_INTERVALS.keys()), index=1)
    refresh_sec = REFRESH_INTERVALS[refresh_label]

    selected_station = st.selectbox("Filtrer par gare", ["Toutes les gares"] + MAJOR_STATIONS)

    st.markdown("---")

    # Real API health check (cached briefly)
    @st.cache_data(ttl=30)
    def _check_health():
        return get_api().check_api_health()

    health = _check_health()
    irail_dot = "🟢 Connecte" if health["irail"] else "🔴 Deconnecte"
    st.markdown(f"""
    <div style="color:#8892b0;font-size:0.8rem;">
        <div style="margin-bottom:8px;">📡 Statut API</div>
        <div>{irail_dot}</div>
        <div style="margin-top:12px;">🕐 Derniere MAJ</div>
        <div style="color:#e6f1ff;">{datetime.now().strftime("%H:%M:%S")}</div>
        <div style="margin-top:4px;color:#64ffda;font-size:0.7rem;">↻ Auto-refresh: {refresh_label}</div>
        <div style="color:#8892b0;font-size:0.65rem;margin-top:2px;">Snapshots: {len(st.session_state.history)}</div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
if HAS_AUTOREFRESH:
    st_autorefresh(interval=refresh_sec * 1000, key="auto_refresh")
else:
    # Fallback: manual rerun timer
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    elapsed = (datetime.now() - st.session_state.last_refresh).total_seconds()
    if elapsed >= refresh_sec:
        st.session_state.last_refresh = datetime.now()
        st.rerun()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;">
    <div>
        <h1 style="margin:0;color:#e6f1ff;font-size:1.8rem;">🚄 SNCB Operations Center</h1>
        <p style="margin:4px 0 0 0;color:#8892b0;font-size:0.9rem;">Monitoring ponctualite en temps reel — Reseau ferroviaire belge — {len(MAJOR_STATIONS)} gares</p>
    </div>
    <div style="text-align:right;">
        <div style="color:#64ffda;font-size:0.85rem;font-weight:600;">● LIVE</div>
        <div style="color:#8892b0;font-size:0.75rem;">{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Fetch data
# ---------------------------------------------------------------------------
with st.spinner("Chargement des donnees en temps reel..."):
    trip_updates, positions, disturbances = fetch_live_data(api)

if trip_updates is None or trip_updates.empty:
    st.error("⚠ API iRail indisponible — Verifiez votre connexion internet.")
    st.stop()

# Apply station filter
live_df = trip_updates.copy()
if selected_station != "Toutes les gares" and "station" in live_df.columns:
    live_df = live_df[live_df["station"] == selected_station]

if live_df.empty:
    st.warning(f"Aucune donnee pour {selected_station}.")
    st.stop()

# ---------------------------------------------------------------------------
# KPIs + history accumulation
# ---------------------------------------------------------------------------
kpi_calc = KPICalculator(live_df)
kpis = kpi_calc.calculate_all()

total_trains = kpis["total_trains"]
on_time_pct = kpis["on_time_percentage"]
avg_delay = kpis["average_delay"]
severe_count = len(kpis["severe_delays"])
canceled_count = int(live_df["is_canceled"].sum()) if "is_canceled" in live_df.columns else 0

# Save snapshot to history (max 120 entries = ~2h at 60s intervals)
now = datetime.now()
snapshot = {
    "timestamp": now,
    "total_trains": total_trains,
    "on_time_pct": on_time_pct,
    "avg_delay": avg_delay,
    "severe_count": severe_count,
    "canceled_count": canceled_count,
}
# Only add if enough time has passed since last snapshot
if (not st.session_state.history or
        (now - st.session_state.history[-1]["timestamp"]).total_seconds() >= 25):
    st.session_state.prev_kpis = st.session_state.history[-1] if st.session_state.history else None
    st.session_state.history.append(snapshot)
    if len(st.session_state.history) > 120:
        st.session_state.history = st.session_state.history[-120:]
    st.session_state.refresh_count += 1

prev = st.session_state.prev_kpis

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">📊 Indicateurs Cles de Performance — Temps Reel</div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
    <div class="kpi-card info">
        <div class="kpi-label">Trains surveilles</div>
        <div class="kpi-value">{total_trains:,}</div>
        <div class="kpi-sub">{len(MAJOR_STATIONS)} gares</div>
    </div>""", unsafe_allow_html=True)

with col2:
    color = "#2ecc71" if on_time_pct >= 90 else ("#f39c12" if on_time_pct >= 70 else "#e74c3c")
    css_cls = "success" if on_time_pct >= 90 else ("warning" if on_time_pct >= 70 else "danger")
    trend_txt, trend_col = create_trend_indicator(on_time_pct, prev["on_time_pct"] if prev else None, "Ponctualite %")
    st.markdown(f"""
    <div class="kpi-card {css_cls}">
        <div class="kpi-label">Ponctualite</div>
        <div class="kpi-value" style="color:{color};">{on_time_pct}%</div>
        <div class="kpi-sub" style="color:{trend_col};">{trend_txt}</div>
    </div>""", unsafe_allow_html=True)

with col3:
    color = "#2ecc71" if avg_delay <= 3 else ("#f39c12" if avg_delay <= 10 else "#e74c3c")
    css_cls = "success" if avg_delay <= 3 else ("warning" if avg_delay <= 10 else "danger")
    trend_txt, trend_col = create_trend_indicator(avg_delay, prev["avg_delay"] if prev else None, "Retard")
    st.markdown(f"""
    <div class="kpi-card {css_cls}">
        <div class="kpi-label">Retard moyen</div>
        <div class="kpi-value" style="color:{color};">{avg_delay} min</div>
        <div class="kpi-sub" style="color:{trend_col};">{trend_txt}</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="kpi-card {"danger" if severe_count > 0 else "success"}">
        <div class="kpi-label">Retards severes</div>
        <div class="kpi-value" style="color:{"#e74c3c" if severe_count > 0 else "#2ecc71"};">{severe_count}</div>
        <div class="kpi-sub">{"> 15 min" if severe_count > 0 else "Aucun"}</div>
    </div>""", unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="kpi-card info">
        <div class="kpi-label">Annulations</div>
        <div class="kpi-value">{canceled_count}</div>
        <div class="kpi-sub">{"0.0%" if total_trains == 0 else f"{canceled_count / total_trains * 100:.1f}%"} du total</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">🎯 Jauges KPI</div>', unsafe_allow_html=True)

g1, g2, g3, g4 = st.columns(4)
with g1:
    pct_color = "#2ecc71" if on_time_pct >= 90 else ("#f39c12" if on_time_pct >= 70 else "#e74c3c")
    st.plotly_chart(create_kpi_gauge(on_time_pct, "Ponctualite", "Objectif: 90%", pct_color), use_container_width=True)
with g2:
    delay_color = "#2ecc71" if avg_delay <= 3 else ("#f39c12" if avg_delay <= 10 else "#e74c3c")
    st.plotly_chart(create_kpi_gauge(avg_delay, "Retard moyen", "Obj: 3 min", delay_color, max_val=30), use_container_width=True)
with g3:
    st.plotly_chart(create_kpi_gauge(severe_count, "Retards severes", "Seuil: 0", "#2ecc71" if severe_count == 0 else "#e74c3c", max_val=max(severe_count * 2, 10)), use_container_width=True)
with g4:
    st.plotly_chart(create_kpi_gauge(canceled_count, "Annulations", "Seuil: 0", "#2ecc71" if canceled_count == 0 else "#e74c3c", max_val=max(canceled_count * 2, 10)), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Evolution chart (from accumulated history)
# ---------------------------------------------------------------------------
if len(st.session_state.history) >= 2:
    st.markdown('<div class="section-title">📈 Evolution en temps reel (depuis le lancement)</div>', unsafe_allow_html=True)
    history_fig = create_history_chart(st.session_state.history)
    if history_fig:
        st.plotly_chart(history_fig, use_container_width=True)
    st.markdown("---")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Carte Reseau", "📊 Distribution", "📈 Analyse par Ligne", "🚉 Analyse par Gare"])

with tab1:
    st.markdown('<div class="section-title">Position des trains en temps reel</div>', unsafe_allow_html=True)
    if positions is not None and not positions.empty:
        st.caption(f"{len(positions)} trains affiches sur {positions['station'].nunique()} gares — Les trains sont repartis autour de leur gare de depart")
        map_fig = create_map_chart(positions)
        if map_fig:
            st.plotly_chart(map_fig, use_container_width=True)
    else:
        st.info("Aucune position disponible")

with tab2:
    st.markdown('<div class="section-title">Distribution des retards</div>', unsafe_allow_html=True)
    st.plotly_chart(create_delay_distribution(live_df), use_container_width=True)

with tab3:
    st.markdown('<div class="section-title">Performance par ligne</div>', unsafe_allow_html=True)
    st.plotly_chart(create_route_analysis(live_df), use_container_width=True)

with tab4:
    st.markdown('<div class="section-title">Ponctualite par gare</div>', unsafe_allow_html=True)
    st.plotly_chart(create_station_analysis(live_df), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Departure board
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">🚉 Tableau des departs en temps reel</div>', unsafe_allow_html=True)

board = live_df.copy()
if "scheduled_datetime" in board.columns:
    board = board.sort_values("scheduled_datetime", ascending=False)
board = board.head(25)

display_cols = []
if "scheduled_datetime" in board.columns:
    board["heure"] = board["scheduled_datetime"].apply(
        lambda x: x.strftime("%H:%M") if pd.notna(x) and hasattr(x, "strftime") else "—"
    )
    display_cols.append("heure")
for c in ["station", "destination", "route_id", "platform"]:
    if c in board.columns:
        display_cols.append(c)
if "delay_min" in board.columns:
    display_cols.append("delay_min")
    board["statut"] = board["delay_min"].apply(
        lambda x: "✓ A l'heure" if x <= 5 else ("⚠ Retard" if x <= 15 else "✗ Severe")
    )
    display_cols.append("statut")

if display_cols:
    st.dataframe(
        board[display_cols], use_container_width=True, height=450,
        column_config={
            "heure": st.column_config.TextColumn("Heure"),
            "station": st.column_config.TextColumn("Gare"),
            "destination": st.column_config.TextColumn("Destination"),
            "route_id": st.column_config.TextColumn("Ligne"),
            "platform": st.column_config.TextColumn("Voie"),
            "delay_min": st.column_config.NumberColumn("Retard (min)", format="%.1f"),
            "statut": st.column_config.TextColumn("Statut"),
        },
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Severe alerts
# ---------------------------------------------------------------------------
severe_alerts = live_df[live_df["delay_min"] > 15].sort_values("delay_min", ascending=False)

if not severe_alerts.empty:
    st.markdown(
        '<div style="color:#e74c3c;font-size:1.1rem;font-weight:600;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #e74c3c;">🚨 Alertes — Retards Severes</div>',
        unsafe_allow_html=True,
    )
    for _, row in severe_alerts.head(8).iterrows():
        station = str(row.get("station", "N/A"))
        route = str(row.get("route_id", "N/A"))
        delay = float(row.get("delay_min", 0))
        dest = str(row.get("destination", ""))
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown(f"**<span style='color:#e74c3c'>{station}</span>** → {dest}  `{route}`", unsafe_allow_html=True)
        with col_b:
            st.markdown(f"<span style='color:#e74c3c;font-weight:700;font-size:1.1rem;'>+{int(delay)} min</span>", unsafe_allow_html=True)
else:
    st.success("✅ Aucun retard severe detecte — Reseau operationnel")

st.markdown("---")

# ---------------------------------------------------------------------------
# Real disturbances
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">⚠ Perturbations en cours (iRail)</div>', unsafe_allow_html=True)

if disturbances is not None and not disturbances.empty:
    for _, row in disturbances.head(10).iterrows():
        title = str(row.get("title", ""))
        desc = str(row.get("description", ""))[:300]
        st.markdown(f"**{title}**")
        if desc and desc != "nan":
            st.caption(desc)
        st.markdown("---")
else:
    st.success("✅ Aucune perturbation signalee")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    '<div style="text-align:center;color:#8892b0;font-size:0.8rem;padding:20px 0;">'
    f"SNCB Operations Center — Dashboard Temps Reel — Tahar Guenfoud — "
    f'Donnees: iRail API — {datetime.now().strftime("%d/%m/%Y %H:%M:%S")} — '
    f'Refresh #{st.session_state.refresh_count}'
    "</div>",
    unsafe_allow_html=True,
)
