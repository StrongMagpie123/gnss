# EVK-F9P GNSS Return-Zone Decision Project

EVK-F9P GNSS data is collected in real time, saved as CSV, and used to compare a
single-point geofence baseline with a GNSS quality-aware decision algorithm.

Main idea:

```text
EVK-F9P
-> NMEA realtime reception
-> Python parsing
-> CSV storage
-> quality-aware return-zone decision
-> baseline vs proposed comparison
-> map/graph visualization
-> FNR/FPR/TPR evaluation
```

This is not a project that perfectly removes GNSS error. It is a decision
improvement project that uses `num_sat`, `HDOP`, and `avg C/N0` to handle
low-confidence positions more carefully.

## Folder Layout

```text
data/
  raw/
  processed/
    realtime_gnss.csv
    01_center.csv
    02_inside_boundary.csv
    03_outside_boundary.csv
    04_bad_signal.csv
outputs/
  maps/
  figures/
  results/
src/
  config.py
  realtime_nmea_logger.py
  nmea_parser.py
  parse_nmea_file.py
  geofence.py
  analyze_results.py
  visualize_map.py
  streamlit_live_dashboard.py
  live_map_updater.py
  plot_results.py
```

## CSV Format

Realtime GNSS CSV columns:

```csv
pc_time,time_utc,lat,lon,fix_quality,num_sat,hdop,altitude_m,avg_cn0
```

Evaluation CSV files also need:

```csv
true_label
```

Allowed `true_label` values are `inside` and `outside`.

## Return Zone

The return zone is configured in `src/config.py`.

```python
RETURN_CENTER_LAT = 36.6331115
RETURN_CENTER_LON = 127.4536338
RETURN_RADIUS_M = 3.0
BOUNDARY_MARGIN_M = 1.0
```

Recommended field workflow:

1. Put the antenna at the intended center point for 30-60 seconds.
2. Compute or inspect the average GNSS coordinate.
3. Use that average as the return-zone center.
4. Use a 3 m radius for the first experiment.

## Algorithms

Baseline:

```text
distance <= radius -> accept
distance > radius  -> reject
```

Proposed algorithm:

```text
distance <= radius - error_radius -> accept
radius - error_radius < distance <= radius + error_radius -> verify
distance > radius + error_radius -> reject
```

With the current 3 m return zone and 1 m boundary margin:

```text
distance <= 2 m  -> accept
2 m < distance <= 4 m -> verify
distance > 4 m   -> reject
```

The verification stage uses recent samples, quality filtering, jump removal,
and majority voting. Output decisions are ASCII-safe:

```text
accept, verify, reject
```

Key output columns:

```text
distance_m
basic_decision
error_radius_m
proposed_decision
verification_result
valid_points
approval_ratio
mean_lat
mean_lon
mean_distance_m
stability_m
proposed_final_decision
```

## Quick Start / Environment Setup

Use these commands when running the project on a new computer.

```powershell
# 1. Create a virtual environment
python -m venv venv

# 2. Activate the virtual environment
venv\Scripts\activate

# 3. Install required libraries
pip install -r requirements.txt
```

Check Python and pip versions if the environment does not work as expected:

```powershell
python --version
python -m pip --version
```

If `requirements.txt` has not been created yet, create it on the original development computer with:

```powershell
pip freeze > requirements.txt
```

Do not upload the `venv/` folder. Recreate it with the commands above on each computer.

## Run Commands

Collect realtime data from EVK-F9P:

```powershell
python src\realtime_nmea_logger.py
```

Run the main pipeline on `data/processed/realtime_gnss.csv`:

```powershell
python src\main.py
```

Analyze labeled experiment files:

```powershell
python src\analyze_results.py
```

Analyze the current realtime file directly when you know the true location:

```powershell
python src\analyze_results.py --input data\processed\realtime_gnss.csv --label inside
```

Use `--label outside` if that measurement was taken outside the return zone.

Create figures:

```powershell
python src\plot_results.py
```

Run Streamlit dashboard:

```powershell
streamlit run src\streamlit_live_dashboard.py
```

HTML maps use OpenStreetMap tiles at zoom level 19 or lower because higher zoom
levels can show blank tiles in some areas. `live_map.html` auto-refreshes for
realtime monitoring, so zoom can reset during updates. For detailed inspection,
use `return_zone_map.html` or pause the live updater.

If the local virtual environment fails because the project path contains Korean
characters, recreate the venv in a path without non-ASCII characters or use a
system Python where `python` and `streamlit` are available on PATH.

## Experiment Files

Use these files for final evaluation:

```text
01_center.csv            true_label=inside
02_inside_boundary.csv   true_label=inside
03_outside_boundary.csv  true_label=outside
04_bad_signal.csv        true_label=inside or outside, depending on the measured point
```

`01_center.csv` has been created from the existing realtime sample data as an
inside-labeled center measurement. The other files should be collected in the
field before final FNR/FPR/TPR evaluation.

## Outputs

```text
outputs/results/gnss_result.csv
outputs/results/metrics_summary.csv
outputs/results/threshold_sweep.csv
outputs/maps/return_zone_map.html
outputs/figures/
```

When `folium` or `matplotlib` is installed, the project creates Folium maps and
PNG figures. If they are unavailable, fallback HTML/SVG outputs are generated so
the pipeline can still run.

## Presentation Claim

The proposed algorithm reduces unfair return failures inside the return zone by
using GNSS quality indicators and repeated measurements, while the verification
stage limits excessive false acceptance outside the return zone.
