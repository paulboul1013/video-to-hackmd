#!/usr/bin/env python3
"""Check a Markdown file for HackMD pitfalls.

Usage: python check_hackmd.py FILE.md [--plain]
--plain checks portable Markdown instead: HackMD-only syntax ([TOC], ::: containers,
{% %} embeds) becomes an error.
Exit codes: 0 no errors (warnings allowed) | 1 errors found | 2 file unreadable
"""
import re
import sys

CONTAINERS = {"info", "success", "warning", "danger", "spoiler"}
MERMAID_STARTS = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram",
                  "gantt", "pie", "journey", "mindmap", "timeline", "gitGraph")
# Below this many headings a table of contents adds little.
TOC_MIN_HEADINGS = 5

FENCE = re.compile(r"^\s*(```|~~~)\s*(\S*)")
HEADING = re.compile(r"^(#{1,6})\s+\S")
CONTAINER = re.compile(r"^:::\s*(\w*)")


def check(lines, plain=False):
    problems = []
    err = lambda n, msg: problems.append(("ERROR", n, msg))
    warn = lambda n, msg: problems.append(("WARN", n, msg))

    if not plain and lines and lines[0].strip() == "---":
        err(1, "YAML front matter found; HackMD ignores it (since 2023-06-20). Remove it and use a '# ' title.")

    fence_open = None            # (line number, marker, mermaid?)
    mermaid_first_seen = False
    container_open = None        # line number of the open ':::' container
    headings, h1_count, last_level, first_content_checked = 0, 0, 0, False

    for n, raw in enumerate(lines, 1):
        line = raw.rstrip("\n")
        fm = FENCE.match(line)
        if fm:
            if fence_open is None:
                fence_open = (n, fm.group(1), fm.group(2).lower() == "mermaid")
                mermaid_first_seen = False
            elif fm.group(1) == fence_open[1]:
                if fence_open[2] and not mermaid_first_seen:
                    warn(fence_open[0], "Empty mermaid block.")
                fence_open = None
            continue
        if fence_open:
            if fence_open[2] and not mermaid_first_seen and line.strip():
                mermaid_first_seen = True
                if not line.strip().startswith(MERMAID_STARTS):
                    warn(n, "Mermaid block should start with a diagram keyword such as 'flowchart'.")
            continue

        if not first_content_checked and line.strip():
            first_content_checked = True
            if not line.startswith("# "):
                err(n, "First non-empty line should be the '# ' title (HackMD uses it as the note title).")

        hm = HEADING.match(line)
        if hm:
            level = len(hm.group(1))
            headings += 1
            h1_count += level == 1
            if last_level and level > last_level + 1:
                warn(n, f"Heading level jumps from h{last_level} to h{level}.")
            last_level = level

        cm = CONTAINER.match(line)
        if plain:
            if cm:
                err(n, "HackMD-only ':::' container; use a '>' blockquote in portable Markdown.")
            if line.strip() == "[TOC]":
                err(n, "HackMD-only [TOC]; remove it in portable Markdown.")
            if "{%" in line:
                err(n, "HackMD-only {% %} embed; use a plain link in portable Markdown.")
            cm = None
        if cm:
            name = cm.group(1)
            if name:
                if name not in CONTAINERS:
                    warn(n, f"Unknown container ':::{name}'.")
                if container_open:
                    warn(n, f"Nested container (outer opened on line {container_open}).")
                container_open = n
            elif container_open:
                container_open = None
            else:
                err(n, "Closing ':::' without an opening container.")

        if line.strip().startswith("###### tags:"):
            warn(n, "Legacy tags line; unverified in current HackMD. Prefer Note settings.")

    if fence_open:
        err(fence_open[0], "Code fence is never closed.")
    if container_open:
        err(container_open, "Container ':::' is never closed.")
    if h1_count > 1:
        warn(1, f"{h1_count} top-level '# ' headings; expected exactly one.")
    if not plain and headings >= TOC_MIN_HEADINGS and not any(l.strip() == "[TOC]" for l in lines):
        warn(1, "No [TOC] found.")
    return problems


def main():
    args = sys.argv[1:]
    plain = "--plain" in args
    files = [a for a in args if a != "--plain"]
    if len(files) != 1:
        print(__doc__)
        sys.exit(2)
    try:
        with open(files[0], encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Cannot read {files[0]}: {exc}", file=sys.stderr)
        sys.exit(2)
    problems = check(lines, plain)
    for level, n, msg in problems:
        print(f"{level} line {n}: {msg}")
    errors = sum(1 for p in problems if p[0] == "ERROR")
    print(f"{errors} error(s), {len(problems) - errors} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
