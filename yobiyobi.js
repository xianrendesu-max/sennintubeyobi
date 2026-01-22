/* ===============================
   yobiyobi.js ULTIMATE + API POOL
   =============================== */

/* ===============================
   APIエンドポイント（GASプール）
   =============================== */
const API_URLS = [
  "https://script.google.com/macros/s/AKfycbzqpav7y2x3q756wRSOhBzaXf-2hKaLTvxoFN8kFegrIvamH03ZXphEw2PK30L7AstC/exec",
  "https://script.google.com/macros/s/AKfycbyXCS6JsBglbqlW0eIOWpVscTdNA8QUISRaGMJUAiMlYfp4Ju-Avkw1ai3A6P_ek-FK/exec",
  "https://script.google.com/macros/s/AKfycby5bmMQBShFOv_inDOo9jUjwxjdF6PeIh8spKAncj0-h5idAHYodOy-jj9YZStcYa-L/exec",
  "https://script.google.com/macros/s/AKfycbw5Cci8LSWChLvGf17uNW5cZDqESr0XFuI3QNZDRsdn5su1K4VzTfB0oq7SKNXzimT1Aw/exec",
  "https://script.google.com/macros/s/AKfycbwJFbZ4CHnuvy8rppZLfbWWuOHMqaM89nlsv7gThIzW_x0Bn2cj7IJU6XHC5CHG2B-yqQ/exec",
  "https://script.google.com/macros/s/AKfycbzYHLmomiijxiaNGcdLY_ddDZIi3QTK408EQDEpsa82FtIt4VTGRuC8ovZxM7kUSrC2/exec",
  "https://script.google.com/macros/s/AKfycbygQyKvfPnMvY8sdOkKow6NzO91dBhQFy0Vex3qVq1tWnqKodNbFVKQhALWWBLXcRTF/exec",
  "https://script.google.com/macros/s/AKfycbyh11OPhy_xaZOPVz3uKVFy8qdN05hVRrpKrNXuIeogsTLwiQQYBUhKZMniStVhg7QF-A/exec",
  "https://script.google.com/macros/s/AKfycbyjbFpmnhvs0BSorjNuIoZkIOsiH7OsovlYkl3DBI9SA3_19jOBqjr999WA_12HYxhT0A/exec"
];

function apiurl() {
  const index = Math.floor(Math.random() * API_URLS.length);
  return API_URLS[index];
}

/* ===============================
   HTMLから渡されたデータ
   =============================== */
const {
  videourls: urls,
  videoid,
  nocookieUrl
} = window.__YOBI_DATA__;

/* ===============================
   DOM
   =============================== */
const video = document.getElementById("videoPlayer");
const backendSelect = document.getElementById("backendSelect");
const qualitySelect = document.getElementById("qualitySelect");

/* ===============================
   状態
   =============================== */
let hlsPlayer = null;
let fallbackTimer = null;
let currentBackendIndex = 0;

const BACKENDS = ["yobiyobi", "yobi", "main"];

/* ===============================
   Overlay UI
   =============================== */
const overlay = document.createElement("div");
overlay.style.cssText = `
  position:fixed;
  inset:0;
  background:rgba(0,0,0,.55);
  z-index:9999;
  display:none;
  align-items:center;
  justify-content:center;
  color:white;
  font-size:16px;
`;
overlay.innerHTML = `<div id="overlayText">再生準備中…</div>`;
document.body.appendChild(overlay);

function showOverlay(text) {
  overlay.style.display = "flex";
  document.getElementById("overlayText").innerText = text;
}
function hideOverlay() {
  overlay.style.display = "none";
}

/* ===============================
   backend URL
   =============================== */
function getStreamBase(name) {
  if (name === "yobi") return "/api/streamurl/yobi";
  if (name === "yobiyobi") return "/api/streamurl/yobiyobi";
  return "/api/streamurl";
}

/* ===============================
   初期再生（main）
   =============================== */
video.src = urls[1] || urls[0];

/* ===============================
   GAS から m3u8 URL 取得
   =============================== */
async function fetchHlsFromApiPool() {
  for (let i = 0; i < API_URLS.length; i++) {
    try {
      const url = `${apiurl()}?video_id=${videoid}`;
      const r = await fetch(url, { cache: "no-store" });
      if (!r.ok) continue;
      const json = await r.json();
      if (json && json.m3u8) {
        return json.m3u8;
      }
    } catch (e) {
      console.warn("GAS API失敗");
    }
  }
  throw new Error("全GAS API失敗");
}

/* ===============================
   HLS 再生
   =============================== */
async function playHLSWithApiPool() {
  showOverlay("高画質ストリーム取得中…");

  let hlsUrl;
  try {
    hlsUrl = await fetchHlsFromApiPool();
  } catch {
    fallback();
    return;
  }

  playHLS(hlsUrl);
}

function playHLS(url) {
  if (hlsPlayer) {
    hlsPlayer.destroy();
    hlsPlayer = null;
  }

  if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = url;
    video.play().then(hideOverlay);
    return;
  }

  if (!window.Hls || !Hls.isSupported()) {
    fallback();
    return;
  }

  hlsPlayer = new Hls({
    enableWorker: true,
    lowLatencyMode: true
  });

  hlsPlayer.loadSource(url);
  hlsPlayer.attachMedia(video);

  hlsPlayer.on(Hls.Events.MANIFEST_PARSED, (_, data) => {
    syncQualitySelector(data.levels);
    video.play();
    hideOverlay();
  });

  hlsPlayer.on(Hls.Events.ERROR, (_, data) => {
    if (data.fatal) {
      fallback();
    }
  });

  fallbackTimer = setTimeout(() => {
    fallback();
  }, 8000);
}

/* ===============================
   m3u8 画質同期
   =============================== */
function syncQualitySelector(levels) {
  qualitySelect.innerHTML = "";

  levels
    .map((l, i) => ({ height: l.height, index: i }))
    .sort((a, b) => b.height - a.height)
    .forEach((l) => {
      const opt = document.createElement("option");
      opt.value = l.index;
      opt.textContent = `${l.height}p`;
      qualitySelect.appendChild(opt);
    });

  qualitySelect.onchange = () => {
    if (hlsPlayer) {
      hlsPlayer.currentLevel = Number(qualitySelect.value);
    }
  };
}

/* ===============================
   フォールバック処理
   =============================== */
function fallback() {
  clearTimeout(fallbackTimer);

  if (hlsPlayer) {
    hlsPlayer.destroy();
    hlsPlayer = null;
  }

  currentBackendIndex++;

  if (currentBackendIndex >= BACKENDS.length) {
    showOverlay("再生失敗。通常再生に戻します");
    video.src = urls[0];
    video.play();
    setTimeout(hideOverlay, 1500);
    return;
  }

  const next = BACKENDS[currentBackendIndex];
  showOverlay(`${next} に切替中…`);

  if (next === "main") {
    video.src = urls[0];
    video.play();
    setTimeout(hideOverlay, 800);
  } else {
    playHLSWithApiPool();
  }
}

/* ===============================
   手動 backend 切替
   =============================== */
backendSelect.onchange = () => {
  currentBackendIndex = BACKENDS.indexOf(backendSelect.value);
  playHLSWithApiPool();
};

/* ===============================
   再生開始（最優先 yobiyobi）
   =============================== */
playHLSWithApiPool();
