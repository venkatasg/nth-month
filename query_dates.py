"""
Query the infini-gram API for every date in a year across multiple format
variations, and write results to a TSV file.

Index used: v4_dclm-baseline_llama (DCLM baseline corpus)
"""

import csv
import datetime
import time

import requests
from requests.adapters import HTTPAdapter, Retry

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
    dt = datetime.date(2000, month, day)  # non-leap year base
    full_month = dt.strftime("%B")  # January
    abbr_month = dt.strftime("%b")  # Jan
    day_num = day  # 1
    day_ord = ordinal(day)  # 1st

    variants = {
        "full_month_day": f"{full_month} {day_num}",  # January 1
        "full_month_ordinal": f"{full_month} {day_ord}",  # January 1st
        "abbr_month_day": f"{abbr_month} {day_num}",  # Jan 1
        "abbr_month_dot_day": f"{abbr_month}. {day_num}",  # Jan. 1
        "abbr_month_ordinal": f"{abbr_month} {day_ord}",  # Jan 1st
    }
    ## IMPORTANT: MAY has duplicate values. abbr_month_day and full_month_day
    ## are the same for May
    return variants


def query_count(session: requests.Session, query: str) -> int:
    """Query infini-gram and return the count for the given string."""
    payload = {
        "index": INDEX,
        "query_type": "count",
        "query": query,
    }

    try:
        resp = session.post(API_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "count" in data:
            return int(data["count"])
        else:
            print(f"  Unexpected response for '{query}': {data}")
            return -1
    except Exception as exc:
        print(f"  Failed to query '{query}': {exc}")
        return -1


def all_dates_in_year(year: int = 2000) -> list[tuple[int, int]]:
    """Return (month, day) tuples for every day in the given year."""
    dates = []
    d = datetime.date(year, 1, 1)
    while d.year == year:
        dates.append((d.month, d.day))
        d += datetime.timedelta(days=1)
    return dates


def main():
    dates_with_leap = all_dates_in_year()

    total = len(dates_with_leap)

    retries = Retry(
        total=8,  # Retry up to 5 times
        backoff_factor=1,
        status_forcelist=[403, 429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retries))

    # Write TSV — one row per date, columns: iso, date_label, total_count, plus per-variant

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        # Determine all variant column names from first result
        fieldnames = [
            "month",
            "day",
            "iso",
            "date_label",
            "count_total",
            "count_full_month_day",
            "count_full_month_ordinal",
            "count_abbr_month_day",
            "count_abbr_month_dot_day",
            "count_abbr_month_ordinal",
        ]
        # Initialize the file
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for i, (month, day) in enumerate(dates_with_leap, 1):
            dt = datetime.date(2000, month, day)
            date_label = dt.strftime("%B %-d")  # "January 1"
            iso_label = f"{month:02d}-{day:02d}"

            variants = date_variants(month, day)
            variant_counts: dict[str, int] = {}
            print(f"[{i}/{total}] {date_label}")
            for variant_name, variant in set(variants.items()):
                variant_counts["count_" + variant_name] = 0

                # We need two versions of the variant_name. One where the number is first and one where the month is first. I add a space before the number first variant because the token counts are exaggerated by double counting 21 June for 1 June etc
                month_first_variant_name = " " + " ".join(variant.split()[::-1])
                var_types = [variant, month_first_variant_name]
                if day < 10 and "ordinal" not in variant_name:
                    padded = variant[: -len(str(day))] + f"0{day}"
                    padded_day_first = " 0" + month_first_variant_name[1:]
                    var_types += [padded, padded_day_first]
                for var_type in var_types:
                    # Vecause of tokenizer, counting 'Jan 20' might also count Jan 2015 etc. This ensures that we're only looking for the exact date by counting 'Jan 20 ', 'Jan 20,'...
                    for ending_char in [" ", ",", ".", "!", "?", ";", ":", ")", "\n"]:
                        count = query_count(session, var_type + ending_char)
                        variant_counts["count_" + variant_name] += count
                        time.sleep(0.1)
                print(f"  '{variant}': {variant_counts['count_' + variant_name]:,}")
                time.sleep(0.5)  # gentle rate limiting

            total_count = sum(set(variant_counts.values()))
            result = {
                "month": month,
                "day": day,
                "date_label": date_label,
                "iso": iso_label,
                "count_total": total_count,
                **variant_counts,
            }

            writer.writerow(result)

    print(f"\nDone! Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
