import pandas as pd
import requests
import zipfile
import io
import os
from typing import Optional


GTFS_URL = os.getenv("GTFS_URL", "https://gtfs.irail.be/nmbs/gtfs/latest.zip")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class GTFSLoader:
    def __init__(self, url: str = GTFS_URL, data_dir: str = DATA_DIR):
        self.url = url
        self.data_dir = data_dir
        self.raw_dir = os.path.join(data_dir, "raw")
        self.clean_dir = os.path.join(data_dir, "clean")
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.clean_dir, exist_ok=True)
        self.zip_file = None
        self.dataframes = {}

    def download(self) -> zipfile.ZipFile:
        print(f"Downloading GTFS from {self.url}...")
        resp = requests.get(self.url, timeout=120)
        resp.raise_for_status()
        self.zip_file = zipfile.ZipFile(io.BytesIO(resp.content))
        zip_path = os.path.join(self.raw_dir, "gtfs_latest.zip")
        with open(zip_path, "wb") as f:
            f.write(resp.content)
        print(f"  Downloaded {len(resp.content) / 1024 / 1024:.1f} MB")
        return self.zip_file

    def load_all(self) -> dict:
        if self.zip_file is None:
            self.download()
        for name in self.zip_file.namelist():
            if name.endswith(".txt"):
                df_name = name.replace(".txt", "")
                self.dataframes[df_name] = pd.read_csv(self.zip_file.open(name))
                print(f"  Loaded {df_name}: {len(self.dataframes[df_name]):,} rows")
        return self.dataframes

    def get_stops(self) -> pd.DataFrame:
        if "stops" not in self.dataframes:
            self.load_all()
        return self.dataframes["stops"]

    def get_routes(self) -> pd.DataFrame:
        if "routes" not in self.dataframes:
            self.load_all()
        return self.dataframes["routes"]

    def get_trips(self) -> pd.DataFrame:
        if "trips" not in self.dataframes:
            self.load_all()
        return self.dataframes["trips"]

    def get_stop_times(self) -> pd.DataFrame:
        if "stop_times" not in self.dataframes:
            self.load_all()
        return self.dataframes["stop_times"]

    def get_calendar(self) -> pd.DataFrame:
        if "calendar" not in self.dataframes:
            self.load_all()
        return self.dataframes["calendar"]

    def clean_stops(self) -> pd.DataFrame:
        df = self.get_stops().copy()
        df = df.dropna(subset=["stop_lat", "stop_lon"])
        df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
        df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
        df = df[(df["stop_lat"] >= 49.0) & (df["stop_lat"] <= 52.0)]
        df = df[(df["stop_lon"] >= 2.0) & (df["stop_lon"] <= 7.0)]
        df = df.drop_duplicates(subset="stop_id")
        clean_path = os.path.join(self.clean_dir, "stops_clean.parquet")
        df.to_parquet(clean_path, index=False)
        print(f"Saved {len(df):,} clean stops to {clean_path}")
        return df

    def clean_routes(self) -> pd.DataFrame:
        df = self.get_routes().copy()
        df = df.drop_duplicates(subset="route_id")
        clean_path = os.path.join(self.clean_dir, "routes_clean.parquet")
        df.to_parquet(clean_path, index=False)
        print(f"Saved {len(df):,} clean routes to {clean_path}")
        return df

    def clean_stop_times(self) -> pd.DataFrame:
        df = self.get_stop_times().copy()
        df = df.dropna(subset=["stop_id", "trip_id"])
        clean_path = os.path.join(self.clean_dir, "stop_times_clean.parquet")
        df.to_parquet(clean_path, index=False)
        print(f"Saved {len(df):,} clean stop_times to {clean_path}")
        return df

    def clean_trips(self) -> pd.DataFrame:
        df = self.get_trips().copy()
        df = df.drop_duplicates(subset="trip_id")
        clean_path = os.path.join(self.clean_dir, "trips_clean.parquet")
        df.to_parquet(clean_path, index=False)
        print(f"Saved {len(df):,} clean trips to {clean_path}")
        return df
