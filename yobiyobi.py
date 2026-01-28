import random
import requests
import urllib.parse

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

app = FastAPI()

INVIDIOUS_INSTANCES = [
    'https://inv.nadeko.net/',
    'https://invidious.f5.si/',
    'https://invidious.lunivers.trade/',
    'https://invidious.ducks.party/',
    'https://super8.absturztau.be/',
    'https://invidious.nikkosphere.com/',
    'https://yt.omada.cafe/',
    'https://iv.melmac.space/',
    'https://iv.duti.dev/',
]

STREAM_API = "https://ytdl-0et1.onrender.com/stream/"
M3U8_API   = "https://ytdl-0et1.onrender.com/m3u8/"


# =========================
# utils
# =========================

def pick_instance():
    return random.choice(INVIDIOUS_INSTANCES).rstrip("/")


def get_invidious_video(video_id: str):
    inst = pick_instance()
    url = f"{inst}/api/v1/videos/{video_id}"
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    return r.json()


def extract_best_progressive(data: dict):
    formats = data.get("formatStreams", [])
    videos = [
        f for f in formats
        if f.get("type", "").startswith("video/")
        and f.get("audioQuality")
        and f.get("url")
    ]
    videos.sort(key=lambda x: x.get("qualityLabel", ""), reverse=True)
    return videos[0]["url"] if videos else None


def extract_1080p_progressive(data: dict):
    formats = data.get("formatStreams", [])
    videos = [
        f for f in formats
        if f.get("type", "").startswith("video/")
        and f.get("audioQuality")
        and f.get("url")
    ]

    for v in videos:
        if v.get("qualityLabel") == "1080p":
            return v["url"]

    videos.sort(key=lambda x: x.get("qualityLabel", ""), reverse=True)
    return videos[0]["url"] if videos else None


# =========================
# yobi（m3u8 → 1080p fallback）
# =========================

@app.get("/api/streamurl/yobi")
def yobi_stream(video_id: str = Query(...)):
    m3u8_url = urllib.parse.urljoin(M3U8_API, video_id)

    try:
        r = requests.head(
            m3u8_url,
            allow_redirects=True,
            timeout=6
        )
        ct = r.headers.get("Content-Type", "").lower()

        if "mpegurl" in ct or ".m3u8" in r.url:
            return RedirectResponse(r.url)
    except Exception:
        pass

    try:
        data = get_invidious_video(video_id)
        url = extract_1080p_progressive(data)
        if url:
            return RedirectResponse(url)
    except Exception:
        pass

    try:
        return RedirectResponse(f"{STREAM_API}{video_id}")
    except Exception:
        pass

    raise HTTPException(status_code=404)


# =========================
# yobiyobi（progressive 専用）
# =========================

@app.get("/api/streamurl/yobiyobi")
def yobiyobi_stream(video_id: str = Query(...)):
    try:
        data = get_invidious_video(video_id)
        url = extract_best_progressive(data)
        if url:
            return RedirectResponse(url)
    except Exception:
        pass

    try:
        return RedirectResponse(f"{STREAM_API}{video_id}")
    except Exception:
        pass

    raise HTTPException(status_code=404)


# =========================
# Content-Type / HEAD 判定
# =========================

@app.get("/api/streammeta")
def stream_meta(
    video_id: str = Query(...),
    backend: str = Query("main")
):
    if backend == "yobi":
        url = f"/api/streamurl/yobi?video_id={video_id}"
    elif backend == "yobiyobi":
        url = f"/api/streamurl/yobiyobi?video_id={video_id}"
    else:
        url = f"/api/streamurl?video_id={video_id}"

    try:
        r = requests.head(
            url,
            allow_redirects=True,
            timeout=6
        )
        ct = r.headers.get("Content-Type", "").lower()

        if "mpegurl" in ct:
            stream_type = "m3u8"
        elif "video/" in ct:
            stream_type = "mp4"
        else:
            stream_type = "m3u8" if ".m3u8" in r.url else "mp4"

        return JSONResponse({
            "url": r.url,
            "type": stream_type,
            "backend": backend
        })

    except Exception:
        return JSONResponse(
            {"error": "streammeta_failed"},
            status_code=500
        )
