#!/usr/bin/env python3
"""Check that an output covers every key point of the key-point sheet, with the same timestamp.

Usage: python check_coverage.py SHEET.md OUTPUT.md

Sheet lines look like:   - KP01 {{0:50}} claim text
Output lines carry a marker after the key point's timestamp, on the same line:
                         ... [0:50](https://youtu.be/ID?t=50) <!-- KP01 -->
                         ... [0:50] <!-- KP01 -->          (sites without time links)
A marker belongs to the closest timestamp before it, so one line can hold several key points.

This is what keeps the content identical across output formats: every format must
contain every key point, at the same time, whatever the layout.

Exit codes: 0 all covered | 1 missing, unknown or mismatched key points | 2 unreadable or empty sheet
"""
import re
import sys

SHEET_LINE = re.compile(r"^\s*-\s*(KP\d+)\s+\{\{(\d+(?::\d{2}){1,2})\}\}")
ITEM = re.compile(r"\[(\d+(?::\d{2}){1,2})\](?:\([^)]*\))?|<!--\s*(KP\d+)\s*-->")


def seconds(t):
    total = 0
    for part in t.split(":"):
        total = total * 60 + int(part)
    return total


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    try:
        sheet = open(sys.argv[1], encoding="utf-8").read().splitlines()
        output = open(sys.argv[2], encoding="utf-8").read().splitlines()
    except OSError as exc:
        print(f"Cannot read input: {exc}", file=sys.stderr)
        sys.exit(2)

    expected = {}
    for line in sheet:
        m = SHEET_LINE.match(line)
        if m:
            expected[m.group(1)] = seconds(m.group(2))
    if not expected:
        print("No key points found in the sheet. Lines must look like '- KP01 {{m:ss}} claim'.", file=sys.stderr)
        sys.exit(2)

    found = {}  # KP id -> link seconds; a marker belongs to the closest link before it on its line
    for line in output:
        last = None
        for m in ITEM.finditer(line):
            if m.group(1):
                last = seconds(m.group(1))
            else:
                found.setdefault(m.group(2), set())
                if last is not None:
                    found[m.group(2)].add(last)
                last = None

    problems = []
    for kp, sec in expected.items():
        if kp not in found:
            problems.append(f"MISSING {kp}: not in the output")
        elif sec not in found[kp]:
            problems.append(f"TIME {kp}: expected t={sec}, found {sorted(found[kp]) or 'no timestamp before its marker'}")
    for kp in sorted(set(found) - set(expected)):
        problems.append(f"UNKNOWN {kp}: in the output but not in the sheet")

    for p in problems:
        print(p)
    print(f"{len(expected) - sum(p.startswith(('MISSING', 'TIME')) for p in problems)}/{len(expected)} key points covered")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
