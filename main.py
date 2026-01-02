import os
import json
import datetime
import time
import asyncio
import requests
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "logs")
SYNC_FILE = os.path.join(DATA_DIR, "sync_state.json")

DISABLE_DOWNLOADS = False
sync_running = False

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY and not DISABLE_DOWNLOADS:
    raise ValueError("ELEVENLABS_API_KEY not set")

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
HEADERS = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}

os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")


# -------------------- STATE HANDLING --------------------

def load_sync_state():
    if os.path.exists(SYNC_FILE):
        try:
            with open(SYNC_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"cursor": None}


def save_sync_state(state):
    with open(SYNC_FILE, "w") as f:
        json.dump(state, f, indent=2)


# -------------------- NETWORK UTILS --------------------

def safe_request(method, url, retries=3, **kwargs):
    if DISABLE_DOWNLOADS:
        print(f"[DISABLED] {method} {url}")
        return None

    for attempt in range(retries):
        try:
            r = requests.request(method, url, timeout=30, **kwargs)
            print(f"{method} {url} → {r.status_code}")
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            return r
        except Exception as e:
            print(f"Request error: {e}")
            time.sleep(2 ** attempt)
    return None


# -------------------- SAVE MESSAGE --------------------

def save_message(item):
    try:
        date_unix = item.get("date_unix", time.time())
        dt = datetime.datetime.utcfromtimestamp(date_unix)
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H-%M-%S")

        base_dir = os.path.join(DATA_DIR, date_str)
        chat_dir = os.path.join(base_dir, "chat")
        voice_dir = os.path.join(base_dir, "voice")

        os.makedirs(chat_dir, exist_ok=True)
        os.makedirs(voice_dir, exist_ok=True)

        json_path = os.path.join(chat_dir, f"{time_str}.json")
        if os.path.exists(json_path):
            return

        with open(json_path, "w") as f:
            json.dump(item, f, indent=2)

        text = item.get("text")
        voice_id = item.get("voice_id")

        if text and voice_id:
            audio_path = os.path.join(voice_dir, f"{time_str}.mp3")
            if not os.path.exists(audio_path):
                r = safe_request(
                    "POST",
                    f"{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}",
                    headers={"xi-api-key": ELEVENLABS_API_KEY},
                    json={
                        "text": text,
                        "voice_settings": {
                            "stability": item.get("settings", {}).get("stability", 0.5),
                            "similarity_boost": item.get("settings", {}).get("similarity_boost", 0.75)
                        }
                    }
                )
                if r and r.status_code == 200:
                    with open(audio_path, "wb") as f:
                        f.write(r.content)

    except Exception as e:
        print(f"Save error: {e}")


# -------------------- HISTORY SYNC --------------------

async def sync_history():
    global sync_running
    if DISABLE_DOWNLOADS:
        print("Downloads disabled.")
        return

    sync_running = True
    state = load_sync_state()
    cursor = state.get("cursor")

    while sync_running:
        params = {"page_size": 100}
        if cursor:
            params["cursor"] = cursor

        r = safe_request(
            "GET",
            f"{ELEVENLABS_BASE_URL}/history",
            headers=HEADERS,
            params=params
        )

        if not r or r.status_code != 200:
            print("Failed to fetch history")
            break

        data = r.json()
        items = data.get("history", [])

        if not items:
            print("No more history")
            break

        for item in items:
            if not sync_running:
                break
            save_message(item)
            await asyncio.sleep(0)

        cursor = data.get("next_cursor")
        save_sync_state({"cursor": cursor})

        if not data.get("has_more"):
            break

    sync_running = False
    print("Sync completed")


# -------------------- ROUTES --------------------

@app.post("/sync")
def manual_sync(background_tasks: BackgroundTasks):
    global sync_running
    if not sync_running:
        background_tasks.add_task(sync_history)
    return RedirectResponse("/", status_code=302)


@app.post("/stop")
def stop_sync():
    global sync_running
    sync_running = False
    return RedirectResponse("/", status_code=302)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    conversations = []

    if os.path.exists(DATA_DIR):
        for date_dir in sorted(os.listdir(DATA_DIR)):
            date_path = os.path.join(DATA_DIR, date_dir)
            chat_dir = os.path.join(date_path, "chat")
            voice_dir = os.path.join(date_path, "voice")

            if not os.path.isdir(chat_dir):
                continue

            messages = []
            for file in sorted(os.listdir(chat_dir)):
                if not file.endswith(".json"):
                    continue

                with open(os.path.join(chat_dir, file)) as f:
                    msg = json.load(f)

                timestamp = msg.get("date_unix", 0)
                time_str = file.replace(".json", "")
                audio_path = f"{date_dir}/voice/{time_str}.mp3" if os.path.exists(
                    os.path.join(voice_dir, f"{time_str}.mp3")
                ) else None

                messages.append({
                    "timestamp": datetime.datetime.utcfromtimestamp(timestamp).isoformat(),
                    "sender": msg.get("voice_name", "Unknown"),
                    "text": msg.get("text", ""),
                    "audio_path": audio_path
                })

            conversations.append({
                "user_id": f"Date: {date_dir}",
                "timestamp": date_dir,
                "messages": messages
            })

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "conversations": conversations,
        "sync_running": sync_running
    })
