#!/usr/bin/env python3
"""Build a local HTML study page: an embedded YouTube player next to the notes.

Usage:
  python render_player.py ARTICLE.md TRANSCRIPT.txt OUT.html    build the page
  python render_player.py --serve PAGE.html                     open it (local server + browser)

ARTICLE.md is the final output of step 6 (links already expanded). Clicking any
timestamp link to the same video seeks the embedded player instead of opening a
new page. The notes are rendered in the browser with marked + DOMPurify, so
caption text can never inject script into the page. YouTube only: other sites
have no embeddable player API that this page supports.

YouTube refuses to play embeds on pages opened as file:// (it shows "400. That's an
error"), so --serve starts a web server on 127.0.0.1 only, opens the page in the
default browser, and runs until Ctrl+C. Opened as a file, the page says so.

Exit codes: 0 ok | 2 bad input | 3 not a YouTube video
"""
import functools
import http.server
import json
import os
import re
import sys
import webbrowser

YOUTUBE_ID = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")
CONTAINER = re.compile(r"^:::\s*(info|success|warning|danger)\s*$")

PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { --bg:#ffffff; --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --card:#f6f8fa; --accent:#0969da;
        --info:#ddf4ff; --success:#dafbe1; --warning:#fff8c5; --danger:#ffebe9; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#3d444d; --card:#151b23; --accent:#4493f8;
          --info:#0c2d48; --success:#0f2e1a; --warning:#3b2e05; --danger:#3c1618; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.7 system-ui, "Noto Sans TC", "Microsoft JhengHei", sans-serif; }
.layout { display:grid; grid-template-columns:minmax(0,1fr); }
.player { position:sticky; top:0; z-index:2; background:var(--bg); border-bottom:1px solid var(--line); padding:8px 16px; }
.frame { position:relative; width:100%; aspect-ratio:16/9; max-height:40vh; margin:0 auto; }
.frame > div, .frame iframe { position:absolute; inset:0; width:100%; height:100%; border:0; border-radius:8px; }
.now { font-size:14px; color:var(--muted); margin-top:4px; }
main { padding:16px; max-width:900px; width:100%; margin:0 auto; overflow-wrap:anywhere; }
@media (min-width: 1100px) {
  .layout { grid-template-columns:minmax(380px,44%) minmax(0,1fr); }
  .player { height:100vh; border-bottom:0; border-right:1px solid var(--line); padding:16px; }
  .frame { max-height:none; }
}
h1 { font-size:1.7em; line-height:1.3; } h2 { border-bottom:1px solid var(--line); padding-bottom:4px; margin-top:2em; }
a { color:var(--accent); }
a.seek { font-variant-numeric:tabular-nums; font-weight:600; text-decoration:none; border:1px solid var(--line);
         border-radius:6px; padding:0 6px; background:var(--card); white-space:nowrap; cursor:pointer; }
a.seek:hover, a.seek.active { background:var(--accent); color:#fff; border-color:var(--accent); }
table { border-collapse:collapse; width:100%; display:block; overflow-x:auto; }
th, td { border:1px solid var(--line); padding:6px 10px; vertical-align:top; }
th { background:var(--card); }
blockquote { margin:1em 0; padding:0 1em; color:var(--muted); border-left:4px solid var(--line); }
pre { background:var(--card); padding:12px; border-radius:8px; overflow-x:auto; }
code { font-family:ui-monospace, Consolas, monospace; font-size:.92em; }
.box { padding:4px 16px; border-radius:8px; margin:1em 0; }
.box.info { background:var(--info); } .box.success { background:var(--success); }
.box.warning { background:var(--warning); } .box.danger { background:var(--danger); }
#toc { background:var(--card); border-radius:8px; padding:8px 16px; }
#toc ul { margin:4px 0; padding-left:20px; }
</style>
</head>
<body>
<div class="layout">
  <aside class="player">
    <div class="frame"><div id="yt"></div></div>
    <div class="now" id="now">點文中任何時間，影片會直接跳到該處。</div>
  </aside>
  <main id="notes"></main>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.1.6/purify.min.js"></script>
__MERMAID__
<script>
const VIDEO_ID = __VIDEO_ID__;
const CAPTION_LANG = __CAPTION_LANG__;
const MARKDOWN = __MARKDOWN__;
const notes = document.getElementById("notes");
notes.innerHTML = DOMPurify.sanitize(marked.parse(MARKDOWN));

// Table of contents in place of HackMD's [TOC].
const toc = document.getElementById("toc");
if (toc) {
  const list = document.createElement("ul");
  notes.querySelectorAll("h2, h3").forEach((h, i) => {
    h.id = h.id || "s" + i;
    const li = document.createElement("li");
    if (h.tagName === "H3") li.style.marginLeft = "1.2em";
    const a = document.createElement("a"); a.href = "#" + h.id; a.textContent = h.textContent;
    li.appendChild(a); list.appendChild(li);
  });
  toc.appendChild(list);
}

// Links to this video become seek buttons.
const seekLinks = [];
notes.querySelectorAll("a[href]").forEach(a => {
  let url; try { url = new URL(a.href); } catch (e) { return; }
  const id = url.hostname.endsWith("youtu.be") ? url.pathname.slice(1) : url.searchParams.get("v");
  const t = parseInt(url.searchParams.get("t") || "", 10);
  if (id !== VIDEO_ID || Number.isNaN(t)) { a.target = "_blank"; a.rel = "noopener"; return; }
  a.classList.add("seek"); a.dataset.t = t; a.title = "跳到 " + a.textContent;
  seekLinks.push(a);
});

let player = null;
function seek(t) {
  if (!player || !player.seekTo) return false;
  player.seekTo(t, true); player.playVideo();
  return true;
}
notes.addEventListener("click", e => {
  const a = e.target.closest("a.seek");
  if (!a) return;
  if (seek(Number(a.dataset.t))) e.preventDefault();   // player not ready yet: fall back to opening the link
});

function fmt(s) { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${x}` : `${m}:${x}`; }
setInterval(() => {
  if (!player || !player.getCurrentTime) return;
  const now = player.getCurrentTime();
  let current = null;
  for (const a of seekLinks) if (Number(a.dataset.t) <= now && (!current || Number(a.dataset.t) >= Number(current.dataset.t))) current = a;
  seekLinks.forEach(a => a.classList.toggle("active", current && a.dataset.t === current.dataset.t));
  document.getElementById("now").textContent = "目前 " + fmt(now) + "　點文中任何時間，影片會直接跳到該處。";
}, 500);

if (location.protocol === "file:") {
  document.querySelector(".frame").innerHTML = '<div style="padding:16px;border:1px dashed var(--line);border-radius:8px">'
    + 'YouTube 不允許在直接開啟的檔案中播放。請在終端機執行：<br><code>python render_player.py --serve "'
    + decodeURIComponent(location.pathname.split("/").pop()) + '"</code><br>（render_player.py 位於 skill 的 scripts 資料夾）</div>';
}
window.onYouTubeIframeAPIReady = () => {
  if (location.protocol === "file:") return;
  // Captions on by default in the spoken language, so the full original text is visible while listening.
  const vars = { rel: 0, playsinline: 1, cc_load_policy: 1 };
  if (CAPTION_LANG) vars.cc_lang_pref = CAPTION_LANG;
  player = new YT.Player("yt", { videoId: VIDEO_ID, playerVars: vars });
};
const api = document.createElement("script");
api.src = "https://www.youtube.com/iframe_api";
document.head.appendChild(api);
if (window.mermaid) { mermaid.initialize({ startOnLoad: false, theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default" });
  notes.querySelectorAll("code.language-mermaid").forEach(c => { const d = document.createElement("div"); d.className = "mermaid";
    d.textContent = c.textContent; c.parentElement.replaceWith(d); }); mermaid.run(); }
</script>
</body>
</html>
"""


def to_portable(markdown):
    """Turn HackMD-only syntax into what marked understands."""
    out = []
    for line in markdown.splitlines():
        m = CONTAINER.match(line)
        if m:
            out += [f'<div class="box {m.group(1)}">', ""]
        elif line.strip() == ":::":
            out += ["", "</div>"]
        elif line.strip() == "[TOC]":
            out.append('<nav id="toc"></nav>')
        else:
            out.append(line)
    return "\n".join(out)


def js_string(text):
    # json.dumps gives a valid JS string; escaping "</" keeps </script> inside it harmless.
    return json.dumps(text, ensure_ascii=False).replace("</", "<\\/")


def serve(page):
    if not os.path.isfile(page):
        print(f"No such page: {page}", file=sys.stderr)
        sys.exit(2)
    folder, name = os.path.split(os.path.abspath(page))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=folder)
    # Port 0 lets the OS pick a free port; 127.0.0.1 keeps the server off the network.
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as httpd:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/{name}"
        print(f"Serving {url} (only this computer can reach it). Press Ctrl+C to stop.", flush=True)
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if len(sys.argv) == 3 and sys.argv[1] == "--serve":
        serve(sys.argv[2])
        return
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    article_path, transcript_path, out_path = sys.argv[1:]
    try:
        article = open(article_path, encoding="utf-8").read()
        transcript = open(transcript_path, encoding="utf-8").read()
    except OSError as exc:
        print(f"Cannot read input: {exc}", file=sys.stderr)
        sys.exit(2)
    url = re.search(r"^URL: (\S+)", transcript, re.M)
    vid = YOUTUBE_ID.search(url.group(1)) if url else None
    if not vid:
        print("The study page needs a YouTube video; this transcript's URL is not one.", file=sys.stderr)
        sys.exit(3)
    # Header line "Captions: auto-generated (ja-orig)" -> "ja"; Whisper transcripts may lack it.
    lang = re.search(r"Captions: [^(\n]*\(([A-Za-z]{2,3}(?:-Hant|-Hans)?)", transcript)
    title = re.search(r"^# (.+)$", article, re.M)
    title = (title.group(1) if title else "Study page").replace("<", "&lt;").replace(">", "&gt;")
    mermaid = ('<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>'
               if "```mermaid" in article else "")
    html = (PAGE.replace("__TITLE__", title).replace("__MERMAID__", mermaid)
            .replace("__VIDEO_ID__", js_string(vid.group(1)))
            .replace("__CAPTION_LANG__", js_string(lang.group(1)) if lang else '""')
            .replace("__MARKDOWN__", js_string(to_portable(article))))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    links = len(re.findall(rf"youtu\.be/{vid.group(1)}\?t=\d+", article))
    print(f"Study page written to {out_path} ({links} seekable timestamps)")


if __name__ == "__main__":
    main()
