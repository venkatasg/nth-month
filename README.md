# nth-month

Which dates are most "meaningful" to an LLM? This project measures how often every calendar date is referenced by name in a large web-text corpus, then visualizes the results as a calendar where each date's font size reflects its prominence.

Inspired by [xkcd #1140](https://xkcd.com/1140/) and [The Missing 11th of the Month](https://drhagen.com/blog/the-missing-11th-of-the-month/).

## How it works

1. **`query_dates.py`** — For every day of the year, queries a search API against the DCLM corpus. Each date is queried in four groups of surface-form variants:
   - **full_month_day**: "January 1", "January 01", and day-first equivalents
   - **full_month_ordinal**: "January 1st" and day-first equivalents
   - **abbr_month_day**: "Jan 1", "Jan. 1", "Jan 01", and day-first equivalents; plus "Sept"/"Sept." for September
   - **abbr_month_ordinal**: "Jan 1st", "Jan. 1st", and day-first equivalents

   Each variant is queried with several trailing delimiter characters (space, comma, period, etc.) to ensure only exact dates are counted — e.g. "January 1," won't match "January 10". Day-first variants (e.g. " 1 January") are prefixed with a space, newline, `(`, or `"` to prevent "1 January" from matching the tail of "21 January". Results are written to a TSV file.

   All queries for a given date are fired concurrently via `asyncio`/`aiohttp` (up to 50 in-flight at once), with exponential-backoff retry on 4xx/5xx responses.

2. **`visualize_dates.py`** — Reads a counts TSV and produces a 4×3 calendar grid where each day number is sized by its rank among all 366 dates. The top 3 dates are rendered extra-large.

### Two backends

Both are accessible from the same script via the `--mini` flag:

| Flag | API | Index | Matching |
|---|---|---|---|
| _(default)_ | [infini-gram](https://api.infini-gram.io/) | `v4_dclm-baseline_llama` | Token-level (suffix array) |
| `--mini` | [infini-gram-mini](https://api.infini-gram-mini.io/) | `v2_dclm_all` | Character-level (FM-Index) |

infini-gram uses a token-level suffix array, so tokenizer artifacts (e.g. the token for "20" being a prefix of "2015") require the delimiter approach. infini-gram-mini uses character-level FM-Index matching, which doesn't have tokenizer artifacts, but the same delimiter logic is applied for consistency and correctness.

## Output

- `date_counts.tsv` — counts from infini-gram; one row per date, with columns: `month`, `day`, `iso`, `date_label`, `count_total`, and per-variant counts.
- `date_counts_mini.tsv` — same schema, counts from infini-gram-mini.
- `calendar_meaningful_dates.png` — the final calendar infographic.
- `calendar_meaningful_dates_mini.png` — infographic from infini-gram-mini counts.

## Setup

Requires Python 3.14+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

## Usage

Query all dates using infini-gram (token-level):

```bash
uv run python query_dates.py
```

Query all dates using infini-gram-mini (character-level):

```bash
uv run python query_dates.py --mini
```

Generate the calendar visualization:

```bash
uv run python visualize_dates.py        # uses date_counts.tsv
uv run python visualize_dates.py --mini # uses date_counts_mini.tsv
```

The visualization uses the `xkcd Script` font — install it on your system if the labels render in a fallback font.

## Notes

- **May**: The abbreviated and full month names are identical ("May"), so abbreviated variants are skipped for May dates — they are already captured by the full-month variants.
- Both query scripts overwrite their output TSV on each run; rename or copy the file to preserve previous results.
