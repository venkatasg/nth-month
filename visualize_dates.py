#!/usr/bin/env python3
"""
Generate an infographic showing the relative prominence of every date in the
year based on infini-gram/DCLM counts.

Expects date_counts.tsv produced by query_dates.py.

Output: date_prominence.png
"""

import csv
import datetime
import math
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter

matplotlib.rcParams["font.family"] = "DejaVu Sans"

TSV_FILE = "date_counts.tsv"
OUTPUT_FILE = "date_prominence.png"

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Notable dates to annotate
NOTABLE = {
    (1, 1):   "New Year's",
    (2, 14):  "Valentine's",
    (2, 29):  "Leap Day",
    (3, 17):  "St. Patrick's",
    (4, 1):   "April Fools'",
    (7, 4):   "July 4th",
    (9, 11):  "9/11",
    (10, 31): "Halloween",
    (11, 11): "Veterans Day",
    (12, 25): "Christmas",
    (12, 31): "New Year's Eve",
}


def load_data(path: str) -> dict[tuple[int, int], int]:
    counts: dict[tuple[int, int], int] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            month = int(row["month"])
            day = int(row["day"])
            counts[(month, day)] = int(row["total_count"])
    return counts


def build_grid(counts: dict[tuple[int, int], int]) -> np.ndarray:
    """Build a 12×31 grid of counts (nan where month has fewer days)."""
    grid = np.full((12, 31), np.nan)
    for month in range(1, 13):
        max_day = MONTH_DAYS[month - 1]
        if month == 2:
            max_day = 29  # include leap day if present
        for day in range(1, max_day + 1):
            val = counts.get((month, day), np.nan)
            if not np.isnan(val):
                grid[month - 1, day - 1] = val
    return grid


def millions(x, _):
    if x >= 1_000_000:
        return f"{x/1_000_000:.1f}M"
    if x >= 1_000:
        return f"{x/1_000:.0f}K"
    return str(int(x))


def main():
    counts = load_data(TSV_FILE)
    grid = build_grid(counts)

    # ── Layout ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(20, 14), facecolor="#0d1117")
    fig.patch.set_facecolor("#0d1117")

    gs = fig.add_gridspec(
        2, 1,
        height_ratios=[3, 1],
        hspace=0.12,
        left=0.07, right=0.97,
        top=0.88, bottom=0.06,
    )

    ax_heat = fig.add_subplot(gs[0])
    ax_bar  = fig.add_subplot(gs[1])

    # ── Colour map ────────────────────────────────────────────────────────────
    # Log-scale normalisation so both low and high ends are visible
    vmin = np.nanmin(grid[grid > 0])
    vmax = np.nanmax(grid)
    norm = mcolors.LogNorm(vmin=max(vmin, 1), vmax=vmax)
    cmap = matplotlib.colormaps["YlOrRd"]

    # ── Heatmap ───────────────────────────────────────────────────────────────
    ax_heat.set_facecolor("#161b22")

    cell_w, cell_h = 0.9, 0.85  # fraction of 1-unit cell
    dx = (1 - cell_w) / 2
    dy = (1 - cell_h) / 2

    for mi in range(12):
        for di in range(31):
            val = grid[mi, di]
            if np.isnan(val):
                continue
            color = cmap(norm(max(val, 1)))
            rect = FancyBboxPatch(
                (di + dx, mi + dy), cell_w, cell_h,
                boxstyle="round,pad=0.04",
                linewidth=0,
                facecolor=color,
                zorder=2,
            )
            ax_heat.add_patch(rect)

            # Annotate notable dates
            key = (mi + 1, di + 1)
            if key in NOTABLE:
                ax_heat.text(
                    di + 0.5, mi + 0.5,
                    NOTABLE[key],
                    ha="center", va="center",
                    fontsize=5.5, fontweight="bold",
                    color="white", zorder=3,
                    clip_on=True,
                )

    # Axes decoration
    ax_heat.set_xlim(0, 31)
    ax_heat.set_ylim(0, 12)
    ax_heat.invert_yaxis()
    ax_heat.set_xticks(np.arange(31) + 0.5)
    ax_heat.set_xticklabels([str(d) for d in range(1, 32)], fontsize=7, color="#8b949e")
    ax_heat.set_yticks(np.arange(12) + 0.5)
    ax_heat.set_yticklabels(MONTH_NAMES, fontsize=9, color="#c9d1d9", fontweight="bold")
    ax_heat.tick_params(length=0)
    for spine in ax_heat.spines.values():
        spine.set_visible(False)

    # ── Colour bar ────────────────────────────────────────────────────────────
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar_ax = fig.add_axes([0.97, 0.35, 0.012, 0.45])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    cbar.ax.yaxis.set_tick_params(color="#8b949e", labelsize=7)
    cbar.ax.yaxis.set_major_formatter(FuncFormatter(millions))
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#8b949e")
    cbar.outline.set_visible(False)
    cbar_ax.set_facecolor("#161b22")
    cbar_ax.set_title("Occurrences\n(log scale)", fontsize=7, color="#8b949e", pad=6)

    # ── Bar chart — total by month ────────────────────────────────────────────
    ax_bar.set_facecolor("#161b22")

    month_totals = [
        np.nansum(grid[mi, :])  # nansum ignores NaN padding for short months
        for mi in range(12)
    ]
    bar_colors = [
        cmap(norm(max(t, 1))) for t in month_totals
    ]
    bars = ax_bar.bar(
        np.arange(12),
        month_totals,
        color=bar_colors,
        width=0.75,
        zorder=2,
    )

    # Label bars
    for bar, total in zip(bars, month_totals):
        ax_bar.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() * 1.03,
            millions(total, None),
            ha="center", va="bottom",
            fontsize=7.5, color="#c9d1d9",
        )

    ax_bar.set_xticks(np.arange(12))
    ax_bar.set_xticklabels(MONTH_NAMES, fontsize=8, color="#c9d1d9")
    ax_bar.yaxis.set_major_formatter(FuncFormatter(millions))
    ax_bar.tick_params(axis="y", labelsize=7, colors="#8b949e", length=0)
    ax_bar.tick_params(axis="x", length=0)
    ax_bar.set_ylabel("Total occurrences", fontsize=8, color="#8b949e", labelpad=6)
    ax_bar.set_facecolor("#161b22")
    for spine in ax_bar.spines.values():
        spine.set_color("#30363d")
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    ax_bar.set_xlim(-0.6, 11.6)
    ax_bar.set_ylim(0, max(month_totals) * 1.18)
    ax_bar.grid(axis="y", color="#21262d", linewidth=0.6, zorder=1)

    # ── Titles & captions ─────────────────────────────────────────────────────
    fig.text(
        0.5, 0.95,
        "How Often Each Date Appears in Text",
        ha="center", va="top",
        fontsize=20, fontweight="bold", color="#e6edf3",
    )
    fig.text(
        0.5, 0.915,
        "Count of every date format variant (e.g. "January 1", "Jan 1st", …) "
        "in the DCLM baseline corpus via infini-gram",
        ha="center", va="top",
        fontsize=10, color="#8b949e",
    )
    fig.text(
        0.5, 0.885,
        "Colour intensity and bar height reflect total occurrences across all variants  •  "
        "Inspired by XKCD #1070",
        ha="center", va="top",
        fontsize=8, color="#6e7681", style="italic",
    )

    # ── Top-10 callout ────────────────────────────────────────────────────────
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top10_lines = []
    for (m, d), c in ranked[:10]:
        dt = datetime.date(2000 if (m == 2 and d == 29) else 2001, m, d)
        top10_lines.append(f"{dt.strftime('%b %-d'):8s}  {millions(c, None)}")

    callout_text = "Top 10 dates:\n" + "\n".join(top10_lines)
    fig.text(
        0.025, 0.88,
        callout_text,
        ha="left", va="top",
        fontsize=7.5, color="#c9d1d9",
        family="monospace",
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor="#161b22",
            edgecolor="#30363d",
            linewidth=0.8,
        ),
    )

    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved infographic to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
