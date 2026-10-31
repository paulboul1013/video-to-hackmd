#!/usr/bin/env python3
"""Fetch a video transcript with yt-dlp (or local Whisper) and write a timestamped text file.

Usage:
  python fetch_transcript.py URL --out-dir DIR [--langs zh-Hant,zh-TW,zh,en]
                             [--track manual:KEY | auto:KEY] [--refresh] [--cache-dir DIR]
                             [--whisper [--hint "Name A, Name B"] [--whisper-lang en]
                                        [--whisper-model small] [--whisper-until SECONDS]]

Works for any site yt-dlp supports (YouTube, Shorts, Vimeo, TikTok, Instagram, X, Bilibili, ...).
Captions are used when the site has them. --whisper instead downloads the audio and
transcribes it locally with faster-whisper; --hint lists names the speaker will say so
Whisper spells them right. Metadata, captions and Whisper results are cached per video;
--refresh re-downloads.

Prints one JSON object on success. Exit codes:
  0 ok | 2 yt-dlp unavailable | 3 no usable captions (consider --whisper)
  4 yt-dlp failed (rate limit, login required, private video) | 5 faster-whisper not installed
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

# One timestamp per ~30 s keeps every line citable without one line per caption event.
BLOCK_SECONDS = 30
CJK_PREFIXES = ("zh", "ja", "ko")
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "video-to-hackmd")
YOUTUBE_ID = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")
X_STATUS_ID = re.compile(r"(?:^|[/.])(?:x|twitter)\.com/[^/?#]+/status/(\d+)", re.I)
# X lists its own speech recognition as ordinary "subtitles"; its VTT cues carry per-word timing tags.
MACHINE_CAPTION_MARKERS = ("<X-word-ms",)
INFO_KEYS = ("id", "title", "uploader", "duration", "chapters", "language", "webpage_url", "extractor_key")
# Caption formats this script can parse, best first (json3 has exact word timing on YouTube).
SUB_FORMATS = "json3/vtt/srt"
# "small" is the smallest model that handles accented English and Mandarin acceptably on CPU.
WHISPER_MODEL = "small"
# Whisper only reads the last ~224 tokens of its prompt; a short list of names fits easily.
HINT_MAX_CHARS = 400


def fail(code, message):
    print(message, file=sys.stderr)
    sys.exit(code)


def ytdlp_command():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "yt_dlp"]


def require_ytdlp(base):
    if base is None:
        fail(2, "yt-dlp not found. Ask the user before installing: pip install -U yt-dlp")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def explain_failure(result):
    err = result.stderr.strip()
    if "429" in err:
        return "yt-dlp was rate limited (HTTP 429). Wait a few minutes and retry once.\n" + err
    if re.search(r"login|log in|cookies|sign in|private", err, re.I):
        return ("The site requires a login or the video is private. Do not use browser cookies "
                "unless the user asks.\n" + err)
    return "yt-dlp failed:\n" + err


def cache_key(url):
    """YouTube URLs share one key per video id, and so do X posts (x.com, twitter.com, ?s=20 ...);
    other sites use a hash of the URL without its #fragment."""
    m = YOUTUBE_ID.search(url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    m = X_STATUS_ID.search(url)
    if m:
        return "x-" + m.group(1)
    return "url-" + hashlib.sha1(url.strip().split("#")[0].encode("utf-8")).hexdigest()[:12]


def is_machine_caption(path):
    """True when a 'manual' track is really the site's speech recognition (X does this)."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        head = f.read(4096)
    return any(marker in head for marker in MACHINE_CAPTION_MARKERS)


def load_info(base, url, vdir, refresh):
    """Return (info, from_cache). Only the fields this script needs are cached."""
    path = os.path.join(vdir, "info.json")
    if not refresh and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f), True
    require_ytdlp(base)
    result = run(base + ["--skip-download", "--no-playlist", "--no-warnings", "--dump-single-json", url])
    if result.returncode != 0:
        fail(4, explain_failure(result))
    full = json.loads(result.stdout)
    info = {k: full.get(k) for k in INFO_KEYS}
    info["description"] = (full.get("description") or "")[:1500]
    # Track names are enough to choose a track; the signed URLs inside expire anyway.
    info["subtitles"] = sorted((full.get("subtitles") or {}).keys())
    info["automatic_captions"] = sorted((full.get("automatic_captions") or {}).keys())
    os.makedirs(vdir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)
    return info, False


def match_lang(tracks, prefs):
    for pref in prefs:
        if pref in tracks:
            return pref
    for pref in prefs:
        base = pref.split("-")[0]
        for key in tracks:
            if key.split("-")[0] == base:
                return key
    return None


def choose_track(info, prefs):
    """Prefer the speaker's own words: human captions in the spoken language, then
    auto captions in the spoken language, then a human translation in `prefs` order,
    then any human captions. Machine-translated auto tracks are never chosen (they
    contain words the speaker did not say)."""
    manual = [k for k in info["subtitles"] if k != "live_chat"]
    auto = info["automatic_captions"]
    spoken = (info.get("language") or "").split("-")[0]
    key = match_lang(manual, [spoken]) if spoken else None
    if key:
        return "manual", key
    # Videos with AI dubbing list one "-orig" track per dubbed language, so the
    # spoken language decides; a lone "-orig" track is safe only when it is the only one.
    origs = [k for k in auto if k.endswith("-orig")]
    orig = next((k for k in origs if spoken and k.split("-")[0] == spoken), None)
    if orig is None and info.get("language") in auto:
        orig = info["language"]
    if orig is None and len(origs) == 1:
        orig = origs[0]
    if orig:
        return "auto", orig
    key = match_lang(manual, prefs)
    if key:
        return "manual", key
    if manual:
        return "manual", manual[0]
    return None, None


def parse_json3(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if segs:
            yield ev.get("tStartMs", 0) / 1000.0, "".join(s.get("utf8", "") for s in segs)


CUE_TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->")


def parse_vtt_srt(path):
    """WebVTT and SRT: a time line, then text lines until a blank line."""
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    start, text = None, []
    for line in lines + [""]:
        m = CUE_TIME.search(line)
        if m:
            h, mnt, s, ms = m.groups()
            start, text = int(h or 0) * 3600 + int(mnt) * 60 + int(s) + int(ms) / 1000, []
        elif not line.strip():
            if start is not None and text:
                yield start, " ".join(text)
            start, text = None, []
        elif start is not None:
            text.append(re.sub(r"<[^>]+>", "", line).strip())


def clean_events(raw):
    """Drop empty cues and the repeated lines of rolling captions."""
    events, seen_tail = [], ""
    for t, text in raw:
        text = text.replace("\n", " ").strip()
        if not text or text == seen_tail:
            continue
        if seen_tail and text.startswith(seen_tail):  # rolling caption repeats the previous line first
            text = text[len(seen_tail):].strip()
            if not text:
                continue
        events.append((t, text))
        seen_tail = text
    return events


def fetch_captions(base, url, vdir, kind, key, refresh):
    existing = glob.glob(os.path.join(glob.escape(vdir), f"captions.{glob.escape(key)}.*"))
    if existing and not refresh:
        return existing[0], True
    require_ytdlp(base)
    flag = "--write-subs" if kind == "manual" else "--write-auto-subs"
    result = run(base + ["--skip-download", "--no-playlist", "--no-warnings", flag, "--sub-langs", key,
                         "--sub-format", SUB_FORMATS, "-o", os.path.join(vdir, "captions.%(ext)s"), url])
    if result.returncode != 0:
        fail(4, explain_failure(result))
    written = glob.glob(os.path.join(glob.escape(vdir), f"captions.{glob.escape(key)}.*"))
    if not written:
        fail(4, "Caption file was not written.")
    return written[0], False


def decode_audio(path):
    """Decode to 16 kHz mono float32 with ffmpeg (Whisper's input format).

    faster-whisper's own decoder (PyAV) breaks when PyAV changes its API, so ffmpeg,
    which yt-dlp already needs, does the decoding. Without ffmpeg, fall back to the path.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return path
    import numpy as np
    pcm = subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-i", path,
                          "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0


def transcribe(base, url, vdir, args):
    """Return (events, from_cache, detected_language, probability)."""
    hint = (args.hint or "").strip()[:HINT_MAX_CHARS]
    tag = hashlib.sha1(f"{args.whisper_model}|{args.whisper_lang}|{hint}|{args.whisper_until}"
                       .encode("utf-8")).hexdigest()[:10]
    cached = os.path.join(vdir, f"whisper-{tag}.json")
    if os.path.isfile(cached) and not args.refresh:
        with open(cached, encoding="utf-8") as f:
            d = json.load(f)
        return [tuple(e) for e in d["events"]], True, d["language"], d["probability"]
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        # `python -I` skips the per-user site-packages, where `pip install` puts packages
        # without admin rights. Add only that folder; -I's other protections stay on.
        import site
        sys.path.append(site.getusersitepackages())
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            WhisperModel = None
    if WhisperModel is None:
        fail(5, "faster-whisper is not installed. Ask the user before installing it "
                "(pip install faster-whisper; the first run also downloads the Whisper model).")
    require_ytdlp(base)
    section = ["--download-sections", f"*0-{args.whisper_until}"] if args.whisper_until else []
    result = run(base + ["--no-playlist", "--no-warnings", "-f", "bestaudio/best", *section,
                         "-o", os.path.join(vdir, "audio.%(ext)s"), url])
    audio = glob.glob(os.path.join(glob.escape(vdir), "audio.*"))
    if result.returncode != 0 or not audio:
        fail(4, explain_failure(result) if result.returncode != 0 else "Audio file was not written.")
    try:
        model = WhisperModel(args.whisper_model, device="cpu", compute_type="int8")
        segments, info = model.transcribe(decode_audio(audio[0]), language=args.whisper_lang or None,
                                          initial_prompt=hint or None, vad_filter=True)
        events = [(s.start, s.text) for s in segments]
    finally:
        for path in audio:  # audio is large and only needed once; the transcript is cached
            os.remove(path)
    with open(cached, "w", encoding="utf-8") as f:
        json.dump({"events": events, "language": info.language, "probability": info.language_probability,
                   "hint": hint, "model": args.whisper_model}, f, ensure_ascii=False)
    return events, False, info.language, info.language_probability


def stamp(seconds):
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"[{h}:{m:02d}:{sec:02d}]" if h else f"[{m}:{sec:02d}]"


def build_lines(events, chapters, joiner):
    lines, block, block_start, chap_idx = [], [], None, -1

    def flush():
        if block:
            lines.append(f"{stamp(block_start)} {joiner.join(block)}")
            block.clear()

    for t, text in events:
        chap = max((i for i, c in enumerate(chapters) if c["start_time"] <= t), default=-1)
        if chap != chap_idx and chap >= 0:
            flush()
            lines.append(f"\n## {stamp(chapters[chap]['start_time'])} {chapters[chap]['title']}")
            chap_idx, block_start = chap, None
        if block_start is None:
            block_start = t
        elif t - block_start >= BLOCK_SECONDS:
            flush()
            block_start = t
        block.append(text)
    flush()
    return lines


def language_code(key):
    # Track keys can carry an opaque id ("en-j3PyPqV-e1s"); keep the language code plus any
    # script ("Hant") or region ("TW") subtag for reporting.
    parts = key.split("-")
    return "-".join([parts[0]] + [p for p in parts[1:] if re.fullmatch(r"[A-Z][a-z]{3}|[A-Z]{2}", p)])


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--langs", default="zh-Hant,zh-TW,zh,en")
    ap.add_argument("--track", help="override choice, e.g. auto:en-orig or manual:en")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and re-download")
    ap.add_argument("--cache-dir", default=CACHE_DIR)
    ap.add_argument("--whisper", action="store_true", help="transcribe the audio locally instead of using captions")
    ap.add_argument("--hint", help="comma-separated names Whisper should expect")
    ap.add_argument("--whisper-lang", help="spoken language code, e.g. en or zh; omit to auto-detect")
    ap.add_argument("--whisper-model", default=WHISPER_MODEL)
    ap.add_argument("--whisper-until", type=int, help="transcribe only the first N seconds")
    args = ap.parse_args()

    base = ytdlp_command()
    os.makedirs(args.out_dir, exist_ok=True)
    vdir = os.path.join(args.cache_dir, cache_key(args.url))
    info, info_cached = load_info(base, args.url, vdir, args.refresh)
    extra = {}

    if args.whisper:
        events, data_cached, lang, prob = transcribe(base, args.url, vdir, args)
        caption_type, language, track = f"whisper ({args.whisper_model})", lang, "whisper"
        extra = {"whisper_language_probability": round(prob, 3), "hint": (args.hint or "")[:HINT_MAX_CHARS]}
    else:
        if args.track:
            kind, _, key = args.track.partition(":")
        else:
            kind, key = choose_track(info, [p for p in args.langs.split(",") if p])
        if not key:
            fail(3, "No usable captions. Manual: %s. Auto (first 15): %s. Either retry with --track auto:KEY "
                    "(only if KEY is the spoken language) or, after asking the user, use --whisper."
                 % (info["subtitles"], info["automatic_captions"][:15]))
        path, data_cached = fetch_captions(base, args.url, vdir, kind, key, args.refresh)
        raw = parse_json3(path) if path.endswith(".json3") else parse_vtt_srt(path)
        events = clean_events(raw)
        caption_type = "manual" if kind == "manual" else "auto-generated"
        if kind == "manual" and is_machine_caption(path):
            caption_type = "auto-generated"
            extra["caption_note"] = ("listed by the site as subtitles, but the file has per-word timing "
                                     "tags of the site's own speech recognition: treat as auto-generated")
        language, track = language_code(key), key
    events = clean_events(events) if args.whisper else events
    if not events:
        fail(3, "The transcript contained no text.")

    joiner = "" if language.lower().startswith(CJK_PREFIXES) else " "
    chapters = info.get("chapters") or []
    body = build_lines(events, chapters, joiner)
    duration = int(info.get("duration") or 0)
    page_url = info.get("webpage_url") or args.url
    header = [
        f"# {info.get('title') or info.get('id')}",
        f"URL: {page_url}",
        f"Channel: {info.get('uploader') or 'unknown'} | Duration: {stamp(duration)} | Captions: {caption_type} ({track})",
        "",
    ]
    text = "\n".join(header + body) + "\n"
    out_path = os.path.join(args.out_dir, f"{cache_key(args.url)}.transcript.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(json.dumps({
        "transcript_path": os.path.abspath(out_path), "video_id": cache_key(args.url),
        "platform": info.get("extractor_key"), "url": page_url, "title": info.get("title"),
        "channel": info.get("uploader"), "description": info.get("description", "")[:500],
        "caption_type": caption_type, "language": language, "track": track, "chars": len(text),
        "chapters": len(chapters), "duration_sec": duration,
        "cached": info_cached and data_cached, **extra,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
