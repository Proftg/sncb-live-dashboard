import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional


class KPICalculator:
    def __init__(self, trip_updates_df: Optional[pd.DataFrame] = None):
        self.trip_updates_df = trip_updates_df
        self.kpis = {}

    def load_data(self, df: pd.DataFrame):
        self.trip_updates_df = df.copy()

    def calculate_all(self) -> dict:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return self._empty_kpis()
        self.kpis = {
            "total_trains": self.total_trains(),
            "on_time_count": self.on_time_count(),
            "delayed_count": self.delayed_count(),
            "on_time_percentage": self.on_time_percentage(),
            "average_delay": self.average_delay(),
            "median_delay": self.median_delay(),
            "max_delay": self.max_delay(),
            "severe_delays": self.severe_delays(),
            "delay_distribution": self.delay_distribution(),
            "delay_by_route": self.delay_by_route(),
            "trend_last_hour": self.trend_last_hour(),
        }
        return self.kpis

    def total_trains(self) -> int:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return 0
        return self.trip_updates_df["trip_id"].nunique()

    def on_time_count(self, threshold: int = 5) -> int:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return 0
        df = self.trip_updates_df.dropna(subset=["arrival_delay"])
        return int((df["arrival_delay"].abs() <= threshold).sum())

    def delayed_count(self, threshold: int = 5) -> int:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return 0
        df = self.trip_updates_df.dropna(subset=["arrival_delay"])
        return int((df["arrival_delay"].abs() > threshold).sum())

    def on_time_percentage(self, threshold: int = 5) -> float:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return 0.0
        total = self.trip_updates_df.dropna(subset=["arrival_delay"])
        if total.empty:
            return 0.0
        on_time = (total["arrival_delay"].abs() <= threshold).sum()
        return round(on_time / len(total) * 100, 1)

    def average_delay(self) -> float:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return 0.0
        df = self.trip_updates_df.dropna(subset=["arrival_delay"])
        if df.empty:
            return 0.0
        return round(df["arrival_delay"].mean(), 1)

    def median_delay(self) -> float:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return 0.0
        df = self.trip_updates_df.dropna(subset=["arrival_delay"])
        if df.empty:
            return 0.0
        return round(df["arrival_delay"].median(), 1)

    def max_delay(self) -> float:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return 0.0
        df = self.trip_updates_df.dropna(subset=["arrival_delay"])
        if df.empty:
            return 0.0
        return round(df["arrival_delay"].max(), 1)

    def severe_delays(self, threshold: int = 15) -> pd.DataFrame:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return pd.DataFrame()
        df = self.trip_updates_df.dropna(subset=["arrival_delay"])
        severe = df[df["arrival_delay"] > threshold]
        return severe.sort_values("arrival_delay", ascending=False)

    def delay_distribution(self) -> pd.Series:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return pd.Series()
        df = self.trip_updates_df.dropna(subset=["arrival_delay"])
        if df.empty:
            return pd.Series()
        bins = [-float("inf"), 0, 5, 15, 30, float("inf")]
        labels = ["Early", "0-5 min", "5-15 min", "15-30 min", "30+ min"]
        return pd.cut(df["arrival_delay"], bins=bins, labels=labels).value_counts()

    def delay_by_route(self) -> pd.DataFrame:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return pd.DataFrame()
        df = self.trip_updates_df.dropna(subset=["arrival_delay", "route_id"])
        if df.empty:
            return pd.DataFrame()
        result = (
            df.groupby("route_id")
            .agg(
                avg_delay=("arrival_delay", "mean"),
                median_delay=("arrival_delay", "median"),
                max_delay=("arrival_delay", "max"),
                train_count=("trip_id", "nunique"),
            )
            .round(1)
        )
        return result.sort_values("avg_delay", ascending=False)

    def trend_last_hour(self) -> dict:
        if self.trip_updates_df is None or self.trip_updates_df.empty:
            return {"current": 0.0, "previous": 0.0, "change": 0.0}
        df = self.trip_updates_df.dropna(subset=["arrival_delay"])
        if "timestamp" not in df.columns:
            current_pct = self.on_time_percentage()
            return {"current": current_pct, "previous": current_pct, "change": 0.0}
        now = df["timestamp"].max()
        one_hour_ago = now - timedelta(hours=1)
        two_hours_ago = now - timedelta(hours=2)
        current_df = df[df["timestamp"] >= one_hour_ago]
        previous_df = df[(df["timestamp"] >= two_hours_ago) & (df["timestamp"] < one_hour_ago)]
        current_pct = round((current_df["arrival_delay"].abs() <= 5).mean() * 100, 1) if len(current_df) > 0 else 0.0
        previous_pct = round((previous_df["arrival_delay"].abs() <= 5).mean() * 100, 1) if len(previous_df) > 0 else 0.0
        change = round(current_pct - previous_pct, 1) if previous_pct > 0 else 0.0
        return {"current": current_pct, "previous": previous_pct, "change": change}

    def _empty_kpis(self) -> dict:
        return {
            "total_trains": 0,
            "on_time_count": 0,
            "delayed_count": 0,
            "on_time_percentage": 0.0,
            "average_delay": 0.0,
            "median_delay": 0.0,
            "max_delay": 0.0,
            "severe_delays": pd.DataFrame(),
            "delay_distribution": pd.Series(),
            "delay_by_route": pd.DataFrame(),
            "trend_last_hour": {"current": 0.0, "previous": 0.0, "change": 0.0},
        }

    def generate_summary(self) -> str:
        if not self.kpis:
            self.calculate_all()
        kpis = self.kpis
        summary = (
            f"Ponctualite SNCB/NMBS\n"
            f"{'=' * 40}\n"
            f"Trains surveilles: {kpis['total_trains']}\n"
            f"A l'heure: {kpis['on_time_percentage']}%\n"
            f"Retard moyen: {kpis['average_delay']} min\n"
            f"Retard median: {kpis['median_delay']} min\n"
            f"Retard max: {kpis['max_delay']} min\n"
            f"Retards severes (>15min): {len(kpis['severe_delays'])}\n"
        )
        return summary
