from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from geofence import ACCEPT, REJECT, VERIFY

try:
    import folium
except ModuleNotFoundError:
    folium = None


DECISION_COLOR = {
    ACCEPT: "green",
    VERIFY: "orange",
    REJECT: "red",
}


def decision_to_color(decision: str | None) -> str:
    return DECISION_COLOR.get(str(decision), "blue")


def add_auto_refresh(html_path: str | Path, refresh_seconds: int = 3) -> None:
    html_path = Path(html_path)
    html = html_path.read_text(encoding="utf-8")
    refresh_tag = f'<meta http-equiv="refresh" content="{refresh_seconds}">\n'

    if refresh_tag not in html:
        html = html.replace("<head>", "<head>\n" + refresh_tag, 1)

    html_path.write_text(html, encoding="utf-8")


def _format_float(value, digits: int = 2) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return ""


def create_folium_map(
    df: pd.DataFrame,
    center_lat: float,
    center_lon: float,
    return_radius_m: float,
    output_path: str | Path,
    auto_refresh: bool = False,
    refresh_seconds: int = 3,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if folium is None:
        create_leaflet_map(
            df=df,
            center_lat=center_lat,
            center_lon=center_lon,
            return_radius_m=return_radius_m,
            output_path=output_path,
            auto_refresh=auto_refresh,
            refresh_seconds=refresh_seconds,
        )
        return

    map_obj = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=19,
        max_zoom=19,
        control_scale=True,
        tiles="OpenStreetMap",
    )

    folium.Circle(
        location=[center_lat, center_lon],
        radius=return_radius_m,
        popup=f"return zone radius={return_radius_m:g}m",
        tooltip="return zone",
        color="green",
        fill=True,
        fill_opacity=0.10,
    ).add_to(map_obj)

    points = df[["lat", "lon"]].dropna().values.tolist()
    if len(points) >= 2:
        folium.PolyLine(points, tooltip="GNSS track", color="blue", weight=2).add_to(map_obj)

    for _, row in df.iterrows():
        if pd.isna(row.get("lat")) or pd.isna(row.get("lon")):
            continue

        popup = f"""
        time_utc: {row.get('time_utc', '')}<br>
        distance_m: {_format_float(row.get('distance_m'))}<br>
        hdop: {row.get('hdop', '')}<br>
        num_sat: {row.get('num_sat', '')}<br>
        avg_cn0: {row.get('avg_cn0', '')}<br>
        error_radius_m: {_format_float(row.get('error_radius_m'))}<br>
        basic: {row.get('basic_decision', '')}<br>
        proposed_initial: {row.get('proposed_decision', '')}<br>
        proposed_final: {row.get('proposed_final_decision', '')}<br>
        verification: {row.get('verification_result', '')}<br>
        approval_ratio: {_format_float(row.get('approval_ratio'))}
        """

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=1,
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.9,
            popup=popup,
        ).add_to(map_obj)

    map_obj.save(str(output_path))

    if auto_refresh:
        add_auto_refresh(output_path, refresh_seconds)


def create_leaflet_map(
    df: pd.DataFrame,
    center_lat: float,
    center_lon: float,
    return_radius_m: float,
    output_path: Path,
    auto_refresh: bool = False,
    refresh_seconds: int = 3,
) -> None:
    rows = []
    for _, row in df.iterrows():
        if pd.isna(row.get("lat")) or pd.isna(row.get("lon")):
            continue
        decision = row.get("proposed_final_decision", row.get("proposed_decision", ""))
        rows.append(
            {
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "color": decision_to_color(decision),
                "popup": (
                    f"time_utc: {row.get('time_utc', '')}<br>"
                    f"distance_m: {_format_float(row.get('distance_m'))}<br>"
                    f"HDOP: {row.get('hdop', '')}<br>"
                    f"num_sat: {row.get('num_sat', '')}<br>"
                    f"avg C/N0: {row.get('avg_cn0', '')}<br>"
                    f"basic: {row.get('basic_decision', '')}<br>"
                    f"proposed: {row.get('proposed_final_decision', '')}"
                ),
            }
        )

    points = [[item["lat"], item["lon"]] for item in rows]
    refresh = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if auto_refresh else ""

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  {refresh}
  <title>GNSS Return Zone Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const center = [{center_lat}, {center_lon}];
    const rows = {json.dumps(rows)};
    const points = {json.dumps(points)};
    const map = L.map('map', {{
      zoomControl: true,
      scrollWheelZoom: true,
      maxZoom: 23
    }}).setView(center, 19);
    L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 23,
      maxNativeZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);
    L.control.scale().addTo(map);
    L.circle(center, {{
      radius: {return_radius_m},
      color: 'green',
      fillColor: 'green',
      fillOpacity: 0.10
    }}).bindPopup('return zone radius={return_radius_m:g}m').addTo(map);
    if (points.length >= 2) {{
      L.polyline(points, {{color: 'blue', weight: 2}}).addTo(map);
    }}
    rows.forEach((row) => {{
      L.circleMarker([row.lat, row.lon], {{
        radius: 1,
        color: 'red',
        fillColor: 'red',
        fillOpacity: 0.9
      }}).bindPopup(row.popup).addTo(map);
    }});
  </script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
