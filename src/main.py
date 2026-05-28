from __future__ import annotations

import pandas as pd

from config import (
    MAP_OUTPUT_PATH,
    RAW_DATA_PATH,
    RESULT_CSV_PATH,
    RETURN_CENTER_LAT,
    RETURN_CENTER_LON,
    RETURN_RADIUS_M,
)
from geofence import process_geofence_dataframe
from visualize_map import create_folium_map


def main() -> None:
    df = pd.read_csv(RAW_DATA_PATH)
    result = process_geofence_dataframe(df)

    RESULT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(RESULT_CSV_PATH, index=False, encoding="utf-8-sig")

    create_folium_map(
        df=result,
        center_lat=RETURN_CENTER_LAT,
        center_lon=RETURN_CENTER_LON,
        return_radius_m=RETURN_RADIUS_M,
        output_path=MAP_OUTPUT_PATH,
    )

    print(f"Processed rows: {len(result)}")
    print(f"Result CSV: {RESULT_CSV_PATH}")
    print(f"Map HTML: {MAP_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
