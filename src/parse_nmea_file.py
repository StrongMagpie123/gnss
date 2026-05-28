from __future__ import annotations

import pandas as pd

from config import PROCESSED_DIR, RAW_DIR
from nmea_parser import epochs_to_dicts, parse_nmea_lines


INPUT_PATH = RAW_DIR / "nmea_log.txt"
OUTPUT_PATH = PROCESSED_DIR / "gnss_from_nmea.csv"


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    lines = INPUT_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    epochs = parse_nmea_lines(lines)
    df = pd.DataFrame(epochs_to_dicts(epochs))

    if df.empty:
        print("No epochs parsed. Check that the file contains GGA and GSV sentences.")
        return

    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"Parsed epochs: {len(df)}")
    print(f"Output CSV: {OUTPUT_PATH}")
    print(df.head())


if __name__ == "__main__":
    main()
