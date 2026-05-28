from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from config import FIGURE_DIR, METRICS_CSV_PATH, RESULT_CSV_PATH, RESULT_DIR, RETURN_RADIUS_M

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    plt = None


def save_distance_plot(df: pd.DataFrame, output_path: Path) -> None:
    if plt is None:
        save_line_svg(
            df["distance_m"].tolist(),
            output_path.with_suffix(".svg"),
            title="Distance to Return Zone Center",
            ylabel="distance (m)",
            reference=RETURN_RADIUS_M,
        )
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    x = df["time_utc"] if "time_utc" in df.columns else df.index
    ax.plot(x, df["distance_m"], label="distance_m", linewidth=1.5)
    ax.axhline(RETURN_RADIUS_M, color="red", linestyle="--", label="return radius")
    ax.set_title("Distance to Return Zone Center")
    ax.set_xlabel("time_utc")
    ax.set_ylabel("distance (m)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def save_quality_plot(df: pd.DataFrame, output_path: Path) -> None:
    if plt is None:
        save_line_svg(
            df["hdop"].tolist(),
            output_path.with_name("hdop_over_time.svg"),
            title="HDOP Over Time",
            ylabel="HDOP",
        )
        save_line_svg(
            df["avg_cn0"].tolist(),
            output_path.with_name("cn0_over_time.svg"),
            title="avg C/N0 Over Time",
            ylabel="avg C/N0",
        )
        return

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    x = df["time_utc"] if "time_utc" in df.columns else df.index

    axes[0].plot(x, df["hdop"], color="tab:orange", label="HDOP")
    axes[0].set_ylabel("HDOP")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(x, df["avg_cn0"], color="tab:green", label="avg C/N0")
    axes[1].set_ylabel("avg C/N0")
    axes[1].set_xlabel("time_utc")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    fig.suptitle("GNSS Quality Indicators")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def save_metrics_plot(metrics: pd.DataFrame, output_path: Path) -> None:
    if plt is None:
        save_metrics_svg(metrics, output_path.with_suffix(".svg"))
        return

    plot_df = metrics.set_index("algorithm")[["FNR", "FPR", "TPR"]] * 100
    ax = plot_df.plot(kind="bar", figsize=(8, 4), rot=0)
    ax.set_title("Baseline vs Proposed")
    ax.set_ylabel("rate (%)")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best")
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def save_sweep_plot(sweep: pd.DataFrame, output_path: Path) -> None:
    if sweep.empty:
        return

    if plt is None:
        save_sweep_svg(sweep, output_path.with_suffix(".svg"))
        return

    labels = sweep.apply(
        lambda row: f"N={int(row['window_size'])}, A={int(row['approval_ratio_threshold'] * 100)}%",
        axis=1,
    )
    plot_df = sweep[["FNR", "FPR", "TPR"]] * 100
    ax = plot_df.plot(kind="line", marker="o", figsize=(11, 4))
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_title("Parameter Sweep")
    ax.set_ylabel("rate (%)")
    ax.grid(True, alpha=0.3)
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _scale(values: list[float], min_v: float, max_v: float, height: float, top: float) -> list[float]:
    span = max(max_v - min_v, 1e-9)
    return [top + height - ((value - min_v) / span * height) for value in values]


def _tick_values(min_v: float, max_v: float, count: int = 5) -> list[float]:
    if count <= 1:
        return [min_v]
    if abs(max_v - min_v) < 1e-9:
        pad = max(abs(max_v) * 0.1, 1.0)
        min_v -= pad
        max_v += pad
    step = (max_v - min_v) / (count - 1)
    return [min_v + i * step for i in range(count)]


def _format_tick(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _y_axis_ticks(
    min_v: float,
    max_v: float,
    left: float,
    top: float,
    plot_w: float,
    plot_h: float,
    count: int = 5,
) -> str:
    ticks = []
    for value in _tick_values(min_v, max_v, count=count):
        y = _scale([value], min_v, max_v, plot_h, top)[0]
        ticks.append(
            f'<line x1="{left - 5}" y1="{y:.1f}" x2="{left}" y2="{y:.1f}" stroke="#444"/>'
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#ddd"/>'
            f'<text x="{left - 9}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{_format_tick(value)}</text>'
        )
    return "".join(ticks)


def save_line_svg(
    values: list[float],
    output_path: Path,
    title: str,
    ylabel: str,
    reference: float | None = None,
) -> None:
    clean = [float(v) for v in values if pd.notna(v)]
    if not clean:
        clean = [0.0]

    width, height = 900, 360
    left, top, plot_w, plot_h = 70, 45, 790, 250
    min_v = min(clean + ([reference] if reference is not None else []))
    max_v = max(clean + ([reference] if reference is not None else []))
    if abs(max_v - min_v) < 1e-9:
        pad = max(abs(max_v) * 0.1, 1.0)
        min_v -= pad
        max_v += pad
    y_values = _scale(clean, min_v, max_v, plot_h, top)
    step = plot_w / max(len(clean) - 1, 1)
    points = " ".join(f"{left + i * step:.1f},{y:.1f}" for i, y in enumerate(y_values))
    y_ticks = _y_axis_ticks(min_v, max_v, left, top, plot_w, plot_h)

    ref_line = ""
    if reference is not None:
        ref_y = _scale([reference], min_v, max_v, plot_h, top)[0]
        ref_line = f'<line x1="{left}" y1="{ref_y:.1f}" x2="{left + plot_w}" y2="{ref_y:.1f}" stroke="#d33" stroke-dasharray="6 5"/>'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{width / 2}" y="25" text-anchor="middle" font-family="Arial" font-size="18">{title}</text>
  <text x="20" y="{top + plot_h / 2}" transform="rotate(-90 20 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="12">{ylabel}</text>
  {y_ticks}
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#444"/>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#444"/>
  {ref_line}
  <polyline fill="none" stroke="#2d6cdf" stroke-width="2" points="{points}"/>
  <text x="{left}" y="{top + plot_h + 35}" font-family="Arial" font-size="11">min={min_v:.2f}</text>
  <text x="{left + plot_w - 90}" y="{top + plot_h + 35}" font-family="Arial" font-size="11">max={max_v:.2f}</text>
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def save_metrics_svg(metrics: pd.DataFrame, output_path: Path) -> None:
    algorithms = metrics["algorithm"].astype(str).tolist()
    measures = ["FNR", "FPR", "TPR"]
    width, height = 820, 380
    left, top, plot_w, plot_h = 70, 45, 700, 260
    colors = {"FNR": "#d9534f", "FPR": "#f0ad4e", "TPR": "#2ca25f"}
    bar_w = 34
    group_w = plot_w / max(len(algorithms), 1)
    y_ticks = _y_axis_ticks(0.0, 100.0, left, top, plot_w, plot_h)

    bars = []
    labels = []
    for i, alg in enumerate(algorithms):
        group_x = left + i * group_w + group_w / 2 - (len(measures) * bar_w) / 2
        labels.append(f'<text x="{left + i * group_w + group_w / 2}" y="{top + plot_h + 25}" text-anchor="middle" font-family="Arial" font-size="12">{alg}</text>')
        row = metrics.iloc[i]
        for j, measure in enumerate(measures):
            value = float(row[measure]) * 100
            bar_h = value / 100 * plot_h
            x = group_x + j * bar_w
            y = top + plot_h - bar_h
            bars.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 4}" height="{bar_h:.1f}" fill="{colors[measure]}"/>'
                f'<text x="{x + (bar_w - 4) / 2:.1f}" y="{max(y - 4, top + 10):.1f}" text-anchor="middle" font-family="Arial" font-size="10">{value:.1f}</text>'
            )

    legend = " ".join(
        f'<rect x="{560 + i * 80}" y="18" width="12" height="12" fill="{colors[m]}"/><text x="{576 + i * 80}" y="29" font-family="Arial" font-size="12">{m}</text>'
        for i, m in enumerate(measures)
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{width / 2}" y="25" text-anchor="middle" font-family="Arial" font-size="18">Baseline vs Proposed</text>
  {legend}
  {y_ticks}
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#444"/>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#444"/>
  <text x="25" y="{top + plot_h / 2}" transform="rotate(-90 25 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="12">rate (%)</text>
  {''.join(bars)}
  {''.join(labels)}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def save_sweep_svg(sweep: pd.DataFrame, output_path: Path) -> None:
    labels = [
        f"N={int(row.window_size)} A={int(row.approval_ratio_threshold * 100)}"
        for row in sweep.itertuples()
    ]
    width, height = 980, 420
    left, top, plot_w, plot_h = 70, 50, 850, 260
    colors = {"FNR": "#d9534f", "FPR": "#f0ad4e", "TPR": "#2ca25f"}
    y_ticks = _y_axis_ticks(0.0, 100.0, left, top, plot_w, plot_h)
    series = {}
    for measure in ["FNR", "FPR", "TPR"]:
        values = (sweep[measure] * 100).astype(float).tolist()
        y_values = _scale(values, 0.0, 100.0, plot_h, top)
        step = plot_w / max(len(values) - 1, 1)
        points = " ".join(f"{left + i * step:.1f},{y:.1f}" for i, y in enumerate(y_values))
        series[measure] = f'<polyline fill="none" stroke="{colors[measure]}" stroke-width="2" points="{points}"/>'

    label_text = []
    step = plot_w / max(len(labels) - 1, 1)
    for i, label in enumerate(labels):
        x = left + i * step
        label_text.append(
            f'<text x="{x:.1f}" y="{top + plot_h + 25}" transform="rotate(35 {x:.1f} {top + plot_h + 25})" font-family="Arial" font-size="10">{label}</text>'
        )

    legend = " ".join(
        f'<rect x="{710 + i * 70}" y="18" width="12" height="12" fill="{colors[m]}"/><text x="{726 + i * 70}" y="29" font-family="Arial" font-size="12">{m}</text>'
        for i, m in enumerate(["FNR", "FPR", "TPR"])
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{width / 2}" y="25" text-anchor="middle" font-family="Arial" font-size="18">Parameter Sweep</text>
  {legend}
  {y_ticks}
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#444"/>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#444"/>
  <text x="25" y="{top + plot_h / 2}" transform="rotate(-90 25 {top + plot_h / 2})" text-anchor="middle" font-family="Arial" font-size="12">rate (%)</text>
  {''.join(series.values())}
  {''.join(label_text)}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create presentation figures from GNSS results.")
    parser.add_argument("--result", type=Path, default=RESULT_CSV_PATH)
    parser.add_argument("--metrics", type=Path, default=METRICS_CSV_PATH)
    parser.add_argument("--sweep", type=Path, default=RESULT_DIR / "threshold_sweep.csv")
    parser.add_argument("--output-dir", type=Path, default=FIGURE_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.result)
    metrics = pd.read_csv(args.metrics)
    sweep = pd.read_csv(args.sweep) if args.sweep.exists() else pd.DataFrame()

    save_distance_plot(df, args.output_dir / "distance_over_time.png")
    save_quality_plot(df, args.output_dir / "quality_over_time.png")
    save_metrics_plot(metrics, args.output_dir / "metrics_comparison.png")
    save_sweep_plot(sweep, args.output_dir / "threshold_sweep.png")

    print(f"Figures saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
