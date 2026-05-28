from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt
from typing import Any

import pandas as pd

from config import (
    APPROVAL_RATIO_THRESHOLD,
    BOUNDARY_MARGIN_M,
    JUMP_THRESHOLD_M,
    MIN_VALID_POINTS,
    QUALITY_MAX_HDOP,
    QUALITY_MIN_CN0,
    QUALITY_MIN_FIX,
    QUALITY_MIN_SAT,
    RETURN_CENTER_LAT,
    RETURN_CENTER_LON,
    RETURN_RADIUS_M,
    VERIFY_WINDOW_SIZE,
)


EARTH_RADIUS_M = 6371000.0

ACCEPT = "accept"
VERIFY = "verify"
REJECT = "reject"

VERIFICATION_PASS = "pass"
VERIFICATION_FAIL = "fail"
VERIFICATION_HOLD = "hold"
VERIFICATION_NOT_NEEDED = "not_needed"


def _as_float(value: Any, default: float | None = None) -> float | None:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calc_distance_m(lat: float, lon: float, center_lat: float, center_lon: float) -> float:
    lat1 = radians(float(lat))
    lon1 = radians(float(lon))
    lat2 = radians(float(center_lat))
    lon2 = radians(float(center_lon))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_M * c


def basic_geofence_decision(distance_m: float, return_radius_m: float = RETURN_RADIUS_M) -> str:
    return ACCEPT if float(distance_m) <= float(return_radius_m) else REJECT


def estimate_error_radius_m(num_sat: Any, avg_cn0: Any, hdop: Any) -> float:
    return BOUNDARY_MARGIN_M


def conservative_geofence_decision(
    distance_m: float,
    return_radius_m: float = RETURN_RADIUS_M,
    error_radius_m: float = BOUNDARY_MARGIN_M,
) -> str:
    distance = float(distance_m)
    radius = float(return_radius_m)
    error_radius = float(error_radius_m)

    if distance <= radius - error_radius:
        return ACCEPT
    if distance <= radius + error_radius:
        return VERIFY
    return REJECT


def normalize_gnss_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "time_utc" not in out.columns and "time" in out.columns:
        out = out.rename(columns={"time": "time_utc"})

    for col in ["lat", "lon", "fix_quality", "num_sat", "hdop", "altitude_m", "avg_cn0"]:
        if col not in out.columns:
            out[col] = pd.NA
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    return out


def filter_bad_quality_points(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = normalize_gnss_dataframe(df)
    return out[
        (out["fix_quality"].fillna(0) >= QUALITY_MIN_FIX)
        & (out["num_sat"].fillna(0) >= QUALITY_MIN_SAT)
        & (out["hdop"].fillna(99) <= QUALITY_MAX_HDOP)
        & (out["avg_cn0"].fillna(0) >= QUALITY_MIN_CN0)
    ].copy()


def remove_jump_points(df: pd.DataFrame, jump_threshold_m: float = JUMP_THRESHOLD_M) -> pd.DataFrame:
    if len(df) <= 1:
        return df.copy()

    out = df.copy().reset_index(drop=True)
    keep_flags = [True]
    prev_lat = out.loc[0, "lat"]
    prev_lon = out.loc[0, "lon"]

    for i in range(1, len(out)):
        cur_lat = out.loc[i, "lat"]
        cur_lon = out.loc[i, "lon"]
        jump_distance = calc_distance_m(prev_lat, prev_lon, cur_lat, cur_lon)

        keep = jump_distance <= jump_threshold_m
        keep_flags.append(keep)
        if keep:
            prev_lat = cur_lat
            prev_lon = cur_lon

    return out.loc[keep_flags].reset_index(drop=True)


def calc_mean_position(df: pd.DataFrame) -> tuple[float | None, float | None]:
    if df.empty:
        return None, None
    return float(df["lat"].mean()), float(df["lon"].mean())


def calc_position_stability_m(df: pd.DataFrame, mean_lat: float | None, mean_lon: float | None) -> float | None:
    if df.empty or mean_lat is None or mean_lon is None:
        return None

    distances = df.apply(
        lambda row: calc_distance_m(row["lat"], row["lon"], mean_lat, mean_lon),
        axis=1,
    )
    return float(distances.mean())


def additional_verification(
    df_recent: pd.DataFrame,
    return_center_lat: float = RETURN_CENTER_LAT,
    return_center_lon: float = RETURN_CENTER_LON,
    return_radius_m: float = RETURN_RADIUS_M,
    min_points: int = MIN_VALID_POINTS,
    jump_threshold_m: float = JUMP_THRESHOLD_M,
    approval_ratio_threshold: float = APPROVAL_RATIO_THRESHOLD,
) -> dict[str, Any]:
    if len(df_recent) < min_points:
        return {
            "verification_result": VERIFICATION_HOLD,
            "valid_points": 0,
            "approval_ratio": 0.0,
            "mean_lat": None,
            "mean_lon": None,
            "mean_distance_m": None,
            "stability_m": None,
        }

    filtered = filter_bad_quality_points(df_recent)
    filtered = remove_jump_points(filtered, jump_threshold_m=jump_threshold_m)

    if len(filtered) < min_points:
        return {
            "verification_result": VERIFICATION_HOLD,
            "valid_points": int(len(filtered)),
            "approval_ratio": 0.0,
            "mean_lat": None,
            "mean_lon": None,
            "mean_distance_m": None,
            "stability_m": None,
        }

    distances = filtered.apply(
        lambda row: calc_distance_m(row["lat"], row["lon"], return_center_lat, return_center_lon),
        axis=1,
    )
    approval_ratio = float((distances <= return_radius_m).mean())
    mean_lat, mean_lon = calc_mean_position(filtered)
    mean_distance_m = calc_distance_m(mean_lat, mean_lon, return_center_lat, return_center_lon)
    stability_m = calc_position_stability_m(filtered, mean_lat, mean_lon)

    result = VERIFICATION_PASS if approval_ratio >= approval_ratio_threshold else VERIFICATION_FAIL

    return {
        "verification_result": result,
        "valid_points": int(len(filtered)),
        "approval_ratio": approval_ratio,
        "mean_lat": mean_lat,
        "mean_lon": mean_lon,
        "mean_distance_m": float(mean_distance_m),
        "stability_m": stability_m,
    }


def process_geofence_dataframe(
    df: pd.DataFrame,
    return_center_lat: float = RETURN_CENTER_LAT,
    return_center_lon: float = RETURN_CENTER_LON,
    return_radius_m: float = RETURN_RADIUS_M,
    verify_window_size: int = VERIFY_WINDOW_SIZE,
    approval_ratio_threshold: float = APPROVAL_RATIO_THRESHOLD,
) -> pd.DataFrame:
    out = normalize_gnss_dataframe(df)

    out["distance_m"] = out.apply(
        lambda row: calc_distance_m(row["lat"], row["lon"], return_center_lat, return_center_lon),
        axis=1,
    )
    out["basic_decision"] = out["distance_m"].apply(
        lambda distance_m: basic_geofence_decision(distance_m, return_radius_m)
    )
    out["error_radius_m"] = out.apply(
        lambda row: estimate_error_radius_m(row["num_sat"], row["avg_cn0"], row["hdop"]),
        axis=1,
    )
    out["proposed_decision"] = out.apply(
        lambda row: conservative_geofence_decision(
            row["distance_m"],
            return_radius_m,
            row["error_radius_m"],
        ),
        axis=1,
    )

    verification_rows: list[dict[str, Any]] = []
    final_decisions: list[str] = []

    for idx, row in out.iterrows():
        if row["proposed_decision"] != VERIFY:
            verification_rows.append(
                {
                    "verification_result": VERIFICATION_NOT_NEEDED,
                    "valid_points": 0,
                    "approval_ratio": None,
                    "mean_lat": None,
                    "mean_lon": None,
                    "mean_distance_m": None,
                    "stability_m": None,
                }
            )
            final_decisions.append(row["proposed_decision"])
            continue

        start_idx = max(0, idx - verify_window_size + 1)
        recent = out.iloc[start_idx : idx + 1]
        verification = additional_verification(
            recent,
            return_center_lat=return_center_lat,
            return_center_lon=return_center_lon,
            return_radius_m=return_radius_m,
            approval_ratio_threshold=approval_ratio_threshold,
        )
        verification_rows.append(verification)
        final_decisions.append(ACCEPT if verification["verification_result"] == VERIFICATION_PASS else REJECT)

    verification_df = pd.DataFrame(verification_rows)
    out = pd.concat([out.reset_index(drop=True), verification_df], axis=1)
    out["proposed_final_decision"] = final_decisions
    return out
