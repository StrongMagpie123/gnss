from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

from config import (
    MAP_OUTPUT_PATH,
    METRICS_CSV_PATH,
    PROCESSED_DIR,
    RAW_DATA_PATH,
    RESULT_CSV_PATH,
    RESULT_DIR,
    RETURN_CENTER_LAT,
    RETURN_CENTER_LON,
    RETURN_RADIUS_M,
)
from geofence import ACCEPT, REJECT, process_geofence_dataframe
from visualize_map import create_folium_map


EXPERIMENT_FILES = [
    "01_center.csv",
    "02_inside_boundary.csv",
    "03_outside_boundary.csv",
    "04_bad_signal.csv",
]

SWEEP_CSV_PATH = RESULT_DIR / "threshold_sweep.csv"
SWEEP_WINDOWS = [5, 10, 15]
SWEEP_APPROVAL_RATIOS = [0.50, 0.70, 0.80]


def normalize_label(value: object) -> str | None:
    if pd.isna(value):
        return None
    label = str(value).strip().lower()
    if label in {"inside", "in", "true", "1", "accept", "positive"}:
        return "inside"
    if label in {"outside", "out", "false", "0", "reject", "negative"}:
        return "outside"
    return None


def confusion_counts(df: pd.DataFrame, decision_col: str) -> dict[str, int]:
    labels = df["true_label"].map(normalize_label)
    decisions = df[decision_col].astype(str).str.lower()

    actual_positive = labels == "inside"
    predicted_positive = decisions == ACCEPT
    actual_negative = labels == "outside"
    predicted_negative = decisions == REJECT

    return {
        "TP": int((actual_positive & predicted_positive).sum()),
        "FN": int((actual_positive & ~predicted_positive).sum()),
        "FP": int((actual_negative & predicted_positive).sum()),
        "TN": int((actual_negative & predicted_negative).sum()),
    }


def rates_from_counts(counts: dict[str, int]) -> dict[str, float]:
    tp = counts["TP"]
    fn = counts["FN"]
    fp = counts["FP"]
    tn = counts["TN"]

    return {
        "FNR": fn / (tp + fn) if (tp + fn) else 0.0,
        "FPR": fp / (fp + tn) if (fp + tn) else 0.0,
        "TPR": tp / (tp + fn) if (tp + fn) else 0.0,
    }


def metric_row(df: pd.DataFrame, algorithm: str, decision_col: str) -> dict[str, object]:
    counts = confusion_counts(df, decision_col)
    rates = rates_from_counts(counts)
    return {
        "algorithm": algorithm,
        **counts,
        **rates,
        "rows": int(len(df)),
    }


def load_experiment_files(input_dir: Path, files: Iterable[str] = EXPERIMENT_FILES) -> pd.DataFrame:
    frames = []

    for file_name in files:
        path = input_dir / file_name
        if not path.exists():
            continue

        df = pd.read_csv(path)
        if "true_label" not in df.columns:
            if "outside" in file_name:
                df["true_label"] = "outside"
            else:
                df["true_label"] = "inside"
        df["source_file"] = file_name
        frames.append(df)

    if not frames:
        if RAW_DATA_PATH.exists():
            raise FileNotFoundError(
                f"No labeled experiment CSV files found in {input_dir}. "
                f"Only realtime data exists at {RAW_DATA_PATH}. "
                "For a quick labeled evaluation, run: "
                "python src\\analyze_results.py --input data\\processed\\realtime_gnss.csv --label inside "
                "or use --label outside if the measured point was outside the return zone."
            )
        raise FileNotFoundError(
            f"No experiment CSV files found in {input_dir}. "
            f"Expected one or more of: {', '.join(files)}"
        )

    return pd.concat(frames, ignore_index=True)


def analyze_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = process_geofence_dataframe(df)

    if "true_label" not in result.columns:
        raise ValueError("Evaluation requires a true_label column with inside/outside values.")

    metrics = pd.DataFrame(
        [
            metric_row(result, "baseline", "basic_decision"),
            metric_row(result, "proposed", "proposed_final_decision"),
        ]
    )
    return result, metrics


def run_parameter_sweep(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for window_size in SWEEP_WINDOWS:
        for approval_ratio in SWEEP_APPROVAL_RATIOS:
            result = process_geofence_dataframe(
                df,
                verify_window_size=window_size,
                approval_ratio_threshold=approval_ratio,
            )
            counts = confusion_counts(result, "proposed_final_decision")
            rates = rates_from_counts(counts)
            rows.append(
                {
                    "window_size": window_size,
                    "approval_ratio_threshold": approval_ratio,
                    **counts,
                    **rates,
                    "rows": int(len(result)),
                }
            )
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze GNSS return-zone decisions.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Single CSV file. If omitted, 01-04 experiment files in data/processed are used.",
    )
    parser.add_argument(
        "--label",
        choices=["inside", "outside"],
        default=None,
        help="True label to apply when --input has no true_label column.",
    )
    parser.add_argument("--output", type=Path, default=RESULT_CSV_PATH)
    parser.add_argument("--metrics", type=Path, default=METRICS_CSV_PATH)
    parser.add_argument("--sweep", type=Path, default=SWEEP_CSV_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.input:
        df = pd.read_csv(args.input)
        if "true_label" not in df.columns:
            if args.label is None:
                raise ValueError(
                    "--input CSV must include true_label for evaluation, "
                    "or provide --label inside/outside."
                )
            df["true_label"] = args.label
        df["source_file"] = args.input.name
    else:
        df = load_experiment_files(PROCESSED_DIR)

    result, metrics = analyze_dataframe(df)
    sweep = run_parameter_sweep(df)

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.sweep.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    metrics.to_csv(args.metrics, index=False, encoding="utf-8-sig")
    sweep.to_csv(args.sweep, index=False, encoding="utf-8-sig")
    create_folium_map(
        result,
        center_lat=RETURN_CENTER_LAT,
        center_lon=RETURN_CENTER_LON,
        return_radius_m=RETURN_RADIUS_M,
        output_path=MAP_OUTPUT_PATH,
    )

    print(f"Result CSV: {args.output}")
    print(f"Metrics CSV: {args.metrics}")
    print(f"Parameter sweep CSV: {args.sweep}")
    print(f"Map HTML: {MAP_OUTPUT_PATH}")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
