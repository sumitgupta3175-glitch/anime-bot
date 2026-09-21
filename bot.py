import asyncio
import sys

if sys.platform == "win32":
  asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
  try:
    loop = asyncio.get_event_loop()
  except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import json
import os
import re
import time
import aiohttp
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import BotCommand

API_ID = 31169133
API_HASH = "b836f4b836df4cf83c2d475a5ad3b285"
BOT_TOKEN = "8958831796:AAFjYOzJMs2jW47ZKZz5Vu4gQ3f_xekLuQ8"

VIDHIDE_API_KEYS = [
    "47650ignlp8w9m7zimhp7",
    "47699lkja012c5mp3mw23",
]

DOMAINS = [
    "https://vidhidepro.com",
    "https://earnvids.com",
    "https://vidhide.com",
    "https://vidhide.pro",
]

SEMAPHORE = asyncio.Semaphore(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

app = Client(
    "7anime_cloud_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN
)

USER_ANIME_NAMES = {}


def make_bar(percent):
  done = int(percent // 10)
  return "🟩" * done + "⬜" * (10 - done)


def safe_text(text):
  if not text:
    return "Anime Episode"
  return re.sub(r"[*_`\[\]()<>]", "", str(text)).strip()


def sanitize_filename(filename):
  name, ext = os.path.splitext(filename)
  if not ext:
    ext = ".mp4"
  clean_name = re.sub(r"[^\w\s-]", "", name).strip()
  clean_name = re.sub(r"[-\s]+", "_", clean_name)
  if not clean_name:
    clean_name = "anime_video"
  return f"{clean_name}{ext}"


def get_video_title(message, user_id):
  title = None
  if message.caption:
    title = message.caption.split("\n")[0].strip()
  elif message.video and message.video.file_name:
    title = message.video.file_name
  elif message.document and message.document.file_name:
    title = message.document.file_name

  for ext in [".mp4", ".mkv", ".avi", ".webm", ".mov"]:
    if title and title.lower().endswith(ext):
      title = title[: -len(ext)]
      break

  clean_title = safe_text(title)
  custom_name = USER_ANIME_NAMES.get(user_id)
  if custom_name:
    return f"{custom_name} - {clean_title}"

  return clean_title


async def get_working_upload_server(session, api_key):
  for domain in DOMAINS:
    url = f"{domain}/api/upload/server?key={api_key}"
    try:
      async with session.get(url, headers=HEADERS, timeout=15) as resp:
        if resp.status == 429:
          return "RATE_LIMIT"
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
  if "RATE_LIMIT" in res_text or "too many requests" in res_text.lower():
    return "RATE_LIMIT"
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
  if match:
    return match.group(1).strip()
  return None


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
          if resp.status == 429:
            return "RATE_LIMIT"
          res = await resp.text()
          return res
      except Exception as e:
        return str(e)
      finally:
        stop_event.set()
        await tracker_task


@app.on_message(filters.command("start"))
async def start_cmd(client, message):
  await message.reply_text(
      "👋 **7anime Cloud Vidhide Bot Active!**\n\n"
      "🔹 **Commands:**\n"
      "• `/changeapi <new_key>` - Nayi API key add karne ke liye\n"
      "• Pehle anime ka naam bhejein, phir videos forward karein."
  )


@app.on_message(filters.command("changeapi"))
async def change_api_cmd(client, message):
  args = message.text.split(maxsplit=1)
  if len(args) > 1:
    new_key = args[1].strip()
    if new_key not in VIDHIDE_API_KEYS:
      VIDHIDE_API_KEYS.append(new_key)
    await message.reply_text(
        f"✅ Nayi API key successfully add ho gayi hai!\n🔑 Total active keys:"
        f" `{len(VIDHIDE_API_KEYS)}`"
    )
  else:
    await message.reply_text(
        "⚠️ Kripya key bhi likhein.\nExample: `/changeapi"
        " 47699lkja012c5mp3mw23`"
    )


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
  user_id = message.from_user.id
  video_title = get_video_title(message, user_id)
  queue_msg = await message.reply_text(
      f"⏳ **{video_title}** Queue mein add ho gaya hai..."
  )

  async with SEMAPHORE:
    msg = queue_msg
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
              f"📥 **Downloading:** {video_title}\n[{bar}]"
              f" {percent:.1f}%\n💾 {mb_cur} MB / {mb_tot} MB"
          )
        except Exception:
          pass

    async def ul_progress(current, total):
      percent = (current / total) * 100
      bar = make_bar(percent)
      mb_cur = round(current / (1024 * 1024), 1)
      mb_tot = round(total / (1024 * 1024), 1)
      try:
        if current >= total:
          await msg.edit_text(
              f"⚙️ **Processing on Server...**\n🎬 `{video_title}`\n⏳ Upload"
              " finished. Generating embed code..."
          )
        else:
          await msg.edit_text(
              f"📤 **Uploading:** {video_title}\n[{bar}]"
              f" {percent:.1f}%\n🚀 {mb_cur} MB / {mb_tot} MB"
          )
      except Exception:
        pass

    try:
      downloaded_path = await message.download(progress=dl_progress)
      if not downloaded_path or not os.path.exists(downloaded_path):
        await msg.edit_text(f"❌ **{video_title}** Download fail ho gaya.")
        return

      clean_fn = sanitize_filename(os.path.basename(downloaded_path))
      code = None
      last_err = ""

      for api_key in list(VIDHIDE_API_KEYS):
        upload_url = None
        for attempt in range(1, 3):
          async with aiohttp.ClientSession() as session:
            upload_url = await get_working_upload_server(session, api_key)

          if upload_url == "RATE_LIMIT":
            break
          if upload_url:
            break
          await asyncio.sleep(2)

        if upload_url == "RATE_LIMIT":
          last_err = f"API Rate Limit on Key: {api_key[:6]}..."
          continue

        if not upload_url:
          continue

        res_text = await upload_file_aiohttp(
            upload_url, downloaded_path, clean_fn, api_key, ul_progress
        )

        if res_text == "RATE_LIMIT":
          last_err = f"API Rate Limit on Key: {api_key[:6]}..."
          continue

        code = extract_filecode(res_text)
        if code == "RATE_LIMIT":
          last_err = f"API Rate Limit on Key: {api_key[:6]}..."
          continue

        if code:
          break
        else:
          last_err = res_text[:120] if res_text else "Empty Response"

      if code and code != "RATE_LIMIT":
        embed = f"https://vidhidepro.com/v/{code}"
        result_text = (
            f"✅ **Upload Complete!**\n\n🎬 **{video_title}**\n\n🔗 **Embed"
            f" Link:**\n`{embed}`\n\n📌 **Iframe Code (7anime"
            f" Website):**\n`<iframe src=\"{embed}\" width=\"100%\""
            ' height="400" frameborder="0" allowfullscreen></iframe>`'
        )
        await msg.edit_text(result_text)
      else:
        await msg.edit_text(
            f"⚠️ **{video_title}** Failed. Reason: `{safe_text(last_err)}`"
        )

    except Exception as e:
      await msg.edit_text(f"⚠️ **{video_title}** Error: `{safe_text(str(e))}`")
    finally:
      if downloaded_path and os.path.exists(downloaded_path):
        try:
          os.remove(downloaded_path)
        except Exception:
          pass


# --- RENDER WEB SERVICE KEEP-ALIVE ---
async def handle(request):
  return web.Response(text="Bot is running 24/7!")


async def start_web_server():
  app_web = web.Application()
  app_web.add_routes([web.get("/", handle)])
  runner = web.AppRunner(app_web)
  await runner.setup()
  port = int(os.environ.get("PORT", 8080))
  site = web.TCPSite(runner, "0.0.0.0", port)
  await site.start()
  print(f"Web server started on port {port}")


if __name__ == "__main__":
  print("🚀 7anime Bot Starting...")
  loop = asyncio.get_event_loop()
  loop.create_task(start_web_server())
  app.run()
    
