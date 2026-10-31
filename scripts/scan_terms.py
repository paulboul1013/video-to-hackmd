#!/usr/bin/env python3
"""List every spelling variant of suspicious terms in a transcript, with line timestamps.

Usage: python scan_terms.py TRANSCRIPT.txt "Grokbot|GraphBot|Rockbot" "P-?Stack|PSAC|PSET" ...

Each argument is one term group: a case-insensitive regex whose alternatives are the
spellings to compare. For each group the script prints how often each spelling occurs
and the transcript line start ([m:ss]) of every occurrence. Use it in step 3 to see
whether a mishearing repeats consistently, and to copy exact times into the appendix
`附錄：字幕校正` instead of guessing them.

Exit codes: 0 ok | 2 bad input
"""
import re
import sys
from collections import Counter, defaultdict

LINE = re.compile(r"^\[(\d+(?::\d{2}){1,2})\]\s*(.*)$")


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    try:
        lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
    except OSError as exc:
        print(f"Cannot read transcript: {exc}", file=sys.stderr)
        sys.exit(2)
    rows = [m.groups() for m in map(LINE.match, lines) if m]
    if not rows:
        print("No '[m:ss] text' lines found; was the transcript written by fetch_transcript.py?", file=sys.stderr)
        sys.exit(2)

    for group in sys.argv[2:]:
        try:
            pattern = re.compile(rf"\b(?:{group})\b", re.I)
        except re.error as exc:
            print(f"Bad pattern {group!r}: {exc}", file=sys.stderr)
            sys.exit(2)
        counts, times = Counter(), defaultdict(list)
        for stamp, text in rows:
            for m in pattern.finditer(text):
                counts[m.group(0)] += 1
                if stamp not in times[m.group(0)]:
                    times[m.group(0)].append(stamp)
        print(f"## {group}")
        if not counts:
            print("  (no matches)")
        for spelling, n in counts.most_common():
            print(f"  {spelling!r} x{n}: {', '.join(times[spelling])}")


if __name__ == "__main__":
    main()
