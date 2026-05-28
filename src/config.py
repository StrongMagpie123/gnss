from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
MAP_DIR = OUTPUT_DIR / "maps"
FIGURE_DIR = OUTPUT_DIR / "figures"
RESULT_DIR = OUTPUT_DIR / "results"

# Return zone. Use the static measurement mean as the center point.
RETURN_CENTER_LAT = 36.6248154
RETURN_CENTER_LON = 127.4574800
RETURN_RADIUS_M = 3.0
BOUNDARY_MARGIN_M = 1.0

# Main input/output files.
RAW_DATA_PATH = PROCESSED_DIR / "realtime_gnss.csv"
RESULT_CSV_PATH = RESULT_DIR / "gnss_result.csv"
METRICS_CSV_PATH = RESULT_DIR / "metrics_summary.csv"
MAP_OUTPUT_PATH = MAP_DIR / "return_zone_map.html"

# Proposed algorithm parameters.
VERIFY_WINDOW_SIZE = 10
MIN_VALID_POINTS = 3
QUALITY_MIN_FIX = 1
QUALITY_MIN_SAT = 8
QUALITY_MAX_HDOP = 3.0
QUALITY_MIN_CN0 = 20.0
JUMP_THRESHOLD_M = 5.0
APPROVAL_RATIO_THRESHOLD = 0.70

# Real-time defaults.
SERIAL_PORT = "COM5"
SERIAL_BAUDRATE = 38400
