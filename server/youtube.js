let client = null;
const ytpl = require("ytpl");

function setClient(newClient){
  client = newClient;
}

async function infoGet(id){
  try {
    return await client.getInfo(id);
  } catch {
    return null;
  }
}

async function search(q){
  return await client.search(q,{type:"all"});
}

async function getChannel(id){
  const channel = await client.getChannel(id);
  const recentVideos = await ytpl(id,{pages:1});
  return { channel, recentVideos };
}

module.exports = {
  setClient,
  infoGet,
  search,
  getChannel
};
