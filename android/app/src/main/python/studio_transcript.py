#!/usr/bin/env python3
r"""studio_transcript.py -- fetch a video's transcript for O'Tav'iel Studio Mode.

Order: (1) yt_dlp manual/auto English captions (YouTube, Rumble) -> parse to timed segments;
(2) if none (often TikTok), download the audio with yt_dlp+ffmpeg and transcribe locally with
faster_whisper. Returns JSON {ok,title,source,url,segments:[{t,text}],text}. No cloud.

CLI: py studio_transcript.py <url> [--whisper base] [--json-only]
"""
import argparse
import json
import os
import re
import sys
import tempfile


def _parse_vtt(path):
    segs = []
    cur_t = None
    buf = []
    tp = re.compile(r"(\d+):(\d\d):(\d\d)[.,](\d+)\s*-->")
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        m = tp.search(line)
        if m:
            if cur_t is not None and buf:
                txt = re.sub(r"<[^>]+>", "", " ".join(buf)).strip()
                if txt:
                    segs.append({"t": cur_t, "text": txt})
            h, mi, s, ms = m.groups()
            cur_t = int(h) * 3600 + int(mi) * 60 + int(s)
            buf = []
        elif line and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            buf.append(line)
        elif not line and cur_t is not None and buf:
            txt = re.sub(r"<[^>]+>", "", " ".join(buf)).strip()
            if txt:
                segs.append({"t": cur_t, "text": txt})
            buf = []
    if cur_t is not None and buf:
        txt = re.sub(r"<[^>]+>", "", " ".join(buf)).strip()
        if txt:
            segs.append({"t": cur_t, "text": txt})
    # de-dup consecutive identical lines (auto-captions repeat)
    out = []
    for s in segs:
        if not out or out[-1]["text"] != s["text"]:
            out.append(s)
    return out


def _captions(url, tmp):
    import yt_dlp
    opts = {"skip_download": True, "quiet": True, "no_warnings": True,
            "writesubtitles": True, "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en-GB", "en-orig"],
            "subtitlesformat": "vtt", "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s")}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    title = info.get("title") or ""
    vtts = [f for f in os.listdir(tmp) if f.endswith(".vtt")]
    # prefer a manual/non-auto track if present (shorter filename usually), else any
    vtts.sort(key=len)
    for f in vtts:
        segs = _parse_vtt(os.path.join(tmp, f))
        if segs:
            return title, segs
    return title, []


def _whisper(url, tmp, model_size):
    import yt_dlp
    from faster_whisper import WhisperModel
    opts = {"quiet": True, "no_warnings": True, "format": "bestaudio/best",
            "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    title = info.get("title") or ""
    audio = None
    for f in os.listdir(tmp):
        if f.startswith("audio."):
            audio = os.path.join(tmp, f)
            break
    if not audio:
        return title, []
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segs_it, _ = model.transcribe(audio, language="en", vad_filter=True)
    return title, [{"t": int(s.start), "text": s.text.strip()} for s in segs_it if s.text.strip()]


def transcript(url, model_size="base"):
    with tempfile.TemporaryDirectory() as tmp:
        try:
            title, segs = _captions(url, tmp)
        except Exception as e:
            title, segs = "", []
        used = "captions"
        if not segs:
            used = "whisper"
            try:
                title2, segs = _whisper(url, tmp, model_size)
                title = title or title2
            except Exception as e:
                return {"ok": False, "error": "no captions and whisper failed: %s" % (type(e).__name__), "url": url}
    text = " ".join(s["text"] for s in segs)
    return {"ok": bool(segs), "title": title, "source": used, "url": url,
            "segments": segs, "text": text}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--whisper", default="base")
    a = p.parse_args()
    r = transcript(a.url, a.whisper)
    print(json.dumps({k: v for k, v in r.items() if k != "segments"} |
                     {"n_segments": len(r.get("segments", []))}))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
