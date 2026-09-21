import asyncio
import json
import os
import re
import time
import aiohttp
from aiohttp import web
from pyrogram import Client, filters

# --- CONFIGURATION ---
API_ID = 31169133
API_HASH = "b836f4b836df4cf83c2d475a5ad3b285"
BOT_TOKEN = "8947200389:AAEhBe-mIYrnG4D26j0rksI5ztR_Jje8O9I"

VIDHIDE_API_KEYS = ["47650ignlp8w9m7zimhp7", "47699lkja012c5mp3mw23"]

DOMAINS = [
    "https://vidhidepro.com",
    "https://earnvids.com",
    "https://vidhide.com",
    "https://vidhide.pro",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

app = Client(
    "7anime_cloud_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

task_queue = asyncio.Queue()
USER_ANIME_NAMES = {}


# --- WEB SERVER FOR RENDER KEEP-ALIVE ---
async def handle_ping(request):
  return web.Response(text="Bot is running 24/7!")


async def start_web_server():
  web_app = web.Application()
  web_app.router.add_get("/", handle_ping)
  runner = web.AppRunner(web_app)
  await runner.setup()
  port = int(os.environ.get("PORT", 8080))
  site = web.TCPSite(runner, "0.0.0.0", port)
  await site.start()


# --- HELPER FUNCTIONS ---
def make_bar(percent):
  done = int(percent // 10)
  return "🟩" * done + "⬜" * (10 - done)


def safe_text(text):
  if not text:
    return "Anime Episode"
  cleaned = re.sub(r"[*_`\[\]()<>]", "", str(text)).strip()
  return cleaned if cleaned else "Anime Episode"


def clean_universal_title(text):
  if not text:
    return ""
  text = text.replace(".", " ").replace("_", " ")
  text = re.sub(
      r"(?:1080p|720p|480p|4k|x265|x264|10bit|BluRay|HDR|WEB-DL|Dual|Audio|ESub|FHD|HD|RareToonsIndia|Hindi|English|Sub|Dub|Multi|\.mkv|\.mp4)",
      "",
      text,
      flags=re.IGNORECASE,
  )
  text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
  text = re.sub(
      r"(?:S\d+E\d+|Season\s*\d+|Episode\s*\d+|\bEp\s*\d+|\bE\s*\d+\b)",
      "",
      text,
      flags=re.IGNORECASE,
  )
  text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
  text = re.sub(r"[-_@#|:]+", " ", text)
  return re.sub(r"\s+", " ", text).strip()


def parse_anime_info(message):
  user_id = message.from_user.id if message.from_user else 0
  caption = message.caption or ""
  filename = ""
  if message.video and message.video.file_name:
    filename = message.video.file_name
  elif message.document and message.document.file_name:
    filename = message.document.file_name

  forward_name = ""
  if message.forward_from_chat and message.forward_from_chat.title:
    forward_name = message.forward_from_chat.title

  combined_text = f"{caption}\n{filename}\n{forward_name}"

  # Priority 1: User-set custom anime name
  anime_name = USER_ANIME_NAMES.get(user_id, "")

  # Priority 2: Auto-extract from caption/filename
  if not anime_name:
    anime_match = re.search(
        r"(?:ANIME|Anime|Title)[:\s-]+\s*(.+)", caption, re.IGNORECASE
    )
    if anime_match:
      raw_found = anime_match.group(1).split("\n")[0]
      anime_name = clean_universal_title(raw_found)

  if not anime_name or len(anime_name) < 2:
    target_str = filename if filename else caption
    cleaned_file = clean_universal_title(target_str)
    if cleaned_file and not any(
        w in cleaned_file.lower()
        for w in ["otaku", "provider", "bot", "stream"]
    ):
      anime_name = cleaned_file

  if not anime_name or len(anime_name) < 2:
    anime_name = "Anime Episode"

  season_num = "01"
  season_match = re.search(
      r"(?:Season|S)[\s:-]*0*(\d+)", combined_text, re.IGNORECASE
  )
  if season_match:
    season_num = season_match.group(1).zfill(2)

  episode_num = "01"
  se_match = re.search(r"S\d+E(\d+)", combined_text, re.IGNORECASE)
  if se_match:
    episode_num = se_match.group(1).zfill(2)
  else:
    ep_match = re.search(
        r"(?:Episode|Ep|E)[\s.-]*0*(\d+)", combined_text, re.IGNORECASE
    )
    if ep_match:
      episode_num = ep_match.group(1).zfill(2)

  return safe_text(anime_name), season_num, episode_num


def sanitize_filename(filename, anime_name, season_num, episode_num):
  clean_name = re.sub(r"[^\w\s-]", "", anime_name).strip()
  clean_name = re.sub(r"[-\s]+", "_", clean_name)
  if not clean_name or clean_name.lower() in ["anime_episode", "anime"]:
    clean_name = "anime_video"
  return f"{clean_name}_S{season_num}E{episode_num}.mp4"


# --- UPLOAD & API LOGIC ---
async def get_working_upload_server(session, api_key):
  for domain in DOMAINS:
    url = f"{domain}/api/upload/server?key={api_key}"
    try:
      async with session.get(url, headers=HEADERS, timeout=15) as resp:
        if resp.status == 200:
          data = await resp.json(content_type=None)
          if data.get("status") == 200 and data.get("result"):
            return data["result"]
    except Exception:
      continue
  return None


def extract_filecode(res_text):
  if not res_text:
    return None
  try:
    data = json.loads(res_text)
    if isinstance(data, list) and len(data) > 0:
      code = data[0].get("filecode")
      if code and str(code).strip():
        return str(code).strip()
    if isinstance(data, dict):
      if (
          "result" in data
          and isinstance(data["result"], list)
          and len(data["result"]) > 0
      ):
        code = data["result"][0].get("filecode")
        if code and str(code).strip():
          return str(code).strip()
  except Exception:
    pass
  match = re.search(r'"filecode"\s*:\s*"([a-zA-Z0-9_-]{3,})"', str(res_text))
  return match.group(1).strip() if match else None


async def upload_file_aiohttp(
    upload_url, filepath, clean_fn, api_key, progress_cb
):
  file_size = os.path.getsize(filepath)
  with open(filepath, "rb") as f:
    data = aiohttp.FormData()
    data.add_field("key", api_key)
    data.add_field("file", f, filename=clean_fn, content_type="video/mp4")
    stop_event = asyncio.Event()

    async def track_progress():
      last_pos = -1
      while not stop_event.is_set():
        try:
          current_pos = f.tell()
          if current_pos != last_pos and file_size > 0:
            last_pos = current_pos
            await progress_cb(current_pos, file_size)
        except Exception:
          pass
        await asyncio.sleep(2.5)

    tracker_task = asyncio.create_task(track_progress())
    timeout = aiohttp.ClientTimeout(total=3600, connect=60, sock_read=300)
    async with aiohttp.ClientSession(timeout=timeout) as session:
      try:
        target = (
            upload_url
            if "key=" in upload_url
            else f"{upload_url}?key={api_key}"
        )
        async with session.post(target, data=data, headers=HEADERS) as resp:
          res = await resp.text()
          return res
      except Exception as e:
        return str(e)
      finally:
        stop_event.set()
        await tracker_task


# --- QUEUE WORKER (ONE BY ONE PROCESSING) ---
async def process_queue_worker():
  while True:
    message = await task_queue.get()
    try:
      await process_single_file(message)
      await asyncio.sleep(5)
    except Exception as e:
      print(f"Queue Worker Error: {e}")
    finally:
      task_queue.task_done()


async def process_single_file(message):
  anime_name, season_num, episode_num = parse_anime_info(message)
  msg = await message.reply_text(
      f"⏳ **{anime_name} - S{season_num}E{episode_num}** Processing shuru ho"
      " gaya hai..."
  )

  downloaded_path = None
  last_update = [0]

  async def dl_progress(current, total):
    now = time.time()
    if now - last_update[0] > 3.0 or current == total:
      last_update[0] = now
      percent = (current / total) * 100
      bar = make_bar(percent)
      mb_cur = round(current / (1024 * 1024), 1)
      mb_tot = round(total / (1024 * 1024), 1)
      try:
        await msg.edit_text(
            f"📥 **Downloading:** {anime_name} (S{season_num}E{episode_num})\n"
            f"[{bar}] {percent:.1f}%\n"
            f"💾 {mb_cur} MB / {mb_tot} MB"
        )
      except Exception:
        pass

  try:
    downloaded_path = await message.download(progress=dl_progress)
    if not downloaded_path or not os.path.exists(downloaded_path):
      await msg.edit_text(f"❌ **{anime_name}** Download fail ho gaya.")
      return

    clean_fn = sanitize_filename(
        os.path.basename(downloaded_path), anime_name, season_num, episode_num
    )

    vidhide_code = None
    vidhide_err = ""

    # Multi-API Keys Rotation
    for api_key in list(VIDHIDE_API_KEYS):
      upload_url = None
      async with aiohttp.ClientSession() as session:
        upload_url = await get_working_upload_server(session, api_key)

      if not upload_url:
        upload_url = "https://vidhidepro.com/api/upload/server"

      async def vidhide_ul_prog(cur, tot):
        now = time.time()
        if now - last_update[0] > 3.0 or cur == tot:
          last_update[0] = now
          percent = (cur / tot) * 100
          bar = make_bar(percent)
          mb_cur = round(cur / (1024 * 1024), 1)
          mb_tot = round(tot / (1024 * 1024), 1)
          try:
            await msg.edit_text(
                "📤 **Uploading to Vidhide:**\n"
                f"🎬 `{anime_name} - S{season_num}E{episode_num}`\n"
                f"[{bar}] {percent:.1f}%\n"
                f"💾 {mb_cur} MB / {mb_tot} MB"
            )
          except Exception:
            pass

      res_text = await upload_file_aiohttp(
          upload_url, downloaded_path, clean_fn, api_key, vidhide_ul_prog
      )

      if res_text and (
          "too many" in res_text.lower() or "limit" in res_text.lower()
      ):
        vidhide_err = f"API Limit Exceeded on Key ({api_key[:6]}...)"
        continue

      vidhide_code = extract_filecode(res_text)
      if vidhide_code:
        break
      else:
        vidhide_err = res_text[:120] if res_text else "Empty Response"

    if vidhide_code:
      v_embed = f"https://vidhidepro.com/v/{vidhide_code}"
      final_output = (
          "✅ **Process Finished!**\n\n"
          f"ANIME NAME - ({anime_name})\n"
          f"🎬 ➡️ Episode - Season - {season_num} , Episode -"
          f" {episode_num}\n\n"
          "🔗 **Embed Link:**\n"
          f"`{v_embed}`\n\n"
          "📌 **Iframe Code (7anime Website):**\n"
          f'`<iframe src="{v_embed}" width="100%" height="400" frameborder="0"'
          ' allowfullscreen></iframe>`'
      )
    else:
      final_output = f"❌ **Upload Failed:** `{safe_text(vidhide_err)}`"

    await msg.edit_text(final_output)

  except Exception as e:
    await msg.edit_text(f"⚠️ **{anime_name}** Error: `{safe_text(str(e))}`")
  finally:
    if downloaded_path and os.path.exists(downloaded_path):
      try:
        os.remove(downloaded_path)
      except Exception:
        pass


# --- COMMAND HANDLERS ---
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
  await message.reply_text(
      "👋 **7anime Cloud Bot Active!**\n\n"
      "🔹 **Usage:**\n"
      "1. Anime ka naam text karke bhej sakte ho (Optional).\n"
      "2. Videos/Documents forward karo, Queue me add ho jayegi.\n"
      "3. `/changeapi <key>` - Nayi API key add karne ke liye."
  )


@app.on_message(filters.command("changeapi"))
async def change_api_cmd(client, message):
  args = message.text.split(maxsplit=1)
  if len(args) > 1:
    new_key = args[1].strip()
    if new_key not in VIDHIDE_API_KEYS:
      VIDHIDE_API_KEYS.append(new_key)
    await message.reply_text(
        "✅ Nayi API key add ho gayi!\n🔑 Total Active Keys:"
        f" `{len(VIDHIDE_API_KEYS)}`"
    )
  else:
    await message.reply_text("⚠️ Kripya key likhein: `/changeapi <your_key>`")


@app.on_message(filters.text & ~filters.command(["start", "changeapi"]))
async def save_anime_name(client, message):
  user_id = message.from_user.id
  anime_name = safe_text(message.text)
  USER_ANIME_NAMES[user_id] = anime_name
  await message.reply_text(
      f"✅ Anime Name Saved: **{anime_name}**\nAb iski videos forward karein!"
  )


@app.on_message(filters.video | filters.document)
async def handle_file(client, message):
  anime_name, season_num, episode_num = parse_anime_info(message)
  await message.reply_text(
      f"⏳ **{anime_name} - S{season_num}E{episode_num}** Queue me add ho gayi"
      " hai!"
  )
  await task_queue.put(message)


# --- MAIN EXECUTION ---
if __name__ == "__main__":
  loop = asyncio.get_event_loop()
  loop.run_until_complete(start_web_server())
  loop.create_task(process_queue_worker())
  print("🚀 7anime Cloud Bot Starting...")
  app.run()
                  
