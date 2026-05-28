from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


DEFAULT_TARGET_SECONDS = 20.0


def parse_time_utc_to_seconds(value) -> float:
    """
    Convert NMEA-style time_utc to seconds from midnight.

    Supports examples:
    - 61720
    - 061720.00
    - "061720.20"
    - "61720.0"

    Meaning:
    HHMMSS.ss -> seconds from midnight
    """
    if pd.isna(value):
        raise ValueError("time_utc contains NaN")

    s = str(value).strip()

    # Pandas may read 061720.00 as 61720.0, so remove trailing .0 safely.
    try:
        num = float(s)
    except ValueError as exc:
        raise ValueError(f"Invalid time_utc value: {value}") from exc

    int_part = int(num)
    frac = num - int_part

    # HHMMSS can be 5 or 6 digits because leading zero may be dropped.
    # Example: 61720 means 06:17:20.
    hhmmss = f"{int_part:06d}"

    hour = int(hhmmss[0:2])
    minute = int(hhmmss[2:4])
    second = int(hhmmss[4:6]) + frac

    return hour * 3600 + minute * 60 + second


def seconds_to_time_utc(seconds: float) -> str:
    """
    Convert seconds from midnight back to HHMMSS.ss string.
    """
    seconds = seconds % 86400

    hour = int(seconds // 3600)
    remain = seconds - hour * 3600

    minute = int(remain // 60)
    sec = remain - minute * 60

    return f"{hour:02d}{minute:02d}{sec:05.2f}"


def remap_time_utc(df: pd.DataFrame, target_seconds: float = DEFAULT_TARGET_SECONDS) -> pd.DataFrame:
    """
    Remap the entire CSV duration to target_seconds.

    The first row keeps its original time_utc.
    The last row becomes first_time + target_seconds.
    Intermediate rows are linearly compressed/expanded.
    """
    if "time_utc" not in df.columns:
        raise KeyError("CSV must contain a 'time_utc' column.")

    if len(df) < 2:
        raise ValueError("Need at least 2 rows to remap time duration.")

    out = df.copy().reset_index(drop=True)

    original_seconds = out["time_utc"].apply(parse_time_utc_to_seconds)
    start_sec = float(original_seconds.iloc[0])
    end_sec = float(original_seconds.iloc[-1])
    original_duration = end_sec - start_sec

    # Handle midnight crossing just in case.
    if original_duration <= 0:
        original_duration = (end_sec + 86400) - start_sec

    if original_duration <= 0:
        raise ValueError("Original duration must be positive.")

    elapsed = original_seconds - start_sec
    elapsed = elapsed.where(elapsed >= 0, elapsed + 86400)

    new_elapsed = elapsed / original_duration * float(target_seconds)

    out["original_time_utc"] = out["time_utc"]
    out["time_utc"] = new_elapsed.apply(lambda x: seconds_to_time_utc(start_sec + float(x)))

    return out


def remap_pc_time_if_possible(df: pd.DataFrame, target_seconds: float = DEFAULT_TARGET_SECONDS) -> pd.DataFrame:
    """
    Optionally remap pc_time too, if it exists and can be parsed as datetime.
    This is useful when plotting or checking logs by pc_time.
    """
    if "pc_time" not in df.columns or len(df) < 2:
        return df

    out = df.copy()

    parsed = pd.to_datetime(out["pc_time"], errors="coerce")
    if parsed.isna().all():
        return out

    if parsed.iloc[0] is pd.NaT or parsed.iloc[-1] is pd.NaT:
        return out

    start = parsed.iloc[0]
    end = parsed.iloc[-1]
    original_duration = (end - start).total_seconds()

    if original_duration <= 0:
        return out

    elapsed = (parsed - start).dt.total_seconds()
    new_elapsed = elapsed / original_duration * float(target_seconds)

    out["original_pc_time"] = out["pc_time"]
    out["pc_time"] = (start + pd.to_timedelta(new_elapsed, unit="s")).dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]

    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remap a GNSS CSV time_utc axis so the whole file spans a target duration, default 20 seconds."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input CSV path, e.g. data/processed/realtime_gnss.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output CSV path, e.g. data/processed/e10_10_20s.csv",
    )
    parser.add_argument(
        "--target-seconds",
        type=float,
        default=DEFAULT_TARGET_SECONDS,
        help="New total measurement length in seconds. Default: 20",
    )
    parser.add_argument(
        "--pc-time",
        action="store_true",
        help="Also remap pc_time if the column exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.input)

    if df.empty:
        raise ValueError("Input CSV is empty.")

    out = remap_time_utc(df, target_seconds=args.target_seconds)

    if args.pc_time:
        out = remap_pc_time_if_possible(out, target_seconds=args.target_seconds)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"Input rows      : {len(df)}")
    print(f"Output rows     : {len(out)}")
    print(f"Target duration : {args.target_seconds:.2f} sec")
    print(f"Original time   : {df['time_utc'].iloc[0]} -> {df['time_utc'].iloc[-1]}")
    print(f"New time        : {out['time_utc'].iloc[0]} -> {out['time_utc'].iloc[-1]}")
    print(f"Saved to        : {args.output}")


if __name__ == "__main__":
    main()
