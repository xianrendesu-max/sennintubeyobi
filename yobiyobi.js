# yobiyobi.py
import random
import time
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

# =========================
# 基本設定
# =========================

router = APIRouter()

TIMEOUT = (3, 6)

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net/",
    "https://invidious.f5.si/",
    "https://invidious.lunivers.trade/",
    "https://invidious.ducks.party/",
    "https://super8.absturztau.be/",
    "https://invidious.nikkosphere.com/",
    "https://yt.omada.cafe/",
    "https://iv.melmac.space/",
    "https://iv.duti.dev/",
]

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "*/*",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        "Accept": "*/*",
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
        "Accept": "*/*",
    },
]

session = requests.Session()


def get_random_headers():
    return random.choice(HEADERS_LIST)


def pick_instance():
    inst = random.choice(INVIDIOUS_INSTANCES)
    if not inst.endswith("/"):
        inst += "/"
    return inst


# =========================
# Invidious m3u8 取得
# =========================

def fetch_m3u8_from_invidious(video_id: str):
    """
    yobiyobi は Invidious API 直叩きのみ
    MP4 は一切扱わない
    """
    instance = pick_instance()
    api_url = f"{instance}api/v1/videos/{video_id}"

    try:
        res = session.get(api_url, headers=get_random_headers(), timeout=TIMEOUT)
        if res.status_code != 200:
            return None

        data = res.json()
        adaptive = data.get("adaptiveFormats", [])

        m3u8_list = []
        for fmt in adaptive:
            if fmt.get("type", "").startswith("video") and "url" in fmt:
                if "m3u8" in fmt.get("url"):
                    m3u8_list.append(fmt)

        if not m3u8_list:
            return None

        # 解像度最大を選択
        def height(fmt):
            try:
                return int(fmt.get("height") or 0)
            except:
                return 0

        best = max(m3u8_list, key=height)
        return best.get("url")

    except Exception:
        return None


# =========================
# API エンドポイント
# =========================

@router.get("/api/streamurl/yobiyobi")
def stream_yobiyobi(video_id: str):
    """
    yobi が死んだ時に呼ばれる最終HLS手段
    """
    # 少し遅延させて yobi と同時死を避ける
    time.sleep(0.3)

    for _ in range(3):
        m3u8 = fetch_m3u8_from_invidious(video_id)
        if m3u8:
            return RedirectResponse(m3u8)

    raise HTTPException(status_code=503, detail="yobiyobi HLS unavailable")


# =========================
# デバッグ用（任意）
# =========================

@router.get("/api/streamurl/yobiyobi/json")
def stream_yobiyobi_json(video_id: str):
    m3u8 = fetch_m3u8_from_invidious(video_id)
    if not m3u8:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "no m3u8"},
        )

    return {
        "status": "ok",
        "backend": "yobiyobi",
        "m3u8": m3u8,
   }
