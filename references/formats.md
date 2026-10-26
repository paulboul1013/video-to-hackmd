# Output format layouts

## Contents
- markdown
- outline

All formats render the same key-point sheet. Only the layout below differs.

## markdown

The `hackmd` article converted to portable Markdown (GitHub, Obsidian, most editors):

| HackMD syntax | Portable replacement |
|---|---|
| `[TOC]` | Remove it |
| `:::success` / `:::info` / `:::warning` block | A `>` blockquote that starts with **結論** / **補充** / **注意** |
| `{%youtube ID %}` | A plain link to the video |
| Fence tagged `js=` | Fence tagged `js` |

Keep `mermaid` blocks; GitHub and Obsidian render them.

## outline

The shortest format. No analogies, no examples written by you, no explanations beyond the key points.

```markdown
# <Title>：章節大綱

> 來源：<video title>（<channel>）<url>
> 字幕：<manual | auto-generated>，語言 <lang>。共 <N> 個重點。

## [m:ss] <chapter title>
- {{m:ss}} <key point, same wording as the sheet> <!-- KP01 -->
- {{m:ss}} <key point> <!-- KP02 -->

## 附錄：字幕校正
| 時間 | 字幕原文 | 處理 | 依據 |
|---|---|---|---|
```

- One bullet per key point, in sheet order, under the chapter heading copied exactly from the sheet.
- `<channel>` comes from the `channel` field of the fetch output; if it is empty, write 未提及.
- Copy the claim wording from the sheet. Shorten only filler words; keep numbers, names, quotes and `(?)` / 未提及 markers.
