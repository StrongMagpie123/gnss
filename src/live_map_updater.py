from __future__ import annotations

import time

import pandas as pd

from config import (
    MAP_DIR,
    RAW_DATA_PATH,
    RETURN_CENTER_LAT,
    RETURN_CENTER_LON,
    RETURN_RADIUS_M,
)
from geofence import process_geofence_dataframe
from visualize_map import create_folium_map


OUTPUT_MAP_PATH = MAP_DIR / "live_map.html"
UPDATE_INTERVAL_SEC = 3
MAX_POINTS = 300


def process_df(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) > MAX_POINTS:
        df = df.tail(MAX_POINTS)
    return process_geofence_dataframe(df)


def main() -> None:
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    print("Live map updater started.")
    print(f"Input CSV : {RAW_DATA_PATH}")
    print(f"Output map: {OUTPUT_MAP_PATH}")
    print("Press Ctrl+C to stop.")

    while True:
        try:
            if not RAW_DATA_PATH.exists():
                print("Waiting for realtime_gnss.csv ...")
                time.sleep(UPDATE_INTERVAL_SEC)
                continue

            df = pd.read_csv(RAW_DATA_PATH)
            if df.empty:
                print("CSV is empty.")
                time.sleep(UPDATE_INTERVAL_SEC)
                continue

            result = process_df(df)
            if result.empty:
                print("No valid lat/lon rows.")
                time.sleep(UPDATE_INTERVAL_SEC)
                continue

            create_folium_map(
                df=result,
                center_lat=RETURN_CENTER_LAT,
                center_lon=RETURN_CENTER_LON,
                return_radius_m=RETURN_RADIUS_M,
                output_path=OUTPUT_MAP_PATH,
                auto_refresh=True,
                refresh_seconds=UPDATE_INTERVAL_SEC,
            )

            last = result.iloc[-1]
            print(
                f"updated time={last.get('time_utc', '')} "
                f"distance={last['distance_m']:.2f}m "
                f"basic={last['basic_decision']} "
                f"proposed={last['proposed_final_decision']}"
            )

        except KeyboardInterrupt:
            print("\nLive map updater stopped.")
            break
        except Exception as exc:
            print(f"Error: {exc}")

        time.sleep(UPDATE_INTERVAL_SEC)


if __name__ == "__main__":
    main()
