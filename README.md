# video-to-hackmd

一個 [Claude Code](https://claude.com/claude-code) skill：把影片整理成**帶時間戳的重點**，輸出成 HackMD 技術文章，並用小例子解釋抽象概念。

支援 YouTube（含 Shorts）、Vimeo、Bilibili、TikTok、Instagram、X 等 `yt-dlp` 能處理的網站。

## 功能

- **抓逐字稿**：優先用平台字幕（人工 → 自動 → 人工翻譯，不用機器翻譯）；沒有字幕時可用本機 Whisper 轉錄，並用影片標題、說明欄裡的名詞當提示，讓專有名詞拼對。
- **專有名詞校正**：例如自動字幕的「Quad Code」→「Claude Code」，只在有佐證時替換，不確定就標 `(?)`，所有更動都列在文末「附錄：字幕校正」。
- **三種輸出格式**，內容完全相同、只差版面：
  - `hackmd`（預設）：完整文章，含 TL;DR、`[TOC]`、提示框、範例與類比
  - `markdown`：同一篇文章的通用 Markdown 版（GitHub、Obsidian）
  - `outline`：章節大綱，每個重點一行
- **時間戳可點**：YouTube、Vimeo、Bilibili 會連到影片對應秒數。
- **自動驗證**：腳本檢查每個重點都有出現、時間對得上逐字稿、HackMD 語法沒有踩雷。
- **學習頁面（YouTube）**：產生本機 HTML，左邊嵌入播放器、右邊是筆記，點時間戳直接跳到那一刻。
- **快取**：同一支影片重做不用重新下載。

## 安裝

把這個 repo clone 到 Claude Code 的 skills 資料夾：

```bash
git clone https://github.com/paulboul1013/video-to-hackmd ~/.claude/skills/video-to-hackmd
```

也可以放在專案裡的 `.claude/skills/video-to-hackmd/`，只在該專案使用。

### 需求

- Python 3
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)：`pip install -U yt-dlp`（新版 YouTube 另需 Node 等 JS runtime）
- 選用：[`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) 與 `ffmpeg`，只在影片沒有字幕時需要。第一次執行會下載約 460 MB 的 `small` 模型。

需要安裝套件或跑 Whisper 時，skill 會先詢問。

## 使用

在 Claude Code 裡貼上影片網址並說明需求即可，例如：

```
https://www.youtube.com/watch?v=Unzc731iCUY 幫我整理影片重點，寫成 HackMD 文章
```

```
幫我把這支影片整理成章節大綱，只要前 4 章
```

```
剛剛那支影片，再做一個影片＋筆記的學習頁面
```

輸出會存成目前資料夾的 `<slug>-<format>.md`。skill 不會自動上傳到 HackMD；tags 與 description 會列在回覆裡，自己貼到 HackMD 的筆記設定。

## 檔案結構

```
SKILL.md                    skill 主說明（流程與規則）
references/
  article-template.md       HackMD 文章結構與「抽象概念 → 小例子」寫法
  formats.md                markdown / outline 版面
  hackmd-syntax.md          HackMD 語法備忘
scripts/
  fetch_transcript.py       抓字幕或 Whisper 轉錄，含快取
  expand_links.py           {{m:ss}} → 時間戳連結
  check_coverage.py         檢查每個重點都有出現、時間一致
  check_hackmd.py           檢查 HackMD／Markdown 語法
  render_player.py          產生並開啟 YouTube 學習頁面
```

## 限制

- 只處理聲音（字幕或轉錄），看不到畫面；依賴投影片或操作示範的影片會缺內容。
- 檢查腳本能驗證結構、覆蓋率和時間戳，無法驗證重點是否正確表達講者原意。
