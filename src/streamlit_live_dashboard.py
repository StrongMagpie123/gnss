from __future__ import annotations

import time

import pandas as pd
import pydeck as pdk
import streamlit as st

from config import RAW_DATA_PATH, RETURN_CENTER_LAT, RETURN_CENTER_LON, RETURN_RADIUS_M
from geofence import ACCEPT, REJECT, VERIFY, process_geofence_dataframe


REFRESH_SEC = 2
MAX_POINTS = 300

COLOR_BY_DECISION = {
    ACCEPT: [30, 160, 70, 190],
    VERIFY: [245, 150, 35, 190],
    REJECT: [220, 60, 60, 190],
}


def decision_color(decision: str) -> list[int]:
    return COLOR_BY_DECISION.get(str(decision), [80, 120, 220, 190])


st.set_page_config(page_title="GNSS Return Zone Dashboard", layout="wide")
st.title("GNSS Return Zone Dashboard")

status_box = st.empty()
metric_cols = st.columns(6)
map_box = st.empty()
table_box = st.empty()

while True:
    try:
        if not RAW_DATA_PATH.exists():
            status_box.warning(f"Waiting for CSV: {RAW_DATA_PATH}")
            time.sleep(REFRESH_SEC)
            continue

        raw = pd.read_csv(RAW_DATA_PATH)
        result = process_geofence_dataframe(raw).tail(MAX_POINTS)

        if result.empty:
            status_box.warning("No valid GNSS rows with lat/lon.")
            time.sleep(REFRESH_SEC)
            continue

        last = result.iloc[-1]
        status_box.info(f"Last update: {last.get('pc_time', '')} / GNSS UTC {last.get('time_utc', '')}")

        metric_cols[0].metric("distance", f"{last['distance_m']:.2f} m")
        metric_cols[1].metric("radius", f"{RETURN_RADIUS_M:.0f} m")
        metric_cols[2].metric("HDOP", f"{last.get('hdop', 0):.2f}")
        metric_cols[3].metric("satellites", f"{last.get('num_sat', 0):.0f}")
        metric_cols[4].metric("avg C/N0", f"{last.get('avg_cn0', 0):.1f}")
        metric_cols[5].metric("decision", str(last["proposed_final_decision"]))

        result = result.copy()
        result["color"] = result["proposed_final_decision"].map(decision_color)

        point_layer = pdk.Layer(
            "ScatterplotLayer",
            data=result,
            get_position="[lon, lat]",
            get_radius=1.8,
            get_fill_color="color",
            pickable=True,
        )
        path_layer = pdk.Layer(
            "PathLayer",
            data=[{"path": result[["lon", "lat"]].values.tolist()}],
            get_path="path",
            get_width=3,
            get_color=[50, 90, 180],
        )
        zone_layer = pdk.Layer(
            "ScatterplotLayer",
            data=pd.DataFrame(
                [{"lat": RETURN_CENTER_LAT, "lon": RETURN_CENTER_LON, "radius": RETURN_RADIUS_M}]
            ),
            get_position="[lon, lat]",
            get_radius="radius",
            get_fill_color=[30, 160, 70, 35],
            get_line_color=[30, 160, 70, 180],
            stroked=True,
            filled=True,
        )

        deck = pdk.Deck(
            layers=[zone_layer, path_layer, point_layer],
            initial_view_state=pdk.ViewState(
                latitude=float(last["lat"]),
                longitude=float(last["lon"]),
                zoom=18,
                pitch=0,
            ),
            tooltip={
                "text": "time: {time_utc}\ndistance: {distance_m}\nHDOP: {hdop}\nC/N0: {avg_cn0}\ndecision: {proposed_final_decision}"
            },
        )

        map_box.pydeck_chart(deck, use_container_width=True)
        table_box.dataframe(result.tail(20), use_container_width=True)

    except Exception as exc:
        status_box.error(f"Dashboard error: {exc}")

    time.sleep(REFRESH_SEC)
