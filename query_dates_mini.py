"""
Query the infini-gram-mini API for every date in a year across multiple format
variations, and write results to a TSV file.

Index used: v2_dclm_all (DCLM corpus)
"""

import csv
import datetime
import time

import requests
from requests.adapters import HTTPAdapter, Retry

API_URL = "https://api.infini-gram-mini.io/"
INDEX = "v2_dclm_all"
OUTPUT_FILE = "date_counts_mini.tsv"


# Ordinal suffixes for day numbers
def ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return {1: f"{n}st", 2: f"{n}nd", 3: f"{n}rd"}.get(n % 10, f"{n}th")


# Characters that can legally precede a day-first date without creating false
# matches (e.g. "21 January" must not match a query for "1 January").
LEADING_CHARS = {
    "space": " ",
    "newline": "\n",
    "paren": "(",
    "dquote": '"',
    "squote": "'",
}

# To reduce false positive matches with other numbers or forms, appending most common characters after the date
ENDING_CHARS = [" ", ",", ".", "!", "?", ";", ":", ")", "\n"]


def date_variants(month: int, day: int) -> dict[str, list[str]]:
    """Return all query strings for a given month/day, grouped by column name.

    Each key is a TSV column name suffix (prepend 'count_'). Each value is the
    list of query strings whose counts are summed into that column: the
    month-first form followed by one day-first form per LEADING_CHARS entry.
    Trailing delimiters are added by the caller.
    """
    dt = datetime.date(2000, month, day)
    full_month = dt.strftime("%B")
    abbr_month = dt.strftime("%b")
    day_num = str(day)
    day_ord = ordinal(day)
    day_pad = f"0{day}" if day < 10 else None

    variants: dict[str, list[str]] = {}

    def add(name: str, mf: str, df_base: str) -> None:
        variants[name] = [mf, *[char + df_base for char in LEADING_CHARS.values()]]

    add("full_month_day", f"{full_month} {day_num}", f"{day_num} {full_month}")
    add("full_month_ordinal", f"{full_month} {day_ord}", f"{day_ord} {full_month}")
    add("abbr_month_dot_day", f"{abbr_month}. {day_num}", f"{day_num} {abbr_month}.")
    # May: strftime("%b") == strftime("%B") == "May"; skip abbr to avoid double-counting
    if month != 5:
        add("abbr_month_day", f"{abbr_month} {day_num}", f"{day_num} {abbr_month}")
        add("abbr_month_ordinal", f"{abbr_month} {day_ord}", f"{day_ord} {abbr_month}")

    if day_pad:
        add("full_month_day_pad", f"{full_month} {day_pad}", f"{day_pad} {full_month}")
        add(
            "abbr_month_dot_day_pad",
            f"{abbr_month}. {day_pad}",
            f"{day_pad} {abbr_month}.",
        )
        if month != 5:
            add(
                "abbr_month_day_pad",
                f"{abbr_month} {day_pad}",
                f"{day_pad} {abbr_month}",
            )

    if month == 9:
        add("abbr_month_day_sept", f"Sept {day_num}", f"{day_num} Sept")
        add("abbr_month_dot_day_sept", f"Sept. {day_num}", f"{day_num} Sept.")
        add("abbr_month_ordinal_sept", f"Sept {day_ord}", f"{day_ord} Sept")
        if day_pad:
            add("abbr_month_day_sept_pad", f"Sept {day_pad}", f"{day_pad} Sept")
            add("abbr_month_dot_day_sept_pad", f"Sept. {day_pad}", f"{day_pad} Sept.")

    # Purely numeric YYYY-MM-DD and YYYY/MM/DD forms. Querying "-MM-DD" / "/MM/DD"
    # naturally anchors to the year-prefixed form — the separator itself is the
    # left boundary, so no additional leading chars are needed.
    month_str = f"{month:02d}"
    day_str = f"{day:02d}"
    variants["numeric"] = [f"-{month_str}-{day_str}", f"/{month_str}/{day_str}"]

    return variants


def query_count(session: requests.Session, query: str) -> int:
    """Query infini-gram-mini and return the count for the given string."""
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

    # September 1 has the largest variant set; use it to fix the TSV schema
    all_variant_keys = list(date_variants(9, 1).keys())
    fieldnames = [
        "month",
        "day",
        "iso",
        "date_label",
        "count_total",
        *[f"count_{k}" for k in all_variant_keys],
    ]

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for i, (month, day) in enumerate(dates_with_leap, 1):
            dt = datetime.date(2000, month, day)
            date_label = dt.strftime("%B %-d")  # "January 1"
            iso_label = f"{month:02d}-{day:02d}"

            variants = date_variants(month, day)
            variant_counts: dict[str, int] = {k: 0 for k in all_variant_keys}
            print(f"[{i}/{total}] {date_label}")
            for col_name, query_strings in variants.items():
                for query_str in query_strings:
                    for ending_char in ENDING_CHARS:
                        variant_counts[col_name] += query_count(
                            session, query_str + ending_char
                        )
                        time.sleep(0.1)
                print(f"  '{col_name}': {variant_counts[col_name]:,}")
                time.sleep(0.5)  # gentle rate limiting

            result = {
                "month": month,
                "day": day,
                "date_label": date_label,
                "iso": iso_label,
                "count_total": sum(variant_counts.values()),
                **{f"count_{k}": variant_counts[k] for k in all_variant_keys},
            }
            writer.writerow(result)

    print(f"\nDone! Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
