const express = require("express");
const axios = require("axios");
const router = express.Router();

const INVIDIOUS = [
  "https://yewtu.be",
  "https://vid.puffyan.us",
  "https://invidious.fdn.fr"
];

router.get("/", async (req,res)=>{
  const id = req.query.v;
  const isWkt = req.query.wkt === "1";

  for (const api of INVIDIOUS) {
    try {
      const r = await axios.get(`${api}/api/v1/videos/${id}`,{timeout:5000});
      const f = r.data.formatStreams;

      const videos = f.filter(x=>x.type?.startsWith("video/"));
      const audios = f.filter(x=>x.type?.startsWith("audio/"));

      videos.sort((a,b)=>(b.width*b.height)-(a.width*a.height));
      audios.sort((a,b)=>(b.bitrate||0)-(a.bitrate||0));

      const v = videos[0];
      const a = audios[0];

      if (!v || !a) continue;

      if (v.height < 720) {
        return res.status(422).json({ error:"high quality not available" });
      }

      if (isWkt) {
        return res.json({
          videoUrl: v.url,
          audioUrl: a.url,
          mimeVideo: v.type,
          mimeAudio: a.type,
          width: v.width,
          height: v.height
        });
      }

      return res.json({ url: v.url });

    } catch {}
  }

  res.status(500).json({ error:"failed" });
});

module.exports = router;
