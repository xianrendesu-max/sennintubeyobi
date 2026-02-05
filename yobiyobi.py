from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import requests
import random
import os
import subprocess
import uuid

app = FastAPI()

# ===============================
# Static
# ===============================
# Render で statics が無くても即死しないようにする
if os.path.isdir("statics"):
    app.mount("/static", StaticFiles(directory="statics"), name="static")

    # ★ 仙人music
    if os.path.isdir("statics/music"):
        app.mount("/music", StaticFiles(directory="statics/music", html=True), name="music")
    else:
        print("⚠ statics/music directory not found (skipped mount)")
else:
    print("⚠ statics directory not found (skipped mount)")

@app.get("/")
def root():
    if os.path.isfile("statics/index.html"):
        return FileResponse("statics/index.html")
    return {"status": "index.html not found"}

# ===============================
# API BASE LIST
# ===============================
VIDEO_APIS = [
    "https://iv.melmac.space",
    "https://pol1.iv.ggtyler.dev",
    "https://cal1.iv.ggtyler.dev",
    "https://invidious.0011.lt",
    "https://yt.omada.cafe",
]

SEARCH_APIS = VIDEO_APIS

COMMENTS_APIS = [
    "https://invidious.lunivers.trade",
    "https://invidious.ducks.party",
    "https://super8.absturztau.be",
    "https://invidious.nikkosphere.com",
    "https://yt.omada.cafe",
    "https://iv.melmac.space",
    "https://iv.duti.dev",
]

EDU_STREAM_API_BASE_URL = "https://raw.githubusercontent.com/toka-kun/Education/refs/heads/main/keys/key1.json"
STREAM_YTDL_API_BASE_URL = "https://yudlp.vercel.app/stream/"
SHORT_STREAM_API_BASE_URL = "https://yt-dl-kappa.vercel.app/short/"

TIMEOUT = 6

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

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

# ===============================
# Search
# ===============================
@app.get("/api/search")
def api_search(q: str):
    results = []
    random.shuffle(SEARCH_APIS)

    for base in SEARCH_APIS:
        data = try_json(f"{base}/api/v1/search", {"q": q, "type": "video"})
        if not isinstance(data, list):
            continue

        for v in data:
            if not v.get("videoId"):
                continue

            results.append({
                "videoId": v.get("videoId"),
                "title": v.get("title"),
                "author": v.get("author"),
                "authorId": v.get("authorId"),
            })

        if results:
            return {
                "count": len(results),
                "results": results,
                "source": base
            }

    raise HTTPException(status_code=503, detail="Search unavailable")

# ===============================
# Video Info
# ===============================
@app.get("/api/video")
def api_video(video_id: str):
    random.shuffle(VIDEO_APIS)

    for base in VIDEO_APIS:
        data = try_json(f"{base}/api/v1/videos/{video_id}")
        if data:
            return {
                "title": data.get("title"),
                "author": data.get("author"),
                "description": data.get("description"),
                "viewCount": data.get("viewCount"),
                "lengthSeconds": data.get("lengthSeconds"),
                "source": base
            }

    raise HTTPException(status_code=503, detail="Video info unavailable")

# ===============================
# Comments
# ===============================
@app.get("/api/comments")
def api_comments(video_id: str):
    for base in COMMENTS_APIS:
        data = try_json(f"{base}/api/v1/comments/{video_id}")
        if data:
            return {
                "comments": [
                    {
                        "author": c.get("author"),
                        "content": c.get("content")
                    }
                    for c in data.get("comments", [])
                ],
                "source": base
            }
    return {"comments": [], "source": None}

# ===============================
# Channel（完全版・修整済）
# ===============================
@app.get("/api/channel")
def api_channel(c: str):
    random.shuffle(VIDEO_APIS)

    for base in VIDEO_APIS:
        ch = try_json(f"{base}/api/v1/channels/{c}")
        if not ch:
            continue

        latest_videos = []

        for v in ch.get("latestVideos", []):
            published_raw = v.get("published")
            published_iso = None

            if isinstance(published_raw, str):
                try:
                    published_iso = published_raw.replace("Z", "+00:00")
                except:
                    published_iso = None

            latest_videos.append({
                "videoId": v.get("videoId"),
                "title": v.get("title"),
                "author": ch.get("author"),
                "authorId": c,
                "viewCount": v.get("viewCount") or 0,
                "viewCountText": v.get("viewCountText") or "0 回視聴",
                "published": published_iso,
                "publishedText": v.get("publishedText") or ""
            })

        view_count = ch.get("viewCount")
        video_count = ch.get("videoCount")
        joined_date = ch.get("joinedDate")

        if not isinstance(video_count, int):
            video_count = len(latest_videos)

        if not isinstance(joined_date, str):
            published_dates = [
                v["published"]
                for v in latest_videos
                if isinstance(v.get("published"), str)
            ]
            joined_date = min(published_dates) if published_dates else None

        related_channels = []

        for r in ch.get("relatedChannels", []):
            icon = None
            thumbs = r.get("authorThumbnails")

            if isinstance(thumbs, list) and thumbs:
                icon = thumbs[-1].get("url")

            related_channels.append({
                "channelId": r.get("authorId"),
                "name": r.get("author"),
                "icon": icon,
                "subCountText": r.get("subCountText") or "?"
            })

        return {
            "author": ch.get("author"),
            "authorId": c,
            "authorThumbnails": ch.get("authorThumbnails"),
            "description": ch.get("description") or "",
            "subCount": ch.get("subCount") or 0,
            "viewCount": view_count or 0,
            "videoCount": video_count,
            "joinedDate": joined_date,
            "latestVideos": latest_videos,
            "relatedChannels": related_channels,
            "source": base
        }

    raise HTTPException(status_code=503, detail="Channel unavailable")

# ===============================
# Stream URL ONLY（yobiyobi / iOS対応・映像＋音声合成）
# ===============================
@app.get("/api/streamurl/yobiyobi")
def api_streamurl_yobiyobi(video_id: str, quality: str = "best"):
    for base in VIDEO_APIS:
        data = try_json(f"{base}/api/v1/videos/{video_id}")
        if not data:
            continue

        video_url = None
        audio_url = None

        for f in data.get("adaptiveFormats", []):
            if f.get("type", "").startswith("video") and f.get("url"):
                if quality == "best" or quality in (f.get("qualityLabel") or ""):
                    video_url = f["url"]
                    break

        for f in data.get("adaptiveFormats", []):
            if f.get("type", "").startswith("audio") and f.get("url"):
                lang = (f.get("language") or "").lower()
                if "en" in lang:
                    continue
                audio_url = f["url"]
                break

        if not video_url or not audio_url:
            continue

        out = f"/tmp/{uuid.uuid4()}.mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_url,
            "-i", audio_url,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-profile:v", "main",
            "-level", "3.1",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ac", "2",
            "-ar", "44100",
            "-af", "aresample=async=1",
            "-movflags", "+faststart",
            out
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return RedirectResponse(out)

    raise HTTPException(status_code=503, detail="yobiyobi stream unavailable")

# ===============================
# Stream URL ONLY（旧）
# ===============================
@app.get("/api/streamurl")
def api_streamurl(video_id: str, quality: str = "best"):
    for base in [
        EDU_STREAM_API_BASE_URL,
        STREAM_YTDL_API_BASE_URL,
        SHORT_STREAM_API_BASE_URL
    ]:
        data = try_json(f"{base}{video_id}", {"quality": quality})
        if data and data.get("url"):
            return RedirectResponse(data["url"])

    for base in VIDEO_APIS:
        data = try_json(f"{base}/api/v1/videos/{video_id}")
        if not data:
            continue

        for f in data.get("adaptiveFormats", []):
            if not f.get("url"):
                continue

            lang = (f.get("language") or "").lower()
            audio_track = str(f.get("audioTrack") or "").lower()

            if "en" in lang:
                continue
            if "english" in audio_track:
                continue

            label = f.get("qualityLabel") or ""

            if quality == "best" or quality in label:
                return RedirectResponse(f["url"])

    raise HTTPException(status_code=503, detail="Stream unavailable")

from music import router as music_router
app.include_router(music_router)
