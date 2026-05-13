"""
Generate an infographic (in xkcd style) showing the relative prominence of
every date in the year based on DCLM and Pile-train counts.

Expects counts file produced by query_dates.py.
"""

import calendar
import csv

import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams["font.family"] = "xkcd Script"


def load_data(path: str) -> dict[tuple[int, int], int]:
    counts: dict[tuple[int, int], int] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            month = int(row["month"])
            day = int(row["day"])
            counts[(month, day)] = int(row["count_total"])
    return counts


def main():
    for OUT_FILENAME, IN_FILENAME, TITLE, corpus_name in zip(
        ["calendar_dclm.png", "calendar_pile.png"],
        ["date_counts_dclm.tsv", "date_counts_pile.tsv"],
        [
            "CALENDAR OF\nMEANINGFUL DATES ON THE WEB",
            "CALENDAR OF\nMEANINGFUL DATES FOR AN LLM",
        ],
        ["DCLM", "The Pile"],
    ):
        counts = load_data(IN_FILENAME)

        # Rank based font scaling
        sorted_keys = sorted(counts.keys(), key=lambda k: counts[k])
        n = len(sorted_keys)
        lo, hi = 7, 33

        size_lookup = {}
        for i, key in enumerate(sorted_keys):
            t = i / (n - 1)
            if i >= n - 3:
                t = 2  # Make top 3 dates BIG
            size_lookup[key] = lo + t * (hi - lo)

        fig, axes = plt.subplots(4, 3, figsize=(10, 15))
        fig.patch.set_facecolor("white")

        fig.suptitle(
            TITLE,
            fontsize=32,
            fontweight="bold",
            va="bottom",
            y=0.93,
        )
        fig.text(
            0.5,
            0.925,
            f"""Each date's size represents how often it is referred to by name
            (e.g. "October 17th, 17 October") in {corpus_name}""",
            ha="center",
            va="top",
            fontsize=15,
            color="0.5",
        )

        for idx, ax in enumerate(axes.flat):
            month = idx + 1
            ax.set_xlim(-0.1, 6.5)
            ax.set_ylim(-0.3, 5.5)
            ax.axis("off")

            x_step = 0.9
            y_step = 0.9

            # Month title
            ax.text(
                3.5,
                4.5,
                calendar.month_name[month].upper(),
                ha="center",
                va="center",
                fontsize=25,
                color="0.25",
            )

            # Day numbers
            cal = calendar.monthcalendar(2024, month)

            for week_i, week in enumerate(cal):
                for dow, day in enumerate(week):
                    if day == 0:
                        continue
                    fs = size_lookup.get((month, day), lo)
                    ax.text(
                        dow * x_step + 0.5,
                        3.75 - week_i * y_step,
                        str(day),
                        ha="center",
                        va="center",
                        fontsize=fs,
                        fontweight="bold",
                    )

        plt.subplots_adjust(
            left=0.03,
            right=0.97,
            top=0.9,
            bottom=0.06,
            hspace=0.03,
            wspace=0.1,
        )

        plt.savefig(OUT_FILENAME, dpi=200, facecolor="white")


if __name__ == "__main__":
    main()
