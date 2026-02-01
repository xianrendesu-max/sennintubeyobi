const axios = require('axios');

let apis = null;
const MAX_API_WAIT_TIME = 3000;
const MAX_TIME = 10000;

async function getapis() {
  try {
    const res = await axios.get(
      'https://raw.githubusercontent.com/wakame02/wktopu/refs/heads/main/inv.json'
    );
    apis = res.data;
  } catch (e) {
    await getapisgit();
  }
}

async function getapisgit() {
  try {
    const res = await axios.get(
      'https://raw.githubusercontent.com/wakame02/wktopu/refs/heads/main/inv.json'
    );
    apis = res.data;
  } catch (e) {}
}

async function ggvideo(videoId) {
  const start = Date.now();
  if (!apis) await getapis();

  for (const api of apis) {
    try {
      const res = await axios.get(
        `${api}/api/v1/videos/${videoId}`,
        { timeout: MAX_API_WAIT_TIME }
      );
      if (res.data && res.data.formatStreams) {
        return res.data;
      }
    } catch (e) {}
    if (Date.now() - start > MAX_TIME) {
      throw new Error("timeout");
    }
  }
  throw new Error("no api");
}

async function getYouTube(videoId) {
  const info = await ggvideo(videoId);

  const videoStreams = info.formatStreams.filter(f =>
    f.type && f.type.startsWith("video/")
  );
  const audioStreams = info.formatStreams.filter(f =>
    f.type && f.type.startsWith("audio/")
  );

  videoStreams.sort((a,b)=> (b.width*b.height)-(a.width*a.height));
  audioStreams.sort((a,b)=> (b.bitrate||0)-(a.bitrate||0));

  const bestVideo = videoStreams[0];
  const bestAudio = audioStreams[0];

  return {
    stream_url: bestVideo?.url || null,
    highstreamUrl: bestVideo?.url || null,
    audioUrl: bestAudio?.url || null,
    mimeVideo: bestVideo?.type || null,
    mimeAudio: bestAudio?.type || null,
    width: bestVideo?.width || null,
    height: bestVideo?.height || null,
    title: info.title,
    description: info.descriptionHtml,
    author: info.author,
    authorId: info.authorId,
    authorImage: info.authorThumbnails?.slice(-1)[0]?.url || ""
  };
}

module.exports = {
  ggvideo,
  getYouTube
};
