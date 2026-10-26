# Article template

## Contents
- Skeleton
- Abstract concept to small example (5 steps)
- Style rules

## Skeleton

```markdown
# <Title>

> 來源：<video title>（<speaker>）<url>
> 字幕：<manual | auto-generated>，語言 <lang>。標示「範例（示意）」者為整理者自行撰寫，非講者原話。

[TOC]

:::success
**一句話結論**：<TL;DR in 1–2 sentences>
:::

## 為什麼要在意
<The pain or situation the talk starts from.>

## <Concept 1>
<Concept block, see below>

## <Concept 2>
...

## 速查表
| 想做的事 | 做法 | 原因 |
|---|---|---|

## 附錄：字幕校正
| 時間 | 字幕原文 | 校正為 | 依據 |
|---|---|---|---|

## 延伸閱讀
```

## Abstract concept to small example (5 steps)

Use this block only for abstract concepts (an idea the reader cannot picture yet). Practical tips and lists of techniques stay as key-point bullets; add an example only where it helps. Keep the TL;DR to 1–2 sentences whatever the scope.

For each abstract concept, write a block in this order:

1. **One-sentence plain definition.** No jargon that the reader has not met yet.
2. **One everyday analogy**, followed by one sentence on where the analogy stops working.
3. **Smallest concrete example** (a prompt, one command, or 5–15 lines of code). State input and expected output. Label it `影片中的案例` with a linked timestamp, or `範例（示意）`.
4. **Walk through the example**, mapping each line back to the definition from step 1.
5. **One pitfall or boundary case** in a `:::warning` container.

Worked mini-example (concept: feedback loop):

> 定義：讓程式能「看到自己做的結果」，再據此修正。
> 類比：像寫書法時邊寫邊看字形，而不是閉著眼寫完才睜開。差別是 Claude 的「眼睛」要你提供（測試、截圖）。
> 範例（示意）：給它設計稿與截圖工具，它做完會自己截圖比對，再調整間距。
> 拆解：設計稿＝目標，截圖＝回饋，比對後修改＝迴圈。
> 雷：沒有可靠的檢查方式時，迴圈只會原地打轉。

## Style rules

- One concept per `##` section; keep each section under about 25 lines.
- Prefer a table for comparisons and a `mermaid` block for flows. Keep a diagram under 10 nodes.
- Use `:::info` for background, `:::success` for conclusions, `:::warning` for pitfalls. Do not nest containers.
- Each key point carries its `{{m:ss}}` token and its `<!-- KPnn -->` marker on the same line.
- Never fill a gap with plausible detail. Say 未提及.
