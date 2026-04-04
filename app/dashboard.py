import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.kpi_calculator import KPICalculator
from src.gtfs_loader import GTFSLoader
from src.realtime_api import RealtimeAPI


st.set_page_config(
    page_title="Dashboard Ponctualite SNCB",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚄 Dashboard Ponctualite SNCB/NMBS")
st.markdown("Donnees en temps reel — Ponctualite ferroviaire belge")

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


def generate_mock_trip_updates(n=500):
    np.random.seed(42)
    route_ids = [
        "IC-01",
        "IC-02",
        "IC-03",
        "IC-04",
        "IC-05",
        "L-01",
        "L-02",
        "L-03",
        "L-04",
        "L-05",
        "S-01",
        "S-02",
        "S-03",
        "S-04",
        "S-05",
        "P-01",
        "P-02",
        "P-03",
    ]
    records = []
    for i in range(n):
        delay = np.random.exponential(5)
        if np.random.random() < 0.15:
            delay = np.random.uniform(15, 60)
        records.append(
            {
                "trip_id": f"TR-{i:05d}",
                "route_id": np.random.choice(route_ids),
                "stop_id": f"ST-{np.random.randint(100, 999)}",
                "arrival_delay": round(delay, 1),
                "departure_delay": round(delay + np.random.uniform(-2, 2), 1),
            }
        )
    return pd.DataFrame(records)


def generate_mock_positions(n=100):
    np.random.seed(42)
    records = []
    for i in range(n):
        records.append(
            {
                "trip_id": f"TR-{i:05d}",
                "route_id": f"IC-{np.random.randint(1, 6)}",
                "latitude": np.random.uniform(49.5, 51.5),
                "longitude": np.random.uniform(2.5, 6.5),
                "departure_delay": round(np.random.exponential(5), 1),
                "arrival_delay": round(np.random.exponential(5), 1),
                "bearing": round(np.random.uniform(0, 360), 1),
            }
        )
    return pd.DataFrame(records)


@st.cache_data(ttl=0)
def fetch_live_data(refresh_interval):
    api = RealtimeAPI()
    all_departures = []
    for station in MAJOR_STATIONS:
        try:
            df = api.get_liveboard(station=station, arrdep="departure")
            if not df.empty:
                all_departures.append(df)
            time.sleep(0.5)
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


@st.cache_data(ttl=300)
def load_gtfs_stations():
    try:
        loader = GTFSLoader()
        stops = loader.clean_stops()
        return stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]]
    except Exception:
        return None


with st.sidebar:
    st.header("Parametres")
    data_source = st.radio(
        "Source de donnees",
        ["Temps reel (iRail)", "Donnees simulees"],
        index=0,
    )
    refresh_interval = st.selectbox(
        "Intervalle de rafraichissement",
        [30, 60, 120, 300],
        index=1,
        format_func=lambda x: f"{x} secondes",
    )
    st.divider()
    st.caption("Derniere mise a jour: " + datetime.now().strftime("%H:%M:%S"))

if data_source == "Temps reel (iRail)":
    trip_updates, positions = fetch_live_data(refresh_interval)
    if trip_updates is None or trip_updates.empty:
        st.warning("API iRail indisponible, utilisation de donnees simulees")
        trip_updates = generate_mock_trip_updates()
        positions = generate_mock_positions()
else:
    trip_updates = generate_mock_trip_updates()
    positions = generate_mock_positions()

kpi_calc = KPICalculator(trip_updates)
kpis = kpi_calc.calculate_all()

st.subheader("KPIs Ponctualite")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Trains surveilles", value=f"{kpis['total_trains']:,}")
with col2:
    st.metric(
        label="Ponctualite",
        value=f"{kpis['on_time_percentage']}%",
        delta=f"{kpis['trend_last_hour']['change']:+.1f}%",
    )
with col3:
    st.metric(
        label="Retard moyen",
        value=f"{kpis['average_delay']} min",
        delta_color="inverse",
    )
with col4:
    st.metric(
        label="Retards severes (>15 min)",
        value=len(kpis["severe_delays"]),
        delta_color="inverse" if len(kpis["severe_delays"]) > 0 else "normal",
    )

st.divider()

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Carte des trains")
    if not positions.empty:
        df = positions.dropna(subset=["latitude", "longitude"]).copy()
        df["color_label"] = df["departure_delay"].apply(
            lambda d: "green" if d <= 5 else ("orange" if d <= 15 else "red")
        )
        fig_map = px.scatter_map(
            df,
            lat="latitude",
            lon="longitude",
            color="color_label",
            color_discrete_map={
                "green": "#2ecc71",
                "orange": "#f39c12",
                "red": "#e74c3c",
            },
            hover_name="trip_id",
            hover_data={"departure_delay": True, "route_id": True},
            size="departure_delay",
            size_max=15,
            zoom=8,
            center={"lat": 50.8503, "lon": 4.3517},
        )
        fig_map.update_layout(
            map_style="carto-positron",
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            height=500,
        )
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Aucune position de train disponible")

with col_right:
    st.subheader("Distribution des retards")
    if kpis["delay_distribution"].empty:
        st.info("Aucune donnee de retard disponible")
    else:
        delay_cats = kpis["delay_distribution"].index.astype(str).tolist()
        delay_counts = kpis["delay_distribution"].values.tolist()
        color_map = {
            "Early": "#2ecc71",
            "0-5 min": "#3498db",
            "5-15 min": "#f39c12",
            "15-30 min": "#e67e22",
            "30+ min": "#e74c3c",
        }
        colors = [color_map.get(cat, "#95a5a6") for cat in delay_cats]
        fig_dist = go.Figure(
            data=[
                go.Bar(
                    x=delay_cats,
                    y=delay_counts,
                    marker_color=colors,
                    text=delay_counts,
                    textposition="outside",
                )
            ],
            layout=go.Layout(
                xaxis_title="Categorie",
                yaxis_title="Nombre",
                margin=dict(l=40, r=20, t=20, b=40),
                height=350,
            ),
        )
        st.plotly_chart(fig_dist, use_container_width=True)

st.divider()

st.subheader("Retard par ligne")
if kpis["delay_by_route"].empty:
    st.info("Aucune donnee par ligne disponible")
else:
    fig_route = px.bar(
        kpis["delay_by_route"].head(15).reset_index(),
        x="route_id",
        y="avg_delay",
        labels={"route_id": "Ligne", "avg_delay": "Retard moyen (min)"},
        color="avg_delay",
        color_continuous_scale="RdYlGn_r",
    )
    st.plotly_chart(fig_route, use_container_width=True)

st.divider()

col_alerts, col_table = st.columns([1, 2])

with col_alerts:
    st.subheader("Alertes")
    severe = kpis["severe_delays"]
    if severe.empty:
        st.success("Aucun retard severe")
    else:
        for _, row in severe.head(5).iterrows():
            st.error(
                f"🔴 **{row.get('route_id', 'N/A')}** — "
                f"Retard: {row.get('arrival_delay', 0):.0f} min"
            )

with col_table:
    st.subheader("Donnees brutes")
    st.dataframe(trip_updates.head(50), use_container_width=True, height=300)

gtfs_stations = load_gtfs_stations()
if gtfs_stations is not None:
    st.divider()
    st.subheader(f"Stations GTFS ({len(gtfs_stations):,} stations)")
    st.dataframe(gtfs_stations.head(20), use_container_width=True)

st.divider()
st.caption("Dashboard SNCB/NMBS — Projet Portfolio — Tahar Guenfoud")
