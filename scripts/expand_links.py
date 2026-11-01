#!/usr/bin/env python3
"""Replace {{m:ss}} tokens with timestamp links.

Usage: python expand_links.py DRAFT.md TRANSCRIPT.txt OUT.md

The video URL is read from the transcript header written by fetch_transcript.py.
Each token becomes [m:ss](link to that moment) on sites that support time links
(YouTube, Vimeo, Bilibili) and plain [m:ss] elsewhere (TikTok, Instagram, X, ...).
Every time must be the start of a transcript line, so each one points at text that exists,
or the start of a caption word when <id>.words.tsv sits next to the transcript (see find_times.py).

Exit codes: 0 ok | 1 some times are not transcript line starts (file still written) | 2 bad input
"""
import os
import re
import sys

TOKEN = re.compile(r"\{\{(\d+(?::\d{2}){1,2})\}\}")
YOUTUBE_ID = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def seconds(t):
    total = 0
    for part in t.split(":"):
        total = total * 60 + int(part)
    return total


def link_builder(url):
    """Return (mode, function seconds -> URL or None)."""
    m = YOUTUBE_ID.search(url)
    if m:
        return "youtube", lambda s: f"https://youtu.be/{m.group(1)}?t={s}"
    if "vimeo.com/" in url:
        return "vimeo", lambda s: f"{url.split('#')[0]}#t={s}s"
    if "bilibili.com/" in url:
        sep = "&" if "?" in url else "?"
        return "bilibili", lambda s: f"{url.split('#')[0]}{sep}t={s}"
    return "plain (site has no time links)", lambda s: None


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    draft_path, transcript_path, out_path = sys.argv[1:]
    try:
        draft = open(draft_path, encoding="utf-8").read()
        transcript = open(transcript_path, encoding="utf-8").read()
    except OSError as exc:
        print(f"Cannot read input: {exc}", file=sys.stderr)
        sys.exit(2)
    m = re.search(r"^URL: (\S+)", transcript, re.M)
    if not m:
        print("Transcript header has no 'URL: ...' line; was it written by fetch_transcript.py?", file=sys.stderr)
        sys.exit(2)
    mode, build = link_builder(m.group(1))
    starts = set(re.findall(r"^(?:## )?\[([\d:]+)\]", transcript, re.M))
    # Exact word times (from find_times.py) are valid too when the words file is next to the transcript.
    words_path = re.sub(r"\.transcript\.txt$", ".words.tsv", transcript_path)
    if words_path != transcript_path and os.path.isfile(words_path):
        with open(words_path, encoding="utf-8") as f:
            for line in f:
                sec = int(float(line.split("\t", 1)[0]))
                h, rem = divmod(sec, 3600)
                starts.add(f"{h}:{rem // 60:02d}:{rem % 60:02d}" if h else f"{rem // 60}:{rem % 60:02d}")
    unknown = []

    def link(match):
        t = match.group(1)
        if t not in starts:
            unknown.append(t)
        target = build(seconds(t))
        return f"[{t}]({target})" if target else f"[{t}]"

    text, count = TOKEN.subn(link, draft)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{count} timestamp(s) written to {out_path} ({mode})")
    if unknown:
        print("Not a transcript line start (use the time printed at the start of the line): "
              + ", ".join(sorted(set(unknown), key=seconds)))
        sys.exit(1)


if __name__ == "__main__":
    main()
