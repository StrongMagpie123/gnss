from __future__ import annotations

import csv
import statistics
import time
from typing import Optional

import serial

from config import PROCESSED_DIR, RAW_DATA_PATH, SERIAL_BAUDRATE, SERIAL_PORT
from nmea_parser import parse_gga, parse_gsv_cn0, remove_checksum


FIELDNAMES = [
    "pc_time",
    "time_utc",
    "lat",
    "lon",
    "fix_quality",
    "num_sat",
    "hdop",
    "altitude_m",
    "avg_cn0",
]


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Opening serial port: {SERIAL_PORT} @ {SERIAL_BAUDRATE}")
    print("Close u-center or any other app that is using the same COM port.")

    ser = serial.Serial(port=SERIAL_PORT, baudrate=SERIAL_BAUDRATE, timeout=1)

    current_gga: Optional[dict] = None
    current_cn0: list[int] = []
    file_exists = RAW_DATA_PATH.exists()

    with RAW_DATA_PATH.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)

        if not file_exists:
            writer.writeheader()

        def write_epoch() -> None:
            nonlocal current_gga, current_cn0

            if current_gga is None:
                return

            avg_cn0 = round(statistics.mean(current_cn0), 2) if current_cn0 else None
            row = {
                "pc_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "time_utc": current_gga["time_utc"],
                "lat": current_gga["lat"],
                "lon": current_gga["lon"],
                "fix_quality": current_gga["fix_quality"],
                "num_sat": current_gga["num_sat"],
                "hdop": current_gga["hdop"],
                "altitude_m": current_gga["altitude_m"],
                "avg_cn0": avg_cn0,
            }
            writer.writerow(row)
            f.flush()
            print(row)

        try:
            while True:
                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("ascii", errors="ignore").strip()
                if not line.startswith("$"):
                    continue

                body = remove_checksum(line)
                msg_type = body.split(",", 1)[0]

                if msg_type.endswith("GGA"):
                    write_epoch()
                    current_gga = parse_gga(line)
                    current_cn0 = []
                elif msg_type.endswith("GSV"):
                    current_cn0.extend(parse_gsv_cn0(line))

        except KeyboardInterrupt:
            print("\nStopping logger.")
            write_epoch()
        finally:
            ser.close()


if __name__ == "__main__":
    main()
