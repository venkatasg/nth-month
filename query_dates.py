#!/usr/bin/env python3
"""
Query the infini-gram API for every date in a year across multiple format
variations, and write results to a TSV file.

Index used: v4_dclm-baseline_llama (DCLM baseline corpus)
"""

import csv
import time
import datetime
import requests
from collections import defaultdict

API_URL = "https://api.infini-gram.io/"
INDEX = "v4_dclm-baseline_llama"
OUTPUT_FILE = "date_counts.tsv"

# Ordinal suffixes for day numbers
def ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return {1: f"{n}st", 2: f"{n}nd", 3: f"{n}rd"}.get(n % 10, f"{n}th")


def date_variants(month: int, day: int) -> list[str]:
    """Return all query string variants for a given month/day."""
    dt = datetime.date(2001, month, day)  # non-leap year base
    full_month = dt.strftime("%B")        # January
    abbr_month = dt.strftime("%b")        # Jan
    day_num = day                         # 1
    day_ord = ordinal(day)                # 1st

    variants = [
        f"{full_month} {day_num}",        # January 1
        f"{full_month} {day_ord}",        # January 1st
        f"{abbr_month} {day_num}",        # Jan 1
        f"{abbr_month}. {day_num}",       # Jan. 1
        f"{abbr_month} {day_ord}",        # Jan 1st
    ]
    return variants


def query_count(query: str, retries: int = 4) -> int:
    """Query infini-gram and return the count for the given string."""
    payload = {
        "index": INDEX,
        "query_type": "count",
        "query": query,
    }
    delay = 2
    for attempt in range(retries + 1):
        try:
            resp = requests.post(API_URL, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "count" in data:
                return int(data["count"])
            else:
                print(f"  Unexpected response for '{query}': {data}")
                return 0
        except Exception as exc:
            if attempt < retries:
                print(f"  Retrying '{query}' after error: {exc} (wait {delay}s)")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"  Failed to query '{query}': {exc}")
                return 0


def all_dates_in_year(year: int = 2001) -> list[tuple[int, int]]:
    """Return (month, day) tuples for every day in the given year."""
    dates = []
    d = datetime.date(year, 1, 1)
    while d.year == year:
        dates.append((d.month, d.day))
        d += datetime.timedelta(days=1)
    return dates


def main():
    year = 2001  # non-leap year; leap day handled separately
    dates = all_dates_in_year(year)
    # Also include Feb 29 for leap-year dates
    dates_with_leap = dates + [(2, 29)]

    results = []  # list of dicts

    total = len(dates_with_leap)
    for i, (month, day) in enumerate(dates_with_leap, 1):
        dt = datetime.date(2000 if (month == 2 and day == 29) else 2001, month, day)
        date_label = dt.strftime("%B %-d")  # "January 1"
        iso_label = f"{month:02d}-{day:02d}"

        variants = date_variants(month, day)
        variant_counts: dict[str, int] = {}

        print(f"[{i}/{total}] {date_label}")
        for variant in variants:
            count = query_count(variant)
            variant_counts[variant] = count
            print(f"  '{variant}': {count:,}")
            time.sleep(0.1)  # gentle rate limiting

        total_count = sum(variant_counts.values())
        results.append({
            "month": month,
            "day": day,
            "date_label": date_label,
            "iso": iso_label,
            "total_count": total_count,
            **{f"count_{v}": c for v, c in variant_counts.items()},
        })

    # Write TSV — one row per date, columns: iso, date_label, total_count, plus per-variant
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        # Determine all variant column names from first result
        variant_cols = [k for k in results[0] if k.startswith("count_")]
        fieldnames = ["month", "day", "iso", "date_label", "total_count"] + variant_cols
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"\nDone! Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
