"""
Query the infini-gram (or infini-gram mini) API for every date in a year across
multiple format variations, and write results to a TSV file.

Indices used: v4_dclm-baseline_llama or v2_dclm_all (DCLM baseline corpus)
"""

import argparse
import asyncio
import csv
import datetime

import aiohttp

INDEX = "v2_dclm_all"
API_URL = "https://api.infini-gram-mini.io/"
OUTPUT_FILE = "date_counts.tsv"
CONCURRENCY = 50


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
}

# To reduce false positive matches with other numbers or forms, appending most common characters after the date
ENDING_CHARS = [" ", ",", ".", ":", ")", "\n"]


def date_variants(month: int, day: int) -> dict[str, list[str]]:
    """Return all ready-to-query strings for a given month/day, grouped into 4 columns.

    Keys: full_month_day, full_month_ordinal, abbr_month_day, abbr_month_ordinal.
    Each value is the fully expanded list of query strings — every combination of
    leading char (for day-first forms), base string, and trailing delimiter —
    ready to be passed directly to query_count.
    """
    dt = datetime.date(2000, month, day)
    full_month = dt.strftime("%B")
    abbr_month = dt.strftime("%b")
    day_num = str(day)
    day_ord = ordinal(day)
    day_pad = f"0{day}" if day < 10 else None

    def mf_df(mf: str, df_base: str) -> list[str]:
        queries = [mf, *[char + df_base for char in LEADING_CHARS.values()]]
        return [
            q + end
            for q in queries
            for end in ENDING_CHARS
            if not (end == "." and "." in q)
        ]

    # full_month_day: "January 1", "January 01", and day-first equivalents
    full_month_day = mf_df(f"{full_month} {day_num}", f"{day_num} {full_month}")
    if day_pad:
        full_month_day += mf_df(f"{full_month} {day_pad}", f"{day_pad} {full_month}")

    # full_month_ordinal: "January 1st" and day-first
    full_month_ordinal = mf_df(f"{full_month} {day_ord}", f"{day_ord} {full_month}")

    # abbr_month_day: plain and dotted abbreviations, zero-padded, and Sept/Sept. for September
    # May: strftime("%b") == strftime("%B") == "May", already counted in full_month_day
    abbr_month_day: list[str] = []
    if month != 5:
        abbr_month_day += mf_df(f"{abbr_month} {day_num}", f"{day_num} {abbr_month}")
        abbr_month_day += mf_df(f"{abbr_month}. {day_num}", f"{day_num} {abbr_month}.")
        if day_pad:
            abbr_month_day += mf_df(
                f"{abbr_month} {day_pad}", f"{day_pad} {abbr_month}"
            )
            abbr_month_day += mf_df(
                f"{abbr_month}. {day_pad}", f"{day_pad} {abbr_month}."
            )
    if month == 9:
        for abbr in ["Sept", "Sept."]:
            abbr_month_day += mf_df(f"{abbr} {day_num}", f"{day_num} {abbr}")
            if day_pad:
                abbr_month_day += mf_df(f"{abbr} {day_pad}", f"{day_pad} {abbr}")

    # abbr_month_ordinal: "Jan 1st", "Jan. 1st", "Sept 1st", "Sept. 1st" and day-first
    # May: already counted in full_month_ordinal
    abbr_month_ordinal: list[str] = []
    if month != 5:
        abbr_month_ordinal += mf_df(
            f"{abbr_month} {day_ord}", f"{day_ord} {abbr_month}"
        )
        abbr_month_ordinal += mf_df(
            f"{abbr_month}. {day_ord}", f"{day_ord} {abbr_month}."
        )
    if month == 9:
        abbr_month_ordinal += mf_df(f"Sept {day_ord}", f"{day_ord} Sept")
        abbr_month_ordinal += mf_df(f"Sept. {day_ord}", f"{day_ord} Sept.")

    return {
        "full_month_day": full_month_day,
        "full_month_ordinal": full_month_ordinal,
        "abbr_month_day": abbr_month_day,
        "abbr_month_ordinal": abbr_month_ordinal,
    }


async def query_count(
    session: aiohttp.ClientSession, sem: asyncio.Semaphore, query: str
) -> int:
    """Query infini-gram and return the count for the given string."""
    payload = {"index": INDEX, "query_type": "count", "query": query}
    async with sem:
        for attempt in range(8):
            try:
                async with session.post(
                    API_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in (403, 429, 500, 502, 503, 504):
                        await asyncio.sleep(2**attempt)
                        continue
                    resp.raise_for_status()
                    data = await resp.json()
                    if "count" in data:
                        return int(data["count"])
                    print(f"  Unexpected response for '{query}': {data}")
                    return -1
            except Exception as exc:
                if attempt == 7:
                    print(f"  Failed '{query}': {exc}")
                    return -1
                await asyncio.sleep(2**attempt)
    return -1


async def query_date(
    session: aiohttp.ClientSession, sem: asyncio.Semaphore, month: int, day: int
) -> dict[str, int]:
    variants = date_variants(month, day)
    col_tasks = {
        col_name: [asyncio.create_task(query_count(session, sem, q)) for q in queries]
        for col_name, queries in variants.items()
    }
    counts: dict[str, int] = {}
    for col_name, tasks in col_tasks.items():
        results = await asyncio.gather(*tasks)
        counts[col_name] = sum(r for r in results if r >= 0)
    return counts


def all_dates_in_year(year: int = 2000) -> list[tuple[int, int]]:
    """Return (month, day) tuples for every day in the given year."""
    dates = []
    d = datetime.date(year, 1, 1)
    while d.year == year:
        dates.append((d.month, d.day))
        d += datetime.timedelta(days=1)
    return dates


async def main_async() -> None:
    dates = all_dates_in_year()
    total = len(dates)
    all_variant_keys = list(date_variants(9, 1).keys())
    fieldnames = [
        "month",
        "day",
        "iso",
        "date_label",
        "count_total",
        *[f"count_{k}" for k in all_variant_keys],
    ]

    sem = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)
    async with aiohttp.ClientSession(connector=connector) as session:
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()

            for i, (month, day) in enumerate(dates, 1):
                dt = datetime.date(2000, month, day)
                date_label = dt.strftime("%B %-d")
                iso_label = f"{month:02d}-{day:02d}"

                print(f"[{i}/{total}] {date_label}")
                variant_counts: dict[str, int] = {k: 0 for k in all_variant_keys}
                counts = await query_date(session, sem, month, day)
                variant_counts.update(counts)
                for col_name, count in counts.items():
                    print(f"  '{col_name}': {count:,}")

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


def main() -> None:
    global INDEX, OUTPUT_FILE
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=str,
        default="v2_dclm_all",
        help="Corpus to query. Default is the DCLM corpus. You can also query v2_piletrain or CommonCrawl dumps. See https://infini-gram-mini.readthedocs.io/en/latest/api.html#overview",
    )
    args = parser.parse_args()

    INDEX = args.corpus
    OUTPUT_FILE = "date_counts" + "_" + args.corpus + ".tsv"
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
