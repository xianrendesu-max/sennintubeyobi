# main.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import requests
import random
import subprocess
import uuid
import os
import threading

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
# 最適 video + audio 選択
# ===============================
def select_best_video_audio(formats, safari=False):
    videos = [f for f in formats if is_video(f)]
    audios = [f for f in formats if is_audio(f)]

    if not videos or not audios:
        return None, None

    h264 = [v for v in videos if is_h264(v)]
    if safari:
        videos = h264 or videos
    else:
        if h264:
            videos = h264

    videos.sort(key=video_score, reverse=True)
    best_video = videos[0]

    jp = [a for a in audios if "ja" in (a.get("language") or "").lower()]
    non_en = [a for a in audios if "en" not in (a.get("language") or "").lower()]
    target = jp or non_en or audios

    aac = [a for a in target if is_aac(a)]
    if safari:
        target = aac or target
    else:
        if aac:
            target = aac

    target.sort(key=audio_score, reverse=True)
    best_audio = target[0]

    return best_video, best_audio


# ===============================
# tmp 自動削除
# ===============================
def delete_later(path, delay=60):
    def _del():
        try:
            os.remove(path)
        except Exception:
            pass
    threading.Timer(delay, _del).start()


# ===============================
# 動画＋音声 mux + Range 対応
# ===============================
@app.get("/api/stream/mux")
def api_stream_mux(request: Request, video_id: str, safari: bool = False):
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

        use_copy = is_h264(video) and is_aac(audio)
        cmd = [
            "ffmpeg",
            "-y",
            "-headers", "User-Agent: Mozilla/5.0\r\n",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", video["url"],
            "-headers", "User-Agent: Mozilla/5.0\r\n",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", audio["url"],
        ]

        if use_copy:
            cmd += [
                "-c:v", "copy",
                "-c:a", "copy",
            ]
        else:
            cmd += [
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-c:a", "aac",
            ]

        cmd += [
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

        file_size = os.path.getsize(out_path)
        range_header = request.headers.get("range")

        def file_iterator(start=0, end=None, chunk_size=1024 * 1024):
            with open(out_path, "rb") as f:
                f.seek(start)
                remaining = (end - start + 1) if end else None
                while True:
                    chunk = f.read(chunk_size if not remaining else min(chunk_size, remaining))
                    if not chunk:
                        break
                    if remaining:
                        remaining -= len(chunk)
                    yield chunk

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": "video/mp4",
        }

        if range_header:
            start, end = range_header.replace("bytes=", "").split("-")
            start = int(start)
            end = int(end) if end else file_size - 1

            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            headers["Content-Length"] = str(end - start + 1)

            delete_later(out_path)
            return StreamingResponse(
                file_iterator(start, end),
                status_code=206,
                headers=headers,
            )

        headers["Content-Length"] = str(file_size)
        delete_later(out_path)
        return StreamingResponse(
            file_iterator(),
            headers=headers,
        )

    raise HTTPException(503, "mux stream failed")
