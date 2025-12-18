import os
import sys
import time
import cv2
import numpy as np
import face_recognition
import tkinter as tk
from tkinter import messagebox, filedialog, StringVar, OptionMenu, ttk
from PIL import Image, ImageTk
import random
import json
import logging
from collections import defaultdict, OrderedDict, deque
import threading

# NEW for notifications & image hosting
import urllib.request, urllib.parse, ssl
import socket, base64, http.server, socketserver

# --- Voice & Comms (optional, safe fallbacks) ---
from tkinter import scrolledtext
import queue  # for UI message queue from threads

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import winsound
    _HAS_WINSOUND = True
except Exception:
    _HAS_WINSOUND = False


############################
# Logging Configuration
############################
logging.basicConfig(
    level=logging.INFO,
    format="(%(asctime)s) [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger()

#############################################
# Brand Theme (Dark mode + Light mode)
#############################################
BRAND_COLORS_DARK = {
    "bg":         "#0B1220",
    "surface":    "#0E1726",
    "panel":      "#12233B",
    "text":       "#E6ECFF",
    "muted":      "#B6C2D9",
    "navy":       "#183E8A",
    "navy2":      "#0F2A48",
    "gold":       "#D4AF37",
    "gold_light": "#FFDF6E",
    "border":     "#21314E",
    "ok":         "#62D394",
    "warn":       "#FFCC66",
    "bad":        "#FF6B6B"
}
BRAND_COLORS_LIGHT = {
    "bg":         "#F6F7FB",
    "surface":    "#FFFFFF",
    "panel":      "#FFFFFF",
    "text":       "#0B1220",
    "muted":      "#3D4C63",
    "navy":       "#183E8A",
    "navy2":      "#2853A5",
    "gold":       "#B9931F",
    "gold_light": "#F4C84A",
    "border":     "#D8DFEA",
    "ok":         "#218A53",
    "warn":       "#B37809",
    "bad":        "#B04242"
}
BRAND = {"active": dict(BRAND_COLORS_DARK)}

def _apply_option_database(root, C):
    root.tk_setPalette(
        background=C["bg"], foreground=C["text"],
        activeBackground=C["navy2"], activeForeground=C["text"],
        highlightColor=C["gold"], highlightBackground=C["bg"], selectColor=C["gold"]
    )
    oa = root.option_add
    oa("*Background", C["bg"])
    oa("*foreground", C["text"])
    oa("*FieldBackground", C["surface"])
    oa("*insertBackground", C["gold"])
    oa("*highlightBackground", C["border"])
    oa("*highlightColor", C["border"])
    oa("*selectBackground", C["navy"])
    oa("*Frame.background", C["surface"])
    oa("*Label.background", C["surface"])
    oa("*Labelframe.background", C["panel"])
    oa("*Labelframe.foreground", C["gold"])
    oa("*Button.background", C["navy2"])
    oa("*Button.foreground", C["text"])
    oa("*Checkbutton.background", C["panel"])
    oa("*Checkbutton.foreground", C["text"])
    oa("*Radiobutton.background", C["panel"])
    oa("*Radiobutton.foreground", C["text"])
    oa("*Listbox.background", C["panel"])
    oa("*Listbox.foreground", C["text"])
    oa("*Entry.background", C["panel"])
    oa("*Entry.foreground", C["text"])
    oa("*Scrollbar.background", C["panel"])

def _apply_ttk_styles(C):
    try:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=C["bg"])
        style.configure("TLabelframe", background=C["panel"], foreground=C["gold"], bordercolor=C["border"])
        style.configure("TLabelframe.Label", background=C["panel"], foreground=C["gold"])
        style.configure("TNotebook", background=C["bg"], bordercolor=C["border"])
        style.configure(
            "TNotebook.Tab",
            background=C["panel"], foreground=C["muted"],
            lightcolor=C["panel"], bordercolor=C["border"], padding=(14, 6)
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", C["surface"])],
            foreground=[("selected", C["gold"])]
        )
        style.configure("TButton", background=C["navy2"], foreground=C["text"], borderwidth=0, focusthickness=3)
        style.map("TButton", background=[("active", C["navy"])], foreground=[("active", C["gold_light"])])
        style.configure("TProgressbar", background=C["gold"], troughcolor=C["panel"])
    except Exception:
        pass

def apply_brand_theme(root):
    C = BRAND["active"]
    _apply_option_database(root, C)
    _apply_ttk_styles(C)

def apply_light_theme(root):
    BRAND["active"] = dict(BRAND_COLORS_LIGHT)
    apply_brand_theme(root)

def apply_dark_theme(root):
    BRAND["active"] = dict(BRAND_COLORS_DARK)
    apply_brand_theme(root)

def brandify_all_widgets(root):
    C = BRAND["active"]
    def paint(w):
        for ch in w.winfo_children():
            try:
                if isinstance(ch, tk.Canvas):
                    ch.configure(background=C["panel"])
                elif isinstance(ch, tk.LabelFrame):
                    ch.configure(background=C["panel"], fg=C["gold"], highlightbackground=C["border"], highlightthickness=1)
                elif isinstance(ch, tk.Frame):
                    ch.configure(background=C["surface"], highlightbackground=C["border"], highlightthickness=0)
                elif isinstance(ch, tk.Label):
                    ch.configure(background=C["surface"], fg=C["text"])
                elif isinstance(ch, tk.Button):
                    ch.configure(background=C["navy2"], fg=C["text"], activebackground=C["navy"], activeforeground=C["gold_light"])
                elif isinstance(ch, tk.Listbox):
                    ch.configure(background=C["panel"], fg=C["text"], selectbackground=C["navy"], highlightbackground=C["border"])
                elif isinstance(ch, tk.Entry):
                    ch.configure(background=C["panel"], fg=C["text"], insertbackground=C["gold"])
                elif isinstance(ch, tk.Toplevel):
                    ch.configure(background=C["bg"])
            except Exception:
                pass
            paint(ch)
    paint(root)

############################
# Configuration (defaults)
############################
KNOWN_FACES_DIR = "known_faces"
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

yolo_weights = "yolov3.weights"
yolo_config = "yolov3.cfg"
yolo_labels = "coco.names"

DETECTION_CONF_THRESH = 0.5
NMS_THRESH = 0.4
AUTO_PLACE_TIMEOUT = 5.0
HELD_LOG_INTERVAL = 1.0
PERSON_LOG_COOLDOWN = 120.0
PERSON_COLOR_LOG_COOLDOWN = 45.0

SNAPSHOT_COOLDOWN_FACE = 0.2
SNAPSHOT_COOLDOWN_VEHICLE = 0.2

UNKNOWN_PERSON_PERSISTENCE = 1.0
UNKNOWN_PERSON_SNAPSHOT_COOLDOWN = 0.4

VEHICLE_IDLE_FRAC = 0.15
UNKNOWN_PERSON_IDLE_FRAC = 0.15

UNKNOWN_MATCH_TOLERANCE = 0.60

# Capture resolution (source). UI can auto-fit display size separately.
FEED_W, FEED_H = 320, 240
FPS_CAP = 33           # ms between UI updates (lower = faster)
FRAME_SKIP = 0         # 0 = process every frame
FACE_MODEL = "hog"

MAX_CAMERAS = 8

RETAG_HOLD_SECONDS = 10.0
SPOT_LOCKS_MAX_PER_KEY = 8
spot_locks = defaultdict(list)

############################
# Check YOLO files
############################
if not all(os.path.exists(f) for f in [yolo_weights, yolo_config, yolo_labels]):
    root_temp = tk.Tk(); root_temp.withdraw()
    messagebox.showerror("YOLO Files Missing", "Please ensure YOLO weight, config, and labels files are present.")
    root_temp.destroy()
    sys.exit(1)

############################
# Load YOLO
############################
net = cv2.dnn.readNet(yolo_weights, yolo_config)
try:
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
    logger.info("Using CUDA backend for DNN.")
except Exception:
    try:
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        logger.info("Using CPU backend for DNN.")
    except Exception:
        pass

with open(yolo_labels, "r") as f:
    classes = [line.strip() for line in f]

layer_names = net.getLayerNames()
output_layers = [layer_names[i - 1] for i in np.array(net.getUnconnectedOutLayers()).reshape(-1).tolist()]

############################
# --- Graceful shutdown & timer management (ADD) ---
############################
SHUTTING_DOWN = False
AFTER_IDS = []

def schedule_after(delay_ms, func, widget=None):
    global AFTER_IDS
    if SHUTTING_DOWN:
        return None
    try:
        w = widget if widget is not None else root
    except NameError:
        return None
    try:
        aid = w.after(int(delay_ms), func)
        AFTER_IDS.append(aid)
        return aid
    except Exception:
        return None

def cancel_all_afters():
    global AFTER_IDS
    try:
        for aid in list(AFTER_IDS):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    finally:
        AFTER_IDS.clear()

############################
# Data Structures
############################
known_encodings, known_names = [], []
unknown_encodings, unknown_ids = [], []
unknown_id_counter = 0

unknown_faces_queue = []
UNKNOWN_FACE_QUEUE_MAX = 100

object_memory = {}
custom_labels_by_yolo = {}
custom_labels_by_yolo_and_color = {}
tracked_objects = set()
colors = {}

object_states = {}

person_memory = {}
PERSON_MEMORY_FILE = "person_memory.json"
person_last_logged = {}

person_last_color_logged = {}
person_current_shirt_color = {}

current_detections = []
camera_live_logs = defaultdict(list)
MAX_LIVE_LOG_LINES = 2000

camera_vars = {}
cam_toggle_text = {}
camera_cells = {}
camera_windows = OrderedDict()
camera_workers = {}

last_face_enqueue_ts_by_uid = {}
unknown_person_presence_start_by_key = defaultdict(float)
last_unknownperson_enqueue_ts_by_key = defaultdict(float)
last_unknownperson_snapshot_box_by_key = {}

unknown_person_id_counter = 0
vehicle_id_counter = 0

# Vehicle snapshot RL dicts (needed by pipeline)
last_vehicle_enqueue_ts_by_camlabel = defaultdict(float)
last_vehicle_snapshot_box_by_camlabel = {}

#############################################
# Live Stats
#############################################
app_start_ts = time.time()
recent_detection_times = deque(maxlen=5000)
recent_object_event_times = deque(maxlen=2000)
detection_rate_history = deque(maxlen=240)

############################
# Vehicle DB (local)
############################
VEHICLE_DB_FILE = "vehicle_db.json"
VEHICLE_SNAPSHOT_DIR = "vehicle_snaps"
os.makedirs(VEHICLE_SNAPSHOT_DIR, exist_ok=True)
vehicle_db = {}

def _vehicle_ahash(img_bgr) -> str:
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        mean = small.mean()
        bits = (small > mean).astype(np.uint8)
        val = 0
        for b in bits.flatten():
            val = (val << 1) | int(b)
        return f"{val:016x}"
    except Exception:
        return f"{random.getrandbits(64):016x}"

def load_vehicle_db():
    global vehicle_db
    if os.path.exists(VEHICLE_DB_FILE):
        try:
            with open(VEHICLE_DB_FILE, "r", encoding="utf-8") as f:
                vehicle_db = json.load(f)
        except Exception as e:
            logger.error(f"Error loading vehicle DB: {e}")
            vehicle_db = {}
    else:
        vehicle_db = {}

def save_vehicle_db():
    try:
        with open(VEHICLE_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(vehicle_db, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving vehicle DB: {e}")

def register_vehicle_sighting(
    roi_bgr, make, model, plate, fleet_id, nickname,
    color_name, color_hex, cam, box, assoc_person=None
):
    if roi_bgr is None or roi_bgr.size == 0:
        return None
    vid = _vehicle_ahash(roi_bgr)
    ts = time.time()

    entry = vehicle_db.get(vid, {
        "id": vid, "first_seen": ts,
        "make": None, "model": None, "plate": None, "fleet_id": None,
        "nicknames": [], "color_name": None, "color_hex": None,
        "snapshots": [], "sightings": []
    })

    if make:      entry["make"] = make
    if model:     entry["model"] = model
    if plate:     entry["plate"] = plate
    if fleet_id:  entry["fleet_id"] = fleet_id
    if nickname and nickname not in entry["nicknames"]:
        entry["nicknames"].append(nickname)

    if color_name: entry["color_name"] = color_name
    if color_hex:  entry["color_hex"] = color_hex

    try:
        snap_path = os.path.join(VEHICLE_SNAPSHOT_DIR, f"{vid}_{int(ts)}.jpg")
        cv2.imwrite(snap_path, roi_bgr)
        entry["snapshots"].append(snap_path)
        entry["snapshots"] = entry["snapshots"][-10:]
    except Exception as e:
        logger.debug(f"Vehicle snapshot save failed: {e}")

    sight = {"time": ts, "camera": cam, "box": box}
    if assoc_person:
        sight["person"] = assoc_person
    entry["sightings"].append(sight)

    vehicle_db[vid] = entry
    save_vehicle_db()
    logger.info(f"[{cam}] Vehicle saved: make={make} model={model} plate={plate} fleet={fleet_id} nick={nickname}")
    return vid

############################
# NEW — Review Notes (persistent documentation)
############################
REVIEW_NOTES_FILE = "review_notes.json"
review_notes = {}

def _load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {path}: {e}")

def load_review_notes():
    global review_notes
    review_notes = _load_json(REVIEW_NOTES_FILE, {}) or {}

def save_review_notes():
    _save_json(REVIEW_NOTES_FILE, review_notes)

def _ensure_note_bucket(category, key):
    if category not in review_notes:
        review_notes[category] = {}
    if key not in review_notes[category]:
        review_notes[category][key] = []

def _add_note(category, key, text):
    _ensure_note_bucket(category, key)
    review_notes[category][key].append({"time": time.time(), "text": text})
    save_review_notes()

def _human_time(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

############################
# Notifications (persisted)
############################
NOTIFY_FILE = "notify.json"
NOTIFY_COOLDOWN_SECONDS = 60.0
NOTIFY_MEDIA_DIR = "notify_media"
os.makedirs(NOTIFY_MEDIA_DIR, exist_ok=True)

notify_config = {
    "channel": "none",
    "attach_images": 1,
    "pushover": {"token": "", "user": ""},
    "telegram": {"bot_token": "", "chat_id": ""},
    "webhook": {"url": ""},
    "twilio": {"sid": "", "token": "", "from": "", "to": ""},
    "media_hosting": {"mode": "none", "port": 8765, "base_url": ""}
}
notify_subscriptions = {"persons": [], "objects": [], "vehicle_labels": []}
_notify_last_sent = defaultdict(float)

def load_notify_settings():
    global notify_config, notify_subscriptions, NOTIFY_COOLDOWN_SECONDS
    data = _load_json(NOTIFY_FILE, {})
    if data:
        cfg = data.get("config", {})
        subs = data.get("subscriptions", {})
        NOTIFY_COOLDOWN_SECONDS = data.get("cooldown", NOTIFY_COOLDOWN_SECONDS)
        for k, v in cfg.items():
            if isinstance(v, dict) and k in notify_config:
                notify_config[k].update(v)
            else:
                notify_config[k] = v
        for k, v in subs.items():
            notify_subscriptions[k] = v

def save_notify_settings():
    _save_json(NOTIFY_FILE, {
        "config": notify_config,
        "subscriptions": notify_subscriptions,
        "cooldown": NOTIFY_COOLDOWN_SECONDS
    })

_media_server = None
_media_server_thread = None

class _MediaHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        rel = path.lstrip("/")
        rel_path = rel.split("..")[0]
        return os.path.join(NOTIFY_MEDIA_DIR, os.path.basename(rel_path))

def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def _start_media_server_if_needed():
    global _media_server, _media_server_thread
    mode = notify_config.get("media_hosting", {}).get("mode", "none")
    if mode != "builtin":
        return
    if _media_server is not None:
        return
    port = int(notify_config.get("media_hosting", {}).get("port", 8765))
    try:
        class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True
        _media_server = _ThreadingServer(("0.0.0.0", port), _MediaHandler)
        _media_server_thread = threading.Thread(target=_media_server.serve_forever, daemon=True)
        _media_server_thread.start()
        logger.info(f"Built-in notify media server started on port {port}.")
    except Exception as e:
        logger.error(f"Failed to start media server: {e}")
        _media_server = None
        _media_server_thread = None

def _save_jpeg_and_get_url(img_bgr):
    if img_bgr is None or img_bgr.size == 0:
        return None, None
    ts = int(time.time() * 1000)
    fname = f"snap_{ts}_{random.randint(1000,9999)}.jpg"
    fpath = os.path.join(NOTIFY_MEDIA_DIR, fname)
    try:
        ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            return None, None
        with open(fpath, "wb") as f:
            f.write(bytearray(buf))
    except Exception as e:
        logger.error(f"Failed to save notify image: {e}")
        return None, None

    try:
        files = sorted((os.path.join(NOTIFY_MEDIA_DIR, x) for x in os.listdir(NOTIFY_MEDIA_DIR) if x.endswith(".jpg")),
                       key=lambda p: os.path.getmtime(p))
        if len(files) > 200:
            for p in files[:-200]:
                try: os.remove(p)
                except Exception: pass
    except Exception:
        pass

    mh = notify_config.get("media_hosting", {})
    mode = (mh.get("mode") or "none").lower()
    if mode == "static_url_prefix":
        base = mh.get("base_url", "").rstrip("/")
        if base:
            return fpath, f"{base}/{os.path.basename(fpath)}"
    elif mode == "builtin":
        _start_media_server_if_needed()
        port = int(mh.get("port", 8765))
        ip = _get_local_ip()
        return fpath, f"http://{ip}:{port}/{os.path.basename(fpath)}"
    return fpath, None

def _send_pushover(title, message, img_bgr=None):
    tok = notify_config.get("pushover", {}).get("token", "").strip()
    usr = notify_config.get("pushover", {}).get("user", "").strip()
    if not tok or not usr:
        raise RuntimeError("Pushover token/user missing")
    boundary = f"----pushover{int(time.time()*1000)}{random.randint(1000,9999)}"
    def _part(name, value):
        return (f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n").encode("utf-8")
    body = b""
    body += _part("token", tok)
    body += _part("user", usr)
    body += _part("title", title)
    body += _part("message", message)
    if notify_config.get("attach_images", 1) and img_bgr is not None:
        ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if ok:
            body += (f"--{boundary}\r\n"
                     f'Content-Disposition: form-data; name="attachment"; filename="snapshot.jpg"\r\n'
                     f"Content-Type: image/jpeg\r\n\r\n").encode("utf-8")
            body += bytearray(buf) + b"\r\n"
    body += (f"--{boundary}--\r\n").encode("utf-8")
    req = urllib.request.Request("https://api.pushover.net/1/messages.json",
                                 data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
        resp.read()

def _send_telegram(title, message, img_bgr=None):
    bot  = notify_config.get("telegram", {}).get("bot_token", "").strip()
    chat = notify_config.get("telegram", {}).get("chat_id", "").strip()
    if not bot or not chat:
        raise RuntimeError("Telegram bot_token/chat_id missing")
    if notify_config.get("attach_images", 1) and img_bgr is not None:
        boundary = f"----tg{int(time.time()*1000)}{random.randint(1000,9999)}"
        def _part_text(name, value):
            return (f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n").encode("utf-8")
        ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            text = f"*{title}*\n{message}"
            data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
            url = f"https://api.telegram.org/bot{bot}/sendMessage"
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp.read()
            return
        body = b""
        body += _part_text("chat_id", chat)
        body += _part_text("caption", f"{title}\n{message}")
        body += (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="photo"; filename="snapshot.jpg"\r\n'
                 f"Content-Type: image/jpeg\r\n\r\n").encode("utf-8")
        body += bytearray(buf) + b"\r\n"
        body += (f"--{boundary}--\r\n").encode("utf-8")
        url = f"https://api.telegram.org/bot{bot}/sendPhoto"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            resp.read()
    else:
        text = f"*{title}*\n{message}"
        data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
        url = f"https://api.telegram.org/bot{bot}/sendMessage"
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=12) as resp:
            resp.read()

def _send_webhook(title, message, img_bgr=None):
    url = notify_config.get("webhook", {}).get("url", "").strip()
    if not url:
        raise RuntimeError("Webhook URL missing")
    payload = {"title": title, "message": message, "ts": time.time()}
    if notify_config.get("attach_images", 1) and img_bgr is not None:
        ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ok:
            payload["image_jpeg_b64"] = base64.b64encode(bytearray(buf)).decode("ascii")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
        resp.read()

def _send_twilio_sms(title, message, img_bgr=None):
    sid   = notify_config.get("twilio", {}).get("sid", "").strip()
    token = notify_config.get("twilio", {}).get("token", "").strip()
    _from = notify_config.get("twilio", {}).get("from", "").strip()
    _to   = notify_config.get("twilio", {}).get("to", "").strip()
    if not sid or not token or not _from or not _to:
        raise RuntimeError("Twilio SID/token/from/to missing")
    text = f"{title}: {message}"
    params = {"To": _to, "From": _from, "Body": text}
    if notify_config.get("attach_images", 1) and img_bgr is not None:
        _, media_url = _save_jpeg_and_get_url(img_bgr)
        if media_url:
            params["MediaUrl"] = media_url
    data = urllib.parse.urlencode(params).encode("utf-8")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    req = urllib.request.Request(url, data=data)
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req, timeout=12) as resp:
        resp.read()

def send_notification(title, message, key_for_cooldown=None, image_bgr=None):
    ch = (notify_config.get("channel") or "none").lower()
    if ch == "none":
        return False
    now = time.time()
    if key_for_cooldown:
        last = _notify_last_sent.get(key_for_cooldown, 0.0)
        if (now - last) < NOTIFY_COOLDOWN_SECONDS:
            return False
    try:
        if ch == "pushover":
            _send_pushover(title, message, image_bgr)
        elif ch == "telegram":
            _send_telegram(title, message, image_bgr)
        elif ch == "webhook":
            _send_webhook(title, message, image_bgr)
        elif ch == "twilio_sms":
            _send_twilio_sms(title, message, image_bgr)
        else:
            return False
        if key_for_cooldown:
            _notify_last_sent[key_for_cooldown] = now
        logger.info(f"Notification sent via {ch}: {title}")
        return True
    except Exception as e:
        logger.error(f"Notification error ({ch}): {e}")
        return False

def _notify_maybe_person(name, camera, image_bgr=None):
    try:
        if name in set(notify_subscriptions.get("persons", [])):
            title = "Person detected"
            message = f"{name} on {camera} at {time.strftime('%H:%M:%S')}"
            send_notification(title, message, key_for_cooldown=f"person:{name}", image_bgr=image_bgr)
    except Exception as e:
        logger.debug(f"notify person failed: {e}")

def _notify_maybe_object(display_label, status, camera, image_bgr=None):
    try:
        if status not in ("Picked Up", "Placed"):
            return
        if display_label in set(notify_subscriptions.get("objects", [])):
            title = "Object event"
            message = f"{display_label} {status} on {camera} at {time.strftime('%H:%M:%S')}"
            send_notification(title, message, key_for_cooldown=f"object:{display_label}:{status}", image_bgr=image_bgr)
    except Exception as e:
        logger.debug(f"notify object failed: {e}")

def _notify_maybe_vehicle_label(yolo_label, camera, image_bgr=None):
    try:
        if yolo_label in set(notify_subscriptions.get("vehicle_labels", [])):
            title = "Vehicle detected"
            message = f"{yolo_label} on {camera} at {time.strftime('%H:%M:%S')}"
            send_notification(title, message, key_for_cooldown=f"vehicle_label:{yolo_label}", image_bgr=image_bgr)
    except Exception as e:
        logger.debug(f"notify vehicle failed: {e}")

# ===================================================================
# Communications Engine + Dataset Q/A (globals + helpers)
# ===================================================================
CHAT_HISTORY_FILE = "chat_history.json"
conversation_history = []

comms_state = {
    "voice_enabled": True,
    "beep_enabled": True,
    "wake_enabled": False,
    "wake_phrase": "hey sentinel ai",   # accepts "hey setinal ai"
    "tts_rate": 160,
    "phrase_time_limit": 6,
    "ambient_ms": 350,
    "dialog_cooldown": 3.0,
    "auto_narrate": True,
    "narrate_persons": True,
    "narrate_objects": True,
    "narrate_vehicles": True,
    "narrate_min_interval": 12.0,
}
_last_dialog_at = 0.0
_chat_ui_queue = queue.Queue()
_wake_thread = None
_wake_stop = threading.Event()

_tts_engine = None
if pyttsx3 is not None:
    try:
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", int(comms_state["tts_rate"]))
    except Exception:
        _tts_engine = None

def _beep(freq=1000, ms=120):
    if not comms_state["beep_enabled"]:
        return
    try:
        if _HAS_WINSOUND:
            winsound.Beep(int(freq), int(ms))
        else:
            try:
                root.bell()
            except Exception:
                pass
    except Exception:
        pass

def speak_tts(text: str):
    if not text or not comms_state["voice_enabled"] or _tts_engine is None:
        return
    try:
        _tts_engine.setProperty("rate", int(comms_state["tts_rate"]))
        _tts_engine.say(text)
        _tts_engine.runAndWait()
    except Exception:
        pass

_sr_rec = sr.Recognizer() if sr is not None else None
_sr_lock = threading.Lock()

def listen_once(seconds=None, use_beep=True) -> str:
    if sr is None or _sr_rec is None:
        return ""
    seconds = seconds if seconds is not None else int(comms_state["phrase_time_limit"])
    try:
        if use_beep: _beep(880, 120)
        with _sr_lock:
            with sr.Microphone() as source:
                _sr_rec.adjust_for_ambient_noise(source, duration=float(comms_state["ambient_ms"])/1000.0)
                audio = _sr_rec.listen(source, phrase_time_limit=int(seconds))
        if use_beep: _beep(1200, 120)
        try:
            text = _sr_rec.recognize_google(audio)
        except sr.UnknownValueError:
            text = ""
        return (text or "").strip()
    except Exception:
        return ""

def load_chat_history():
    global conversation_history
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                conversation_history = json.load(f)
        except Exception:
            conversation_history = []
    else:
        conversation_history = []

def save_chat_history():
    try:
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(conversation_history, f, indent=2)
    except Exception:
        pass

def _append_chat(sender, text):
    if not text: return
    conversation_history.append({"time": time.time(), "sender": sender, "text": text})
    save_chat_history()

# --- dataset Q/A helpers using existing memory stores ---
def _best_fuzzy(query, candidates):
    q = (query or "").lower().strip()
    best, score = None, -1
    for cand in candidates:
        c = str(cand).lower()
        s = 3 if c == q else (2 if q in c or c in q else (1 if c.startswith(q) or q.startswith(c) else 0))
        if s > score:
            best, score = cand, s
    return best

def _answer_where_person(name):
    name2 = _best_fuzzy(name, person_memory.keys())
    if not name2:
        return f"I don't have any record of '{name}'."
    return recall_person_last_location_text(name2)

def _answer_where_object(name):
    keys = list(object_memory.keys())
    label = _best_fuzzy(name, keys) or _best_fuzzy(name, [str(k).replace("["," ").replace("]"," ").strip() for k in keys])
    if not label:
        return f"I can't find an object like '{name}'."
    if label not in object_memory:
        mapped = dict(zip([str(k).replace("["," ").replace("]"," ").strip() for k in keys], keys))
        label = mapped.get(label, label)
    return recall_object_last_location_text(label)

def _answer_where_vehicle(query):
    q = (query or "").lower().strip()
    best_entry, best_score = None, -1
    for entry in vehicle_db.values():
        cands = [entry.get("plate",""), " ".join(filter(None,[entry.get("make",""), entry.get("model","")]))]
        cands += entry.get("nicknames", []) or []
        for cand in cands:
            c = (cand or "").lower()
            s = 3 if c == q else (2 if q in c or c in q else (1 if c.startswith(q) or q.startswith(c) else 0))
            if s > best_score:
                best_entry, best_score = entry, s
    if not best_entry:
        return f"No vehicle found matching '{query}'."
    last_seen = max((s["time"] for s in best_entry.get("sightings", [])), default=None)
    cam = "Unknown"
    if last_seen is not None:
        for sgt in reversed(best_entry.get("sightings", [])):
            if sgt.get("time") == last_seen:
                cam = sgt.get("camera","Unknown"); break
    desc = " ".join(filter(None,[best_entry.get('make'), best_entry.get('model')])) or "Vehicle"
    plate = best_entry.get("plate") or "—"
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_seen)) if last_seen else "n/a"
    return f"{desc} (plate {plate}) was last seen on [{cam}] at {when}."

def _answer_who_picked_up(obj_name):
    label = _best_fuzzy(obj_name, object_memory.keys())
    if not label:
        return f"I have no events for '{obj_name}'."
    for e in reversed(object_memory.get(label, [])):
        if e.get("status") == "Picked Up" and e.get("person"):
            return f"{e['person']} picked up {label} on [{e.get('camera','Unknown')}] at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e['time']))}."
    return f"I don't see who picked up {label} yet."

def answer_from_dataset(user_text):
    tl = (user_text or "").lower().strip()
    if tl.startswith("where is ") or tl.startswith("where's "):
        target = user_text.split(" ", 2)[-1].strip(" ?")
        if _best_fuzzy(target, person_memory.keys()):
            return _answer_where_person(target)
        if _best_fuzzy(target, object_memory.keys()) or _best_fuzzy(target, [str(k).replace("["," ").replace("]"," ").strip() for k in object_memory.keys()]):
            return _answer_where_object(target)
        return _answer_where_vehicle(target)
    if "who picked up" in tl:
        target = tl.split("who picked up",1)[-1].strip(" ?.").strip()
        return _answer_who_picked_up(target)
    if "when did we last see" in tl:
        target = tl.split("when did we last see",1)[-1].strip(" ?.")
        if _best_fuzzy(target, person_memory.keys()):
            nm = _best_fuzzy(target, person_memory.keys())
            evts = person_memory.get(nm, [])
            if not evts: return f"No history for {nm}."
            last = evts[-1]
            return f"{nm} was last seen on [{last.get('camera','Unknown')}] at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last['time']))}."
        if _best_fuzzy(target, object_memory.keys()):
            return _answer_where_object(target)
        return _answer_where_vehicle(target)
    if "list known persons" in tl or "list people" in tl:
        names = ", ".join(sorted(k for k in person_memory.keys() if not str(k).lower().startswith("unknown"))) or "none"
        return f"Known persons: {names}."
    if "list objects" in tl:
        objs = ", ".join(sorted(object_memory.keys())) or "none"
        return f"Objects: {objs}."
    if "list vehicles" in tl:
        v = []
        for e in vehicle_db.values():
            desc = " ".join(filter(None,[e.get('make'), e.get('model')])) or "Vehicle"
            plate = e.get("plate") or "—"
            v.append(f"{desc} (plate {plate})")
        return "Vehicles: " + (", ".join(sorted(v)) or "none") + "."
    return None

def smalltalk_reply(_):
    return "Okay."

def answer_user(user_text):
    global _last_dialog_at
    now = time.time()
    if (now - _last_dialog_at) < float(comms_state["dialog_cooldown"]):
        time.sleep(0.05)
    _last_dialog_at = time.time()
    ds = answer_from_dataset(user_text)
    if ds: return ds
    return smalltalk_reply(user_text)

def _wake_loop():
    if sr is None or _sr_rec is None: return
    try:
        with sr.Microphone() as source:
            _sr_rec.adjust_for_ambient_noise(source, duration=float(comms_state["ambient_ms"])/1000.0)
            while not _wake_stop.is_set():
                try:
                    audio = _sr_rec.listen(source, timeout=1.2, phrase_time_limit=4)
                    text = ""
                    try:
                        text = _sr_rec.recognize_google(audio)
                    except sr.UnknownValueError:
                        text = ""
                    tl = (text or "").lower().strip()
                    if not tl:
                        continue
                    if (comms_state["wake_phrase"] in tl) or ("hey setinal ai" in tl):
                        try: _beep(880, 100); _beep(1200, 100)
                        except Exception: pass
                        q = listen_once(comms_state["phrase_time_limit"], use_beep=False)
                        if q:
                            chat_add_message("You", q)
                            reply = answer_user(q)
                            chat_add_message("AI", reply, speak=True)
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    time.sleep(0.2)
    except Exception:
        pass

def start_wake_listener():
    global _wake_thread
    if _wake_thread and _wake_thread.is_alive(): return
    _wake_stop.clear()
    _wake_thread = threading.Thread(target=_wake_loop, daemon=True)
    _wake_thread.start()

def stop_wake_listener():
    _wake_stop.set()

def stop_wake_listener_and_join(timeout=1.5):
    try:
        stop_wake_listener()
    finally:
        t = _wake_thread
        if t and t.is_alive():
            try:
                t.join(timeout=timeout)
            except Exception:
                pass

comms_widgets = {}  # set later by UI

def chat_add_message(sender, text, speak=False):
    _append_chat(sender, text)
    _chat_ui_queue.put((sender, text, speak))

def _drain_chat_ui():
    if SHUTTING_DOWN:
        return
    try:
        while True:
            sender, text, speak = _chat_ui_queue.get_nowait()
            try:
                box = comms_widgets.get("display")
                if box is not None:
                    box.config(state="normal")
                    box.insert("end", f"{sender}: {text}\n\n")
                    box.yview("end")
                    box.config(state="disabled")
            except Exception:
                pass
            if speak:
                try: speak_tts(text)
                except Exception: pass
    except queue.Empty:
        pass
    schedule_after(80, _drain_chat_ui)

last_narrated_at_by_key = defaultdict(float)
def _narrate_detection(cam, label):
    msg = None
    if label.startswith("person:") and comms_state["narrate_persons"]:
        who = label.split("person:",1)[-1].strip()
        msg = f"I see {who} on {cam}."
    elif any(label.lower().startswith(x) for x in ["car","bus","truck","motorbike","bicycle","train","boat","airplane","aeroplane"]) and comms_state["narrate_vehicles"]:
        msg = f"Vehicle detected ({label}) on {cam}."
    elif comms_state["narrate_objects"] and not label.startswith("person:"):
        msg = f"{label} on {cam}."
    if msg:
        chat_add_message("AI", msg, speak=True)

def comms_tick():
    if SHUTTING_DOWN:
        return
    try:
        if comms_state["auto_narrate"]:
            now = time.time()
            for cam, label, *_ in list(current_detections)[-50:]:
                k = f"{cam}|{label}"
                if (now - last_narrated_at_by_key[k]) >= float(comms_state["narrate_min_interval"]):
                    _narrate_detection(cam, label)
                    last_narrated_at_by_key[k] = now
    except Exception:
        pass
    schedule_after(1500, comms_tick)

############################
# Utils
############################
def get_display_label(yolo_label: str, color_name: str = None) -> str:
    base = None
    if color_name is not None:
        base = custom_labels_by_yolo_and_color.get((yolo_label, color_name))
    if base is None:
        base = custom_labels_by_yolo.get(yolo_label, yolo_label)
    if color_name:
        return f"{base} [{color_name}]"
    return base

def ensure_color(label: str):
    if label not in colors:
        colors[label] = (random.randint(60, 255), random.randint(60, 255), random.randint(60, 255))
    return colors[label]

def boxes_overlap(boxA, boxB) -> bool:
    xA, yA, wA, hA = boxA
    xB, yB, wB, hB = boxB
    inter_x1 = max(xA, xB)
    inter_y1 = max(yA, yB)
    inter_x2 = min(xA + wA, xB + wB)
    inter_y2 = min(yA + hA, yB + hB)
    return (inter_x2 > inter_x1) and (inter_y2 > inter_y1)

def log_camera_event(cam, text):
    ts = time.strftime("%H:%M:%S")
    line = f"{ts} | {text}"
    camera_live_logs[cam].append(line)
    if len(camera_live_logs[cam]) > MAX_LIVE_LOG_LINES:
        camera_live_logs[cam] = camera_live_logs[cam][-MAX_LIVE_LOG_LINES:]

def camera_name(idx):
    return f"Camera {idx}"

############################
# Color Utils (+ Shirt Color)
############################
def rgb_tuple_to_hex(rgb):
    r, g, b = rgb
    return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))

def dominant_color_from_bgr(bgr_img) -> tuple:
    if bgr_img is None or bgr_img.size == 0:
        return (0, 0, 0)
    h, w = bgr_img.shape[:2]
    scale = 0.25 if (h * w > 40000) else 1.0
    if scale != 1.0:
        bgr_img = cv2.resize(bgr_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    Z = bgr_img.reshape((-1, 3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(Z, 3, None, criteria, 1, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten())
    dom_bgr = centers[np.argmax(counts)]
    b, g, r = dom_bgr.astype(int).tolist()
    return (r, g, b)

def rgb_to_basic_name(r, g, b) -> str:
    bgr = np.uint8([[[b, g, r]]])
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0]
    h, s, v = int(hsv[0]) * 2, int(hsv[1]), int(hsv[2])
    if v < 40: return "Black"
    if s < 25:
        if v > 210: return "White"
        return "Gray"
    if   (h < 15) or (h >= 345): return "Red"
    elif h < 33:  return "Orange"
    elif h < 45:  return "Yellow"
    elif h < 70:  return "Lime"
    elif h < 150: return "Green"
    elif h < 190: return "Cyan"
    elif h < 255: return "Blue"
    elif h < 285: return "Purple"
    else:         return "Magenta"

def color_swatches_on_frame(frame, x, y, rgb):
    r, g, b = [int(c) for c in rgb]
    bgr = (b, g, r)
    y1 = max(0, y - 16)
    cv2.rectangle(frame, (x, y1), (x + 18, y1 + 12), bgr, -1)
    cv2.rectangle(frame, (x, y1), (x + 18, y1 + 12), (0, 0, 0), 1)

def compute_shirt_color(frame_bgr, face_box=None, person_box=None):
    try:
        H, W = frame_bgr.shape[:2]
        if face_box is not None:
            left  = int(face_box["left"]);   top = int(face_box["top"])
            right = int(face_box["right"]);  bottom = int(face_box["bottom"])
            fw = max(1, right - left); fh = max(1, bottom - top)
            cx = (left + right) // 2
            x1 = max(0, int(cx - 0.8 * fw))
            x2 = min(W, int(cx + 0.8 * fw))
            y1 = max(0, int(bottom + 0.2 * fh))
            y2 = min(H, int(bottom + 2.2 * fh))
        elif person_box is not None:
            x, y, pw, ph = [int(v) for v in person_box]
            x1 = max(0, int(x + 0.20 * pw))
            x2 = min(W, int(x + 0.80 * pw))
            y1 = max(0, int(y + 0.25 * ph))
            y2 = min(H, int(y + 0.75 * ph))
        else:
            return None, None, None
        if (x2 - x1) < 6 or (y2 - y1) < 6:
            return None, None, None
        roi = frame_bgr[y1:y2, x1:x2]
        if roi is None or roi.size == 0:
            return None, None, None
        rgb = dominant_color_from_bgr(roi)
        hexv = rgb_tuple_to_hex(rgb)
        name = rgb_to_basic_name(*rgb)
        return rgb, hexv, name
    except Exception:
        return None, None, None

############################
# Spot lock helpers
############################
def _prune_locks_now(now=None):
    if now is None:
        now = time.time()
    for key, lst in list(spot_locks.items()):
        keep = [lk for lk in lst if (now - lk['ts']) <= RETAG_HOLD_SECONDS]
        if keep:
            keep.sort(key=lambda d: d['ts'])
            spot_locks[key] = keep[-SPOT_LOCKS_MAX_PER_KEY:]
        else:
            spot_locks.pop(key, None)

def _center(box):
    x, y, w, h = box
    return (x + w / 2.0, y + h / 2.0, w, h)

def _box_close(a, b, frac):
    cx1, cy1, w1, h1 = _center(a)
    cx2, cy2, w2, h2 = _center(b)
    thrx = frac * max(w1, w2); thry = frac * max(h1, h2)
    return (abs(cx2 - cx1) <= thrx) and (abs(cy2 - cy1) <= thry)

def _box_idle(last_box, new_box, frac):
    cx1, cy1, w1, h1 = _center(last_box)
    cx2, cy2, w2, h2 = _center(new_box)
    thrx = frac * max(w1, w2)
    thry = frac * max(h1, h2)
    return (abs(cy2 - cy1) <= thry) and (abs(cx2 - cx1) <= thrx)

def _vehicle_is_idle(last_box, new_box):
    return _box_idle(last_box, new_box, VEHICLE_IDLE_FRAC)

def _is_in_locked_spot(key, new_box, idle_frac):
    now = time.time()
    _prune_locks_now(now)
    for lk in spot_locks.get(key, []):
        if _box_close(lk['box'], new_box, idle_frac):
            lk['ts'] = now
            return True
    return False

def _push_spot_lock(key, new_box):
    now = time.time()
    lst = spot_locks.get(key, [])
    merged = False
    for lk in lst:
        if boxes_overlap(lk['box'], new_box) or _box_close(lk['box'], new_box, 0.15):
            lk['box'] = new_box
            lk['ts'] = now
            merged = True
            break
    if not merged:
        lst.append({'box': new_box, 'ts': now})
        if len(lst) > SPOT_LOCKS_MAX_PER_KEY:
            lst.sort(key=lambda d: d['ts'])
            lst[:] = lst[-SPOT_LOCKS_MAX_PER_KEY:]
    spot_locks[key] = lst

############################
# Known faces load/save
############################
def load_known_faces():
    global known_encodings, known_names
    known_encodings, known_names = [], []
    if os.path.isdir(KNOWN_FACES_DIR):
        for person_name in os.listdir(KNOWN_FACES_DIR):
            person_dir = os.path.join(KNOWN_FACES_DIR, person_name)
            if os.path.isdir(person_dir):
                enc_path = os.path.join(person_dir, "encodings.npy")
                if os.path.exists(enc_path):
                    try:
                        data = np.load(enc_path, allow_pickle=True)
                        for enc in data:
                            known_encodings.append(enc)
                            known_names.append(person_name)
                        logger.info(f"Loaded encodings for {person_name}.")
                    except Exception as e:
                        logger.error(f"Error loading encodings for {person_name}: {e}")

def save_new_face(person_name, face_bgr_image, encoding):
    person_dir = os.path.join(KNOWN_FACES_DIR, person_name)
    os.makedirs(person_dir, exist_ok=True)
    timestamp = int(time.time() * 1000)
    image_path = os.path.join(person_dir, f"face_{timestamp}.png")
    try:
        cv2.imwrite(image_path, face_bgr_image)
    except Exception as e:
        logger.error(f"Failed to save face image: {e}")
    encodings_path = os.path.join(person_dir, "encodings.npy")
    try:
        if os.path.exists(encodings_path):
            existing = np.load(encodings_path, allow_pickle=True)
            new_encodings = np.vstack((existing, encoding))
        else:
            new_encodings = np.array([encoding])
        np.save(encodings_path, new_encodings)
    except Exception as e:
        logger.error(f"Error saving encodings for {person_name}: {e}")
    load_known_faces()

############################
# Person memory persistence
############################
def load_person_memory():
    global person_memory
    if os.path.exists(PERSON_MEMORY_FILE):
        try:
            with open(PERSON_MEMORY_FILE, 'r') as f:
                person_memory = json.load(f)
            for person, events in person_memory.items():
                if events:
                    person_last_logged[person] = events[-1]["time"]
            logger.info("Loaded person memory.")
        except Exception as e:
            logger.error(f"Error loading person memory: {e}")
            person_memory = {}
    else:
        person_memory = {}

def save_person_memory():
    try:
        with open(PERSON_MEMORY_FILE, 'w') as f:
            json.dump(person_memory, f, indent=4)
        logger.info("Person memory saved.")
    except Exception as e:
        logger.error(f"Error saving person memory: {e}")

############################
# YOLO detection
############################
def yolo_detect(frame, conf_thresh, nms_thresh):
    height, width, _ = frame.shape
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), (0, 0, 0), swapRB=True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)

    boxes, confidences, class_ids = [], [], []
    for out in outs:
        for det in out:
            scores = det[5:]
            cid = int(np.argmax(scores))
            class_score = float(scores[cid])
            objectness = float(det[4])
            conf = objectness * class_score
            if conf >= conf_thresh:
                cx, cy, ww, hh = det[0] * width, det[1] * height, det[2] * width, det[3] * height
                x = int(cx - ww / 2); y = int(cy - hh / 2)
                boxes.append([x, y, int(ww), int(hh)])
                confidences.append(conf)
                class_ids.append(cid)

    idxs = cv2.dnn.NMSBoxes(boxes, confidences, conf_thresh, nms_thresh)
    filtered_boxes, filtered_cids, filtered_conf = [], [], []
    if idxs is not None and len(idxs) > 0:
        for i in np.array(idxs).reshape(-1).tolist():
            filtered_boxes.append(boxes[i])
            filtered_cids.append(class_ids[i])
            filtered_conf.append(confidences[i])

    return filtered_boxes, filtered_cids, filtered_conf

def rate_detection(label, confidence, x, y, frame):
    if confidence > 0.85: rating = "Excellent"
    elif confidence > 0.7: rating = "Good"
    elif confidence > 0.5: rating = "Average"
    else: rating = "Poor"
    cv2.putText(frame, f"Rating: {rating}", (x, max(0, y - 25)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

############################
# Person logging (faces)
############################
def record_person_event(name, box, camera, shirt_rgb=None, shirt_hex=None, shirt_name=None):
    current_time = time.time()
    last_logged = person_last_logged.get(name, 0)
    if current_time - last_logged < PERSON_LOG_COOLDOWN:
        if shirt_name or shirt_hex or shirt_rgb:
            person_current_shirt_color[name] = {
                "rgb": shirt_rgb, "hex": shirt_hex, "name": shirt_name, "ts": current_time
            }
        return
    person_last_logged[name] = current_time
    if name not in person_memory:
        person_memory[name] = []
    event = {"time": current_time, "box": box, "camera": camera}
    if shirt_name or shirt_hex or shirt_rgb:
        event["shirt_color_rgb"]  = shirt_rgb
        event["shirt_color_hex"]  = shirt_hex
        event["shirt_color_name"] = shirt_name
        person_current_shirt_color[name] = {
            "rgb": shirt_rgb, "hex": shirt_hex, "name": shirt_name, "ts": current_time
        }
    person_memory[name].append(event)
    save_person_memory()
    update_person_dropdown()

def record_person_shirt_event(name, box, camera, shirt_rgb, shirt_hex, shirt_name):
    now = time.time()
    last = person_last_color_logged.get(name, 0.0)
    if (now - last) < PERSON_COLOR_LOG_COOLDOWN:
        return
    person_last_color_logged[name] = now
    record_person_event(name, box, camera, shirt_rgb=shirt_rgb, shirt_hex=shirt_hex, shirt_name=shirt_name)

############################
# Face recognition — returns shirt color info
############################
def assign_unknown_id(face_encoding) -> str:
    global unknown_id_counter
    if len(unknown_encodings) > 0:
        dists = face_recognition.face_distance(unknown_encodings, face_encoding)
        best_idx = int(np.argmin(dists))
        if dists[best_idx] < UNKNOWN_MATCH_TOLERANCE:
            return unknown_ids[best_idx]
    unknown_id_counter += 1
    uid = f"Unknown #{unknown_id_counter}"
    unknown_encodings.append(face_encoding)
    unknown_ids.append(uid)
    return uid

def remove_unknown_id(unknown_id: str):
    global unknown_encodings, unknown_ids
    keep_enc, keep_ids = [], []
    for enc, uid in zip(unknown_encodings, unknown_ids):
        if uid != unknown_id:
            keep_enc.append(enc)
            keep_ids.append(uid)
    unknown_encodings = keep_enc
    unknown_ids = keep_ids

def rename_person_everywhere(old_name: str, new_name: str):
    if old_name == new_name:
        return
    if old_name in person_memory:
        if new_name in person_memory:
            person_memory[new_name].extend(person_memory.pop(old_name))
        else:
            person_memory[new_name] = person_memory.pop(old_name)
    if old_name in person_last_logged:
        person_last_logged[new_name] = person_last_logged.pop(old_name)
    for label, events in object_memory.items():
        for evt in events:
            if evt.get("person") == old_name:
                evt["person"] = new_name
    for st in object_states.values():
        if st.get("person") == old_name:
            st["person"] = new_name
    update_person_dropdown()

def identify_faces(frame, camera_tag):
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame, model=FACE_MODEL)
    face_encs = face_recognition.face_encodings(rgb_frame, face_locations)
    labeled_faces = []
    now = time.time()

    for enc, loc in zip(face_encs, face_locations):
        top, right, bottom, left = loc
        name = "Unknown"

        if known_encodings:
            matches = face_recognition.compare_faces(known_encodings, enc, tolerance=0.6)
            distances = face_recognition.face_distance(known_encodings, enc)
            if len(distances) > 0:
                best_idx = int(np.argmin(distances))
                if matches[best_idx]:
                    name = known_names[best_idx]

        box_dict = {"left": int(left), "top": int(top), "right": int(right), "bottom": int(bottom)}
        s_rgb, s_hex, s_name = compute_shirt_color(frame, face_box=box_dict, person_box=None)

        if name == "Unknown":
            uid = assign_unknown_id(enc)
            name = uid
            record_person_event(name, box_dict, camera=camera_tag, shirt_rgb=s_rgb, shirt_hex=s_hex, shirt_name=s_name)
            last_ts = last_face_enqueue_ts_by_uid.get(uid, 0.0)
            if (now - last_ts) >= SNAPSHOT_COOLDOWN_FACE:
                face_crop = frame[max(0, top):max(0, bottom), max(0, left):max(0, right)].copy()
                if face_crop.size > 0:
                    unknown_faces_queue.append((enc, face_crop, uid, camera_tag, "face"))
                    while len(unknown_faces_queue) > UNKNOWN_FACE_QUEUE_MAX:
                        unknown_faces_queue.pop(0)
                    last_face_enqueue_ts_by_uid[uid] = now
        else:
            record_person_event(name, box_dict, camera=camera_tag, shirt_rgb=s_rgb, shirt_hex=s_hex, shirt_name=s_name)
            try:
                face_crop = frame[max(0, top):max(0, bottom), max(0, left):max(0, right)].copy()
            except Exception:
                face_crop = None
            _notify_maybe_person(name, camera_tag, image_bgr=face_crop)

        labeled_faces.append((top, right, bottom, left, name, s_name, s_hex, s_rgb))
        log_camera_event(camera_tag, f"Face: {name} at (x={left}, y={top}, w={right-left}, h={bottom-top})"
                         f"{' | shirt '+str(s_name)+' '+str(s_hex) if s_hex else ''}")
    return labeled_faces

############################
# Object events
############################
def record_event(display_label, status, box, person=None, held_duration=None, yolo_label=None, camera=None,
                 color_rgb=None, color_hex=None, color_name=None):
    if display_label not in object_memory:
        object_memory[display_label] = []
    event = {"time": time.time(), "box": box, "status": status, "person": person,
             "held_duration": held_duration, "yolo": yolo_label, "camera": camera,
             "color_rgb": color_rgb, "color_hex": color_hex, "color_name": color_name}
    object_memory[display_label].append(event)
    recent_object_event_times.append(time.time())
    tracked_objects.add(display_label)
    refresh_tracked_objects_list()
    update_object_dropdown()
    x, y, w, h = box
    held_str = f" | Held {held_duration:.2f}s" if held_duration is not None else ""
    color_str = f" | Color {color_name or ''} {color_hex or ''}".strip()
    log_camera_event(camera, f"Object '{display_label}' {status} by {person or 'No one'} at (x={x}, y={y}, w={w}, h={h}){held_str}{(' | '+color_str) if color_hex else ''}")
    try: _update_tracked_recall_label(display_label)
    except Exception: pass

def update_object_events(display_label, yolo_label, box, person, last_event, camera_tag,
                         color_rgb, color_hex, color_name):
    event_emitted = None
    now = time.time()
    first_seen = display_label not in object_states
    if first_seen:
        object_states[display_label] = {'state': 'Placed','last_seen': now,'person': None,'box': box,
                                        'picked_up_time': None,'last_hold_log': None,'yolo': yolo_label,'camera': camera_tag,
                                        'color_rgb': color_rgb,'color_hex': color_hex,'color_name': color_name}
        record_event(display_label, "Placed", box, person=None, held_duration=None,
                     yolo_label=yolo_label, camera=camera_tag, color_rgb=color_rgb, color_hex=color_hex, color_name=color_name)
        return "Placed"

    st = object_states[display_label]
    prev_state = st['state']; prev_person = st['person']
    st['last_seen'] = now; st['box'] = box; st['yolo'] = yolo_label; st['camera'] = camera_tag
    st['color_rgb'] = color_rgb; st['color_hex'] = color_hex; st['color_name'] = color_name

    if person:
        if prev_state == 'Placed' or (prev_state in ['Picked Up', 'Held'] and prev_person != person):
            st['state'] = 'Picked Up'; st['person'] = person; st['picked_up_time'] = now; st['last_hold_log'] = None
            record_event(display_label, "Picked Up", box, person=person, held_duration=None,
                         yolo_label=yolo_label, camera=camera_tag, color_rgb=color_rgb, color_hex=color_hex, color_name=color_name)
            event_emitted = "Picked Up"
        else:
            st['state'] = 'Held'; st['person'] = person
            last_hold_log = st['last_hold_log']
            if (last_hold_log is None) or (now - last_hold_log >= HELD_LOG_INTERVAL):
                start_time = st['picked_up_time'] if st['picked_up_time'] else (last_hold_log or now)
                held_duration = max(0.0, now - start_time)
                record_event(display_label, "Held", box, person=person, held_duration=held_duration,
                             yolo_label=yolo_label, camera=camera_tag, color_rgb=color_rgb, color_hex=color_hex, color_name=color_name)
                st['last_hold_log'] = now
                event_emitted = "Held"
    else:
        if prev_state in ['Picked Up', 'Held']:
            picked_up_time = st['picked_up_time'] or st['last_seen']
            held_duration = max(0.0, now - picked_up_time)
            record_event(display_label, "Placed", box, person=prev_person, held_duration=held_duration,
                         yolo_label=yolo_label, camera=camera_tag, color_rgb=color_rgb, color_hex=color_hex, color_name=color_name)
            st['state'] = 'Placed'; st['person'] = None; st['picked_up_time'] = None; st['last_hold_log'] = None
            event_emitted = "Placed"
    return event_emitted

############################
# Camera backend
############################
def _open_capture(idx, width, height, fps_cap_ms):
    api_prefs = []
    for attr in ["CAP_DSHOW", "CAP_MSMF", "CAP_V4L2", "CAP_AVFOUNDATION", "CAP_ANY"]:
        if hasattr(cv2, attr):
            api_prefs.append(getattr(cv2, attr))
    target_fps = max(15, min(60, int(1000.0 / max(1.0, float(fps_cap_ms)))))
    for api in api_prefs:
        cap = None
        try:
            cap = cv2.VideoCapture(idx, api)
        except Exception:
            try:
                cap = cv2.VideoCapture(idx)
            except Exception:
                cap = None
        if not cap or not cap.isOpened():
            if cap:
                try: cap.release()
                except Exception: pass
            continue
        try: cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        except Exception: pass
        try: cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        except Exception: pass
        try: cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        except Exception: pass
        try: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        except Exception: pass
        try: cap.set(cv2.CAP_PROP_FPS, target_fps)
        except Exception: pass
        if cap.isOpened():
            logger.info(f"{camera_name(idx)} opened.")
            return cap
        try: cap.release()
        except Exception: pass
    logger.error(f"Failed to open {camera_name(idx)} on all backends.")
    return None

class CameraWorker(threading.Thread):
    def __init__(self, idx, name, width, height, fps_cap_ms):
        super().__init__(daemon=True)
        self.idx = idx
        self.name = name
        self._width = width
        self._height = height
        self._fps_cap_ms = max(1, int(fps_cap_ms))
        self._sleep_interval = max(0.001, self._fps_cap_ms / 1000.0)
        self.cap = None
        self.lock = threading.Lock()
        self.latest_frame = None
        self.running = threading.Event()
        self._fail_count = 0

    def set_resolution(self, w, h):
        self._width, self._height = int(w), int(h)
        if self.cap and self.cap.isOpened():
            try: self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            except Exception: pass
            try: self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            except Exception: pass

    def set_fps_cap(self, fps_cap_ms):
        self._fps_cap_ms = max(1, int(fps_cap_ms))
        self._sleep_interval = max(0.001, self._fps_cap_ms / 1000.0)

    def run(self):
        self.running.set()
        while self.running.is_set():
            if self.cap is None or not self.cap.isOpened():
                self.cap = _open_capture(self.idx, self._width, self._height, self._fps_cap_ms)
                if not self.cap:
                    log_camera_event(self.name, "ERROR: Open failed; retrying...")
                    time.sleep(1.0)
                    continue
                self._fail_count = 0
                log_camera_event(self.name, "INFO: Camera opened.")

            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.latest_frame = frame
                time.sleep(self._sleep_interval)
            else:
                self._fail_count += 1
                if self._fail_count >= 5:
                    log_camera_event(self.name, "WARNING: Read fail; reopening...")
                    try: self.cap.release()
                    except Exception: pass
                    self.cap = None
                    self._fail_count = 0
                time.sleep(0.1)

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception: pass
        log_camera_event(self.name, "INFO: Camera stopped.")

    def get_frame(self):
        with self.lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def stop(self):
        self.running.clear()

############################
# Frame processing
############################
VEHICLE_LABELS = set(["car","bus","truck","motorbike","bicycle","train","boat","aeroplane","airplane"])

def process_frame(frame, camera_tag):
    boxes, cids, confs = yolo_detect(frame, DETECTION_CONF_THRESH, NMS_THRESH)
    face_labels = identify_faces(frame, camera_tag)
    now = time.time()

    for (ftop, fright, fbottom, fleft, fname, sname, shex, srgb) in face_labels:
        fx, fy, fw, fh = fleft, ftop, (fright - fleft), (fbottom - ftop)
        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 255, 0), 2)
        label = f"{fname} [face] [{camera_tag}]"
        if sname: label += f" | shirt {sname} {shex or ''}"
        cv2.putText(frame, label, (fx, max(0, fy - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        if srgb: color_swatches_on_frame(frame, fx, fy, srgb)
        current_detections.append((camera_tag, f"face:{fname}" + (f" [shirt {sname}]" if sname else ""), fx, fy, fw, fh, 1.0))
        recent_detection_times.append(time.time())

    people = []
    seen_unknown_keys_this_frame = set()

    # Persons
    for i, (x, y, w, h) in enumerate(boxes):
        cid = cids[i]
        yolo_label = classes[cid]
        if yolo_label == "person":
            person_name = "Unknown Person"
            matched_face_box = None
            matched_face_color = (None, None, None)

            for (ftop, fright, fbottom, fleft, fname, sname, shex, srgb) in face_labels:
                face_box = (fleft, ftop, fright - fleft, fbottom - ftop)
                if boxes_overlap((x, y, w, h), face_box):
                    person_name = fname
                    matched_face_box = {"left": int(fleft), "top": int(ftop),
                                        "right": int(fright), "bottom": int(fbottom)}
                    matched_face_color = (srgb, shex, sname)
                    break

            if matched_face_box is not None and matched_face_color[2]:
                s_rgb, s_hex, s_name = matched_face_color
            else:
                s_rgb, s_hex, s_name = compute_shirt_color(
                    frame,
                    face_box=matched_face_box if matched_face_box else None,
                    person_box=(x, y, w, h)
                )

            color = (255, 0, 0)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            label_str = f"{person_name} [person] [{camera_tag}]"
            if s_name: label_str += f" | shirt {s_name} {s_hex or ''}"
            cv2.putText(frame, label_str, (x, max(0, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if s_rgb: color_swatches_on_frame(frame, x, y, s_rgb)

            current_detections.append((camera_tag, f"person:{person_name}" + (f" [shirt {s_name}]" if s_name else ""), x, y, w, h, confs[i]))
            recent_detection_times.append(time.time())

            people.append(((x, y, w, h), person_name))
            if person_name != "Unknown Person" and s_name:
                box_dict = {"left": int(x), "top": int(y), "right": int(x + w), "bottom": int(y + h)}
                record_person_shirt_event(person_name, box_dict, camera_tag, s_rgb, s_hex, s_name)

            # Unknown person snapshot logic
            is_unknown_person = (person_name == "Unknown Person") or (isinstance(person_name, str) and person_name.startswith("Unknown #"))
            if is_unknown_person:
                key = (camera_tag, person_name if isinstance(person_name, str) and person_name.startswith("Unknown #") else "UnknownPersonGeneric")
                seen_unknown_keys_this_frame.add(key)

                start = unknown_person_presence_start_by_key.get(key, 0.0)
                if start == 0.0:
                    unknown_person_presence_start_by_key[key] = now
                else:
                    if (now - start) >= UNKNOWN_PERSON_PERSISTENCE:
                        rl_ok = (now - last_unknownperson_enqueue_ts_by_key[key]) >= UNKNOWN_PERSON_SNAPSHOT_COOLDOWN
                        last_box = last_unknownperson_snapshot_box_by_key.get(key)
                        idle = False
                        if last_box is not None:
                            idle = _box_idle(last_box, (x, y, w, h), UNKNOWN_PERSON_IDLE_FRAC)

                        spot_locked = _is_in_locked_spot((camera_tag, 'person'), (x, y, w, h), UNKNOWN_PERSON_IDLE_FRAC)

                        if rl_ok and (not idle) and (not spot_locked) and ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR.get() == 1:
                            roi = frame[max(0, y):max(0, y + h), max(0, x):max(0, x + w)].copy()
                            if roi.size > 0:
                                global unknown_person_id_counter
                                unknown_person_id_counter += 1
                                uid = f"UnknownPerson #{unknown_person_id_counter}" if person_name == "Unknown Person" else person_name
                                unknown_faces_queue.append((None, roi, uid, camera_tag, "person"))
                                while len(unknown_faces_queue) > UNKNOWN_FACE_QUEUE_MAX:
                                    unknown_faces_queue.pop(0)
                                last_unknownperson_enqueue_ts_by_key[key] = now
                                last_unknownperson_snapshot_box_by_key[key] = (x, y, w, h)
                                _push_spot_lock((camera_tag, 'person'), (x, y, w, h))

    # Reset persistence for keys not seen this frame
    for key in list(unknown_person_presence_start_by_key.keys()):
        cam, _ = key
        if cam == camera_tag and key not in seen_unknown_keys_this_frame:
            unknown_person_presence_start_by_key[key] = 0.0

    # Objects & vehicles
    now_obj = time.time()
    for i, (x, y, w, h) in enumerate(boxes):
        cid = cids[i]
        yolo_label = classes[cid]
        conf = confs[i]
        if yolo_label != "person":
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = max(0, x + w), max(0, y + h)
            roi = frame[y1:y2, x1:x2]
            dom_rgb = dominant_color_from_bgr(roi)
            color_hex = rgb_tuple_to_hex(dom_rgb)
            color_name = rgb_to_basic_name(*dom_rgb)

            display_label_color = get_display_label(yolo_label, color_name=color_name)
            color_draw = ensure_color(display_label_color)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color_draw, 2)
            text_str = f"{display_label_color} {int(conf * 100)}% {color_hex}"
            cv2.putText(frame, f"{text_str} [{camera_tag}]",
                        (x, max(0, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_draw, 2)
            rate_detection(display_label_color, conf, x, y, frame)
            color_swatches_on_frame(frame, x, y, dom_rgb)

            current_detections.append((camera_tag, display_label_color, x, y, w, h, conf))
            recent_detection_times.append(time.time())

            # Vehicle snapshots + notify
            if yolo_label in VEHICLE_LABELS and ENABLE_VEHICLE_SNAPSHOTS_VAR.get() == 1:
                key = (camera_tag, yolo_label)
                last_ts = last_vehicle_enqueue_ts_by_camlabel[key]
                last_box = last_vehicle_snapshot_box_by_camlabel.get(key)
                idle = False
                if last_box is not None:
                    idle = _vehicle_is_idle(last_box, (x, y, w, h))
                v_lock_key = (camera_tag, 'vehicle', yolo_label)
                spot_locked = _is_in_locked_spot(v_lock_key, (x, y, w, h), VEHICLE_IDLE_FRAC)

                if (not idle) and (now_obj - last_ts) >= SNAPSHOT_COOLDOWN_VEHICLE and (not spot_locked):
                    v_roi = frame[y1:y2, x1:x2].copy()
                    if v_roi.size > 0:
                        global vehicle_id_counter
                        vehicle_id_counter += 1
                        vuid = f"VehicleSnap #{vehicle_id_counter} ({yolo_label})"
                        unknown_faces_queue.append((None, v_roi, vuid, camera_tag, "vehicle"))
                        while len(unknown_faces_queue) > UNKNOWN_FACE_QUEUE_MAX:
                            unknown_faces_queue.pop(0)
                        last_vehicle_enqueue_ts_by_camlabel[key] = now_obj
                        last_vehicle_snapshot_box_by_camlabel[key] = (x, y, w, h)
                        _push_spot_lock(v_lock_key, (x, y, w, h))
                        _notify_maybe_vehicle_label(yolo_label, camera_tag, image_bgr=v_roi)

            person_for_obj = None
            for (pbox, pname) in people:
                if boxes_overlap((x, y, w, h), pbox):
                    person_for_obj = pname
                    break

            events = object_memory.get(display_label_color, [])
            last_event = events[-1] if events else None

            emitted = update_object_events(
                display_label_color, yolo_label, (x, y, w, h), person_for_obj, last_event,
                camera_tag=camera_tag, color_rgb=dom_rgb, color_hex=color_hex, color_name=color_name
            )
            if emitted in ("Picked Up", "Placed"):
                try:
                    roi_notify = frame[y1:y2, x1:x2].copy()
                except Exception:
                    roi_notify = None
                _notify_maybe_object(display_label_color, emitted, camera_tag, image_bgr=roi_notify)

    now2 = time.time()
    for display_label, st in list(object_states.items()):
        if st['state'] in ['Picked Up', 'Held'] and (now2 - st['last_seen']) > AUTO_PLACE_TIMEOUT:
            picked_up_time = st['picked_up_time'] or st['last_seen']
            held_duration = max(0.0, now2 - picked_up_time)
            record_event(
                display_label, "Placed", st['box'], person=st['person'],
                held_duration=held_duration, yolo_label=st.get('yolo'), camera=st.get('camera'),
                color_rgb=st.get('color_rgb'), color_hex=st.get('color_hex'), color_name=st.get('color_name')
            )
            _notify_maybe_object(display_label, "Placed", st.get('camera'), image_bgr=None)
            st['state'] = 'Placed'; st['person'] = None; st['picked_up_time'] = None; st['last_hold_log'] = None
    return frame

#############################################
# NEW — Pop-up Reviewer for Tracking Totals
#############################################
def open_review_popup(category):
    cat_title = {
        "persons_all": "Persons (All)",
        "persons_known": "Persons (Known)",
        "persons_unknown": "Persons (Unknown)",
        "objects": "Objects",
        "vehicles": "Vehicles"
    }.get(category, category)

    win = tk.Toplevel(root); win.title(f"Review — {cat_title}")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = int(sw*0.65), int(sh*0.7); x = (sw - ww)//2; y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1100x750+120+80")

    top = tk.Frame(win); top.pack(fill="x", padx=8, pady=6)
    tk.Label(top, text=f"Category: {cat_title}").pack(side=tk.LEFT)
    tk.Label(top, text="   Filter:").pack(side=tk.LEFT, padx=(10,4))
    filt_var = tk.StringVar(); tk.Entry(top, textvariable=filt_var, width=28).pack(side=tk.LEFT)

    body = tk.Frame(win); body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2,8))
    for c in (0,1): body.columnconfigure(c, weight=1)
    body.rowconfigure(0, weight=1)

    left = tk.Frame(body); left.grid(row=0, column=0, sticky="nsew", padx=(0,6))
    left.rowconfigure(1, weight=1)
    tk.Label(left, text="Items").grid(row=0, column=0, sticky="w")
    lb = tk.Listbox(left, exportselection=False)
    sb = tk.Scrollbar(left, orient=tk.VERTICAL, command=lb.yview)
    lb.config(yscrollcommand=sb.set)
    lb.grid(row=1, column=0, sticky="nsew"); sb.grid(row=1, column=1, sticky="ns")

    right = tk.Frame(body); right.grid(row=0, column=1, sticky="nsew")
    right.rowconfigure(3, weight=1)
    tk.Label(right, text="Details").grid(row=0, column=0, sticky="w")
    details = tk.Text(right, height=10, wrap="word")
    details.grid(row=1, column=0, sticky="nsew", pady=(2,6))
    actions = tk.Frame(right); actions.grid(row=2, column=0, sticky="ew", pady=(0,6))

    notes_frame = tk.LabelFrame(right, text="Documentation / Notes")
    notes_frame.grid(row=3, column=0, sticky="nsew")
    notes_frame.rowconfigure(1, weight=1)
    notes_frame.columnconfigure(0, weight=1)

    note_entry = tk.Text(notes_frame, height=4, wrap="word")
    note_entry.grid(row=0, column=0, sticky="ew", padx=6, pady=(6,2))
    notes_list = tk.Listbox(notes_frame)
    notes_scroll = tk.Scrollbar(notes_frame, orient=tk.VERTICAL, command=notes_list.yview)
    notes_list.config(yscrollcommand=notes_scroll.set)
    notes_list.grid(row=1, column=0, sticky="nsew", padx=(6,0), pady=(0,6))
    notes_scroll.grid(row=1, column=1, sticky="ns", padx=(0,6), pady=(0,6))

    def _save_note_for(current_key):
        txt = note_entry.get("1.0", "end").strip()
        if not current_key:
            messagebox.showinfo("No selection", "Select an item first."); return
        if not txt:
            messagebox.showinfo("Empty note", "Type a note before saving."); return
        _add_note(category, current_key, txt)
        note_entry.delete("1.0", "end")
        _refresh_notes(current_key)

    def _export_notes(current_key):
        if not current_key:
            messagebox.showinfo("No selection", "Select an item first."); return
        bucket = (review_notes.get(category, {}) or {}).get(current_key, [])
        if not bucket:
            messagebox.showinfo("No notes", "No notes to export for this item."); return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text Files","*.txt")],
                                            initialfile=f"{category}_{str(current_key).replace(' ','_')}_notes.txt")
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Notes for [{category}] {current_key}\n\n")
            for n in bucket:
                f.write(f"{_human_time(n['time'])}: {n['text']}\n")
        messagebox.showinfo("Saved", f"Exported notes to:\n{path}")

    def _items_for_category():
        if category == "persons_all":
            return sorted(person_memory.keys()), lambda k: k
        if category == "persons_known":
            items = sorted([k for k in person_memory.keys() if not str(k).lower().startswith("unknown")])
            return items, lambda k: k
        if category == "persons_unknown":
            items = sorted([k for k in person_memory.keys() if str(k).lower().startswith("unknown")])
            return items, lambda k: k
        if category == "objects":
            return sorted(object_memory.keys()), lambda k: k
        if category == "vehicles":
            return sorted(vehicle_db.keys()), lambda vid: vid
        return [], lambda k: k

    def _details_for_person(name):
        if name not in person_memory or not person_memory[name]:
            return "No history."
        last = person_memory[name][-1]
        b = last["box"]; cam = last.get("camera","Unknown")
        x, y, w, h = b["left"], b["top"], b["right"]-b["left"], b["bottom"]-b["top"]
        s = ""
        if last.get("shirt_color_hex"):
            s = f"\nShirt: {last.get('shirt_color_name','')} {last.get('shirt_color_hex','')}"
        return (f"Name: {name}\nLast seen: {_human_time(last['time'])}\n"
                f"Camera: {cam}\nBox: x={x} y={y} w={w} h={h}{s}")

    def _details_for_object(label):
        evts = object_memory.get(label, [])
        if not evts:
            return "No history."
        placed = None
        for e in reversed(evts):
            if e.get("status") == "Placed":
                placed = e; break
        last = placed or evts[-1]
        x, y, w, h = last["box"]; cam = last.get("camera","Unknown")
        person = (last.get("person") if placed else None) or "Unknown"
        held = f"{last['held_duration']:.2f}s" if last.get("held_duration") is not None else "—"
        color = ""
        if last.get("color_hex"):
            color = f"\nColor: {last.get('color_name','')} {last.get('color_hex','')}"
        return (f"Object: {label}\nStatus: {last['status']} (held {held})\nPlaced by: {person}\n"
                f"Last seen: {_human_time(last['time'])}\nCamera: {cam}\nBox: x={x} y={y} w={w} h={h}{color}")

    def _fmt_vehicle_line(entry):
        last_seen = max((s["time"] for s in entry.get("sightings", [])), default=0.0)
        ts = _human_time(last_seen) if last_seen else "n/a"
        parts = []
        if entry.get("make"): parts.append(entry["make"])
        if entry.get("model"): parts.append(entry["model"])
        mm = " ".join(parts) if parts else "Unknown"
        plate = entry.get("plate") or "—"
        nick = (", ".join(entry.get("nicknames", []))) or "—"
        color = f'{entry.get("color_name","?")} {entry.get("color_hex","")}'.strip()
        return f"{mm} | plate {plate} | nick {nick} | color {color} | last {ts} | id {entry['id'][:8]}…"

    def _details_for_vehicle(vid):
        entry = vehicle_db.get(vid)
        if not entry:
            return "Vehicle not found."
        line = _fmt_vehicle_line(entry)
        return f"{line}\n\nFull ID: {entry['id']}\nFirst seen: {_human_time(entry.get('first_seen', 0))}\nSnapshots: {len(entry.get('snapshots', []))}"

    def _refresh_notes(key):
        notes_list.delete(0, tk.END)
        bucket = (review_notes.get(category, {}) or {}).get(key, [])
        for n in bucket:
            notes_list.insert(tk.END, f"{_human_time(n['time'])} — {n['text']}")

    current_key = {"value": None}
    def _render_actions():
        for w in actions.winfo_children():
            w.destroy()
        if current_key["value"] is None:
            return
        key = current_key["value"]
        if category.startswith("persons"):
            tk.Button(actions, text="Recall",
                      command=lambda: messagebox.showinfo("Recall", recall_person_last_location_text(key))
                      ).pack(side=tk.LEFT, padx=4)
            tk.Button(actions, text="History", command=lambda: open_person_history_window(key)).pack(side=tk.LEFT, padx=4)
        elif category == "objects":
            tk.Button(actions, text="History", command=lambda: open_object_history_window(key)).pack(side=tk.LEFT, padx=4)
        elif category == "vehicles":
            def _open_last_snap_for(vid):
                entry = vehicle_db.get(vid)
                if not entry or not entry.get("snapshots"):
                    messagebox.showinfo("No snapshots", "This vehicle has no snapshots saved."); return
                last_path = entry["snapshots"][-1]
                if not os.path.exists(last_path):
                    messagebox.showwarning("Missing file", f"Snapshot not found:\n{last_path}"); return
                img_bgr = cv2.imread(last_path)
                if img_bgr is None or img_bgr.size == 0:
                    messagebox.showwarning("Load error", "Could not load snapshot image."); return
                win2 = tk.Toplevel(win); win2.title(f"Vehicle {vid[:8]}… | Last Snapshot")
                canvas = tk.Canvas(win2, background="black"); canvas.pack(fill=tk.BOTH, expand=True)
                rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB); pil = Image.fromarray(rgb); imgtk = ImageTk.PhotoImage(pil)
                canvas.create_image(0, 0, anchor="nw", image=imgtk); canvas.image = imgtk
                win2.geometry("1000x700+140+100")
            tk.Button(actions, text="Open Last Snapshot", command=lambda: _open_last_snap_for(key)).pack(side=tk.LEFT, padx=4)
            tk.Button(actions, text="Details",
                      command=lambda: messagebox.showinfo("Vehicle details", json.dumps(vehicle_db.get(key, {}), indent=2))
                      ).pack(side=tk.LEFT, padx=4)

        tk.Button(notes_frame, text="Save Note", command=lambda: _save_note_for(current_key["value"])).grid(row=2, column=0, sticky="w", padx=8, pady=(0,8))
        tk.Button(notes_frame, text="Export Notes", command=lambda: _export_notes(current_key["value"])).grid(row=2, column=0, sticky="e", padx=8, pady=(0,8))

    def _refresh_list():
        items, key_fn = _items_for_category()
        query = (filt_var.get() or "").strip().lower()
        lb.delete(0, tk.END)
        rendered = []
        for k in items:
            disp = str(k)
            if category == "vehicles":
                entry = vehicle_db.get(k, {})
                disp = _fmt_vehicle_line(entry)
            if query and (query not in disp.lower()):
                continue
            lb.insert(tk.END, disp)
            rendered.append(k)
        lb._keys = rendered

    def _on_select(_=None):
        sel = lb.curselection()
        current_key["value"] = None
        details.delete("1.0", "end")
        notes_list.delete(0, tk.END)
        if not sel:
            _render_actions(); return
        idx = sel[0]
        key = lb._keys[idx]
        current_key["value"] = key

        if category.startswith("persons"):
            details.insert("end", _details_for_person(key))
        elif category == "objects":
            details.insert("end", _details_for_object(key))
        elif category == "vehicles":
            details.insert("end", _details_for_vehicle(key))
        _refresh_notes(key)
        _render_actions()

    filt_var.trace_add("write", lambda *_: _refresh_list())
    lb.bind("<<ListboxSelect>>", _on_select)

    _refresh_list()
    if lb.size() > 0:
        lb.selection_set(0)
        _on_select()

#############################################
# Stats Tab (live totals and rates) — now with Review buttons
#############################################
def _fmt_uptime(sec: float) -> str:
    sec = int(sec)
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

def _draw_sparkline(canvas: tk.Canvas, data):
    C = BRAND["active"]
    canvas.delete("all")
    w = max(40, int(canvas.winfo_width()))
    h = max(40, int(canvas.winfo_height()))
    pad = 6
    if not data:
        return
    mx = max(max(data), 1)
    step = (w - 2*pad) / max(1, (len(data)-1))
    pts = []
    for i, v in enumerate(data):
        x = pad + i * step
        y = h - pad - (v / mx) * (h - 2*pad)
        pts.append((x, y))
    flat = [p for xy in pts for p in xy]
    canvas.create_line(*flat, smooth=True, width=6, fill=C["gold_light"])
    canvas.create_line(*flat, smooth=True, width=3, fill=C["gold"])
    canvas.create_line(pad, h-pad, w-pad, h-pad, fill=C["border"])

def build_stats_tab(notebook: ttk.Notebook):
    C = BRAND["active"]
    tab = tk.Frame(notebook)
    notebook.add(tab, text="Stats")

    for c in range(3):
        tab.columnconfigure(c, weight=1)
    tab.rowconfigure(0, weight=0)
    tab.rowconfigure(1, weight=0)
    tab.rowconfigure(2, weight=1)

    sec_sys = tk.LabelFrame(tab, text="System")
    sec_tot = tk.LabelFrame(tab, text="Tracking Totals")
    sec_q   = tk.LabelFrame(tab, text="Review Queue")
    sec_r   = tk.LabelFrame(tab, text="Rates (per minute)")

    sec_sys.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
    sec_tot.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
    sec_q.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
    sec_r.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

    sv = {k: tk.StringVar(value="–") for k in [
        "uptime","cams","fps","skip","persons","persons_known","persons_unknown",
        "objects","vehicles","q_total","q_faces","q_persons","q_vehicles","det_min","evt_min"
    ]}

    def row(parent, r, label, key, review_cmd=None):
        tk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=6, pady=2)
        tk.Label(parent, textvariable=sv[key], fg=C["gold"]).grid(row=r, column=1, sticky="e", padx=6, pady=2)
        if review_cmd:
            tk.Button(parent, text="Review…", command=review_cmd).grid(row=r, column=2, sticky="e", padx=(0,6), pady=2)

    sec_sys.columnconfigure(1, weight=1)
    row(sec_sys, 0, "Uptime",     "uptime")
    row(sec_sys, 1, "Active cams","cams")
    row(sec_sys, 2, "Target FPS", "fps")
    row(sec_sys, 3, "Frame Skip", "skip")

    for c in range(3): sec_tot.columnconfigure(c, weight=1)
    row(sec_tot, 0, "Persons (all)",  "persons",         review_cmd=lambda: open_review_popup("persons_all"))
    row(sec_tot, 1, "Known persons",  "persons_known",   review_cmd=lambda: open_review_popup("persons_known"))
    row(sec_tot, 2, "Unknown persons","persons_unknown", review_cmd=lambda: open_review_popup("persons_unknown"))
    row(sec_tot, 3, "Objects tracked","objects",         review_cmd=lambda: open_review_popup("objects"))
    row(sec_tot, 4, "Vehicles in DB","vehicles",         review_cmd=lambda: open_review_popup("vehicles"))

    sec_q.columnconfigure(1, weight=1)
    row(sec_q, 0, "Queue items", "q_total")
    row(sec_q, 1, "Faces",       "q_faces")
    row(sec_q, 2, "Persons",     "q_persons")
    row(sec_q, 3, "Vehicles",    "q_vehicles")

    sec_r.columnconfigure(1, weight=1)
    row(sec_r, 0, "Detections/min", "det_min")
    row(sec_r, 1, "Events/min",     "evt_min")
    spark = tk.Canvas(tab, height=90, bd=0, highlightthickness=0)
    spark.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=(0,6))

    def refresh_stats():
        if SHUTTING_DOWN:
            return
        now = time.time()

        sv["uptime"].set(_fmt_uptime(now - app_start_ts))
        sv["cams"].set(str(len([1 for (w,_,_) in camera_windows.values() if w and w.is_alive()])))
        sv["fps"].set(f"{max(1, int(1000/max(1, FPS_CAP)))}")
        sv["skip"].set(str(int(FRAME_SKIP)))

        persons_total = len(person_memory)
        known = sum(1 for k in person_memory.keys() if not (str(k).lower().startswith("unknown")))
        unknown = persons_total - known
        sv["persons"].set(str(persons_total))
        sv["persons_known"].set(str(known))
        sv["persons_unknown"].set(str(max(0, unknown)))
        sv["objects"].set(str(len(object_memory)))
        sv["vehicles"].set(str(len(vehicle_db)))

        total = len(unknown_faces_queue)
        faces = sum(1 for _,_,_,_,k in unknown_faces_queue if k == "face")
        persn = sum(1 for _,_,_,_,k in unknown_faces_queue if k == "person")
        vehs  = sum(1 for _,_,_,_,k in unknown_faces_queue if k == "vehicle")
        sv["q_total"].set(str(total))
        sv["q_faces"].set(str(faces))
        sv["q_persons"].set(str(persn))
        sv["q_vehicles"].set(str(vehs))

        dpm = sum(1 for t in recent_detection_times if (now - t) <= 60.0)
        epm = sum(1 for t in recent_object_event_times if (now - t) <= 60.0)
        sv["det_min"].set(str(dpm))
        sv["evt_min"].set(str(epm))

        detection_rate_history.append(dpm)
        _draw_sparkline(spark, list(detection_rate_history))

        aid = tab.after(1000, refresh_stats)
        AFTER_IDS.append(aid)

    tab.after(300, refresh_stats)
    tab.bind("<Configure>", lambda e: _draw_sparkline(spark, list(detection_rate_history)))

############################
# Tkinter GUI
############################
root = tk.Tk()
root.title("Multi-Camera Recognition (Feeds • Notifications • Vehicle DB)")
root.geometry("1366x900")

apply_dark_theme(root)
schedule_after(50, lambda: brandify_all_widgets(root))

object_dropdowns = []
person_dropdowns = []
object_var = StringVar(root, value="No objects logged")
person_var = StringVar(root, value="No persons logged")

for c in range(3):
    root.columnconfigure(c, weight=1, uniform="cols")
root.rowconfigure(0, weight=1)
root.rowconfigure(1, weight=2)
root.rowconfigure(2, weight=2)
root.rowconfigure(3, weight=2)

############################
# Row 0: Video Feeds (one-row horizontal strip with optional auto-fit)
############################
video_feed_frame = tk.LabelFrame(root, text="Video Feeds")
video_feed_frame.grid(row=0, column=0, columnspan=3, padx=8, pady=8, sticky="nsew")

video_canvas = tk.Canvas(video_feed_frame, highlightthickness=0)
h_scroll = tk.Scrollbar(video_feed_frame, orient="horizontal", command=video_canvas.xview)
video_canvas.configure(xscrollcommand=h_scroll.set)
video_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

video_strip = tk.Frame(video_canvas)
video_canvas.create_window((0, 0), window=video_strip, anchor="nw")

def _update_video_strip_scrollregion(event=None):
    try:
        video_canvas.configure(scrollregion=video_canvas.bbox("all"))
    except Exception:
        pass
video_strip.bind("<Configure>", _update_video_strip_scrollregion)

# Auto-fit state
AUTO_FIT_VAR = tk.IntVar(value=1)  # auto-fit feeds horizontally across available width
_display_size_cache = {}           # idx -> (dw, dh)
BASE_AR = FEED_W / FEED_H if FEED_H else 4/3

def _compute_autofit_sizes():
    """Compute per-camera display sizes (pixels) so all active feeds fit across one row."""
    active = [idx for idx in camera_windows.keys()]
    n = max(1, len(active))
    view_w = max(200, int(video_canvas.winfo_width()))  # visible width
    pad_each = 12  # left+right pack padx per cell
    total_pad = n * pad_each
    avail_w = max(100, view_w - total_pad - 10)
    dw = max(120, int(avail_w / n))
    dh = int(dw / BASE_AR)
    for idx in active:
        _display_size_cache[idx] = (dw, dh)

def make_camera_cell(parent, title):
    cell = tk.Frame(parent, bd=1, relief=tk.SOLID)
    tk.Label(cell, text=title, anchor="w").pack(fill=tk.X)
    img_lbl = tk.Label(cell, bg="#111")
    img_lbl.pack()
    return cell, img_lbl

############################
# Generic centered scrolling pop-up
############################
def _open_scrolling_window(title, header_lines, rows):
    win = tk.Toplevel(root)
    win.title(title)
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = int(sw*0.6), int(sh*0.6)
        x = (sw - ww)//2; y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1000x700")

    header = tk.Frame(win); header.pack(side=tk.TOP, fill=tk.X)
    for line in (header_lines or []):
        tk.Label(header, text=line, anchor="w", justify="left").pack(side=tk.TOP, anchor="w", padx=8, pady=2)

    body = tk.Frame(win); body.pack(fill=tk.BOTH, expand=True)
    lb = tk.Listbox(body)
    sb = tk.Scrollbar(body, orient=tk.VERTICAL, command=lb.yview)
    lb.config(yscrollcommand=sb.set)
    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    for r in rows or []:
        lb.insert(tk.END, r)
    lb.see(tk.END)

    def _export_txt():
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")], initialfile=title.replace(" ", "_") + ".txt")
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            if header_lines:
                for hl in header_lines:
                    f.write(hl + "\n")
                f.write("\n")
            for r in rows or []:
                f.write(r + "\n")
        messagebox.showinfo("Saved", f"Saved to {path}")

    footer = tk.Frame(win); footer.pack(side=tk.BOTTOM, fill=tk.X)
    tk.Button(footer, text="Save as .txt", command=_export_txt).pack(side=tk.LEFT, padx=6, pady=6)
    tk.Button(footer, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=6, pady=6)

############################
# LEFT COLUMN STACK (Controls + Panels + Tuner)
############################
col0_stack = tk.Frame(root)
col0_stack.grid(row=1, column=0, rowspan=3, padx=8, pady=8, sticky="nsew")
col0_stack.rowconfigure(0, weight=0)
col0_stack.rowconfigure(1, weight=1)
col0_stack.columnconfigure(0, weight=1)

controls_frame = tk.LabelFrame(col0_stack, text="Controls (Cameras • Snapshots • Display)")
controls_frame.grid(row=0, column=0, sticky="ew")
controls_frame.columnconfigure(0, weight=1)

cam_ctrl_frame = tk.LabelFrame(controls_frame, text="Cameras")
cam_ctrl_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6,3))

toggle_bar = tk.Frame(cam_ctrl_frame); toggle_bar.pack(fill="x")

def on_toggle(idx):
    if camera_vars[idx].get() == 1:
        enable_camera(idx)
    else:
        disable_camera(idx)
    try:
        cam_toggle_text[idx].set(f"{camera_name(idx)} {'ON' if camera_vars[idx].get()==1 else 'OFF'}")
    except Exception:
        pass
    if AUTO_FIT_VAR.get() == 1:
        _compute_autofit_sizes()

for i in range(MAX_CAMERAS):
    var = tk.IntVar(value=0)
    camera_vars[i] = var
    cam_toggle_text[i] = tk.StringVar(value=f"{camera_name(i)} OFF")
    cb = tk.Checkbutton(toggle_bar, textvariable=cam_toggle_text[i], variable=var,
                        indicatoron=False, command=lambda ii=i: on_toggle(ii))
    cb.pack(side=tk.LEFT, padx=3, pady=2)

panel_row = tk.Frame(cam_ctrl_frame); panel_row.pack(fill="x", padx=6, pady=(4,3))
panel_mode_var = tk.StringVar(value="objects")

def switch_panel_mode():
    if panel_mode_var.get() == "objects":
        tracked_persons_frame.grid_remove()
        tracked_objects_frame.grid(row=0, column=0, sticky="nsew")
    else:
        tracked_objects_frame.grid_remove()
        tracked_persons_frame.grid(row=0, column=0, sticky="nsew")

tk.Label(panel_row, text="Panel:").pack(side=tk.LEFT)
tk.Radiobutton(panel_row, text="Objects", variable=panel_mode_var, value="objects",
               indicatoron=False, command=switch_panel_mode).pack(side=tk.LEFT, padx=2)
tk.Radiobutton(panel_row, text="Persons", variable=panel_mode_var, value="persons",
               indicatoron=False, command=switch_panel_mode).pack(side=tk.LEFT, padx=2)

TUNER_SWITCH_VAR = tk.IntVar(value=0)
def on_tuner_switch():
    if TUNER_SWITCH_VAR.get() == 1:
        show_tuner_overlay()
    else:
        hide_tuner_overlay()
tk.Checkbutton(panel_row, text="Tuner", variable=TUNER_SWITCH_VAR,
               indicatoron=False, command=on_tuner_switch).pack(side=tk.RIGHT, padx=4)

snap_frame = tk.LabelFrame(controls_frame, text="Snapshot Toggles")
snap_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=(3,3))

ENABLE_VEHICLE_SNAPSHOTS_VAR = tk.IntVar(value=1)
ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR = tk.IntVar(value=1)
veh_snap_text = tk.StringVar(value="Vehicle Snapshots: ON")
unk_snap_text = tk.StringVar(value="Unknown Person Snapshots: ON")
def _update_snap_text():
    veh_snap_text.set(f"Vehicle Snapshots: {'ON' if ENABLE_VEHICLE_SNAPSHOTS_VAR.get()==1 else 'OFF'}")
    unk_snap_text.set(f"Unknown Person Snapshots: {'ON' if ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR.get()==1 else 'OFF'}")
tk.Checkbutton(snap_frame, textvariable=veh_snap_text, variable=ENABLE_VEHICLE_SNAPSHOTS_VAR, indicatoron=False,
               command=_update_snap_text).pack(side=tk.LEFT, padx=4, pady=2)
tk.Checkbutton(snap_frame, textvariable=unk_snap_text, variable=ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR, indicatoron=False,
               command=_update_snap_text).pack(side=tk.LEFT, padx=4, pady=2)

display_frame = tk.LabelFrame(controls_frame, text="Display")
display_frame.grid(row=2, column=0, sticky="ew", padx=6, pady=(3,6))
DISPLAY_FEEDS_VAR = tk.IntVar(value=1)
display_feeds_text = tk.StringVar(value="Feeds: ON")
def on_display_feeds_toggle():
    if DISPLAY_FEEDS_VAR.get() == 1:
        video_feed_frame.grid()
    else:
        video_feed_frame.grid_remove()
def _update_display_text():
    display_feeds_text.set(f"Feeds: {'ON' if DISPLAY_FEEDS_VAR.get()==1 else 'OFF'}")

tk.Checkbutton(display_frame, textvariable=display_feeds_text,
               variable=DISPLAY_FEEDS_VAR, indicatoron=False,
               command=lambda: (on_display_feeds_toggle(), _update_display_text())
               ).pack(anchor='w', padx=4, pady=2)

auto_fit_text = tk.StringVar(value="Auto-Fit Feeds: ON")
def _on_autofit_toggle():
    auto_fit_text.set(f"Auto-Fit Feeds: {'ON' if AUTO_FIT_VAR.get()==1 else 'OFF'}")
    if AUTO_FIT_VAR.get() == 1:
        _compute_autofit_sizes()
video_canvas.bind("<Configure>", lambda e: (_compute_autofit_sizes() if AUTO_FIT_VAR.get()==1 else None))
tk.Checkbutton(display_frame, textvariable=auto_fit_text, variable=AUTO_FIT_VAR, indicatoron=False,
               command=_on_autofit_toggle).pack(anchor='w', padx=4, pady=2)

############################
# LEFT lower area: Objects panel (default) + Persons panel
############################
lower_area = tk.Frame(col0_stack)
lower_area.grid(row=1, column=0, sticky="nsew")
lower_area.rowconfigure(0, weight=1)
lower_area.columnconfigure(0, weight=1)

tracked_objects_frame = tk.LabelFrame(lower_area, text="Tracked Objects")
tracked_objects_frame.grid(row=0, column=0, sticky="nsew")
tracked_objects_frame.rowconfigure(1, weight=1)
tracked_objects_frame.columnconfigure(0, weight=1)

tk.Label(tracked_objects_frame, text="Objects currently tracked (color-pooled):").grid(row=0, column=0, sticky="w", padx=4, pady=2)

tracked_objects_listbox = tk.Listbox(tracked_objects_frame, exportselection=False)
tracked_objects_listbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2,4))
tracked_objects_scrollbar = tk.Scrollbar(tracked_objects_frame, orient=tk.VERTICAL, command=tracked_objects_listbox.yview)
tracked_objects_scrollbar.grid(row=1, column=1, sticky="ns")
tracked_objects_listbox.config(yscrollcommand=tracked_objects_scrollbar.set)

def refresh_tracked_objects_list():
    selected = None
    sel = tracked_objects_listbox.curselection()
    if sel: selected = tracked_objects_listbox.get(sel[0])

    items = sorted(tracked_objects)
    current = list(tracked_objects_listbox.get(0, tk.END))
    if items == current:
        _update_tracked_recall_label()
        return

    tracked_objects_listbox.delete(0, tk.END)
    for obj in items:
        tracked_objects_listbox.insert(tk.END, obj)

    if selected and selected in items:
        idx = items.index(selected)
        tracked_objects_listbox.selection_set(idx)
        tracked_objects_listbox.see(idx)
    _update_tracked_recall_label()

def show_selected_history():
    selection = tracked_objects_listbox.curselection()
    if not selection:
        messagebox.showinfo("No selection", "No object selected.")
        return
    obj = tracked_objects_listbox.get(selection[0])
    open_object_history_window(obj)
    _update_tracked_recall_label(obj)

btn_tracked_row = tk.Frame(tracked_objects_frame)
btn_tracked_row.grid(row=2, column=0, sticky="ew", padx=4, pady=2)
tk.Button(btn_tracked_row, text="Show Selected Object History", command=show_selected_history).pack(side=tk.LEFT, padx=3)

tracked_recall_label = tk.Label(btn_tracked_row, text="", fg="blue", anchor="w")
tracked_recall_label.pack(side=tk.LEFT, padx=6, pady=2, fill="x", expand=True)

def _update_tracked_recall_label(obj=None):
    try:
        if obj is None:
            sel = tracked_objects_listbox.curselection()
            obj = tracked_objects_listbox.get(sel[0]) if sel else None
        if not obj or obj not in object_memory or not object_memory[obj]:
            tracked_recall_label.config(text=""); return
        events = object_memory[obj]
        placed_evt = None
        for evt in reversed(events):
            if evt.get("status") == "Placed": placed_evt = evt; break
        last_event = placed_evt or events[-1]
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_event["time"]))
        x, y, w, h = last_event["box"]; status = last_event["status"]
        placer = (last_event["person"] if placed_evt else None) or "Unknown"
        cam = last_event.get("camera", "Unknown")
        held_str = f" | Held {last_event['held_duration']:.2f}s" if last_event["held_duration"] is not None else ""
        color_part = ""
        if last_event.get("color_hex"):
            color_part = f" | Color {last_event.get('color_name','')} {last_event.get('color_hex','')}"
        tracked_recall_label.config(text=f"[{cam}] Last {obj}: {status} by {placer} @ {t_str}{held_str}{color_part}")
    except Exception:
        pass

tracked_objects_listbox.bind('<Double-1>', lambda e: show_selected_history())
tracked_objects_listbox.bind('<<ListboxSelect>>', lambda e: _update_tracked_recall_label())

tracked_persons_frame = tk.LabelFrame(lower_area, text="Persons")
tracked_persons_frame.rowconfigure(1, weight=1)
tracked_persons_frame.columnconfigure(0, weight=1)

tk.Label(tracked_persons_frame, text="Known/Unknown persons:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
tracked_persons_listbox = tk.Listbox(tracked_persons_frame, exportselection=False)
tracked_persons_listbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2,4))
tracked_persons_scrollbar = tk.Scrollbar(tracked_persons_frame, orient=tk.VERTICAL, command=tracked_persons_listbox.yview)
tracked_persons_scrollbar.grid(row=1, column=1, sticky="ns")
tracked_persons_listbox.config(yscrollcommand=tracked_persons_scrollbar.set)

def refresh_tracked_persons_list():
    selected = None
    sel = tracked_persons_listbox.curselection()
    if sel: selected = tracked_persons_listbox.get(sel[0])

    items = sorted(person_memory.keys())
    current = list(tracked_persons_listbox.get(0, tk.END))
    if items == current:
        _update_tracked_person_recall_label(); return

    tracked_persons_listbox.delete(0, tk.END)
    for p in items:
        tracked_persons_listbox.insert(tk.END, p)

    if selected and selected in items:
        idx = items.index(selected)
        tracked_persons_listbox.selection_set(idx)
        tracked_persons_listbox.see(idx)
    _update_tracked_person_recall_label()

p_btn_row = tk.Frame(tracked_persons_frame)
p_btn_row.grid(row=2, column=0, sticky="ew", padx=4, pady=2)

def show_selected_person_history():
    sel = tracked_persons_listbox.curselection()
    if not sel:
        messagebox.showinfo("No selection", "No person selected.")
        return
    name = tracked_persons_listbox.get(sel[0])
    open_person_history_window(name)
    _update_tracked_person_recall_label(name)

tk.Button(p_btn_row, text="Show Selected Person History", command=show_selected_person_history).pack(side=tk.LEFT, padx=3)

p_last_label = tk.Label(p_btn_row, text="", fg="green", anchor="w")
p_last_label.pack(side=tk.LEFT, padx=6, pady=2, fill="x", expand=True)

def _update_tracked_person_recall_label(name=None):
    try:
        if name is None:
            sel = tracked_persons_listbox.curselection()
            name = tracked_persons_listbox.get(sel[0]) if sel else None
        if not name or name not in person_memory or not person_memory[name]:
            p_last_label.config(text=""); return
        last_event = person_memory[name][-1]
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_event["time"]))
        b = last_event["box"]
        x, y, w, h = b["left"], b["top"], b["right"] - b["left"], b["bottom"] - b["top"]
        cam = last_event.get("camera", "Unknown")
        shirt = ""
        if last_event.get("shirt_color_hex"):
            shirt = f" | Shirt {last_event.get('shirt_color_name','')} {last_event.get('shirt_color_hex','')}"
        p_last_label.config(text=f"[{cam}] Last {name}: {t_str} (x={x},y={y},w={w},h={h}){shirt}")
    except Exception:
        pass

tracked_persons_listbox.bind('<Double-1>', lambda e: show_selected_person_history())
tracked_persons_listbox.bind('<<ListboxSelect>>', lambda e: _update_tracked_person_recall_label())
tracked_persons_frame.grid_remove()

#########################################
# Tuner Overlay (left side)
#########################################
tuner_overlay = None
tuner_overlay_state = {"visible": False}

conf_var = tk.DoubleVar(value=DETECTION_CONF_THRESH)
nms_var = tk.DoubleVar(value=NMS_THRESH)
auto_place_var = tk.DoubleVar(value=AUTO_PLACE_TIMEOUT)
held_log_var = tk.DoubleVar(value=HELD_LOG_INTERVAL)
person_cd_var = tk.DoubleVar(value=PERSON_LOG_COOLDOWN)
fps_cap_var = tk.IntVar(value=FPS_CAP)
frame_skip_var = tk.IntVar(value=FRAME_SKIP)
feed_w_var = tk.IntVar(value=FEED_W)
feed_h_var = tk.IntVar(value=FEED_H)
face_model_var = StringVar(value=FACE_MODEL)
vehicle_idle_percent_var = tk.DoubleVar(value=VEHICLE_IDLE_FRAC * 100.0)
unknown_person_idle_percent_var = tk.DoubleVar(value=UNKNOWN_PERSON_IDLE_FRAC * 100.0)
retag_hold_var = tk.DoubleVar(value=RETAG_HOLD_SECONDS)

def _spin(parent, row, label, var, from_, to_, inc, width=8):
    tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=3)
    w = tk.Spinbox(parent, textvariable=var, from_=from_, to=to_, increment=inc, width=width)
    w.grid(row=row, column=1, sticky="w", padx=6, pady=3)

def apply_tuning():
    global DETECTION_CONF_THRESH, NMS_THRESH, AUTO_PLACE_TIMEOUT, HELD_LOG_INTERVAL
    global PERSON_LOG_COOLDOWN, FPS_CAP, FRAME_SKIP, FEED_W, FEED_H, FACE_MODEL
    global VEHICLE_IDLE_FRAC, UNKNOWN_PERSON_IDLE_FRAC, RETAG_HOLD_SECONDS

    DETECTION_CONF_THRESH = float(conf_var.get())
    NMS_THRESH = float(nms_var.get())
    AUTO_PLACE_TIMEOUT = float(auto_place_var.get())
    HELD_LOG_INTERVAL = float(held_log_var.get())
    PERSON_LOG_COOLDOWN = float(person_cd_var.get())
    FPS_CAP = int(fps_cap_var.get())
    FRAME_SKIP = int(frame_skip_var.get())
    new_w, new_h = int(feed_w_var.get()), int(feed_h_var.get())
    FACE_MODEL = face_model_var.get()
    VEHICLE_IDLE_FRAC = max(0.0, min(1.0, float(vehicle_idle_percent_var.get()) / 100.0))
    UNKNOWN_PERSON_IDLE_FRAC = max(0.0, min(1.0, float(unknown_person_idle_percent_var.get()) / 100.0))
    RETAG_HOLD_SECONDS = float(retag_hold_var.get())

    for idx, (worker, name, lbl) in camera_windows.items():
        worker.set_resolution(new_w, new_h)
        worker.set_fps_cap(FPS_CAP)

    global FEED_W, FEED_H, BASE_AR
    FEED_W, FEED_H = new_w, new_h
    BASE_AR = FEED_W / FEED_H if FEED_H else BASE_AR
    _update_video_strip_scrollregion()
    if AUTO_FIT_VAR.get() == 1:
        _compute_autofit_sizes()

    messagebox.showinfo("Tuning Applied", "Updated settings.")

def apply_and_close_tuner():
    apply_tuning()
    hide_tuner_overlay()

def build_tuner_overlay():
    ov = tk.Frame(lower_area, bd=1, relief=tk.RIDGE, bg="#202020")
    ov.place(in_=lower_area, relx=0, rely=0, relwidth=1, relheight=1)

    top = tk.Frame(ov, bg="#2b2b2b")
    top.pack(side=tk.TOP, fill="x")
    tk.Label(top, text="Tuning (Recognition & Idle Thresholds)", fg="#ffffff", bg="#2b2b2b").pack(side=tk.LEFT, padx=8, pady=6)
    tk.Button(top, text="Close", command=hide_tuner_overlay).pack(side=tk.RIGHT)

    body_wrap = tk.Frame(ov, bg="#202020")
    body_wrap.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    canvas = tk.Canvas(body_wrap, highlightthickness=0, bg="#202020")
    vbar = tk.Scrollbar(body_wrap, orient=tk.VERTICAL, command=canvas.yview)
    inner = tk.Frame(canvas, bg="#202020")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=vbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)

    form = tk.LabelFrame(inner, text="Parameters", bg="#202020", fg="#dddddd")
    form.grid(row=0, column=0, sticky="nw", padx=6, pady=6)
    form.columnconfigure(1, weight=1)

    _spin(form, 0,  "YOLO Conf",                  conf_var, 0.1, 0.99, 0.01)
    _spin(form, 1,  "YOLO NMS",                   nms_var, 0.1, 0.9,  0.01)
    _spin(form, 2,  "Auto-Place Timeout (s)",     auto_place_var, 0.5, 30.0, 0.5)
    _spin(form, 3,  "Held Log Interval (s)",      held_log_var, 0.2, 10.0, 0.2)
    _spin(form, 4,  "Person Log Cooldown (s)",    person_cd_var, 5.0, 600.0, 5.0)
    _spin(form, 5,  "Loop Delay (ms)",            fps_cap_var, 15, 200, 1)
    _spin(form, 6,  "Frame Skip",                 frame_skip_var, 0, 10, 1)
    _spin(form, 7,  "Feed Width",                 feed_w_var, 160, 1920, 10)
    _spin(form, 8,  "Feed Height",                feed_h_var, 120, 1080, 10)

    tk.Label(form, text="Face Model").grid(row=9, column=0, sticky="w", padx=6, pady=3)
    ttk.Combobox(form, textvariable=face_model_var, values=["hog", "cnn"], width=8).grid(row=9, column=1, sticky="w", padx=6, pady=3)

    _spin(form, 10, "Vehicle Idle (%)",           vehicle_idle_percent_var, 1.0, 100.0, 0.5)
    _spin(form, 11, "Unknown Idle (%)",           unknown_person_idle_percent_var, 1.0, 100.0, 0.5)
    _spin(form, 12, "Retag Hold (s)",             retag_hold_var, 1.0, 120.0, 1.0)

    fbar = tk.Frame(inner, bg="#202020")
    fbar.grid(row=1, column=0, sticky="ew", padx=6, pady=(10,0))
    tk.Button(fbar, text="Apply & Close", command=apply_and_close_tuner).pack(side=tk.LEFT, padx=4)
    tk.Button(fbar, text="Cancel", command=hide_tuner_overlay).pack(side=tk.LEFT, padx=4)

    def _on_mousewheel(event):
        try:
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except Exception:
            pass
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    return ov

def show_tuner_overlay():
    global tuner_overlay
    if tuner_overlay_state["visible"]:
        return
    tuner_overlay = build_tuner_overlay()
    tuner_overlay_state["visible"] = True
    TUNER_SWITCH_VAR.set(1)

def hide_tuner_overlay():
    global tuner_overlay
    if tuner_overlay is not None:
        try:
            tuner_overlay.place_forget()
            tuner_overlay.destroy()
        except Exception:
            pass
        tuner_overlay = None
    tuner_overlay_state["visible"] = False
    TUNER_SWITCH_VAR.set(0)

#########################################
# Optional: compact tuning popup
#########################################
def open_tuning_popup():
    win = tk.Toplevel(root)
    win.title("Tuning")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = 520, 560; x = (sw - ww)//2; y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("520x560+120+80")

    grid = tk.Frame(win); grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def add_row(r, label, widget):
        tk.Label(grid, text=label).grid(row=r, column=0, sticky="w", padx=4, pady=3)
        widget.grid(row=r, column=1, sticky="w", padx=4, pady=3)

    add_row(0,  "YOLO Conf", tk.Spinbox(grid, textvariable=conf_var, from_=0.1, to=0.99, increment=0.01, width=8))
    add_row(1,  "YOLO NMS", tk.Spinbox(grid, textvariable=nms_var, from_=0.1, to=0.9, increment=0.01, width=8))
    add_row(2,  "Auto-Place Timeout (s)", tk.Spinbox(grid, textvariable=auto_place_var, from_=0.5, to=30.0, increment=0.5, width=8))
    add_row(3,  "Held Log Interval (s)", tk.Spinbox(grid, textvariable=held_log_var, from_=0.2, to=10.0, increment=0.2, width=8))
    add_row(4,  "Person Log Cooldown (s)", tk.Spinbox(grid, textvariable=person_cd_var, from_=5.0, to=600.0, increment=5.0, width=8))
    add_row(5,  "Loop Delay (ms)", tk.Spinbox(grid, textvariable=fps_cap_var, from_=15, to=200, increment=1, width=8))
    add_row(6,  "Frame Skip", tk.Spinbox(grid, textvariable=frame_skip_var, from_=0, to=10, increment=1, width=8))
    add_row(7,  "Feed Width", tk.Spinbox(grid, textvariable=feed_w_var, from_=160, to=1920, increment=10, width=8))
    add_row(8,  "Feed Height", tk.Spinbox(grid, textvariable=feed_h_var, from_=120, to=1080, increment=10, width=8))
    tk.Label(grid, text="Face Model").grid(row=9, column=0, sticky="w", padx=4, pady=3)
    ttk.Combobox(grid, textvariable=face_model_var, values=["hog", "cnn"], width=6).grid(row=9, column=1, sticky="w", padx=4, pady=3)
    add_row(10, "Vehicle Idle (%)", tk.Spinbox(grid, textvariable=vehicle_idle_percent_var, from_=1.0, to=100.0, increment=0.5, width=8))
    add_row(11, "Unknown Idle (%)", tk.Spinbox(grid, textvariable=unknown_person_idle_percent_var, from_=1.0, to=100.0, increment=0.5, width=8))
    add_row(12, "Retag Hold (s)", tk.Spinbox(grid, textvariable=retag_hold_var, from_=1.0, to=120.0, increment=1.0, width=8))

    tk.Button(win, text="Apply", command=apply_tuning).pack(pady=8, fill="x")
    win.bind("<Escape>", lambda e: win.destroy())

############################
# Row 1 Column 1: REVIEW QUEUE
############################
unknown_face_frame = tk.LabelFrame(root, text="Review Queue (Faces / Persons / Vehicles)")
unknown_face_frame.grid(row=1, column=1, padx=8, pady=8, sticky="nsew")
unknown_face_frame.columnconfigure(0, weight=1)
unknown_face_frame.rowconfigure(7, weight=1)

tk.Label(unknown_face_frame, text="Double-click preview for full-size. Save only if FACE. Use vehicle form below for VEHICLE.").grid(row=0, column=0, sticky="w", padx=4, pady=(4,2))

button_frame = tk.Frame(unknown_face_frame)
button_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=2)
button_frame.columnconfigure((0,1,2,3), weight=1)

def _dequeue_all_for_uid(target_uid):
    kept, picked = [], []
    for item in unknown_faces_queue:
        enc, img, uid, cam, kind = item
        if uid == target_uid:
            picked.append(item)
        else:
            kept.append(item)
    unknown_faces_queue[:] = kept
    return picked

def save_face_callback():
    if not unknown_faces_queue:
        return
    enc0, img0, uid0, cam0, kind0 = unknown_faces_queue[0]
    if kind0 != "face":
        return
    person_name = entry_name.get().strip()
    if not person_name:
        return
    items = _dequeue_all_for_uid(uid0)
    for enc, face_img_bgr, uid, cam, kind in items:
        if kind == "face" and enc is not None:
            save_new_face(person_name, face_img_bgr, enc)
    remove_unknown_id(uid0)
    rename_person_everywhere(uid0, person_name)
    entry_name.delete(0, tk.END)
    update_unknown_count()

def reject_face_callback():
    if not unknown_faces_queue:
        return
    _, _, uid, _, _ = unknown_faces_queue[0]
    _dequeue_all_for_uid(uid)
    entry_name.delete(0, tk.END)
    update_unknown_count()

def open_fullsize_window():
    if not unknown_faces_queue:
        return
    enc, img_bgr, uid, cam, kind = unknown_faces_queue[0]

    win = tk.Toplevel(root)
    win.title(f"Queue Item: {uid} | {kind} | {cam}")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = int(sw*0.7), int(sh*0.7)
        x = (sw - ww)//2; y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1200x800")

    top_bar = tk.Frame(win); top_bar.pack(side=tk.TOP, fill=tk.X)
    tk.Label(top_bar, text=f"{uid}  |  {kind}  |  {cam}").pack(side=tk.LEFT, padx=8, pady=6)

    def _reject_and_next():
        _dequeue_all_for_uid(uid)
        update_unknown_count()
        try:
            if unknown_faces_queue:
                canvas.delete("all")
                enc2, img2, uid2, cam2, kind2 = unknown_faces_queue[0]
                rgb2 = cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)
                pil2 = Image.fromarray(rgb2)
                imgtk2 = ImageTk.PhotoImage(pil2)
                canvas.create_image(0, 0, anchor="nw", image=imgtk2)
                canvas.image = imgtk2
                canvas.config(scrollregion=(0, 0, pil2.width, pil2.height))
                title_lbl.config(text=f"{uid2}  |  {kind2}  |  {cam2}")
            else:
                win.destroy()
        except Exception:
            win.destroy()

    tk.Button(top_bar, text="Reject & Next", command=_reject_and_next).pack(side=tk.RIGHT, padx=6)
    tk.Button(top_bar, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=6)
    title_lbl = tk.Label(top_bar, text=""); title_lbl.pack_forget()

    canvas_frame = tk.Frame(win); canvas_frame.pack(fill=tk.BOTH, expand=True)
    vbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
    hbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
    canvas = tk.Canvas(canvas_frame, background="black", yscrollcommand=vbar.set, xscrollcommand=hbar.set)
    vbar.config(command=canvas.yview); hbar.config(command=canvas.xview)
    vbar.pack(side=tk.RIGHT, fill=tk.Y); hbar.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    imgtk = ImageTk.PhotoImage(pil)
    canvas.create_image(0, 0, anchor="nw", image=imgtk); canvas.image = imgtk
    canvas.config(scrollregion=(0, 0, pil.width, pil.height))
    win.bind("<Escape>", lambda e: win.destroy())
    win.bind("r", lambda e: _reject_and_next())

tk.Button(button_frame, text="Open Full Size", command=open_fullsize_window).grid(row=0, column=0, padx=4, pady=2, sticky="ew")
tk.Button(button_frame, text="Save Face", command=save_face_callback).grid(row=0, column=1, padx=4, pady=2, sticky="ew")
tk.Button(button_frame, text="Reject", command=reject_face_callback).grid(row=0, column=2, padx=4, pady=2, sticky="ew")

entry_name = tk.Entry(unknown_face_frame); entry_name.grid(row=2, column=0, sticky="ew", padx=4, pady=2)

unknown_count_label = tk.Label(unknown_face_frame, text="Queue: 0 items", fg="red")
unknown_count_label.grid(row=3, column=0, sticky="w", padx=4, pady=(2,2))

PREVIEW_W, PREVIEW_H = 320, 240
face_display_label = tk.Label(unknown_face_frame, text="Queue is empty.", bd=1, relief=tk.SOLID, bg="black")
face_display_label.grid(row=7, column=0, sticky="nsew", padx=4, pady=(2,4))
face_display_label.bind("<Double-Button-1>", lambda e: open_fullsize_window())

def _make_preview_canvas(img_bgr, box_w=PREVIEW_W, box_h=PREVIEW_H):
    h, w = img_bgr.shape[:2]
    if w <= 0 or h <= 0:
        return np.zeros((box_h, box_w, 3), dtype=np.uint8)
    scale = min(box_w / float(w), box_h / float(h), 1.0)
    new_w, new_h = int(w * scale), int(h * scale)
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=interp)
    canvas = np.zeros((box_h, box_w, 3), dtype=np.uint8)
    x_off = (box_w - new_w) // 2; y_off = (box_h - new_h) // 2
    canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
    return canvas

def show_unknown_face_image():
    if unknown_faces_queue:
        _, img, uid, cam, kind = unknown_faces_queue[0]
        disp = img.copy()
        cv2.putText(disp, f"{uid} | {cam} | {kind}", (6, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        lb = _make_preview_canvas(disp)
        rgb = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(pil)
        face_display_label.config(image=imgtk, text="")
        face_display_label.image = imgtk
    else:
        face_display_label.config(image='', text="Queue is empty.")
        face_display_label.image = None

def update_unknown_count():
    total = len(unknown_faces_queue)
    faces = sum(1 for _, _, _, _, k in unknown_faces_queue if k == "face")
    persons = sum(1 for _, _, _, _, k in unknown_faces_queue if k == "person")
    vehicles = sum(1 for _, _, _, _, k in unknown_faces_queue if k == "vehicle")
    unknown_count_label.config(text=f"Queue: {total} item(s) [faces: {faces}, persons: {persons}, vehicles: {vehicles}]")
    show_unknown_face_image()

veh_form = tk.LabelFrame(unknown_face_frame, text="Save Vehicle (active when current item is VEHICLE)")
veh_form.grid(row=4, column=0, sticky="ew", padx=4, pady=4)
for c in range(6): veh_form.columnconfigure(c, weight=1)
tk.Label(veh_form, text="Make").grid(row=0, column=0, sticky="w")
tk.Label(veh_form, text="Model").grid(row=0, column=2, sticky="w")
tk.Label(veh_form, text="Plate").grid(row=1, column=0, sticky="w")
tk.Label(veh_form, text="Fleet ID").grid(row=1, column=2, sticky="w")
tk.Label(veh_form, text="Nickname").grid(row=2, column=0, sticky="w")
tk.Label(veh_form, text="Detected Color").grid(row=2, column=2, sticky="w")

veh_make_var = StringVar(); veh_model_var = StringVar(); veh_plate_var = StringVar()
veh_fleet_var = StringVar(); veh_nick_var = StringVar(); veh_color_show_var = StringVar(value="(auto)")
tk.Entry(veh_form, textvariable=veh_make_var).grid(row=0, column=1, sticky="ew", padx=3, pady=2)
tk.Entry(veh_form, textvariable=veh_model_var).grid(row=0, column=3, sticky="ew", padx=3, pady=2)
tk.Entry(veh_form, textvariable=veh_plate_var).grid(row=1, column=1, sticky="ew", padx=3, pady=2)
tk.Entry(veh_form, textvariable=veh_fleet_var).grid(row=1, column=3, sticky="ew", padx=3, pady=2)
tk.Entry(veh_form, textvariable=veh_nick_var).grid(row=2, column=1, sticky="ew", padx=3, pady=2)
tk.Label(veh_form, textvariable=veh_color_show_var).grid(row=2, column=3, sticky="w", padx=3, pady=2)

def _peek_vehicle_color_from_current(img_bgr):
    try:
        rgb = dominant_color_from_bgr(img_bgr)
        return rgb_to_basic_name(*rgb), rgb_tuple_to_hex(rgb)
    except Exception:
        return None, None

def save_vehicle_callback():
    if not unknown_faces_queue:
        messagebox.showinfo("No item", "Review queue is empty."); return
    enc0, img_bgr, uid0, cam0, kind0 = unknown_faces_queue[0]
    if kind0 != "vehicle":
        messagebox.showinfo("Not a vehicle", "Current queue item is not a VEHICLE."); return
    make = veh_make_var.get().strip()
    model = veh_model_var.get().strip()
    plate = veh_plate_var.get().strip()
    fleet = veh_fleet_var.get().strip()
    nick = veh_nick_var.get().strip()

    color_name, color_hex = _peek_vehicle_color_from_current(img_bgr)
    veh_color_show_var.set(f"{color_name or ''} {color_hex or ''}".strip() or "(unknown)")

    h, w = img_bgr.shape[:2]
    box = (0, 0, w, h)
    vid = register_vehicle_sighting(img_bgr, make, model, plate, fleet, nick, color_name, color_hex, cam0, box, assoc_person=None)
    if vid:
        _dequeue_all_for_uid(uid0)
        update_unknown_count()
        veh_make_var.set(""); veh_model_var.set(""); veh_plate_var.set("")
        veh_fleet_var.set(""); veh_nick_var.set("")
        messagebox.showinfo("Vehicle Saved", f"Saved vehicle entry #{vid[:8]}…")
    else:
        messagebox.showwarning("Save failed", "Could not save this vehicle.")

tk.Button(veh_form, text="Save Vehicle Entry", command=save_vehicle_callback).grid(row=3, column=0, columnspan=4, sticky="ew", padx=3, pady=(4,2))

############################
# Row 1 Column 2: Right-top tabs (Detections/Notifications/Vehicles/Stats)
############################
right_top_tabs = ttk.Notebook(root)
right_top_tabs.grid(row=1, column=2, padx=8, pady=8, sticky="nsew")

# Tab: Detections
tab_detections = tk.Frame(right_top_tabs)
right_top_tabs.add(tab_detections, text="Detections (This Cycle)")
tab_detections.rowconfigure(0, weight=1)
tab_detections.columnconfigure(0, weight=1)
detections_listbox = tk.Listbox(tab_detections)
detections_listbox.grid(row=0, column=0, sticky="nsew")
dets_scroll = tk.Scrollbar(tab_detections, orient=tk.VERTICAL, command=detections_listbox.yview)
dets_scroll.grid(row=0, column=1, sticky="ns")
detections_listbox.config(yscrollcommand=dets_scroll.set)
detection_label_entry = tk.Entry(tab_detections)
detection_label_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(4,2))

def refresh_current_detections_list():
    detections_listbox.delete(0, tk.END)
    for i, (cam, label, x, y, w, h, conf) in enumerate(current_detections):
        detections_listbox.insert(tk.END, f"[{i}] {cam} | {label} (x={x}, y={y}, w={w}, h={h}, conf={conf:.2f})")

def _rename_object_everywhere(old_display, new_display):
    if not new_display or old_display == new_display:
        return
    if old_display in object_memory:
        if new_display in object_memory:
            object_memory[new_display].extend(object_memory.pop(old_display))
        else:
            object_memory[new_display] = object_memory.pop(old_display)
    if old_display in object_states:
        object_states[new_display] = object_states.pop(old_display)
    if old_display in tracked_objects:
        tracked_objects.discard(old_display)
        tracked_objects.add(new_display)
    try:
        if object_var.get() == old_display:
            object_var.set(new_display)
    except Exception:
        pass
    refresh_tracked_objects_list()
    update_object_dropdown()
    try:
        _update_tracked_recall_label(new_display)
    except Exception:
        pass

def custom_label_selected_detection():
    sel = detections_listbox.curselection()
    if not sel:
        messagebox.showinfo("No selection", "Please select a detection to label."); return
    new_label_base = detection_label_entry.get().strip()
    if not new_label_base:
        messagebox.showwarning("Invalid Label", "Please enter a valid label first."); return
    idx = sel[0]
    cam, label, *_ = current_detections[idx]
    if label.startswith("person:") or label.startswith("face:"):
        messagebox.showinfo("Not Applicable", "Custom labeling applies to objects, not persons/faces."); return
    st = object_states.get(label)
    if not st:
        messagebox.showwarning("Unavailable", "Underlying object state not found yet. Try after the object is seen."); return
    yolo_label = st.get("yolo"); color_name = st.get("color_name")
    if yolo_label and color_name:
        custom_labels_by_yolo_and_color[(yolo_label, color_name)] = new_label_base
        new_display = get_display_label(yolo_label, color_name=color_name)
    else:
        custom_labels_by_yolo[yolo_label] = new_label_base
        new_display = new_label_base
    _rename_object_everywhere(label, new_display)
    detection_label_entry.delete(0, tk.END)
    refresh_current_detections_list()

tk.Button(tab_detections, text="Save Custom Label for Selected Detection", command=custom_label_selected_detection).grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 6))

# Tab: Notifications
tab_notify = tk.Frame(right_top_tabs)
right_top_tabs.add(tab_notify, text="Notifications")
for r in range(6): tab_notify.rowconfigure(r, weight=0)
tab_notify.rowconfigure(5, weight=1)
tab_notify.columnconfigure(0, weight=1); tab_notify.columnconfigure(1, weight=1)

notify_channel_var = StringVar(value="none")
attach_images_var = tk.IntVar(value=1)
hosting_mode_var = StringVar(value="none")
hosting_port_var = tk.IntVar(value=8765)
hosting_baseurl_var = StringVar(value="")
tk.Label(tab_notify, text="Channel").grid(row=0, column=0, sticky="w", padx=4, pady=2)
ttk.Combobox(tab_notify, textvariable=notify_channel_var, values=["none","pushover","telegram","webhook","twilio_sms"], width=14).grid(row=0, column=1, sticky="w", padx=4, pady=2)
tk.Checkbutton(tab_notify, text="Attach images (when available)", variable=attach_images_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=2)

cred_frame = tk.LabelFrame(tab_notify, text="Credentials / Endpoints")
cred_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
for c in range(4): cred_frame.columnconfigure(c, weight=1)
pushover_token_var = StringVar(); pushover_user_var = StringVar()
telegram_bot_var = StringVar(); telegram_chat_var = StringVar()
webhook_url_var = StringVar()
tw_sid_var = StringVar(); tw_token_var = StringVar(); tw_from_var = StringVar(); tw_to_var = StringVar()
tk.Label(cred_frame, text="Pushover token").grid(row=0, column=0, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=pushover_token_var).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
tk.Label(cred_frame, text="Pushover user").grid(row=0, column=2, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=pushover_user_var).grid(row=0, column=3, sticky="ew", padx=4, pady=2)
tk.Label(cred_frame, text="Telegram bot_token").grid(row=1, column=0, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=telegram_bot_var).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
tk.Label(cred_frame, text="Telegram chat_id").grid(row=1, column=2, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=telegram_chat_var).grid(row=1, column=3, sticky="ew", padx=4, pady=2)
tk.Label(cred_frame, text="Webhook URL").grid(row=2, column=0, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=webhook_url_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=2)
tk.Label(cred_frame, text="Twilio SID").grid(row=3, column=0, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=tw_sid_var).grid(row=3, column=1, sticky="ew", padx=4, pady=2)
tk.Label(cred_frame, text="Twilio Token").grid(row=3, column=2, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=tw_token_var, show="•").grid(row=3, column=3, sticky="ew", padx=4, pady=2)
tk.Label(cred_frame, text="From").grid(row=4, column=0, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=tw_from_var).grid(row=4, column=1, sticky="ew", padx=4, pady=2)
tk.Label(cred_frame, text="To").grid(row=4, column=2, sticky="w", padx=4, pady=2)
tk.Entry(cred_frame, textvariable=tw_to_var).grid(row=4, column=3, sticky="ew", padx=4, pady=2)

host_frame = tk.LabelFrame(tab_notify, text="Image Hosting (for Twilio MMS MediaUrl)")
host_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
for c in range(4): host_frame.columnconfigure(c, weight=1)
tk.Label(host_frame, text="Mode").grid(row=0, column=0, sticky="w", padx=4, pady=2)
ttk.Combobox(host_frame, textvariable=hosting_mode_var, values=["none","builtin","static_url_prefix"], width=16).grid(row=0, column=1, sticky="w", padx=4, pady=2)
tk.Label(host_frame, text="Port (builtin)").grid(row=0, column=2, sticky="w", padx=4, pady=2)
tk.Spinbox(host_frame, from_=1024, to=65535, textvariable=hosting_port_var, width=8).grid(row=0, column=3, sticky="w", padx=4, pady=2)
tk.Label(host_frame, text="Base URL (static)").grid(row=1, column=0, sticky="w", padx=4, pady=2)
tk.Entry(host_frame, textvariable=hosting_baseurl_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=4, pady=2)

subs_frame = tk.LabelFrame(tab_notify, text="Subscriptions")
subs_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
for c in range(6): subs_frame.columnconfigure(c, weight=1)
subs_frame.rowconfigure(1, weight=1)

tk.Label(subs_frame, text="Persons").grid(row=0, column=0, sticky="w")
tk.Label(subs_frame, text="Objects").grid(row=0, column=2, sticky="w")
tk.Label(subs_frame, text="Vehicle Labels").grid(row=0, column=4, sticky="w")

persons_av = tk.Listbox(subs_frame, exportselection=False)
objects_av = tk.Listbox(subs_frame, exportselection=False)
vehicles_av = tk.Listbox(subs_frame, exportselection=False)
persons_av.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
objects_av.grid(row=1, column=2, sticky="nsew", padx=2, pady=2)
vehicles_av.grid(row=1, column=4, sticky="nsew", padx=2, pady=2)

persons_sub = tk.Listbox(subs_frame, exportselection=False)
objects_sub = tk.Listbox(subs_frame, exportselection=False)
vehicles_sub = tk.Listbox(subs_frame, exportselection=False)
persons_sub.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
objects_sub.grid(row=1, column=3, sticky="nsew", padx=2, pady=2)
vehicles_sub.grid(row=1, column=5, sticky="nsew", padx=2, pady=2)

def _refresh_sub_lists():
    persons_av.delete(0, tk.END)
    for p in sorted(person_memory.keys()):
        persons_av.insert(tk.END, p)
    persons_sub.delete(0, tk.END)
    for p in sorted(set(notify_subscriptions.get("persons", []))):
        persons_sub.insert(tk.END, p)

    objects_av.delete(0, tk.END)
    for o in sorted(tracked_objects | set(object_memory.keys())):
        objects_av.insert(tk.END, o)
    objects_sub.delete(0, tk.END)
    for o in sorted(set(notify_subscriptions.get("objects", []))):
        objects_sub.insert(tk.END, o)

    vehicles_av.delete(0, tk.END)
    for v in sorted(VEHICLE_LABELS):
        vehicles_av.insert(tk.END, v)
    vehicles_sub.delete(0, tk.END)
    for v in sorted(set(notify_subscriptions.get("vehicle_labels", []))):
        vehicles_sub.insert(tk.END, v)

def _pull_ui_to_config():
    notify_config["channel"] = notify_channel_var.get()
    notify_config["attach_images"] = int(attach_images_var.get())
    notify_config["pushover"]["token"] = pushover_token_var.get().strip()
    notify_config["pushover"]["user"] = pushover_user_var.get().strip()
    notify_config["telegram"]["bot_token"] = telegram_bot_var.get().strip()
    notify_config["telegram"]["chat_id"] = telegram_chat_var.get().strip()
    notify_config["webhook"]["url"] = webhook_url_var.get().strip()
    notify_config["twilio"]["sid"] = tw_sid_var.get().strip()
    notify_config["twilio"]["token"] = tw_token_var.get().strip()
    notify_config["twilio"]["from"] = tw_from_var.get().strip()
    notify_config["twilio"]["to"] = tw_to_var.get().strip()
    notify_config["media_hosting"]["mode"] = hosting_mode_var.get()
    notify_config["media_hosting"]["port"] = int(hosting_port_var.get())
    notify_config["media_hosting"]["base_url"] = hosting_baseurl_var.get().strip()

def _push_config_to_ui():
    notify_channel_var.set(notify_config.get("channel","none"))
    attach_images_var.set(int(notify_config.get("attach_images",1)))
    pushover_token_var.set(notify_config.get("pushover",{}).get("token",""))
    pushover_user_var.set(notify_config.get("pushover",{}).get("user",""))
    telegram_bot_var.set(notify_config.get("telegram",{}).get("bot_token",""))
    telegram_chat_var.set(notify_config.get("telegram",{}).get("chat_id",""))
    webhook_url_var.set(notify_config.get("webhook",{}).get("url",""))
    tw_sid_var.set(notify_config.get("twilio",{}).get("sid",""))
    tw_token_var.set(notify_config.get("twilio",{}).get("token",""))
    tw_from_var.set(notify_config.get("twilio",{}).get("from",""))
    tw_to_var.set(notify_config.get("twilio",{}).get("to",""))
    hosting_mode_var.set(notify_config.get("media_hosting",{}).get("mode","none"))
    hosting_port_var.set(int(notify_config.get("media_hosting",{}).get("port",8765)))
    hosting_baseurl_var.set(notify_config.get("media_hosting",{}).get("base_url",""))

def save_notify_ui():
    _pull_ui_to_config()
    save_notify_settings()
    if notify_config.get("media_hosting",{}).get("mode") == "builtin":
        _start_media_server_if_needed()
    messagebox.showinfo("Notifications", "Saved.")

btns = tk.Frame(tab_notify); btns.grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
tk.Button(btns, text="Save", command=save_notify_ui).pack(side=tk.LEFT, padx=4)

# Tab: Vehicles search/manage
tab_vehicles = tk.Frame(right_top_tabs)
right_top_tabs.add(tab_vehicles, text="Vehicles (Search & Manage)")
for r in range(4): tab_vehicles.rowconfigure(r, weight=0)
tab_vehicles.rowconfigure(3, weight=1)
for c in range(4): tab_vehicles.columnconfigure(c, weight=1)

tk.Label(tab_vehicles, text="Color contains").grid(row=0, column=0, sticky="w", padx=4, pady=2)
tk.Label(tab_vehicles, text="Plate contains").grid(row=0, column=1, sticky="w", padx=4, pady=2)
tk.Label(tab_vehicles, text="Nickname contains").grid(row=0, column=2, sticky="w", padx=4, pady=2)

veh_search_color_var = StringVar(); veh_search_plate_var = StringVar(); veh_search_nick_var = StringVar()
tk.Entry(tab_vehicles, textvariable=veh_search_color_var).grid(row=1, column=0, sticky="ew", padx=4, pady=2)
tk.Entry(tab_vehicles, textvariable=veh_search_plate_var).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
tk.Entry(tab_vehicles, textvariable=veh_search_nick_var).grid(row=1, column=2, sticky="ew", padx=4, pady=2)

vehicle_results_list = tk.Listbox(tab_vehicles)
vehicle_results_list.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=4, pady=4)
vehicle_results_scroll = tk.Scrollbar(tab_vehicles, orient=tk.VERTICAL, command=vehicle_results_list.yview)
vehicle_results_scroll.grid(row=3, column=4, sticky="ns")
vehicle_results_list.config(yscrollcommand=vehicle_results_scroll.set)

vehicle_search_cache = []
def _fmt_vehicle_line(entry):
    last_seen = max((s["time"] for s in entry.get("sightings", [])), default=0.0)
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_seen)) if last_seen else "n/a"
    parts = []
    if entry.get("make"): parts.append(entry["make"])
    if entry.get("model"): parts.append(entry["model"])
    mm = " ".join(parts) if parts else "Unknown"
    plate = entry.get("plate") or "—"
    nick = (", ".join(entry.get("nicknames", []))) or "—"
    color = f'{entry.get("color_name","?")} {entry.get("color_hex","")}'.strip()
    return f"{mm} | plate {plate} | nick {nick} | color {color} | last {ts} | id {entry['id'][:8]}…"

def search_vehicles():
    vehicle_results_list.delete(0, tk.END); vehicle_search_cache.clear()
    c = veh_search_color_var.get().strip().lower()
    p = veh_search_plate_var.get().strip().lower()
    n = veh_search_nick_var.get().strip().lower()
    for entry in vehicle_db.values():
        ok = True
        if c:
            cn = (entry.get("color_name") or "").lower()
            ch = (entry.get("color_hex") or "").lower()
            ok = ok and (c in cn or c in ch)
        if p:
            ok = ok and (p in (entry.get("plate") or "").lower())
        if n:
            ok = ok and any(n in (nm or "").lower() for nm in entry.get("nicknames", []))
        if ok:
            vehicle_search_cache.append(entry)
            vehicle_results_list.insert(tk.END, _fmt_vehicle_line(entry))

def open_vehicle_last_snap():
    sel = vehicle_results_list.curselection()
    if not sel:
        messagebox.showinfo("No selection", "Select a vehicle in the list first."); return
    entry = vehicle_search_cache[sel[0]]
    snaps = entry.get("snapshots", [])
    if not snaps:
        messagebox.showinfo("No snapshots", "This vehicle has no snapshots saved."); return
    last_path = snaps[-1]
    if not os.path.exists(last_path):
        messagebox.showwarning("Missing file", f"Snapshot not found:\n{last_path}"); return
    img_bgr = cv2.imread(last_path)
    if img_bgr is None or img_bgr.size == 0:
        messagebox.showwarning("Load error", "Could not load snapshot image."); return
    win = tk.Toplevel(root); win.title(f"Vehicle {entry['id'][:8]}… | Last Snapshot")
    canvas = tk.Canvas(win, background="black"); canvas.pack(fill=tk.BOTH, expand=True)
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB); pil = Image.fromarray(rgb); imgtk = ImageTk.PhotoImage(pil)
    canvas.create_image(0, 0, anchor="nw", image=imgtk); canvas.image = imgtk
    win.geometry("1000x700+140+100")
    win.bind("<Escape>", lambda e: win.destroy())

def show_vehicle_details():
    sel = vehicle_results_list.curselection()
    if not sel:
        messagebox.showinfo("No selection", "Select a vehicle in the list first."); return
    entry = vehicle_search_cache[sel[0]]
    msg = json.dumps(entry, indent=2)
    messagebox.showinfo("Vehicle details", msg)

btn_row_vehicle = tk.Frame(tab_vehicles)
btn_row_vehicle.grid(row=2, column=0, columnspan=4, sticky="ew", padx=4, pady=2)
tk.Button(btn_row_vehicle, text="Search", command=search_vehicles).pack(side=tk.LEFT, padx=3)
tk.Button(btn_row_vehicle, text="Open Last Snap", command=open_vehicle_last_snap).pack(side=tk.LEFT, padx=3)
tk.Button(btn_row_vehicle, text="Details", command=show_vehicle_details).pack(side=tk.LEFT, padx=3)

build_stats_tab(right_top_tabs)

# ==============================
# Bottom-right Communications UI
# ==============================
root.rowconfigure(3, weight=2)
comms_frame = tk.LabelFrame(root, text="Communications — Sentinel AI")
comms_frame.grid(row=3, column=2, padx=8, pady=8, sticky="nsew")
comms_frame.rowconfigure(1, weight=1)
comms_frame.columnconfigure(0, weight=1)

hdr = tk.Frame(comms_frame); hdr.grid(row=0, column=0, sticky="ew", padx=6, pady=6)

voice_var = tk.IntVar(value=1 if comms_state["voice_enabled"] else 0)
beep_var  = tk.IntVar(value=1 if comms_state["beep_enabled"] else 0)
wake_var  = tk.IntVar(value=1 if comms_state["wake_enabled"] else 0)
tuner_visible = tk.BooleanVar(value=False)

def _refresh_thread_status():
    w = "running" if (_wake_thread and _wake_thread.is_alive() and comms_state["wake_enabled"]) else "stopped"
    t = "ok" if _tts_engine is not None else "off"
    try:
        thread_status.config(text=f"Threads: wake={w}, tts={t}")
    except Exception:
        pass

def _apply_comms_toggles():
    comms_state["voice_enabled"] = (voice_var.get()==1)
    comms_state["beep_enabled"]  = (beep_var.get()==1)
    want_wake = (wake_var.get()==1)
    if want_wake and sr is not None:
        comms_state["wake_enabled"] = True
        start_wake_listener()
    else:
        comms_state["wake_enabled"] = False
        stop_wake_listener()
    _refresh_thread_status()

tk.Checkbutton(hdr, text="Voice (TTS)", variable=voice_var, indicatoron=False, command=_apply_comms_toggles).pack(side=tk.LEFT, padx=4)
tk.Checkbutton(hdr, text="Beep",        variable=beep_var,  indicatoron=False, command=_apply_comms_toggles).pack(side=tk.LEFT, padx=4)
tk.Checkbutton(hdr, text="Wake phrase", variable=wake_var,  indicatoron=False, command=_apply_comms_toggles,
               state=("normal" if sr is not None else "disabled")).pack(side=tk.LEFT, padx=4)

tt_btn = tk.Button(hdr, text="Show Tuner"); tt_btn.pack(side=tk.RIGHT, padx=4)

display = scrolledtext.ScrolledText(comms_frame, wrap="word", height=12, state="disabled")
display.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0,6))

row = tk.Frame(comms_frame); row.grid(row=2, column=0, sticky="ew", padx=6, pady=(0,6))
msg_var = tk.StringVar(); ent = tk.Entry(row, textvariable=msg_var); ent.pack(side=tk.LEFT, fill="x", expand=True)

def _send():
    txt = msg_var.get().strip()
    if not txt: return
    msg_var.set("")
    chat_add_message("You", txt)
    reply = answer_user(txt)
    chat_add_message("AI", reply, speak=True)
tk.Button(row, text="Send", command=_send).pack(side=tk.LEFT, padx=4)

def _listen():
    if sr is None:
        messagebox.showinfo("Voice not available","Install 'speech_recognition' to enable mic."); return
    chat_add_message("System","Listening…")
    heard = listen_once(comms_state["phrase_time_limit"], use_beep=True)
    if heard:
        chat_add_message("You", heard)
        reply = answer_user(heard)
        chat_add_message("AI", reply, speak=True)
    else:
        chat_add_message("System","I didn’t catch that.")
tk.Button(row, text="🎤 Listen", command=_listen, state=("normal" if sr is not None else "disabled")).pack(side=tk.LEFT, padx=4)

tuner = tk.LabelFrame(comms_frame, text="Voice / Response Tuner")
tuner.grid(row=3, column=0, sticky="ew", padx=6, pady=(0,6))
tuner.grid_remove()
for c in range(8): tuner.columnconfigure(c, weight=1)

wake_phrase_var = tk.StringVar(value=comms_state["wake_phrase"])
tts_var         = tk.IntVar(value=int(comms_state["tts_rate"]))
ptl_var         = tk.IntVar(value=int(comms_state["phrase_time_limit"]))
amb_var         = tk.IntVar(value=int(comms_state["ambient_ms"]))
dlc_var         = tk.DoubleVar(value=float(comms_state["dialog_cooldown"]))
auto_var        = tk.IntVar(value=1 if comms_state["auto_narrate"] else 0)
per_var         = tk.IntVar(value=1 if comms_state["narrate_persons"] else 0)
obj_var         = tk.IntVar(value=1 if comms_state["narrate_objects"] else 0)
veh_var         = tk.IntVar(value=1 if comms_state["narrate_vehicles"] else 0)
nmi_var         = tk.DoubleVar(value=float(comms_state["narrate_min_interval"]))

tk.Label(tuner, text="Wake phrase").grid(row=0, column=0, sticky="w")
tk.Entry(tuner, textvariable=wake_phrase_var, width=20).grid(row=0, column=1, sticky="w")
tk.Label(tuner, text="TTS rate").grid(row=0, column=2, sticky="w")
tk.Spinbox(tuner, textvariable=tts_var, from_=100, to=240, width=6).grid(row=0, column=3, sticky="w")
tk.Label(tuner, text="Phrase time (s)").grid(row=0, column=4, sticky="w")
tk.Spinbox(tuner, textvariable=ptl_var, from_=3, to=12, width=6).grid(row=0, column=5, sticky="w")
tk.Label(tuner, text="Ambient (ms)").grid(row=0, column=6, sticky="w")
tk.Spinbox(tuner, textvariable=amb_var, from_=100, to=1500, increment=50, width=8).grid(row=0, column=7, sticky="w")

tk.Label(tuner, text="Dialog cooldown (s)").grid(row=1, column=0, sticky="w")
tk.Spinbox(tuner, textvariable=dlc_var, from_=0.0, to=10.0, increment=0.5, width=8).grid(row=1, column=1, sticky="w")

nar = tk.Frame(tuner); nar.grid(row=1, column=2, columnspan=6, sticky="ew")
tk.Checkbutton(nar, text="Auto-narrate", variable=auto_var, indicatoron=False).pack(side=tk.LEFT, padx=4)
tk.Checkbutton(nar, text="Persons",     variable=per_var,  indicatoron=False).pack(side=tk.LEFT, padx=4)
tk.Checkbutton(nar, text="Objects",     variable=obj_var,  indicatoron=False).pack(side=tk.LEFT, padx=4)
tk.Checkbutton(nar, text="Vehicles",    variable=veh_var,  indicatoron=False).pack(side=tk.LEFT, padx=4)

tk.Label(tuner, text="Narration min interval (s)").grid(row=2, column=0, sticky="w")
tk.Spinbox(tuner, textvariable=nmi_var, from_=3.0, to=60.0, increment=0.5, width=8).grid(row=2, column=1, sticky="w")

thread_status = tk.Label(tuner, text="Threads: wake=stopped, tts=" + ("ok" if _tts_engine else "off"))
thread_status.grid(row=2, column=7, sticky="e")

def _apply_tuner():
    comms_state["wake_phrase"] = (wake_phrase_var.get() or "hey sentinel ai").strip().lower()
    comms_state["tts_rate"] = int(tts_var.get())
    comms_state["phrase_time_limit"] = int(ptl_var.get())
    comms_state["ambient_ms"] = int(amb_var.get())
    comms_state["dialog_cooldown"] = float(dlc_var.get())
    comms_state["auto_narrate"] = (auto_var.get()==1)
    comms_state["narrate_persons"] = (per_var.get()==1)
    comms_state["narrate_objects"] = (obj_var.get()==1)
    comms_state["narrate_vehicles"] = (veh_var.get()==1)
    comms_state["narrate_min_interval"] = float(nmi_var.get())
    if _tts_engine is not None:
        try: _tts_engine.setProperty("rate", int(comms_state["tts_rate"]))
        except Exception: pass
    _refresh_thread_status()
    messagebox.showinfo("Applied", "Voice / Response tuner settings applied.")

tk.Button(tuner, text="Apply", command=_apply_tuner).grid(row=2, column=6, sticky="e")

def _toggle_tuner():
    if tuner_visible.get():
        tuner.grid_remove(); tuner_visible.set(False); tt_btn.config(text="Show Tuner")
    else:
        tuner.grid(); tuner_visible.set(True); tt_btn.config(text="Hide Tuner")
        _refresh_thread_status()
tt_btn.config(command=_toggle_tuner)

comms_widgets["display"] = display
comms_widgets["input"]   = ent

load_chat_history()
if conversation_history:
    display.config(state="normal")
    for row_ in conversation_history[-200:]:
        display.insert("end", f"{row_['sender']}: {row_['text']}\n\n")
    display.config(state="disabled"); display.yview("end")

schedule_after(150, _drain_chat_ui)
schedule_after(350, comms_tick)
brandify_all_widgets(root)

##########################
# Recall & History Helpers
##########################
def open_object_history_window(obj_label=None):
    obj_label = obj_label or object_var.get()
    if not obj_label or obj_label == "No objects logged" or obj_label not in object_memory or not object_memory[obj_label]:
        messagebox.showinfo("No history", f"No history for {obj_label or 'object'}."); return
    events = object_memory[obj_label]
    placed_evt = None
    for evt in reversed(events):
        if evt.get("status") == "Placed":
            placed_evt = evt; break
    last_event = placed_evt or events[-1]
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_event["time"]))
    x, y, w, h = last_event["box"]; status = last_event["status"]
    placer = (last_event["person"] if placed_evt else None) or "Unknown"
    cam = last_event.get("camera", "Unknown")
    held_str = f" | Held {last_event['held_duration']:.2f}s" if last_event["held_duration"] is not None else ""
    color_part = ""
    if last_event.get("color_hex"):
        color_part = f" | Color {last_event.get('color_name','')} {last_event.get('color_hex','')}"
    header_lines = [
        f"Object: {obj_label}",
        f"Last [{cam}] {t_str}: {status} by {placer} (x={x}, y={y}, w={w}, h={h}){held_str}{color_part}"
    ]
    rows = []
    for evt in events:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(evt["time"]))
        x, y, w, h = evt["box"]
        status = evt["status"]; person = evt["person"] if evt["person"] else "No one"
        cam = evt.get("camera", "Unknown")
        held = f" | Held {evt['held_duration']:.2f}s" if evt["held_duration"] is not None else ""
        color_part = ""
        if evt.get("color_hex"):
            color_part = f" | Color {evt.get('color_name','')} {evt.get('color_hex','')}"
        rows.append(f"[{cam}] {t}: {obj_label} {status} by {person} at (x={x}, y={y}, w={w}, h={h}){held}{color_part}")
    _open_scrolling_window(f"History — {obj_label}", header_lines, rows)

def open_person_history_window(name=None):
    name = name or person_var.get()
    if not name or name == "No persons logged" or name not in person_memory or not person_memory[name]:
        messagebox.showinfo("No history", f"No history for {name or 'person'}."); return
    events = person_memory[name]
    last_event = events[-1]
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_event["time"]))
    b = last_event["box"]
    x, y, w, h = b["left"], b["top"], b["right"] - b["left"], b["bottom"] - b["top"]
    cam = last_event.get("camera", "Unknown")
    shirt = ""
    if last_event.get("shirt_color_hex"):
        shirt = f" | Shirt {last_event.get('shirt_color_name','')} {last_event.get('shirt_color_hex','')}"
    header_lines = [f"Person: {name}", f"Last seen [{cam}] {t_str} at (x={x}, y={y}, w={w}, h={h}){shirt}"]
    rows = []
    for evt in events:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(evt["time"]))
        bb = evt["box"]; xx, yy = bb["left"], bb["top"]; ww, hh = bb["right"] - bb["left"], bb["bottom"] - bb["top"]
        cam = evt.get("camera", "Unknown")
        s = ""
        if evt.get("shirt_color_hex"):
            s = f" | Shirt {evt.get('shirt_color_name','')} {evt.get('shirt_color_hex','')}"
        rows.append(f"[{cam}] {t}: (x={xx}, y={yy}, w={ww}, h={hh}){s}")
    _open_scrolling_window(f"History — {name}", header_lines, rows)

def recall_object_last_location_text(obj_label):
    events = object_memory.get(obj_label, [])
    if not events:
        return f"No history for {obj_label}."
    placed_evt = None
    for evt in reversed(events):
        if evt.get("status") == "Placed":
            placed_evt = evt; break
    evt = placed_evt or events[-1]
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(evt["time"]))
    cam = evt.get("camera", "Unknown")
    placer = (evt.get("person") if placed_evt else None) or "Unknown"
    return f"Last known location: [{cam}] at {t_str}\nPlaced by: {placer}"

def recall_person_last_location_text(name):
    events = person_memory.get(name, [])
    if not events:
        return f"No history for {name}."
    evt = events[-1]
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(evt["time"]))
    cam = evt.get("camera", "Unknown")
    return f"Last seen: [{cam}] at {t_str}"

############################
# Row 2 Column 1: LIVE LOGS
############################
live_logs_frame = tk.LabelFrame(root, text="Per-Camera Live Logs")
live_logs_frame.grid(row=2, column=1, padx=8, pady=(0,8), sticky="nsew")
live_logs_frame.rowconfigure(1, weight=1)
live_logs_frame.columnconfigure(0, weight=1)

live_log_cam_var = StringVar(root); live_log_cam_var.set("All")

top_logs = tk.Frame(live_logs_frame); top_logs.grid(row=0, column=0, sticky="ew")
tk.Label(top_logs, text="Camera:").pack(side=tk.LEFT, padx=4)
live_log_dropdown = tk.OptionMenu(top_logs, live_log_cam_var, "All"); live_log_dropdown.pack(side=tk.LEFT)
tk.Button(top_logs, text="Refresh", command=lambda: refresh_live_logs_ui()).pack(side=tk.LEFT, padx=6)
tk.Button(top_logs, text="Clear", command=lambda: clear_live_logs()).pack(side=tk.LEFT, padx=6)

log_area = tk.Frame(live_logs_frame); log_area.grid(row=1, column=0, sticky="nsew")
live_log_listbox = tk.Listbox(log_area); live_log_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
live_log_scrollbar = tk.Scrollbar(log_area, orient=tk.VERTICAL, command=live_log_listbox.yview)
live_log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
live_log_listbox.config(yscrollcommand=live_log_scrollbar.set)

def _refresh_live_log_dropdown():
    names = sorted([tpl[1] for tpl in camera_windows.values()])
    menu = live_log_dropdown["menu"]; menu.delete(0, "end")
    menu.add_command(label="All", command=lambda v="All": live_log_cam_var.set(v))
    for c in names:
        menu.add_command(label=c, command=lambda v=c: live_log_cam_var.set(v))

def refresh_live_logs_ui():
    live_log_listbox.delete(0, tk.END)
    target = live_log_cam_var.get()
    if target == "All":
        for cam in sorted(camera_live_logs.keys()):
            live_log_listbox.insert(tk.END, f"--- {cam} ---")
            for line in camera_live_logs[cam][-800:]:
                live_log_listbox.insert(tk.END, line)
    else:
        for line in camera_live_logs.get(target, [])[-1200:]:
            live_log_listbox.insert(tk.END, line)

def clear_live_logs():
    target = live_log_cam_var.get()
    if target == "All":
        camera_live_logs.clear()
    else:
        camera_live_logs[target] = []
    refresh_live_logs_ui()

############################
# Settings window (Recall/History/Logs)
############################
def open_settings_window():
    win = tk.Toplevel(root)
    win.title("Settings — Recall, History & Logs")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = int(sw*0.6), int(sh*0.7); x = (sw - ww)//2; y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1000x780")

    nb = ttk.Notebook(win); nb.pack(fill=tk.BOTH, expand=True)

    tab_rh = tk.Frame(nb); nb.add(tab_rh, text="Recall & History")
    tab_rh.rowconfigure(2, weight=1); tab_rh.columnconfigure(0, weight=1)

    mode_var = tk.StringVar(value="objects")
    mode_bar = tk.Frame(tab_rh); mode_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
    tk.Label(mode_bar, text="Mode:").pack(side=tk.LEFT)
    tk.Radiobutton(mode_bar, text="Objects", variable=mode_var, value="objects", indicatoron=False).pack(side=tk.LEFT, padx=4)
    tk.Radiobutton(mode_bar, text="Persons", variable=mode_var, value="persons", indicatoron=False).pack(side=tk.LEFT, padx=4)

    obj_frame = tk.Frame(tab_rh); per_frame = tk.Frame(tab_rh)
    obj_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
    obj_frame.rowconfigure(1, weight=1); obj_frame.columnconfigure(0, weight=1)

    tk.Label(obj_frame, text="Select object:").grid(row=0, column=0, sticky="w")
    obj_list = tk.Listbox(obj_frame, exportselection=False)
    obj_list.grid(row=1, column=0, sticky="nsew")
    obj_scroll = tk.Scrollbar(obj_frame, orient=tk.VERTICAL, command=obj_list.yview)
    obj_scroll.grid(row=1, column=1, sticky="ns")
    obj_list.config(yscrollcommand=obj_scroll.set)

    obj_btns = tk.Frame(obj_frame); obj_btns.grid(row=2, column=0, sticky="ew", pady=6)
    def _obj_recall():
        sel = obj_list.curselection()
        if not sel: messagebox.showinfo("Recall", "Select an object first."); return
        label = obj_list.get(sel[0]); messagebox.showinfo("Recall", recall_object_last_location_text(label))
    def _obj_hist():
        sel = obj_list.curselection()
        if not sel: messagebox.showinfo("History", "Select an object first."); return
        open_object_history_window(obj_list.get(sel[0]))
    def _obj_refresh():
        items = sorted(tracked_objects | set(object_memory.keys()))
        current = list(obj_list.get(0, tk.END))
        if items != current:
            sel_val = obj_list.get(obj_list.curselection()[0]) if obj_list.curselection() else None
            obj_list.delete(0, tk.END)
            for it in items: obj_list.insert(tk.END, it)
            if sel_val and sel_val in items:
                idx = items.index(sel_val)
                obj_list.selection_set(idx); obj_list.see(idx)
    tk.Button(obj_btns, text="Recall", command=_obj_recall).pack(side=tk.LEFT, padx=4)
    tk.Button(obj_btns, text="Show History", command=_obj_hist).pack(side=tk.LEFT, padx=4)
    tk.Button(obj_btns, text="Refresh", command=_obj_refresh).pack(side=tk.LEFT, padx=12)

    per_frame.grid_forget(); per_frame.rowconfigure(1, weight=1); per_frame.columnconfigure(0, weight=1)
    tk.Label(per_frame, text="Select person:").grid(row=0, column=0, sticky="w")
    per_list = tk.Listbox(per_frame, exportselection=False); per_list.grid(row=1, column=0, sticky="nsew")
    per_scroll = tk.Scrollbar(per_frame, orient=tk.VERTICAL, command=per_list.yview); per_scroll.grid(row=1, column=1, sticky="ns")
    per_list.config(yscrollcommand=per_scroll.set)

    per_btns = tk.Frame(per_frame); per_btns.grid(row=2, column=0, sticky="ew", pady=6)
    def _per_recall():
        sel = per_list.curselection()
        if not sel: messagebox.showinfo("Recall", "Select a person first."); return
        name = per_list.get(sel[0]); messagebox.showinfo("Recall", recall_person_last_location_text(name))
    def _per_hist():
        sel = per_list.curselection()
        if not sel: messagebox.showinfo("History", "Select a person first."); return
        open_person_history_window(per_list.get(sel[0]))
    def _per_refresh():
        items = sorted(person_memory.keys())
        current = list(per_list.get(0, tk.END))
        if items != current:
            sel_val = per_list.get(per_list.curselection()[0]) if per_list.curselection() else None
            per_list.delete(0, tk.END)
            for it in items: per_list.insert(tk.END, it)
            if sel_val and sel_val in items:
                idx = items.index(sel_val)
                per_list.selection_set(idx); per_list.see(idx)
    tk.Button(per_btns, text="Recall", command=_per_recall).pack(side=tk.LEFT, padx=4)
    tk.Button(per_btns, text="Show History", command=_per_hist).pack(side=tk.LEFT, padx=4)
    tk.Button(per_btns, text="Refresh", command=_per_refresh).pack(side=tk.LEFT, padx=12)

    def _switch_mode(*_):
        if mode_var.get() == "objects":
            per_frame.grid_forget()
            obj_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        else:
            obj_frame.grid_forget()
            per_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
    mode_var.trace_add("write", _switch_mode)

    def _toggle_mode():
        new_mode = "persons" if mode_var.get() == "objects" else "objects"
        mode_var.set(new_mode); _switch_mode()
    tk.Button(obj_btns, text="Toggle → Persons", command=_toggle_mode).pack(side=tk.RIGHT, padx=8)
    tk.Button(per_btns, text="Toggle → Objects", command=_toggle_mode).pack(side=tk.RIGHT, padx=8)

    def _initial_fill():
        obj_list.delete(0, tk.END)
        for it in sorted(tracked_objects | set(object_memory.keys())):
            obj_list.insert(tk.END, it)
        per_list.delete(0, tk.END)
        for it in sorted(person_memory.keys()):
            per_list.insert(tk.END, it)
    _initial_fill()

    tab_logs = tk.Frame(nb); nb.add(tab_logs, text="Logs")
    tab_logs.rowconfigure(2, weight=1); tab_logs.columnconfigure(0, weight=1)

    filt_var = tk.StringVar(value="all")
    top = tk.Frame(tab_logs); top.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
    tk.Label(top, text="Filter:").pack(side=tk.LEFT)
    tk.Radiobutton(top, text="All", variable=filt_var, value="all", indicatoron=False).pack(side=tk.LEFT, padx=4)
    tk.Radiobutton(top, text="Objects", variable=filt_var, value="objects", indicatoron=False).pack(side=tk.LEFT, padx=4)
    tk.Radiobutton(top, text="Persons", variable=filt_var, value="persons", indicatoron=False).pack(side=tk.LEFT, padx=4)

    cam_var = tk.StringVar(value="All")
    tk.Label(top, text="   Camera:").pack(side=tk.LEFT, padx=(16,4))
    cam_drop = tk.OptionMenu(top, cam_var, "All"); cam_drop.pack(side=tk.LEFT)

    logbox = tk.Listbox(tab_logs); logbox.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0,8))
    logscroll = tk.Scrollbar(tab_logs, orient=tk.VERTICAL, command=logbox.yview)
    logscroll.grid(row=2, column=1, sticky="ns", pady=(0,8))
    logbox.config(yscrollcommand=logscroll.set)

    btns2 = tk.Frame(tab_logs); btns2.grid(row=1, column=0, sticky="ew", padx=8, pady=(0,8))
    def _fill_cam():
        names = sorted([tpl[1] for tpl in camera_windows.values()])
        menu = cam_drop["menu"]; menu.delete(0, "end")
        menu.add_command(label="All", command=lambda v="All": cam_var.set(v))
        for c in names:
            menu.add_command(label=c, command=lambda v=c: cam_var.set(v))
    def _refresh_logs():
        logbox.delete(0, tk.END)
        camsel = cam_var.get(); f = filt_var.get()
        cams = [camsel] if camsel != "All" else sorted(camera_live_logs.keys())
        for cam in cams:
            lines = camera_live_logs.get(cam, [])
            if f == "objects": lines = [ln for ln in lines if "Object" in ln]
            elif f == "persons": lines = [ln for ln in lines if ("Person:" in ln or "Face:" in ln)]
            if camsel == "All": logbox.insert(tk.END, f"--- {cam} ---")
            for ln in lines[-800:]:
                logbox.insert(tk.END, ln)
    def _clear_logs():
        camsel = cam_var.get()
        if camsel == "All":
            camera_live_logs.clear()
        else:
            camera_live_logs[camsel] = []
        _refresh_logs()
    def _export_logs():
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files","*.txt")], initialfile="logs.txt")
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            for i in range(logbox.size()):
                f.write(logbox.get(i) + "\n")
        messagebox.showinfo("Saved", f"Saved to {path}")
    tk.Button(btns2, text="Refresh", command=_refresh_logs).pack(side=tk.LEFT, padx=4)
    tk.Button(btns2, text="Clear", command=_clear_logs).pack(side=tk.LEFT, padx=4)
    tk.Button(btns2, text="Export", command=_export_logs).pack(side=tk.LEFT, padx=12)
    _fill_cam(); _refresh_logs()

############################
# Top-right overlay Controls
############################
def create_top_right_controls():
    def show_overlay():
        overlay.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)
        overlay.lift(); overlay.tkraise(); handle.place_forget()
    def hide_overlay():
        overlay.place_forget()
        handle.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

    overlay = tk.LabelFrame(video_feed_frame, text="Controls")
    overlay.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)
    overlay.lift(); overlay.tkraise()

    hdr = tk.Frame(overlay); hdr.pack(fill="x", padx=6, pady=(6,2))
    tk.Label(hdr, text="Quick Controls").pack(side=tk.LEFT)
    tk.Button(hdr, text="Hide", command=hide_overlay).pack(side=tk.RIGHT)

    toggles = tk.Frame(overlay); toggles.pack(fill="x", padx=6, pady=2)
    tk.Checkbutton(toggles, textvariable=display_feeds_text, variable=DISPLAY_FEEDS_VAR, indicatoron=False,
                   command=lambda: (on_display_feeds_toggle(), _update_display_text())).pack(side=tk.LEFT, padx=2)
    tk.Checkbutton(toggles, textvariable=veh_snap_text, variable=ENABLE_VEHICLE_SNAPSHOTS_VAR,
                   indicatoron=False, command=_update_snap_text).pack(side=tk.LEFT, padx=6)
    tk.Checkbutton(toggles, textvariable=unk_snap_text, variable=ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR,
                   indicatoron=False, command=_update_snap_text).pack(side=tk.LEFT, padx=6)

    DARK_MODE_VAR = tk.IntVar(value=1)
    dark_mode_text = tk.StringVar(value="Dark Mode: ON")
    def _on_dark():
        if DARK_MODE_VAR.get() == 1:
            apply_dark_theme(root)
        else:
            apply_light_theme(root)
        brandify_all_widgets(root)
        dark_mode_text.set(f"Dark Mode: {'ON' if DARK_MODE_VAR.get()==1 else 'OFF'}")
    tk.Checkbutton(toggles, textvariable=dark_mode_text, variable=DARK_MODE_VAR, indicatoron=False, command=_on_dark).pack(side=tk.LEFT, padx=6)

    cams = tk.LabelFrame(overlay, text="Cameras"); cams.pack(fill="x", padx=6, pady=6)
    row1 = tk.Frame(cams); row1.pack(fill="x")
    row2 = tk.Frame(cams); row2.pack(fill="x")
    for i in range(MAX_CAMERAS):
        parent = row1 if i < (MAX_CAMERAS//2 + MAX_CAMERAS%2) else row2
        tk.Checkbutton(parent, textvariable=cam_toggle_text[i], variable=camera_vars[i],
                       indicatoron=False, command=lambda ii=i: on_toggle(ii)).pack(side=tk.LEFT, padx=2)

    obj_blk = tk.LabelFrame(overlay, text="Object"); obj_blk.pack(fill="x", padx=6, pady=4)
    obj_row = tk.Frame(obj_blk); obj_row.pack(fill="x", padx=4, pady=2)
    dd_obj = OptionMenu(obj_row, object_var, "No objects logged")
    dd_obj.pack(side=tk.LEFT, fill="x", expand=True); object_dropdowns.append(dd_obj)
    tk.Button(obj_row, text="Recall", command=lambda: messagebox.showinfo("Recall", recall_object_last_location_text(object_var.get()))).pack(side=tk.LEFT, padx=3)
    tk.Button(obj_row, text="History", command=lambda: open_object_history_window(object_var.get())).pack(side=tk.LEFT, padx=3)

    per_blk = tk.LabelFrame(overlay, text="Person"); per_blk.pack(fill="x", padx=6, pady=4)
    per_row = tk.Frame(per_blk); per_row.pack(fill="x", padx=4, pady=2)
    dd_per = OptionMenu(per_row, person_var, "No persons logged")
    dd_per.pack(side=tk.LEFT, fill="x", expand=True); person_dropdowns.append(dd_per)
    tk.Button(per_row, text="Recall", command=lambda: messagebox.showinfo("Recall", recall_person_last_location_text(person_var.get()))).pack(side=tk.LEFT, padx=3)
    tk.Button(per_row, text="History", command=lambda: open_person_history_window(person_var.get())).pack(side=tk.LEFT, padx=3)

    misc = tk.Frame(overlay); misc.pack(fill="x", padx=6, pady=6)
    tk.Button(misc, text="Settings…", command=open_settings_window).pack(side=tk.LEFT, padx=3)
    tk.Button(misc, text="Tuning Popup…", command=open_tuning_popup).pack(side=tk.LEFT, padx=12)
    tk.Button(misc, text="Refresh Logs", command=refresh_live_logs_ui).pack(side=tk.LEFT, padx=12)
    tk.Button(misc, text="Clear Logs", command=clear_live_logs).pack(side=tk.LEFT, padx=3)

    handle = tk.Button(video_feed_frame, text="Controls ▸", command=show_overlay)
    handle.place_forget()

create_top_right_controls()

############################
# Dropdown updaters
############################
def update_object_dropdown():
    keys = sorted(object_memory.keys())
    for dd in object_dropdowns:
        try:
            menu = dd["menu"]; menu.delete(0, "end")
            if keys:
                for obj in keys:
                    menu.add_command(label=obj, command=lambda value=obj: object_var.set(value))
            else:
                menu.add_command(label="No objects logged", command=lambda: None)
        except Exception:
            pass
    if keys and object_var.get() not in object_memory:
        object_var.set(keys[0])
    _refresh_sub_lists()

def update_person_dropdown():
    keys = sorted(person_memory.keys())
    for dd in person_dropdowns:
        try:
            menu = dd["menu"]; menu.delete(0, "end")
            if keys:
                for person in keys:
                    menu.add_command(label=person, command=lambda value=person: person_var.set(value))
            else:
                menu.add_command(label="No persons logged", command=lambda: None)
        except Exception:
            pass
    if keys and person_var.get() not in person_memory:
        person_var.set(keys[0])
    _refresh_sub_lists()

############################
# Camera toggle handlers
############################
def enable_camera(idx):
    if idx in camera_workers and camera_workers[idx] and camera_workers[idx].is_alive():
        logger.debug(f"{camera_name(idx)} already running.")
    else:
        name = camera_name(idx)
        worker = CameraWorker(idx, name, FEED_W, FEED_H, FPS_CAP)
        worker.start()
        camera_workers[idx] = worker
        log_camera_event(name, "INFO: Worker thread started.")

    if idx not in camera_cells:
        cell, lbl = make_camera_cell(video_strip, camera_name(idx))
        camera_cells[idx] = (cell, lbl)
    else:
        cell, lbl = camera_cells[idx]
    try:
        cell.pack_forget()
        cell.pack(side=tk.LEFT, padx=6, pady=6)
    except Exception:
        pass

    worker = camera_workers[idx]
    camera_windows[idx] = (worker, camera_name(idx), camera_cells[idx][1])
    if AUTO_FIT_VAR.get() == 1:
        _compute_autofit_sizes()

    _update_video_strip_scrollregion()
    _refresh_live_log_dropdown()
    logger.info(f"Enabled {camera_name(idx)}.")

def disable_camera(idx):
    worker = camera_workers.get(idx)
    if worker:
        try: worker.stop()
        except Exception: pass
    camera_workers[idx] = None

    if idx in camera_cells:
        cell, lbl = camera_cells[idx]
        try:
            lbl.config(image='', text='')
            cell.pack_forget()
        except Exception:
            pass

    if idx in camera_windows:
        try: del camera_windows[idx]
        except Exception: pass

    _display_size_cache.pop(idx, None)
    _update_video_strip_scrollregion()
    _refresh_live_log_dropdown()
    if AUTO_FIT_VAR.get() == 1:
        _compute_autofit_sizes()
    logger.info(f"Disabled {camera_name(idx)}.")

############################
# Load persisted data
############################
def load_person_memory_safe():
    try:
        load_person_memory()
    except Exception as e:
        logger.error(f"Failed loading person memory: {e}")

load_known_faces()
load_person_memory_safe()
load_notify_settings()
load_vehicle_db()
load_review_notes()
if notify_config.get("media_hosting",{}).get("mode") == "builtin":
    _start_media_server_if_needed()

update_object_dropdown()
update_person_dropdown()

############################
# Main UI/detection loop
############################
_loop_counter = 0
def update_cameras():
    global _loop_counter
    if SHUTTING_DOWN:
        return

    current_detections.clear()
    _loop_counter += 1

    if AUTO_FIT_VAR.get() == 1:
        _compute_autofit_sizes()

    for idx, (worker, cam_name, lbl) in list(camera_windows.items()):
        if worker is None or not worker.is_alive():
            log_camera_event(cam_name, "ERROR: Worker not alive.")
            continue

        frame = worker.get_frame()
        if frame is None:
            continue

        if FRAME_SKIP > 0 and (_loop_counter % (FRAME_SKIP + 1)) != 1:
            processed = frame
        else:
            processed = process_frame(frame.copy(), camera_tag=cam_name)

        if DISPLAY_FEEDS_VAR.get() == 1:
            try:
                if AUTO_FIT_VAR.get() == 1:
                    dw, dh = _display_size_cache.get(idx, (FEED_W, FEED_H))
                else:
                    dw, dh = (FEED_W, FEED_H)
                disp = cv2.resize(processed, (int(dw), int(dh)), interpolation=cv2.INTER_AREA)
            except Exception:
                disp = processed
            rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=pil_img)
            try:
                lbl.config(image=imgtk)
                lbl.imgtk = imgtk
            except Exception:
                pass

    update_unknown_count()
    refresh_tracked_objects_list()
    refresh_tracked_persons_list()
    refresh_current_detections_list()
    refresh_live_logs_ui()

    schedule_after(max(1, int(FPS_CAP)), update_cameras)

schedule_after(10, update_cameras)

############################
# Initialize notifications UI data
############################
push_once = False
def _push_once():
    global push_once
    if push_once: return
    _push_config_to_ui()
    _refresh_sub_lists()
    push_once = True
schedule_after(200, _push_once)

############################
# Cleanup
############################
def on_closing():
    """Robust, idempotent shutdown with clean thread and timer teardown."""
    global SHUTTING_DOWN
    if SHUTTING_DOWN:
        return
    SHUTTING_DOWN = True

    # Stop wake listener & TTS
    try:
        stop_wake_listener_and_join(timeout=1.5)
    except Exception:
        pass
    try:
        if _tts_engine is not None:
            _tts_engine.stop()
    except Exception:
        pass

    # Cancel all Tk timers we created
    try:
        cancel_all_afters()
    except Exception:
        pass

    # Stop camera workers (then join)
    try:
        for idx, worker in list(camera_workers.items()):
            if worker:
                try:
                    worker.stop()
                except Exception:
                    pass
        for idx, worker in list(camera_workers.items()):
            if worker:
                try:
                    worker.join(timeout=1.5)
                except Exception:
                    pass
    except Exception:
        pass

    # Shutdown built-in media server if running
    try:
        if _media_server is not None:
            try: _media_server.shutdown()
            except Exception: pass
            try: _media_server.server_close()
            except Exception: pass
        if _media_server_thread is not None:
            try: _media_server_thread.join(timeout=1.5)
            except Exception: pass
    except Exception:
        pass

    # Persist everything
    for saver in (save_person_memory, save_notify_settings, save_vehicle_db, save_review_notes, save_chat_history):
        try:
            saver()
        except Exception:
            pass

    # Close OpenCV windows and the Tk app
    try: cv2.destroyAllWindows()
    except Exception: pass
    try: root.quit()
    except Exception: pass
    try: root.destroy()
    except Exception: pass

    logger.info("Clean exit.")

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
