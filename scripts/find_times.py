#!/usr/bin/env python3
"""Print the exact moment each term is spoken, from the word-timing file of fetch_transcript.py.

Usage: python find_times.py WORDS.tsv "term1" "term2|alt spelling" ... [--after m:ss]

WORDS.tsv has one caption word per line: "<seconds>\t<text>" (YouTube json3 captions only).
A term may span several caption words; spaces are ignored when matching, so "all over the world"
and "思い出" both work. Each occurrence prints as m:ss (rounded down), usable as a {{m:ss}} token:
expand_links.py accepts these times when the words file sits next to the transcript.

Exit codes: 0 ok | 1 some terms not found | 2 bad input
"""
import sys


def stamp(sec):
    s = int(sec)
    h, rem = divmod(s, 3600)
    m, x = divmod(rem, 60)
    return f"{h}:{m:02d}:{x:02d}" if h else f"{m}:{x:02d}"


def seconds(t):
    total = 0
    for part in t.split(":"):
        total = total * 60 + int(part)
    return total


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    after = 0
    if "--after" in args:
        i = args.index("--after")
        after = seconds(args[i + 1])
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    try:
        rows = [line.rstrip("\n").split("\t", 1) for line in open(args[0], encoding="utf-8") if "\t" in line]
    except OSError as exc:
        print(f"Cannot read input: {exc}", file=sys.stderr)
        sys.exit(2)
    # One string of all words without spaces, plus the start time of each character.
    text, times = [], []
    for t, w in rows:
        w = w.replace(" ", "")
        text.append(w)
        times.extend([float(t)] * len(w))
    text = "".join(text)

    missing = False
    for term in args[1:]:
        hits = []
        for alt in term.split("|"):
            needle = alt.replace(" ", "")
            start = text.find(needle)
            while needle and start != -1:
                if times[start] >= after:
                    hits.append((times[start], alt))
                start = text.find(needle, start + 1)
        print(f"## {term}")
        if not hits:
            print("  (not found)")
            missing = True
        for t, alt in sorted(hits):
            print(f"  {stamp(t)}  ({t:.2f}s)  {alt}")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
