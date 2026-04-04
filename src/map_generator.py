import folium
import pandas as pd
import numpy as np
from typing import Optional, Tuple
from folium.plugins import MarkerCluster, HeatMap


BELGIUM_CENTER = [50.8503, 4.3517]
BELGIUM_ZOOM = 8


def delay_color(delay_minutes: float) -> str:
    if delay_minutes is None or delay_minutes <= 5:
        return "green"
    elif delay_minutes <= 15:
        return "orange"
    else:
        return "red"


def delay_icon(delay_minutes: float) -> str:
    if delay_minutes is None or delay_minutes <= 5:
        return "🟢"
    elif delay_minutes <= 15:
        return "🟠"
    else:
        return "🔴"


class MapGenerator:
    def __init__(
        self, center: Tuple[float, float] = BELGIUM_CENTER, zoom: int = BELGIUM_ZOOM
    ):
        self.center = center
        self.zoom = zoom
        self.map = None

    def create_base_map(self) -> folium.Map:
        self.map = folium.Map(
            location=self.center,
            zoom_start=self.zoom,
            tiles="OpenStreetMap",
        )
        folium.TileLayer(
            tiles="CartoDB dark_matter",
            name="Dark Mode",
        ).add_to(self.map)
        folium.TileLayer(
            tiles="CartoDB positron",
            name="Light Mode",
        ).add_to(self.map)
        folium.LayerControl().add_to(self.map)
        return self.map

    def add_train_positions(
        self,
        positions_df: pd.DataFrame,
        stops_df: Optional[pd.DataFrame] = None,
        cluster: bool = True,
    ) -> folium.Map:
        if self.map is None:
            self.create_base_map()
        if positions_df is None or positions_df.empty:
            return self.map
        df = positions_df.dropna(subset=["latitude", "longitude"]).copy()
        if cluster and len(df) > 50:
            marker_cluster = MarkerCluster(name="Train Positions").add_to(self.map)
            target = marker_cluster
        else:
            target = self.map
        for _, row in df.iterrows():
            delay = row.get("departure_delay") or row.get("arrival_delay")
            color = delay_color(delay)
            popup_text = (
                f"<b>Train</b><br>"
                f"Trip ID: {row.get('trip_id', 'N/A')}<br>"
                f"Route ID: {row.get('route_id', 'N/A')}<br>"
                f"Delay: {delay:.0f} min"
                if delay is not None
                else "Delay: N/A"
            )
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                popup=folium.Popup(popup_text, max_width=200),
                tooltip=f"Train - {delay:.0f}min" if delay is not None else "Train",
            ).add_to(target)
        return self.map

    def add_stops(
        self,
        stops_df: pd.DataFrame,
        max_stops: int = 500,
        sample: bool = True,
    ) -> folium.Map:
        if self.map is None:
            self.create_base_map()
        if stops_df is None or stops_df.empty:
            return self.map
        df = stops_df.dropna(subset=["stop_lat", "stop_lon"]).copy()
        if sample and len(df) > max_stops:
            df = df.sample(n=max_stops, random_state=42)
        for _, row in df.iterrows():
            folium.CircleMarker(
                location=[row["stop_lat"], row["stop_lon"]],
                radius=3,
                color="blue",
                fill=True,
                fill_color="blue",
                fill_opacity=0.5,
                popup=row.get("stop_name", row.get("stop_id", "Stop")),
            ).add_to(self.map)
        return self.map

    def add_heatmap(
        self,
        positions_df: pd.DataFrame,
        radius: int = 15,
        blur: int = 8,
    ) -> folium.Map:
        if self.map is None:
            self.create_base_map()
        if positions_df is None or positions_df.empty:
            return self.map
        df = positions_df.dropna(subset=["latitude", "longitude"])
        if df.empty:
            return self.map
        heat_data = []
        for _, row in df.iterrows():
            delay = row.get("departure_delay") or row.get("arrival_delay") or 0
            intensity = min(delay / 3.0 + 0.7, 1.0)
            heat_data.append([row["latitude"], row["longitude"], intensity])
        HeatMap(
            heat_data,
            radius=radius,
            blur=blur,
            max_zoom=13,
            min_opacity=0.5,
            gradient={
                0.0: "blue",
                0.3: "cyan",
                0.5: "lime",
                0.7: "yellow",
                1.0: "red",
            },
        ).add_to(self.map)
        return self.map

    def heatmap_plotly(self, positions_df: pd.DataFrame):
        if positions_df is None or positions_df.empty:
            return None
        df = positions_df.dropna(subset=["latitude", "longitude"])
        if df.empty:
            return None
        import plotly.graph_objects as go

        fig = go.Figure(
            go.Densitymapbox(
                lat=df["latitude"],
                lon=df["longitude"],
                z=df["departure_delay"].fillna(0),
                radius=15,
                colorscale=[
                    [0, "blue"],
                    [0.3, "cyan"],
                    [0.5, "lime"],
                    [0.7, "yellow"],
                    [1.0, "red"],
                ],
                hovertemplate="Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<br>Delay: %{z:.1f} min<extra></extra>",
            )
        )
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox_center={"lat": self.center[0], "lon": self.center[1]},
            mapbox_zoom=self.zoom,
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            height=500,
        )
        return fig

    def add_delayed_trains(
        self,
        trip_updates_df: pd.DataFrame,
        stops_df: Optional[pd.DataFrame] = None,
        threshold: int = 15,
    ) -> folium.Map:
        if self.map is None:
            self.create_base_map()
        if trip_updates_df is None or trip_updates_df.empty:
            return self.map
        if stops_df is None or stops_df.empty:
            return self.map
        delayed = trip_updates_df[trip_updates_df["arrival_delay"] > threshold]
        if delayed.empty:
            return self.map
        stop_coords = stops_df.set_index("stop_id")[["stop_lat", "stop_lon"]]
        for _, row in delayed.iterrows():
            stop_id = row.get("stop_id")
            if stop_id in stop_coords.index:
                lat = stop_coords.loc[stop_id, "stop_lat"]
                lon = stop_coords.loc[stop_id, "stop_lon"]
                delay = row["arrival_delay"]
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.Icon(
                        color="red", icon="warning-sign", prefix="glyphicon"
                    ),
                    popup=f"<b>Retard: {delay:.0f} min</b><br>Trip: {row.get('trip_id', 'N/A')}<br>Stop: {stop_id}",
                    tooltip=f"⚠️ {delay:.0f} min",
                ).add_to(self.map)
        return self.map

    def add_legend(self) -> folium.Map:
        if self.map is None:
            self.create_base_map()
        legend_html = """
        <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                    background-color: white; padding: 10px; border-radius: 5px;
                    border: 2px solid grey; font-size: 14px;">
            <b>Legende Retards</b><br>
            <i style="color: green;">&#9679;</i> A l'heure (&lt;5 min)<br>
            <i style="color: orange;">&#9679;</i> Retard moyen (5-15 min)<br>
            <i style="color: red;">&#9679;</i> Retard severe (&gt;15 min)
        </div>
        """
        self.map.get_root().html.add_child(folium.Element(legend_html))
        return self.map

    def save(self, filepath: str = "data/clean/map.html") -> str:
        if self.map is None:
            self.create_base_map()
        self.map.save(filepath)
        print(f"Map saved to {filepath}")
        return filepath

    def get_map(self) -> folium.Map:
        if self.map is None:
            self.create_base_map()
        return self.map
