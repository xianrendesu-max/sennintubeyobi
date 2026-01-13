import json
import requests
import urllib.parse
import time
import datetime
import random
import os
import subprocess

from cache import cache

from fastapi import FastAPI, Response, Cookie, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Union


# =========================
# 基本設定
# =========================

max_api_wait_time = 3
max_time = 10
version = "1.0"

apis = [
    "https://yewtu.be/",
    "https://invidious.adminforge.de/",
    "https://invidious.perennialte.ch/",
    "https://iv.nboeck.de/",
    "https://invidious.jing.rocks/",
    "https://inv.nadeko.net/",
    "https://invidious.reallyaweso.me/",
    "https://invidious.privacyredirect.com/",
    "https://invidious.nerdvpn.de/",
    "https://iv.nowhere.moe/",
    "https://inv.tux.pizza/",
    "https://invidious.privacydev.net/",
    "https://invidious.yourdevice.ch/",
    "https://iv.ggtyler.dev/",
    "https://invidious.einfachzocken.eu/",
    "https://iv.datura.network/",
    "https://invidious.private.coffee/",
    "https://invidious.protokolla.fi/",
    "https://yt.cdaut.de/",
    "https://invidious.materialio.us/",
    "https://invidious.fdn.fr/",
    "https://invidious.drgns.space/",
    "https://vid.puffyan.us/",
    "https://youtube.076.ne.jp/",
    "https://inv.riverside.rocks/",
    "https://invidio.xamh.de/",
    "https://y.com.sb/",
    "https://invidious.sethforprivacy.com/",
    "https://invidious.tiekoetter.com/",
    "https://inv.bp.projectsegfau.lt/",
    "https://inv.vern.cc/",
    "https://inv.privacy.com.de/",
    "https://invidious.rhyshl.live/",
    "https://invidious.slipfox.xyz/",
    "https://invidious.weblibre.org/",
    "https://invidious.namazso.eu/"
]

apichannels = apis.copy()
apicomments = apis.copy()

os.chmod("./senninverify", 0o755)

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


# =========================
# 例外
# =========================

class APItimeoutError(Exception):
    pass


# =========================
# 共通関数
# =========================

def is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


def rotate_api(api_list, api):
    api_list.append(api)
    api_list.remove(api)


def api_request_core(api_list, url):
    starttime = time.time()

    for _ in range(len(api_list)):
        if time.time() - starttime >= max_time - 1:
            break

        api = api_list[0]
        try:
            res = session.get(api + url, timeout=max_api_wait_time)
            if res.status_code == 200 and is_json(res.text):
                return res.text
            else:
                print(f"APIエラー: {api}")
                rotate_api(api_list, api)
        except requests.RequestException:
            print(f"APIタイムアウト: {api}")
            rotate_api(api_list, api)

    raise APItimeoutError("APIがタイムアウトしました")


def apirequest(url):
    return api_request_core(apis, url)


def apichannelrequest(url):
    return api_request_core(apichannels, url)


def apicommentsrequest(url):
    return api_request_core(apicomments, url)


def check_cookie(cookie: Union[str, None]) -> bool:
    return cookie == "True"


# =========================
# APIラッパー（キャッシュ）
# =========================

@cache(seconds=60)
def get_data(videoid):
    t = json.loads(apirequest("api/v1/videos/" + urllib.parse.quote(videoid)))
    return (
        [{"id": i["videoId"], "title": i["title"], "authorId": i["authorId"], "author": i["author"]}
         for i in t["recommendedVideos"]],
        list(reversed([i["url"] for i in t["formatStreams"]]))[:2],
        t["descriptionHtml"].replace("\n", "<br>"),
        t["title"],
        t["authorId"],
        t["author"],
        t["authorThumbnails"][-1]["url"]
    )


@cache(seconds=30)
def get_search(q, page):
    t = json.loads(apirequest(
        f"api/v1/search?q={urllib.parse.quote(q)}&page={page}&hl=jp"
    ))

    results = []
    for i in t:
        if i["type"] == "video":
            results.append({
                "title": i["title"],
                "id": i["videoId"],
                "authorId": i["authorId"],
                "author": i["author"],
                "length": str(datetime.timedelta(seconds=i["lengthSeconds"])),
                "published": i["publishedText"],
                "type": "video"
            })
        elif i["type"] == "playlist":
            results.append({
                "title": i["title"],
                "id": i["playlistId"],
                "thumbnail": i["videos"][0]["videoId"],
                "count": i["videoCount"],
                "type": "playlist"
            })
        else:
            thumb = i["authorThumbnails"][-1]["url"]
            if not thumb.startswith("https"):
                thumb = "https://" + thumb
            results.append({
                "author": i["author"],
                "id": i["authorId"],
                "thumbnail": thumb,
                "type": "channel"
            })
    return results


@cache(seconds=120)
def get_channel(channelid):
    t = json.loads(apichannelrequest(
        "api/v1/channels/" + urllib.parse.quote(channelid)
    ))

    if not t["latestVideos"]:
        raise APItimeoutError("チャンネル取得失敗")

    return (
        [{"title": i["title"], "id": i["videoId"], "authorId": t["authorId"],
          "author": t["author"], "published": i["publishedText"], "type": "video"}
         for i in t["latestVideos"]],
        {
            "channelname": t["author"],
            "channelicon": t["authorThumbnails"][-1]["url"],
            "channelprofile": t["descriptionHtml"]
        }
    )


def get_playlist(listid, page):
    t = json.loads(apirequest(
        "api/v1/playlists/" + urllib.parse.quote(listid) + "?page=" + urllib.parse.quote(page)
    ))["videos"]

    return [{"title": i["title"], "id": i["videoId"], "authorId": i["authorId"],
             "author": i["author"], "type": "video"} for i in t]


def get_comments(videoid):
    t = json.loads(apicommentsrequest(
        "api/v1/comments/" + urllib.parse.quote(videoid) + "?hl=jp"
    ))["comments"]

    return [{"author": i["author"], "authoricon": i["authorThumbnails"][-1]["url"],
             "authorid": i["authorId"],
             "body": i["contentHtml"].replace("\n", "<br>")} for i in t]


def get_verifycode():
    result = subprocess.run(["./senninverify"], encoding="utf-8", stdout=subprocess.PIPE)
    return result.stdout.strip()


# =========================
# FastAPI
# =========================

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.mount("/css", StaticFiles(directory="./css"), name="css")
app.mount("/word", StaticFiles(directory="./blog", html=True), name="word")

app.add_middleware(GZipMiddleware, minimum_size=1000)

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request, response: Response, yuki: Union[str, None] = Cookie(None)):
    if check_cookie(yuki):
        response.set_cookie("yuki", "True", max_age=7 * 24 * 60 * 60)
        return templates.TemplateResponse("home.html", {"request": request})
    return RedirectResponse("/word")


@app.get("/watch", response_class=HTMLResponse)
def watch(v: str, request: Request, response: Response,
          yuki: Union[str, None] = Cookie(None),
          proxy: Union[str, None] = Cookie(None)):
    if not check_cookie(yuki):
        return RedirectResponse("/")
    response.set_cookie("yuki", "True", max_age=7 * 24 * 60 * 60)
    data = get_data(v)
    return templates.TemplateResponse("video.html", {
        "request": request,
        "videoid": v,
        "videourls": data[1],
        "res": data[0],
        "description": data[2],
        "videotitle": data[3],
        "authorid": data[4],
        "author": data[5],
        "authoricon": data[6],
        "proxy": proxy
    })


@app.exception_handler(APItimeoutError)
def api_error(request: Request, exc: APItimeoutError):
    return templates.TemplateResponse("APIwait.html", {"request": request}, status_code=500)
