import os
import requests
import pandas as pd
from datetime import datetime
from typing import Optional


IRAIR_API_BASE = "https://api.irail.be"
IRAIR_STATIONS_URL = f"{IRAIR_API_BASE}/stations/?format=json"
IRAIR_LIVEBOARD_URL = f"{IRAIR_API_BASE}/liveboard/"
IRAIR_CONNECTIONS_URL = f"{IRAIR_API_BASE}/connections/"
IRAIR_VEHICLE_URL = f"{IRAIR_API_BASE}/vehicle/"
IRAIR_DISTURBANCES_URL = f"{IRAIR_API_BASE}/disturbances/?format=json"


class RealtimeAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {
            "Accept": "application/json",
        }
        self._stations_cache = None

    def _get(self, url: str, params: Optional[dict] = None) -> Optional[dict]:
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def get_stations(self) -> pd.DataFrame:
        if self._stations_cache is not None:
            return self._stations_cache
        data = self._get(IRAIR_STATIONS_URL)
        if data is None or "station" not in data:
            return pd.DataFrame()
        stations = (
            data["station"] if isinstance(data["station"], list) else [data["station"]]
        )
        df = pd.DataFrame(stations)
        if "locationX" in df.columns:
            df["locationX"] = pd.to_numeric(df["locationX"], errors="coerce")
        if "locationY" in df.columns:
            df["locationY"] = pd.to_numeric(df["locationY"], errors="coerce")
        self._stations_cache = df
        return df

    def get_liveboard(
        self,
        station: str = "Gent-Sint-Pieters",
        date: Optional[str] = None,
        time: Optional[str] = None,
        arrdep: str = "departure",
        lang: str = "en",
    ) -> pd.DataFrame:
        params = {
            "station": station,
            "arrdep": arrdep,
            "lang": lang,
            "format": "json",
        }
        if date:
            params["date"] = date
        if time:
            params["time"] = time
        data = self._get(IRAIR_LIVEBOARD_URL, params)
        if data is None:
            return pd.DataFrame()
        departures = data.get("departures", {})
        if isinstance(departures, dict):
            dep_list = departures.get("departure", [])
        elif isinstance(departures, list):
            dep_list = departures
        else:
            dep_list = []
        if not dep_list:
            return pd.DataFrame()
        records = []
        for dep in dep_list:
            record = {
                "station": data.get("station", station),
                "vehicle": dep.get("vehicle", ""),
                "time": dep.get("time"),
                "delay": dep.get("delay", 0),
                "canceled": dep.get("canceled", 0),
                "left": dep.get("left", 0),
                "platform": dep.get("platform", ""),
            }
            stationinfo = dep.get("stationinfo", {})
            record["destination"] = stationinfo.get("name", "")
            record["destination_id"] = stationinfo.get("id", "")
            if "vehicleinfo" in dep:
                vi = dep["vehicleinfo"]
                record["vehicle_shortname"] = vi.get("shortname", "")
            records.append(record)
        df = pd.DataFrame(records)
        if "time" in df.columns:
            df["time"] = pd.to_numeric(df["time"], errors="coerce")
            df["scheduled_datetime"] = pd.to_datetime(
                df["time"], unit="s", errors="coerce"
            )
        if "delay" in df.columns:
            df["delay"] = pd.to_numeric(df["delay"], errors="coerce")
            df["delay_min"] = df["delay"] / 60
        return df

    def get_connections(
        self,
        from_station: str = "Gent-Sint-Pieters",
        to_station: str = "Brussels-Central",
        date: Optional[str] = None,
        time: Optional[str] = None,
        lang: str = "en",
    ) -> pd.DataFrame:
        params = {
            "from": from_station,
            "to": to_station,
            "lang": lang,
            "format": "json",
        }
        if date:
            params["date"] = date
        if time:
            params["time"] = time
        data = self._get(IRAIR_CONNECTIONS_URL, params)
        if data is None:
            return pd.DataFrame()
        connections = data.get("connection", [])
        if not connections:
            return pd.DataFrame()
        records = []
        for conn in connections:
            dep = conn.get("departure", {})
            arr = conn.get("arrival", {})
            record = {
                "duration": conn.get("duration", 0),
                "departure_vehicle": dep.get("vehicle", ""),
                "departure_time": dep.get("time"),
                "departure_delay": dep.get("delay", 0),
                "departure_canceled": dep.get("canceled", 0),
                "departure_platform": dep.get("platform", ""),
                "departure_station": dep.get("stationinfo", {}).get("name", ""),
                "arrival_vehicle": arr.get("vehicle", ""),
                "arrival_time": arr.get("time"),
                "arrival_delay": arr.get("delay", 0),
                "arrival_canceled": arr.get("canceled", 0),
                "arrival_platform": arr.get("platform", ""),
                "arrival_station": arr.get("stationinfo", {}).get("name", ""),
            }
            records.append(record)
        df = pd.DataFrame(records)
        if "duration" in df.columns:
            df["duration"] = pd.to_numeric(df["duration"], errors="coerce")
            df["duration_min"] = df["duration"] / 60
        if "departure_delay" in df.columns:
            df["departure_delay"] = pd.to_numeric(
                df["departure_delay"], errors="coerce"
            )
            df["departure_delay_min"] = df["departure_delay"] / 60
        if "arrival_delay" in df.columns:
            df["arrival_delay"] = pd.to_numeric(df["arrival_delay"], errors="coerce")
            df["arrival_delay_min"] = df["arrival_delay"] / 60
        return df

    def get_vehicle(self, vehicle_id: str, date: Optional[str] = None) -> pd.DataFrame:
        params = {
            "id": vehicle_id,
            "format": "json",
        }
        if date:
            params["date"] = date
        data = self._get(IRAIR_VEHICLE_URL, params)
        if data is None:
            return pd.DataFrame()
        stops = data.get("stops", {})
        if isinstance(stops, dict):
            stop_list = stops.get("stop", [])
        elif isinstance(stops, list):
            stop_list = stops
        else:
            stop_list = []
        if not stop_list:
            return pd.DataFrame()
        records = []
        for stop in stop_list:
            record = {
                "station": stop.get("stationinfo", {}).get("name", ""),
                "station_id": stop.get("stationinfo", {}).get("id", ""),
                "time": stop.get("time"),
                "delay": stop.get("delay", 0),
                "canceled": stop.get("canceled", 0),
                "left": stop.get("left", 0),
                "platform": stop.get("platform", ""),
                "departure_delay": stop.get("departureDelay", 0),
                "arrival_delay": stop.get("arrivalDelay", 0),
                "departure_canceled": stop.get("departureCanceled", 0),
                "arrival_canceled": stop.get("arrivalCanceled", 0),
            }
            records.append(record)
        df = pd.DataFrame(records)
        if "time" in df.columns:
            df["time"] = pd.to_numeric(df["time"], errors="coerce")
            df["scheduled_datetime"] = pd.to_datetime(
                df["time"], unit="s", errors="coerce"
            )
        if "delay" in df.columns:
            df["delay_min"] = df["delay"] / 60
        return df

    def get_disturbances(self) -> pd.DataFrame:
        data = self._get(IRAIR_DISTURBANCES_URL)
        if data is None:
            return pd.DataFrame()
        disturbances = data.get("disturbance", [])
        if isinstance(disturbances, dict):
            disturbances = [disturbances]
        if not disturbances:
            return pd.DataFrame()
        records = []
        for d in disturbances:
            record = {
                "id": d.get("id", ""),
                "title": d.get("title", ""),
                "description": d.get("description", ""),
                "start": d.get("start", ""),
                "end": d.get("end", ""),
                "link": d.get("link", ""),
            }
            records.append(record)
        return pd.DataFrame(records)

    def trip_updates_to_df(self) -> pd.DataFrame:
        return pd.DataFrame()

    def vehicle_positions_to_df(self) -> pd.DataFrame:
        return pd.DataFrame()

    def alerts_to_df(self) -> pd.DataFrame:
        return self.get_disturbances()
