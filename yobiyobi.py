# main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import requests
import random
import subprocess
import uuid
import os

app = FastAPI()

VIDEO_APIS = [
    "https://iv.melmac.space",
    "https://pol1.iv.ggtyler.dev",
    "https://cal1.iv.ggtyler.dev",
    "https://invidious.0011.lt",
    "https://yt.omada.cafe",
]

TIMEOUT = 6
HEADERS = {"User-Agent": "Mozilla/5.0"}

TMP_DIR = "tmp"
os.makedirs(TMP_DIR, exist_ok=True)


# ===============================
# Utils
# ===============================
def try_json(url, params=None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("request error:", e)
    return None


def is_video(fmt):
    return (
        fmt.get("url")
        and isinstance(fmt.get("type"), str)
        and fmt["type"].startswith("video")
    )


def is_audio(fmt):
    return (
        fmt.get("url")
        and isinstance(fmt.get("type"), str)
        and fmt["type"].startswith("audio")
    )


def is_h264(fmt):
    return "video/mp4" in (fmt.get("type") or "") and "avc1" in (fmt.get("codecs") or "")


def is_aac(fmt):
    return "audio/mp4" in (fmt.get("type") or "") and "mp4a" in (fmt.get("codecs") or "")


def video_score(fmt):
    return (
        (fmt.get("height") or 0) * 1_000_000
        + (fmt.get("fps") or 0) * 10_000
        + (fmt.get("bitrate") or 0)
    )


def audio_score(fmt):
    return fmt.get("bitrate") or 0


# ===============================
# 最適 video + audio 選択（完全版）
# ===============================
def select_best_video_audio(formats, safari=False):
    videos = [f for f in formats if is_video(f)]
    audios = [f for f in formats if is_audio(f)]

    if not videos or not audios:
        return None, None

    if safari:
        h264 = [v for v in videos if is_h264(v)]
        videos = h264 or videos

    videos.sort(key=video_score, reverse=True)
    best_video = videos[0]

    jp = [a for a in audios if "ja" in (a.get("language") or "").lower()]
    non_en = [a for a in audios if "en" not in (a.get("language") or "").lower()]
    target = jp or non_en or audios

    if safari:
        aac = [a for a in target if is_aac(a)]
        target = aac or target

    target.sort(key=audio_score, reverse=True)
    best_audio = target[0]

    return best_video, best_audio


# ===============================
# 動画＋音声 mux API（最終完成形）
# ===============================
@app.get("/api/stream/mux")
def api_stream_mux(video_id: str, safari: bool = False):
    random.shuffle(VIDEO_APIS)

    for base in VIDEO_APIS:
        data = try_json(f"{base}/api/v1/videos/{video_id}")
        if not data:
            continue

        formats = data.get("adaptiveFormats")
        if not isinstance(formats, list):
            continue

        video, audio = select_best_video_audio(formats, safari=safari)
        if not video or not audio:
            continue

        uid = uuid.uuid4().hex
        out_path = os.path.join(TMP_DIR, f"{uid}.mp4")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video["url"],
            "-i", audio["url"],
            "-c:v", "copy",
            "-c:a", "copy",
            "-movflags", "+faststart",
            out_path,
        ]

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except Exception as e:
            print("ffmpeg error:", e)
            continue

        return FileResponse(
            out_path,
            media_type="video/mp4",
            filename=f"{video_id}.mp4",
        )

    raise HTTPException(503, "mux stream failed")
