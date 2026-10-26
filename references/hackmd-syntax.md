# HackMD syntax notes

## Contents
- Front matter
- Supported syntax
- Pitfalls

## Front matter

HackMD stopped accepting YAML front matter on 2023-06-20 and ignores that block (official: https://hackmd.io/yaml-metadata). Do not emit `---` front matter. The title is the first `# ` heading. Tags and description are entered in the HackMD UI, so list them in the reply.

## Supported syntax

Taken from the open-source CodiMD feature list (https://github.com/hackmdio/codimd/blob/develop/public/docs/features.md), which HackMD shares. Not re-checked against the current hosted docs.

| Feature | Syntax |
|---|---|
| Table of contents | `[TOC]` (3 levels by default, up to 5) |
| Containers | `:::info`, `:::success`, `:::warning`, `:::danger`, closed with `:::` |
| Collapsible | `:::spoiler Title` ... `:::` |
| Diagram | a fenced block tagged `mermaid` |
| Math | `$inline$` and `$$block$$` |
| Line numbers | a fence tagged `js=` (from 1), `js=101`, or `js=+` (continue) |
| Embed | `{%youtube VIDEO_ID %}` |

## Pitfalls

- Every opened `:::` needs its own closing `:::`. Do not nest containers.
- Close every code fence. An unclosed fence swallows the rest of the page.
- Keep Mermaid diagrams small; start with a diagram keyword such as `flowchart`.
- Legacy tag line `###### tags: ...` may still work, but this is unverified. Do not rely on it.
- Generic Markdown linters misreport `:::`, `[TOC]` and `js=` fences. Use `scripts/check_hackmd.py` instead.
