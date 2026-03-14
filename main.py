import json
import urllib.parse
import time
import datetime
import os
import asyncio
import base64

# cache.py が同ディレクトリに存在することを前提としています
try:
    from cache import cache
except ImportError:
    # キャッシュデコレータのスタブ（cache.pyがない場合用）
    def cache(seconds=30):
        def decorator(f):
            return f
        return decorator

from flask import Flask, request, response, render_template, redirect, make_response, send_from_directory, abort, Response as FlaskResponse
from flask_compress import Compress
import httpx
from bs4 import BeautifulSoup

# =========================
# 基本設定
# =========================

max_api_wait_time = 3
max_time = 10
version = "1.0"

apis = [
    "https://yewtu.be/",
    "https://invidious.f5.si/",
    "https://invidious.perennialte.ch/",
    "https://iv.nboeck.de/",
    "https://invidious.jing.rocks/",
    "https://yt.omada.cafe/",
    "https://invidious.reallyaweso.me/",
    "https://invidious.privacyredirect.com/",
    "https://invidious.nerdvpn.de/",
    "https://iv.nowhere.moe/",
    "https://inv.tux.pizza/",
    "https://invidious.private.coffee/",
    "https://iv.ggtyler.dev/",
    "https://iv.datura.network/",
    "https://yt.cdaut.de/",
]

apichannels = apis.copy()
apicomments = apis.copy()

if os.path.exists("./senninverify"):
    try:
        os.chmod("./senninverify", 0o755)
    except:
        pass

# =========================
# 例外
# =========================

class APItimeoutError(Exception):
    pass

# =========================
# 共通
# =========================

def check_cookie(cookie_value) -> bool:
    return cookie_value == "True"

def run_async(coro):
    """Flask(同期)からasync関数を呼び出すためのヘルパー"""
    return asyncio.run(coro)

# =========================
# 並列API最速勝ち
# =========================

async def api_request_core(api_list, url):
    start = time.time()
    lock = asyncio.Lock()

    async def fetch(client, api):
        try:
            r = await client.get(api + url, timeout=max_api_wait_time)
            r.raise_for_status()
            return api, r.text
        except:
            return None

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        tasks = [fetch(client, api) for api in api_list[:8]]
        # asyncio.as_completed をそのまま利用
        for fut in asyncio.as_completed(tasks, timeout=max_time):
            try:
                result = await fut
            except asyncio.TimeoutError:
                continue
            if not result:
                continue
            api, text = result
            try:
                json.loads(text)
            except:
                continue
            async with lock:
                if api in api_list:
                    api_list.remove(api)
                    api_list.insert(0, api)
            return text

    raise APItimeoutError("API timeout")

async def apirequest(url):
    return await api_request_core(apis, url)

async def apichannelrequest(url):
    return await api_request_core(apichannels, url)

async def apicommentsrequest(url):
    return await api_request_core(apicomments, url)

# =========================
# APIラッパー
# =========================

@cache(seconds=30)
async def get_search(q, page):
    data = json.loads(
        await apirequest(f"api/v1/search?q={urllib.parse.quote(q)}&page={page}&hl=jp")
    )

    results = []
    for i in data:
        t = i.get("type")
        if t == "video":
            results.append({
                "type": "video",
                "title": i["title"],
                "id": i["videoId"],
                "author": i["author"],
                "authorId": i["authorId"],
                "length": str(datetime.timedelta(seconds=i["lengthSeconds"])),
                "published": i["publishedText"]
            })
        elif t == "playlist":
            results.append({
                "type": "playlist",
                "title": i["title"],
                "id": i["playlistId"],
                "count": i["videoCount"]
            })
        else:
            thumb = i["authorThumbnails"][-1]["url"]
            if not thumb.startswith("https"):
                thumb = "https://" + thumb
            results.append({
                "type": "channel",
                "author": i["author"],
                "id": i["authorId"],
                "thumbnail": thumb
            })
    return results

# =========================
# ★ DASH対応
# =========================

async def get_data(videoid):
    t = json.loads(await apirequest("api/v1/videos/" + urllib.parse.quote(videoid)))

    videourls = [i["url"] for i in t.get("formatStreams", [])]
    hls_url = t.get("hlsUrl")
    nocookie_url = f"https://www.youtube-nocookie.com/embed/{videoid}"

    adaptive = t.get("adaptiveFormats", [])

    audio = None
    videos = {}

    for f in adaptive:
        mime = f.get("type", "")
        if mime.startswith("audio/"):
            if not audio or f.get("bitrate", 0) > audio.get("bitrate", 0):
                audio = f
        elif mime.startswith("video/"):
            h = f.get("height")
            if h and (h not in videos or "mp4" in mime):
                videos[h] = f

    dash = None
    if audio and videos:
        dash = {
            "audio": {
                "url": audio["url"],
                "mime": audio["type"],
                "bitrate": audio.get("bitrate")
            },
            "videos": {
                str(h): {
                    "url": videos[h]["url"],
                    "mime": videos[h]["type"],
                    "fps": videos[h].get("fps"),
                    "bitrate": videos[h].get("bitrate")
                }
                for h in sorted(videos.keys(), reverse=True)
            }
        }

    return (
        [{"id": i["videoId"], "title": i["title"], "author": i["author"], "authorId": i["authorId"]}
         for i in t["recommendedVideos"]],
        videourls,
        t["descriptionHtml"].replace("\n", "<br>"),
        t["title"],
        t["authorId"],
        t["author"],
        t["authorThumbnails"][-1]["url"],
        nocookie_url,
        hls_url,
        dash,
        t
    )

# =========================
# ★ チャンネル
# =========================

async def get_channel(channelid):
    t = json.loads(await apichannelrequest("api/v1/channels/" + urllib.parse.quote(channelid)))

    videos = []
    shorts = []

    for i in t.get("latestVideos", []):
        videos.append({
            "title": i["title"],
            "id": i["videoId"],
            "view_count_text": i.get("viewCountText", ""),
            "length_str": i.get("lengthText", "")
        })

    return (
        videos,
        shorts,
        {
            "channelname": t["author"],
            "channelicon": t["authorThumbnails"][-1]["url"],
            "channelprofile": t.get("description", ""),
            "subscribers_count": t.get("subCountText"),
            "cover_img_url": t["authorBanners"][-1]["url"] if t.get("authorBanners") else None
        }
    )

# =========================
# ホーム
# =========================

@cache(seconds=30)
async def get_home():
    data = json.loads(await apirequest("api/v1/popular?hl=jp"))

    videos = []
    shorts = []
    channels = []

    for i in data:
        if i.get("type") == "video":
            if i.get("isShort") or not i.get("lengthSeconds"):
                shorts.append(i)
            else:
                videos.append(i)
        elif i.get("type") == "channel":
            channels.append(i)

    return videos, shorts, channels

async def get_comments(videoid):
    t = json.loads(await apicommentsrequest("api/v1/comments/" + urllib.parse.quote(videoid) + "?hl=jp"))
    return [{
        "author": i["author"],
        "authoricon": i["authorThumbnails"][-1]["url"],
        "body": i["contentHtml"].replace("\n", "<br>")
    } for i in t["comments"]]

# =========================
# Flask Setup
# =========================

app = Flask(__name__, static_folder=None)
Compress(app)

# 静的ファイル設定 (FastAPIのmountの代替)
@app.route('/css/<path:filename>')
def custom_static_css(filename):
    return send_from_directory('./css', filename)

@app.route('/word/')
@app.route('/word/<path:filename>')
def custom_static_word(filename="index.html"):
    return send_from_directory('./blog', filename)

# =========================
# 高画質ストリーム
# =========================

STREAM_API = "https://ytdl-0et1.onrender.com/stream/"
M3U8_API   = "https://ytdl-0et1.onrender.com/m3u8/"

@app.route("/stream/high")
def stream_high():
    v = request.args.get("v")
    try:
        return redirect(f"{M3U8_API}{v}")
    except:
        pass

    try:
        return redirect(f"{STREAM_API}{v}")
    except:
        pass

    t_str = run_async(apirequest("api/v1/videos/" + urllib.parse.quote(v)))
    t = json.loads(t_str)
    if t.get("hlsUrl"):
        return redirect(t["hlsUrl"])

    abort(503, description="High quality stream unavailable")

# =========================
# ルーティング
# =========================

@app.route("/")
def home():
    sennin = request.cookies.get("sennin")
    if not check_cookie(sennin):
        return redirect("/word")

    videos, shorts, channels = run_async(get_home())

    resp = make_response(render_template(
        "home.html",
        videos=videos,
        shorts=shorts,
        channels=channels,
    ))
    resp.set_cookie("sennin", "True", max_age=7 * 24 * 60 * 60)
    return resp

@app.route("/search")
def search():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    sennin = request.cookies.get("sennin")
    
    if not check_cookie(sennin):
        return redirect("/")
    
    results = run_async(get_search(q, page))
    
    resp = make_response(render_template(
        "search.html",
        results=results,
        word=q,
        next=f"/search?q={q}&page={page+1}",
    ))
    resp.set_cookie("sennin", "True", max_age=7 * 24 * 60 * 60)
    return resp

@app.route("/watch")
def watch():
    v = request.args.get("v")
    sennin = request.cookies.get("sennin")
    
    if not check_cookie(sennin):
        return redirect("/")

    data = run_async(get_data(v))
    t = data[10]

    if t.get("isShort") is True:
        template = "shorts.html"
        context = {
            "videoid": v,
            "author": t["author"],
            "authorid": t["authorId"],
            "authoricon": t["authorThumbnails"][-1]["url"],
            "title": t["title"],
            "hls_url": t.get("hlsUrl"),
        }
    else:
        template = "video.html"
        context = {
            "videoid": v,
            "videourls": data[1],
            "res": data[0],
            "description": data[2],
            "videotitle": data[3],
            "authorid": data[4],
            "author": data[5],
            "authoricon": data[6],
            "nocookie_url": data[7],
            "hls_url": data[8],
            "dash": data[9],
        }

    resp = make_response(render_template(template, **context))
    resp.set_cookie("sennin", "True", max_age=7 * 24 * 60 * 60)
    return resp

@app.route("/channel/<cid>")
def channel(cid):
    sennin = request.cookies.get("sennin")
    if not check_cookie(sennin):
        return redirect("/")

    videos, shorts, info = run_async(get_channel(cid))

    resp = make_response(render_template(
        "channel.html",
        results=videos,
        shorts=shorts,
        channelname=info["channelname"],
        channelicon=info["channelicon"],
        channelprofile=info["channelprofile"],
        subscribers_count=info["subscribers_count"],
        cover_img_url=info["cover_img_url"],
    ))
    resp.set_cookie("sennin", "True", max_age=7 * 24 * 60 * 60)
    return resp

@app.route("/subuscript")
def subuscript():
    sennin = request.cookies.get("sennin")
    if not check_cookie(sennin):
        return redirect("/")
    return render_template("subuscript.html")

@app.route("/comments")
def comments():
    v = request.args.get("v")
    comment_data = run_async(get_comments(v))
    return render_template("comments.html", comments=comment_data)

@app.route("/thumbnail")
def thumbnail():
    v = request.args.get("v")
    
    async def fetch_thumb():
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://img.youtube.com/vi/{v}/0.jpg")
            return r.content
            
    content = run_async(fetch_thumb())
    return FlaskResponse(content, mimetype="image/jpeg")

# ============================================================
# ★★★ X (Nitter系) 統合 ★★★
# ============================================================

X_INSTANCES = [
    "https://nitter.net",
    "https://xcancel.com",
    "https://nuku.trabun.org",
]

async def x_fetch(path: str):
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, timeout=max_api_wait_time) as client:
        for base in X_INSTANCES:
            try:
                r = await client.get(base + path, follow_redirects=True)
                r.raise_for_status()
                return r.text, base
            except:
                continue
    raise APItimeoutError("X fetch failed")

def encode_media_url(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode()).decode()

def decode_media_url(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode()).decode()

def parse_x_tweets(html: str, base: str):
    soup = BeautifulSoup(html, "lxml")
    tweets = []

    for item in soup.select(".timeline-item"):
        content = item.select_one(".tweet-content")
        if not content:
            continue

        text = content.get_text("\n", strip=True)

        images = []
        for img in item.select("a.still-image img"):
            src = img.get("src")
            if src:
                if not src.startswith("http"):
                    src = base + src
                images.append("/x/media?u=" + encode_media_url(src))

        videos = []
        for v in item.select("video source"):
            src = v.get("src")
            if src:
                if not src.startswith("http"):
                    src = base + src
                videos.append("/x/media?u=" + encode_media_url(src))

        tweets.append({
            "text": text,
            "images": images,
            "videos": videos,
        })

    return tweets

@app.route("/api/x/search")
@cache(seconds=60)
def x_search_api():
    q = request.args.get("q", "")
    async def get_x():
        html, base = await x_fetch("/search?f=tweets&q=" + urllib.parse.quote(q))
        return {"query": q, "tweets": parse_x_tweets(html, base)}
    
    return run_async(get_x())

@app.route("/x/search")
def x_search_page():
    q = request.args.get("q", "")
    # APIルートの関数を内部的に呼ぶ
    async def get_x():
        html, base = await x_fetch("/search?f=tweets&q=" + urllib.parse.quote(q))
        return parse_x_tweets(html, base)
    
    tweets = run_async(get_x())
    return render_template(
        "x_search.html",
        query=q,
        tweets=tweets,
    )

# ============================================================
# ★★★ X メディアプロキシ ★★★
# ============================================================

@app.route("/x/media")
def x_media_proxy():
    u = request.args.get("u")
    url = decode_media_url(u)

    if not url.startswith("https://"):
        abort(400)

    async def fetch_media():
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, timeout=5) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content, r.headers.get("content-type", "application/octet-stream")

    content, mime = run_async(fetch_media())
    return FlaskResponse(content, mimetype=mime)

if __name__ == "__main__":
    # Flaskの開発用サーバー。本番環境では Waitress や Gunicorn + Gevent を推奨
    app.run(host="0.0.0.0", port=8000, debug=True)
