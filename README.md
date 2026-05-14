# Meaningful dates on the web and for a language model

Inspired by [xkcd #1140](https://xkcd.com/1140/) and [The Missing 11th of the Month](https://drhagen.com/blog/the-missing-11th-of-the-month/), I wanted to  measure how often every calendar date is referenced by name in a large web-text corpus (and a language modeling corpus), then visualize the results as a calendar similar to the comic. Here are the results:

## How it works

1. **`query_dates.py`** — For every day of the year, queries the [Infini-gram-mini API]() against the [DCLM]()/[Pile-train]() corpus. Each date is queried in four groups of surface-form variants:
   - **full_month_day**: "January 1", "January 01", and day-first equivalents
   - **full_month_ordinal**: "January 1st" and day-first equivalents
   - **abbr_month_day**: "Jan 1", "Jan. 1", "Jan 01", and day-first equivalents; plus "Sept"/"Sept." for September
   - **abbr_month_ordinal**: "Jan 1st", "Jan. 1st", and day-first equivalents

   Each variant is queried with several trailing delimiter characters (space, comma, period, etc.) to ensure only exact dates are counted — e.g. "January 1," won't match "January 10". Day-first variants (e.g. " 1 January") are prefixed with a space, newline, `(`, or `"` to prevent "1 January" from matching the tail of "21 January". Results are written to a TSV file.

   All queries for a given date are fired concurrently via `asyncio`/`aiohttp` (up to 50 in-flight at once), with exponential-backoff retry on 4xx/5xx responses.

2. **`visualize_dates.py`** — Reads a counts TSV and produces a 4×3 calendar grid where each day number is sized by its rank among all 366 dates. The top 3 dates are rendered extra-large.

## Output

- `date_counts_{corpus}.tsv` — counts from infini-gram-mini; one row per date, with columns: `month`, `day`, `iso`, `date_label`, `count_total`, and per-variant counts.
- `calendar_{corpus}.png` — the final calendar infographic.

## Setup

Requires Python 3.14+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

## Usage

Query all dates using infini-gram-mini:

```bash
uv run python query_dates.py
```

Generate the calendar visualizations:

```bash
uv run python visualize_dates.py
```

The visualization uses the `xkcd Script` font — install it on your system if the labels render in a fallback font.

## Notes

- **May**: The abbreviated and full month names are identical ("May"), so abbreviated variants are skipped for May dates — they are already captured by the full-month variants.
- Both query scripts overwrite their output TSV on each run; rename or copy the file to preserve previous results.
