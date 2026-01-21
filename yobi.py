from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import requests
import random
import os

app = FastAPI()

# ===============================
# Static
# ===============================
if os.path.isdir("statics"):
    app.mount("/static", StaticFiles(directory="statics"), name="static")
else:
    print("⚠ statics directory not found (skipped mount)")

@app.get("/")
def root():
    if os.path.isfile("statics/index.html"):
        return FileResponse("statics/index.html")
    return {"status": "index.html not found"}

# ===============================
# API BASE LIST（既存）
# ===============================
VIDEO_APIS = [
    "https://iv.melmac.space",
    "https://pol1.iv.ggtyler.dev",
    "https://cal1.iv.ggtyler.dev",
    "https://invidious.0011.lt",
    "https://yt.omada.cafe",
]

SEARCH_APIS = VIDEO_APIS.copy()

COMMENTS_APIS = [
    "https://invidious.lunivers.trade",
    "https://invidious.ducks.party",
    "https://super8.absturztau.be",
    "https://invidious.nikkosphere.com",
    "https://yt.omada.cafe",
    "https://iv.melmac.space",
    "https://iv.duti.dev",
]

# ===============================
# API BASE LIST（追加分）
# ===============================
VIDEO_APIS_EXTRA = [
    "https://invidious.exma.de/",
    "https://invidious.f5.si/",
    "https://siawaseok-wakame-server2.glitch.me/",
    "https://lekker.gay/",
    "https://id.420129.xyz/",
    "https://invid-api.poketube.fun/",
    "https://eu-proxy.poketube.fun/",
    "https://cal1.iv.ggtyler.dev/",
    "https://pol1.iv.ggtyler.dev/",
]

SEARCH_APIS_EXTRA = [
    "https://pol1.iv.ggtyler.dev/",
    "https://youtube.mosesmang.com/",
    "https://iteroni.com/",
    "https://invidious.0011.lt/",
    "https://iv.melmac.space/",
    "https://rust.oskamp.nl/",
]

CHANNEL_APIS_EXTRA = [
    "https://siawaseok-wakame-server2.glitch.me/",
    "https://id.420129.xyz/",
    "https://invidious.0011.lt/",
    "https://invidious.nietzospannend.nl/",
]

PLAYLIST_APIS_EXTRA = [
    "https://siawaseok-wakame-server2.glitch.me/",
    "https://invidious.0011.lt/",
    "https://invidious.nietzospannend.nl/",
    "https://youtube.mosesmang.com/",
    "https://iv.melmac.space/",
    "https://lekker.gay/",
]

COMMENTS_APIS_EXTRA = [
    "https://siawaseok-wakame-server2.glitch.me/",
    "https://invidious.0011.lt/",
    "https://invidious.nietzospannend.nl/",
]

# ===============================
# API BASE LIST（統合）
# ===============================
VIDEO_APIS = list(dict.fromkeys(VIDEO_APIS + VIDEO_APIS_EXTRA))
SEARCH_APIS = list(dict.fromkeys(SEARCH_APIS + SEARCH_APIS_EXTRA))
COMMENTS_APIS = list(dict.fromkeys(COMMENTS_APIS + COMMENTS_APIS_EXTRA))
CHANNEL_APIS = VIDEO_APIS + CHANNEL_APIS_EXTRA
PLAYLIST_APIS = PLAYLIST_APIS_EXTRA

# ===============================
# Stream APIs
# ===============================
STREAM_YTDL_API_BASE_URL = "https://yudlp.vercel.app/stream/"
SHORT_STREAM_API_BASE_URL = "https://yt-dl-kappa.vercel.app/short/"
HLS_API_BASE_URL = "https://yudlp.vercel.app/m3u8/"

TIMEOUT = 6
HEADERS = {"User-Agent": "Mozilla/5.0"}

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
def api_search(q: str, type: str = "all"):
    results = []
    random.shuffle(SEARCH_APIS)

    for base in SEARCH_APIS:
        data = try_json(
            f"{base}/api/v1/search",
            {"q": q, "type": "video"}
        )
        if not isinstance(data, list):
            continue

        for v in data:
            if not v.get("videoId"):
                continue

            length = int(v.get("lengthSeconds") or 0)

            if type == "shorts" and length >= 60:
                continue
            if type == "video" and length < 60:
                continue

            results.append({
                "videoId": v.get("videoId"),
                "title": v.get("title"),
                "author": v.get("author"),
                "authorId": v.get("authorId"),
                "lengthSeconds": length,
                "published": v.get("published"),
                "publishedText": v.get("publishedText") or ""
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
                    {"author": c.get("author"), "content": c.get("content")}
                    for c in data.get("comments", [])
                ],
                "source": base
            }
    return {"comments": [], "source": None}

# ===============================
# Channel
# ===============================
@app.get("/api/channel")
def api_channel(c: str):
    random.shuffle(CHANNEL_APIS)

    for base in CHANNEL_APIS:
        ch = try_json(f"{base}/api/v1/channels/{c}")
        if not ch:
            continue

        latest_videos = []
        for v in ch.get("latestVideos", []):
            latest_videos.append({
                "videoId": v.get("videoId"),
                "title": v.get("title"),
                "author": ch.get("author"),
                "authorId": c,
                "viewCount": v.get("viewCount") or 0,
                "viewCountText": v.get("viewCountText") or "0 回視聴",
                "published": v.get("published"),
                "publishedText": v.get("publishedText") or ""
            })

        return {
            "author": ch.get("author"),
            "authorId": c,
            "authorThumbnails": ch.get("authorThumbnails"),
            "description": ch.get("description") or "",
            "subCount": ch.get("subCount") or 0,
            "viewCount": ch.get("viewCount") or 0,
            "videoCount": ch.get("videoCount") or len(latest_videos),
            "joinedDate": ch.get("joinedDate"),
            "latestVideos": latest_videos,
            "relatedChannels": ch.get("relatedChannels", []),
            "source": base
        }

    raise HTTPException(status_code=503, detail="Channel unavailable")

# ===============================
# Stream URL（main互換）
# ===============================
@app.get("/api/streamurl")
def api_streamurl(video_id: str):
    try:
        data = try_json(f"{HLS_API_BASE_URL}{video_id}")
        if data:
            m3u8s = [f for f in data.get("m3u8_formats", []) if f.get("url")]
            if m3u8s:
                best = sorted(
                    m3u8s,
                    key=lambda f: int((f.get("resolution") or "0x0").split("x")[-1]),
                    reverse=True
                )[0]
                return RedirectResponse(best["url"])
    except Exception:
        pass

    for base in [STREAM_YTDL_API_BASE_URL, SHORT_STREAM_API_BASE_URL]:
        data = try_json(f"{base}{video_id}")
        if not data:
            continue

        for f in data.get("formats", []):
            if f.get("itag") == "18" and f.get("url"):
                return RedirectResponse(f["url"])

    random.shuffle(VIDEO_APIS)
    for base in VIDEO_APIS:
        data = try_json(f"{base}/api/v1/videos/{video_id}")
        if not data:
            continue

        for f in data.get("formatStreams", []):
            if f.get("url"):
                return RedirectResponse(f["url"])

    raise HTTPException(status_code=503, detail="Stream unavailable")

# ===============================
# Stream URL（yobi専用：UI切替用）
# ===============================
@app.get("/api/streamurl/yobi")
def api_streamurl_yobi(video_id: str):
    try:
        data = try_json(f"{HLS_API_BASE_URL}{video_id}")
        if data:
            m3u8s = [f for f in data.get("m3u8_formats", []) if f.get("url")]
            if m3u8s:
                best = sorted(
                    m3u8s,
                    key=lambda f: int((f.get("resolution") or "0x0").split("x")[-1]),
                    reverse=True
                )[0]
                return RedirectResponse(best["url"])
    except Exception:
        pass

    for base in [STREAM_YTDL_API_BASE_URL, SHORT_STREAM_API_BASE_URL]:
        data = try_json(f"{base}{video_id}")
        if not data:
            continue

        for f in data.get("formats", []):
            if f.get("itag") == "18" and f.get("url"):
                return RedirectResponse(f["url"])

    random.shuffle(VIDEO_APIS)
    for base in VIDEO_APIS:
        data = try_json(f"{base}/api/v1/videos/{video_id}")
        if not data:
            continue

        for f in data.get("formatStreams", []):
            if f.get("url"):
                return RedirectResponse(f["url"])

    raise HTTPException(status_code=503, detail="Stream unavailable")
