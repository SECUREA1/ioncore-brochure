import asyncio
import threading
import platform
import binascii
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, simpledialog
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from async_timeout import timeout
import queue
import datetime
import xml.etree.ElementTree as ET
import re
import csv
import io
import os
import math
import hashlib
import sqlite3
import json
import time
from collections import deque
import statistics
import subprocess
import shutil
import webbrowser
import urllib.request
import urllib.error

# numpy & PIL for satellite overlay
import numpy as np
from PIL import Image, ImageDraw, ImageTk

# matplotlib (3D map)
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (import activates 3D)

# Optional: geocoding for window title
try:
    from geopy.geocoders import Nominatim
    HAVE_GEOPY = True
except Exception:
    Nominatim = None
    HAVE_GEOPY = False

# Optional: folium map rendering
try:
    import folium
    try:
        from folium.plugins import MousePosition
        HAVE_MOUSEPOS = True
    except Exception:
        HAVE_MOUSEPOS = False
    HAVE_FOLIUM = True
except Exception:
    folium = None
    HAVE_MOUSEPOS = False
    HAVE_FOLIUM = False

# Classic Bluetooth (PyBluez)
try:
    import bluetooth  # pybluez / pybluez2
    HAVE_PYBLUEZ = True
except Exception:
    bluetooth = None
    HAVE_PYBLUEZ = False

# OBEX FTP (Classic) for file browsing / PBAP
HAVE_PYOBEX = False
FTPClient = None
OBEXClient = None
OBEX_HEADERS = None
try:
    from PyOBEX.ftp import FTPClient as _FTPClient
    from PyOBEX.client import Client as _OBEXClient
    from PyOBEX import headers as _HEADERS
    FTPClient = _FTPClient
    OBEXClient = _OBEXClient
    OBEX_HEADERS = _HEADERS
    HAVE_PYOBEX = True
except Exception:
    try:
        from pyobex.ftp import FTPClient as _FTPClient2
        from pyobex.client import Client as _OBEXClient2
        from pyobex import headers as _HEADERS2
        FTPClient = _FTPClient2
        OBEXClient = _OBEXClient2
        OBEX_HEADERS = _HEADERS2
        HAVE_PYOBEX = True
    except Exception:
        HAVE_PYOBEX = False

# --- Windows WinRT (paired device enumeration) ---
HAVE_WINRT = False
try:
    from winrt.windows.devices.enumeration import DeviceInformation
    from winrt.windows.devices.bluetooth import BluetoothLEDevice, BluetoothDevice
    HAVE_WINRT = True
except Exception:
    DeviceInformation = None
    BluetoothLEDevice = None
    BluetoothDevice = None
    HAVE_WINRT = False

IS_WINDOWS = platform.system() == "Windows"

# === Real-time GPS sources (ADDED) ===
HAVE_WIN_GEO = False
try:
    # Windows Location API (Geolocator)
    from winrt.windows.devices.geolocation import (
        Geolocator, GeolocationAccessStatus, PositionAccuracy
    )
    HAVE_WIN_GEO = True
except Exception:
    HAVE_WIN_GEO = False

HAVE_SERIAL = False
try:
    import serial
    import serial.tools.list_ports
    HAVE_SERIAL = True
except Exception:
    HAVE_SERIAL = False

HAVE_GPSD = False
try:
    from gps3 import gps3  # Linux gpsd client
    HAVE_GPSD = True
except Exception:
    HAVE_GPSD = False

# UUIDs
OBEX_FTP_UUID = "00001106-0000-1000-8000-00805f9b34fb"
PBAP_PSE_UUID = "0000112f-0000-1000-8000-00805f9b34fb"  # Phonebook Access - Server (on phone)
PBAP_TARGET_UUID_BYTES = bytes.fromhex("796135F0F0C511D809660800200C9A66")


# ---------------- Ioncore Branding -----------------
IONCORE_LOGO_SVG = """<svg width=\"160\" height=\"160\" viewBox=\"0 0 160 160\" xmlns=\"http://www.w3.org/2000/svg\">\n  <defs>\n    <linearGradient id=\"ioncoreGradient\" x1=\"0%\" y1=\"0%\" x2=\"100%\" y2=\"100%\">\n      <stop offset=\"0%\" stop-color=\"#38F0D1\"/>\n      <stop offset=\"100%\" stop-color=\"#6AFF3B\"/>\n    </linearGradient>\n  </defs>\n  <circle cx=\"80\" cy=\"80\" r=\"74\" fill=\"url(#ioncoreGradient)\"/>\n  <circle cx=\"80\" cy=\"80\" r=\"46\" fill=\"#060B1A\" opacity=\"0.94\"/>\n  <path d=\"M40 80c0-22.091 17.909-40 40-40s40 17.909 40 40-17.909 40-40 40S40 102.091 40 80zm52 0a12 12 0 10-24 0 12 12 0 0024 0z\" fill=\"#F4F9FF\" opacity=\"0.88\"/>\n  <path d=\"M34 64a60 60 0 0092 0\" stroke=\"#38F0D1\" stroke-width=\"6\" stroke-linecap=\"round\" fill=\"none\"/>\n  <path d=\"M34 96a60 60 0 0092 0\" stroke=\"#6AFF3B\" stroke-width=\"6\" stroke-linecap=\"round\" fill=\"none\"/>\n</svg>"""


def get_default_theme_mode(default="dark"):
    """Return the preferred Ioncore theme, honoring environment overrides."""
    mode = os.environ.get("IONCORE_THEME_MODE", "").strip().lower()
    if mode in {"light", "dark"}:
        return mode
    return default


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in range(0, 6, 2))


def _blend_channel(start, end, factor):
    return int(start + (end - start) * factor)


def _gradient_color(start_rgb, end_rgb, factor):
    return tuple(_blend_channel(s, e, factor) for s, e in zip(start_rgb, end_rgb))


def create_ioncore_logo_image(size=160):
    size = int(size)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    outer_radius = size // 2 - 4
    center = size / 2
    start_rgb = _hex_to_rgb("#38F0D1")
    end_rgb = _hex_to_rgb("#6AFF3B")

    for step, radius in enumerate(range(outer_radius, 0, -1)):
        factor = step / max(1, outer_radius)
        color = _gradient_color(start_rgb, end_rgb, factor)
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            fill=color,
        )

    inner_radius = int(outer_radius * 0.58)
    draw.ellipse(
        [center - inner_radius, center - inner_radius, center + inner_radius, center + inner_radius],
        fill=(6, 11, 26, 235),
    )

    orbit_radius = outer_radius - size * 0.1
    orbit_width = max(2, size // 30)
    draw.arc(
        [center - orbit_radius, center - orbit_radius, center + orbit_radius, center + orbit_radius],
        start=215,
        end=325,
        width=orbit_width,
        fill="#38F0D1",
    )
    draw.arc(
        [center - orbit_radius, center - orbit_radius, center + orbit_radius, center + orbit_radius],
        start=35,
        end=145,
        width=orbit_width,
        fill="#6AFF3B",
    )

    core_radius = int(inner_radius * 0.42)
    draw.ellipse(
        [center - core_radius, center - core_radius, center + core_radius, center + core_radius],
        fill=(244, 249, 255, 235),
    )

    bar_width = max(6, size // 12)
    bar_radius = bar_width // 2
    draw.rounded_rectangle(
        [center - bar_width * 1.6, center - bar_width * 0.3, center + bar_width * 1.6, center + bar_width * 0.3],
        radius=bar_radius,
        fill="#38F0D1",
    )
    draw.rounded_rectangle(
        [center - bar_width * 0.9, center - bar_width * 0.9, center + bar_width * 0.9, center - bar_width * 0.35],
        radius=bar_radius,
        fill="#6AFF3B",
    )

    return ImageTk.PhotoImage(canvas)


IONCORE_THEMES = {
    "dark": {
        "bg": "#030712",
        "surface": "#0D182E",
        "surface_alt": "#11203D",
        "accent": "#6AFF3B",
        "accent_alt": "#38F0D1",
        "accent_fg": "#02110B",
        "text": "#F5F8FF",
        "muted_text": "#B7C7E4",
        "border": "#1C2A41",
        "list_bg": "#09101D",
        "list_fg": "#F5F8FF",
        "entry_bg": "#0B1424",
        "entry_fg": "#F5F8FF",
        "log_bg": "#0B1424",
        "log_fg": "#AEE8B4",
    },
    "light": {
        "bg": "#F5F8FF",
        "surface": "#FFFFFF",
        "surface_alt": "#EDF4FF",
        "accent": "#4CD067",
        "accent_alt": "#32B5F0",
        "accent_fg": "#082015",
        "text": "#13233C",
        "muted_text": "#506080",
        "border": "#CAD7EF",
        "list_bg": "#FFFFFF",
        "list_fg": "#13233C",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#13233C",
        "log_bg": "#FFFFFF",
        "log_fg": "#24502F",
    },
}

# ---------- Tracking constants ----------
TRACK_SAMPLE_TTL_SEC = 90       # keep last 90s of rings for each device
TRACK_MIN_SAMPLES = 3           # need >= 3 rings to solve a 2D position robustly

# ---------------- Range Qualification & Smoothing -----------------
class DistanceFilter:
    """Per-radio RSSI smoother with outlier rejection and distance clamps."""
    def __init__(self, window=12, ema_alpha=0.30, min_m=0.25, max_m=40.0):
        self.window = int(window)
        self.ema_alpha = float(ema_alpha)
        self.min_m = float(min_m)
        self.max_m = float(max_m)
        # key may be BLE addr, WIFI:<BSSID>, CELL:<modem>/<tech>
        self.buffers = {}   # key -> deque of recent RSSI
        self.ema = {}       # key -> smoothed RSSI

    def push_rssi(self, key: str, rssi: float):
        """Push a raw RSSI sample. Returns the updated EMA RSSI or None if outlier."""
        if rssi is None:
            return None
        dq = self.buffers.setdefault(key, deque(maxlen=self.window))
        dq.append(rssi)
        # Robust outlier guard using MAD (and a hard 8 dB floor)
        med = statistics.median(dq)
        mad = statistics.median([abs(x - med) for x in dq]) or 1.0
        if abs(rssi - med) > max(8.0, 2.5 * mad):
            return None  # reject this sample
        prev = self.ema.get(key)
        ema = rssi if prev is None else (self.ema_alpha * rssi + (1.0 - self.ema_alpha) * prev)
        self.ema[key] = ema
        return ema

    def stats(self, key: str):
        """Return (count, stdev) for the current buffer, or (0, inf)."""
        dq = self.buffers.get(key)
        if not dq:
            return 0, float('inf')
        if len(dq) < 2:
            return len(dq), float('inf')
        try:
            stdev = statistics.pstdev(dq)
        except Exception:
            stdev = float('inf')
        return len(dq), stdev

    def quality_grade(self, key: str):
        """A/B/C/D based on sample count and stability (lower stdev -> better)."""
        count, stdev = self.stats(key)
        if count >= 8 and stdev <= 3.0:
            return 'A'
        if count >= 5 and stdev <= 6.0:
            return 'B'
        if count >= 3:
            return 'C'
        return 'D'

    def clamp_distance(self, d_m: float, min_m=None, max_m=None):
        """Clamp distance with optional override bounds."""
        if d_m is None:
            return None
        lo = self.min_m if min_m is None else float(min_m)
        hi = self.max_m if max_m is None else float(max_m)
        return max(lo, min(hi, float(d_m)))

# ---------- Local tangent-plane helpers (meters) ----------
_EARTH_R = 6378137.0
def _deg2rad(v): return v * math.pi / 180.0
def _rad2deg(v): return v * 180.0 / math.pi

# ---------- Tracking core ----------
class _TrackerMath:
    @staticmethod
    def latlon_to_xy(lat0, lon0, lat, lon):
        """Equirectangular approximation (good for city/house scale)."""
        if lat0 is None or lon0 is None:
            return 0.0, 0.0
        x = _EARTH_R * _deg2rad(lon - lon0) * math.cos(_deg2rad(lat0))
        y = _EARTH_R * _deg2rad(lat - lat0)
        return x, y

    @staticmethod
    def xy_to_latlon(lat0, lon0, x, y):
        lat = lat0 + _rad2deg(y / _EARTH_R)
        lon = lon0 + _rad2deg(x / (_EARTH_R * math.cos(_deg2rad(lat0))))
        return lat, lon

    @staticmethod
    def linear_initial_guess(samples):
        """
        Classic linearized multilateration vs first anchor:
        (x-xi)^2 + (y-yi)^2 = ri^2 -> subtract i=0 to get Ax=b.
        """
        if len(samples) < 3:
            return None
        x1, y1, r1 = samples[0]["x"], samples[0]["y"], samples[0]["r"]
        A, b = [], []
        for s in samples[1:]:
            xi, yi, ri = s["x"], s["y"], s["r"]
            A.append([2*(x1 - xi), 2*(y1 - yi)])
            b.append(r1*r1 - ri*ri - (x1*x1 - xi*xi) - (y1*y1 - yi*yi))
        try:
            At = list(zip(*A))
            AtA_00 = sum(At[0][i]*A[i][0] for i in range(len(A)))
            AtA_01 = sum(At[0][i]*A[i][1] for i in range(len(A)))
            AtA_11 = sum(At[1][i]*A[i][1] for i in range(len(A)))
            Atb_0 = sum(At[0][i]*b[i] for i in range(len(A)))
            Atb_1 = sum(At[1][i]*b[i] for i in range(len(A)))
            det = AtA_00*AtA_11 - AtA_01*AtA_01
            if abs(det) < 1e-9:
                return None
            inv00 =  AtA_11 / det
            inv01 = -AtA_01 / det
            inv11 =  AtA_00 / det
            x = inv00*Atb_0 + inv01*Atb_1
            y = inv01*Atb_0 + inv11*Atb_1
            return (x, y)
        except Exception:
            return None

    @staticmethod
    def gauss_newton(samples, x0, y0, iters=6):
        """Refine (x,y) by minimizing sum( (||p-pi|| - ri)^2 )."""
        x, y = float(x0), float(y0)
        for _ in range(iters):
            JtJ_00 = JtJ_01 = JtJ_11 = 0.0
            Jtf_0 = Jtf_1 = 0.0
            for s in samples:
                dx = x - s["x"]; dy = y - s["y"]
                d = math.hypot(dx, dy)
                if d < 1e-6:
                    continue
                fi = d - s["r"]
                gx = dx / d
                gy = dy / d
                JtJ_00 += gx*gx
                JtJ_01 += gx*gy
                JtJ_11 += gy*gy
                Jtf_0 += gx*fi
                Jtf_1 += gy*fi
            det = JtJ_00*JtJ_11 - JtJ_01*JtJ_01
            if abs(det) < 1e-9:
                break
            inv00 =  JtJ_11 / det
            inv01 = -JtJ_01 / det
            inv11 =  JtJ_00 / det
            dx = -(inv00*Jtf_0 + inv01*Jtf_1)
            dy = -(inv01*Jtf_0 + inv11*Jtf_1)
            step = math.hypot(dx, dy)
            if step > 5.0:
                scale = 5.0 / step
                dx *= scale; dy *= scale
            x += dx; y += dy
            if step < 1e-3:
                break
        return x, y

class BluetoothApp:
    def _register_theme_widget(self, widget, category):
        self.theme_widgets.setdefault(category, []).append(widget)

    def _init_branding(self):
        self.branding_frame = tk.Frame(self.root, bd=0, highlightthickness=0)
        self.branding_frame.pack(fill="x", pady=(12, 18))
        self._register_theme_widget(self.branding_frame, "frames")

        self.logo_label = tk.Label(self.branding_frame, image=self.logo_large, borderwidth=0, highlightthickness=0)
        self.logo_label.grid(row=0, column=0, rowspan=2, padx=(14, 18), pady=4, sticky="w")

        self.branding_title = tk.Label(
            self.branding_frame,
            text="Ioncore Radiance Console",
            font=("Montserrat", 20, "bold"),
            anchor="w",
        )
        self.branding_title.grid(row=0, column=1, sticky="w")
        self._register_theme_widget(self.branding_title, "labels")

        self.branding_tagline = tk.Label(
            self.branding_frame,
            text="Ioncore Index telemetry for Bluetooth, Wi‑Fi, and cellular intelligence.",
            font=("Montserrat", 12),
            anchor="w",
            wraplength=660,
            justify="left",
        )
        self.branding_tagline.grid(row=1, column=1, sticky="w", pady=(4, 0))
        self._register_theme_widget(self.branding_tagline, "labels")

        self.theme_status = tk.Label(
            self.branding_frame,
            text="Dark Mode" if self.theme_mode == "dark" else "Light Mode",
            font=("Segoe UI", 11, "bold"),
            anchor="e",
        )
        self.theme_status.grid(row=0, column=2, sticky="e", padx=(16, 14))
        self._register_theme_widget(self.theme_status, "labels")

        self.theme_button = tk.Button(
            self.branding_frame,
            text="Switch Theme",
            command=self.toggle_theme,
            padx=18,
            pady=8,
            relief="flat",
            cursor="hand2",
            bd=0,
        )
        self.theme_button.grid(row=1, column=2, sticky="e", padx=(16, 14), pady=(4, 0))
        self._register_theme_widget(self.theme_button, "buttons")

        self.branding_frame.columnconfigure(1, weight=1)

    def _apply_theme_recursive(self, widget, colors):
        try:
            widget_class = widget.winfo_class()
        except Exception:
            widget_class = ""

        for child in widget.winfo_children():
            self._apply_theme_recursive(child, colors)

        try:
            if widget_class in {"Frame", "Labelframe", "TFrame"}:
                widget.configure(bg=colors["surface"], highlightbackground=colors["border"])
            elif widget_class in {"Label", "Message", "TLabel"}:
                widget.configure(bg=colors["surface"], fg=colors["text"])
            elif widget_class in {"Entry", "TEntry", "Spinbox"}:
                widget.configure(
                    bg=colors["entry_bg"],
                    fg=colors["entry_fg"],
                    insertbackground=colors["accent"],
                    highlightbackground=colors["border"],
                    highlightcolor=colors["accent"],
                )
            elif widget_class in {"Listbox"}:
                widget.configure(
                    bg=colors["list_bg"],
                    fg=colors["list_fg"],
                    selectbackground=colors["accent"],
                    selectforeground=colors["accent_fg"],
                    highlightbackground=colors["border"],
                    highlightcolor=colors["accent"],
                    bd=0,
                )
            elif widget_class in {"Text"}:
                widget.configure(
                    bg=colors["log_bg"],
                    fg=colors["log_fg"],
                    insertbackground=colors["accent"],
                    highlightbackground=colors["border"],
                    highlightcolor=colors["accent"],
                )
            elif widget_class in {"Button", "Checkbutton", "Menubutton", "Radiobutton"}:
                widget.configure(
                    bg=colors["accent"],
                    fg=colors["accent_fg"],
                    activebackground=colors["accent_alt"],
                    activeforeground=colors["accent_fg"],
                    highlightbackground=colors["border"],
                    highlightcolor=colors["accent"],
                    bd=0,
                    relief="flat",
                )
            elif widget_class in {"Canvas"}:
                widget.configure(bg=colors["surface"])
            elif widget_class in {"Scrollbar"}:
                widget.configure(bg=colors["surface"], troughcolor=colors["surface_alt"], activebackground=colors["accent"])
        except tk.TclError:
            pass

    def apply_theme(self):
        colors = IONCORE_THEMES[self.theme_mode]
        self.root.configure(bg=colors["bg"])

        self._apply_theme_recursive(self.root, colors)

        self.branding_frame.configure(bg=colors["surface_alt"], highlightbackground=colors["border"])
        self.logo_label.configure(bg=colors["surface_alt"])
        self.branding_title.configure(bg=colors["surface_alt"], fg=colors["text"])
        self.branding_tagline.configure(bg=colors["surface_alt"], fg=colors["muted_text"])
        self.theme_status.configure(bg=colors["surface_alt"], fg=colors["accent_alt"])
        self.theme_button.configure(
            bg=colors["accent"],
            fg=colors["accent_fg"],
            activebackground=colors["accent_alt"],
            activeforeground=colors["accent_fg"],
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
            bd=0,
            relief="flat",
        )

        self.theme_button.configure(
            text="Switch to Light Mode" if self.theme_mode == "dark" else "Switch to Dark Mode"
        )
        self.theme_status.configure(
            text="Dark Mode" if self.theme_mode == "dark" else "Light Mode",
        )

        self.root.update_idletasks()

    def toggle_theme(self):
        self.theme_mode = "light" if self.theme_mode == "dark" else "dark"
        self.apply_theme()
        self.log(f"Ioncore theme switched to {self.theme_mode.title()} Mode.")

    def __init__(self, root):
        self.root = root
        self.root.title("Ioncore Radiance Console • Bluetooth • Wi‑Fi • Cellular")

        self.theme_mode = get_default_theme_mode()
        self.theme_widgets = {
            "frames": [],
            "labels": [],
            "buttons": [],
            "entries": [],
            "lists": [],
            "texts": [],
        }

        self.logo_large = create_ioncore_logo_image(128)
        self.logo_small = create_ioncore_logo_image(48)
        try:
            self.root.iconphoto(False, self.logo_small)
        except Exception:
            pass

        self._init_branding()

        # ---------- Async loop (single, persistent) ----------
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._run_loop, args=(self.loop,), daemon=True)
        self.loop_thread.start()

        # ---------- DB (thread-safe) ----------
        self.db = None
        self.db_lock = threading.Lock()
        self._init_db()

        # ---------- GPS origin (initial placeholder; will be updated live) ----------
        self.gps_lat = 40.730610
        self.gps_lon = -73.935242

        # Live-GPS refresh throttle & WinRT tokens (ADDED)
        self._pending_map_refresh = False
        self.winrt_geo = None
        self.winrt_geo_token = None
        self.winrt_geo_status_token = None

        # ---------- UI: device list and controls ----------
        self.device_frame = tk.Frame(root, highlightthickness=0, bd=0)
        self.device_frame.pack(pady=10)
        self._register_theme_widget(self.device_frame, "frames")

        self.device_list = tk.Listbox(self.device_frame, width=130, height=22)
        self.device_list.grid(row=0, column=0, columnspan=15, padx=5, pady=5)
        self._register_theme_widget(self.device_list, "lists")

        self.scan_button = tk.Button(self.device_frame, text="Scan BLE/Classic", command=self.start_scan_devices)
        self.scan_button.grid(row=1, column=0, padx=5, pady=5)

        self.scan_wifi_button = tk.Button(self.device_frame, text="Scan Wi‑Fi", command=self.start_scan_wifi)
        self.scan_wifi_button.grid(row=1, column=1, padx=5, pady=5)

        self.scan_cell_button = tk.Button(self.device_frame, text="Scan Cellular", command=self.start_scan_cell)
        self.scan_cell_button.grid(row=1, column=2, padx=5, pady=5)

        self.test_button = tk.Button(self.device_frame, text="Test Connection", command=self.start_test_connection)
        self.test_button.grid(row=1, column=3, padx=5, pady=5)

        self.connect_button = tk.Button(self.device_frame, text="Connect Device", command=self.start_start_connect)
        self.connect_button.grid(row=1, column=4, padx=5, pady=5)

        self.disconnect_button = tk.Button(self.device_frame, text="Disconnect", command=self.disconnect_device)
        self.disconnect_button.grid(row=1, column=5, padx=5, pady=5)

        self.explore_button = tk.Button(self.device_frame, text="Explore (BLE)", command=self.start_explore_ble)
        self.explore_button.grid(row=1, column=6, padx=5, pady=5)

        self.obex_button = tk.Button(self.device_frame, text="Browse Files (OBEX)", command=self.open_obex_browser)
        self.obex_button.grid(row=1, column=7, padx=5, pady=5)

        self.pbap_button = tk.Button(self.device_frame, text="Contacts (PBAP/FTP)", command=self.open_contacts_browser)
        self.pbap_button.grid(row=1, column=8, padx=5, pady=5)

        self.map3d_button = tk.Button(self.device_frame, text="3D Map", command=self.open_map3d_popup)
        self.map3d_button.grid(row=1, column=9, padx=5, pady=5)

        self.open_map_button = tk.Button(self.device_frame, text="Open Map (Interactive)", command=self.open_interactive_map)
        self.open_map_button.grid(row=1, column=10, padx=5, pady=5)

        self.relabel_button = tk.Button(self.device_frame, text="Relabel", command=self.relabel_selected_device)
        self.relabel_button.grid(row=1, column=11, padx=5, pady=5)

        self.clearlabel_button = tk.Button(self.device_frame, text="Clear Label", command=self.clear_label_selected_device)
        self.clearlabel_button.grid(row=1, column=12, padx=5, pady=5)

        self.scan_paired_button = tk.Button(self.device_frame, text="Scan Paired (Windows)", command=self.start_scan_paired_windows)
        self.scan_paired_button.grid(row=1, column=13, padx=5, pady=5)

        self.export_button = tk.Button(self.device_frame, text="Export", command=self.download_info)
        self.export_button.grid(row=1, column=14, padx=5, pady=5)

        self.send_button = tk.Button(self.device_frame, text="Send Data", command=self.send_data_to_device)
        self.send_button.grid(row=2, column=0, padx=5, pady=5)

        self.receive_button = tk.Button(self.device_frame, text="Receive Data", command=self.receive_data_from_device)
        self.receive_button.grid(row=2, column=1, padx=5, pady=5)

        self.advertise_button = tk.Button(self.device_frame, text="Advertise 'Bullish'", command=self.start_advertising)
        self.advertise_button.grid(row=2, column=2, padx=5, pady=5)

        for button in (
            self.scan_button,
            self.scan_wifi_button,
            self.scan_cell_button,
            self.test_button,
            self.connect_button,
            self.disconnect_button,
            self.explore_button,
            self.obex_button,
            self.pbap_button,
            self.map3d_button,
            self.open_map_button,
            self.relabel_button,
            self.clearlabel_button,
            self.scan_paired_button,
            self.export_button,
            self.send_button,
            self.receive_button,
            self.advertise_button,
        ):
            self._register_theme_widget(button, "buttons")

        # Disable features if libs/OS don’t support them
        if IS_WINDOWS or not HAVE_PYBLUEZ:
            self.advertise_button.configure(state="disabled")
        if not HAVE_PYBLUEZ:
            self.send_button.configure(state="disabled")
            self.receive_button.configure(state="disabled")
            self.obex_button.configure(state="disabled")
            self.pbap_button.configure(state="disabled")
        if HAVE_PYBLUEZ and not HAVE_PYOBEX:
            self.obex_button.configure(state="disabled")
            self.pbap_button.configure(state="disabled")
        if not (IS_WINDOWS and HAVE_WINRT):
            self.scan_paired_button.configure(state="disabled")

        # ---------- Tuning panel (distance model) ----------
        self.tuner_frame = tk.Frame(root, highlightthickness=0, bd=0)
        self.tuner_frame.pack(pady=(0, 10))
        self._register_theme_widget(self.tuner_frame, "frames")

        tx_label = tk.Label(self.tuner_frame, text="Tx Power @1m (BLE default, dBm):")
        tx_label.grid(row=0, column=0, sticky="e", padx=4)
        env_label = tk.Label(self.tuner_frame, text="Environment n (1.5–4.0):")
        env_label.grid(row=0, column=2, sticky="e", padx=4)
        self._register_theme_widget(tx_label, "labels")
        self._register_theme_widget(env_label, "labels")

        self.tx_power_1m_default = -59.0
        self.path_loss_n = 2.0

        self.tx_power_var = tk.StringVar(value=str(self.tx_power_1m_default))
        self.n_var = tk.StringVar(value=str(self.path_loss_n))

        self.tx_power_entry = tk.Entry(self.tuner_frame, width=8, textvariable=self.tx_power_var)
        self.n_entry = tk.Entry(self.tuner_frame, width=8, textvariable=self.n_var)
        self._register_theme_widget(self.tx_power_entry, "entries")
        self._register_theme_widget(self.n_entry, "entries")

        self.tx_power_entry.grid(row=0, column=1, sticky="w", padx=4)
        self.n_entry.grid(row=0, column=3, sticky="w", padx=4)

        self.apply_button = tk.Button(self.tuner_frame, text="Apply Tuning", command=self.apply_tuning)
        self.apply_button.grid(row=0, column=4, padx=(10, 0))
        self._register_theme_widget(self.apply_button, "buttons")

        # ---------- Log ----------
        self.log_text = scrolledtext.ScrolledText(root, width=130, height=12, state='disabled', highlightthickness=0, bd=0)
        self.log_text.pack(pady=10)
        self._register_theme_widget(self.log_text, "texts")

        # ---------- Data ----------
        self.devices = []           # ("BLE", bleak_device) | ("Classic", dict) | ("WiFi", dict) | ("Cell", dict)
        self.connection_results = {}
        self.connected_socket = None
        self.ble_client = None
        self.server_sock = None

        self.ble_meta = {}          # addr -> {...}
        self.wifi_meta = {}         # bssid -> {...}
        self.cell_meta = {}         # cid -> {...}

        # BLE Explorer
        self.explorer_win = None
        self.explorer_text = None
        self.last_services = None

        # OBEX Browser state
        self.obex = {"win": None, "list": None, "path_var": None, "client": None, "addr": None, "port": None, "items": []}

        # Contacts window state
        self.contacts = {"win": None, "list": None, "log": None, "data": []}

        # 3D Map state + satellite overlay
        self.map3d = {
            "win": None, "fig": None, "ax": None, "canvas": None,
            "animate_var": None, "anim_on": False, "timer": None,
            "trees": [], "targets": [], "bases": [], "labels": [],
            "radial_scale": 1.0,          # meters -> meters on plot (1:1)
            "classic_default_dist": 8.0,  # Classic when unknown
            "wifi_default_dist": 10.0,    # Wi‑Fi when unknown
            "cell_default_dist": 120.0,   # visualize cell at distance
            "growth_rate": 0.06,
            "cid_scroll": None,
            "sat_overlay_var": None,
            "sat_status": None,
            "sat_zoom": 18,
            "sat_tiles": 3,
            "overlay_img": None,
            "overlay_extent": None,
            "overlay_cache_key": None
        }

        # Thread-safe UI queue
        self.queue = queue.Queue()
        self.root.after(100, self.process_queue)

        # Clean shutdown
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if not HAVE_PYBLUEZ:
            self.log("PyBluez not installed; Classic Bluetooth features limited/disabled.")
        if not HAVE_PYOBEX:
            self.log("PyOBEX not installed; OBEX (files/contacts) disabled.")
        if not HAVE_GEOPY:
            self.log("geopy not installed; window title will show coordinates only (no reverse-geocoded address).")
        if not HAVE_FOLIUM:
            self.log("folium not installed; interactive web map disabled.")
        if not HAVE_WINRT and IS_WINDOWS:
            self.log("winrt not installed; paired-device enumeration (stable iPhone IDs) disabled.")

        # Set title with geocoded location (best-effort)
        self._update_title_by_gps()
        self.apply_theme()
        self.log(f"Ioncore theme initialized in {self.theme_mode.title()} Mode.")

        # === Range qualification / smoothing ===
        self.dist_filter = DistanceFilter(window=12, ema_alpha=0.30, min_m=0.25, max_m=40.0)

        # === Start live GPS (ADDED) ===
        self._start_realtime_location()

        # ---------- Tracking state (NEW) ----------
        self.origin_lat = None
        self.origin_lon = None
        self.tracks = {}         # key -> {"samples": deque, "trail": deque, "est": {"x","y","t"}, "speed": float}
        self._next_list_refresh_ts = 0.0
        self._tracker_view = {"win": None, "canvas": None, "zoom": 1.0,
                              "show_rings": tk.BooleanVar(value=False),
                              "last_draw": 0.0}

        # Tracking controls (NEW)
        self.tracking_enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.device_frame, text="Track live (estimate x,y)",
                       variable=self.tracking_enabled_var).grid(row=2, column=4, padx=5, pady=5)
        self.tracker_view_button = tk.Button(self.device_frame, text="Tracker View", command=self.open_tracker_view)
        self.tracker_view_button.grid(row=2, column=5, padx=5, pady=5)

        # periodic housekeeping for trackers
        self.root.after(3000, self._tracker_housekeeping)
        # poll Wi‑Fi periodically while tracking
        self.root.after(3500, self._wifi_poll_timer)

        # === Auto-scan on launch ===
        self.root.after(600, self.start_scan_devices)
        self.root.after(1400, self.start_scan_wifi)
        self.root.after(2200, self.start_scan_cell)

        # === Start continuous BLE scanner for live tracking (NEW) ===
        self.live_ble_scanner_active = False
        self.run_coro(self._ble_live_scanner())

    # ---------- Title / GPS ----------
    def _update_title_by_gps(self):
        lat, lon = self.get_gps_coordinates()
        title = f"Ioncore Radiance Console — GPS {lat:.6f}, {lon:.6f}"
        if HAVE_GEOPY:
            try:
                geolocator = Nominatim(user_agent="expanded_radio_manager")
                loc = geolocator.reverse(f"{lat},{lon}", timeout=5)
                if loc and getattr(loc, "address", None):
                    title = f"Ioncore Radiance Console — {loc.address}"
            except Exception:
                pass
        self.root.title(title)

    def prompt_set_gps_coordinates(self):
        s = simpledialog.askstring("Set GPS", "Enter GPS as 'lat, lon':",
                                   initialvalue=f"{self.gps_lat:.6f}, {self.gps_lon:.6f}")
        if not s:
            return
        try:
            parts = [p.strip() for p in s.split(",")]
            lat = float(parts[0]); lon = float(parts[1])
        except Exception:
            messagebox.showerror("Invalid", "Format must be: 40.7128, -74.0060")
            return
        self.gps_lat, self.gps_lon = lat, lon
        # Fix origin on manual set if not set yet
        if self.origin_lat is None or self.origin_lon is None:
            self.origin_lat, self.origin_lon = lat, lon
        self._update_title_by_gps()
        # reset overlay cache so it reloads
        self.map3d["overlay_cache_key"] = None
        if self.map3d["win"] and tk.Toplevel.winfo_exists(self.map3d["win"]):
            self._render_map3d()

    def get_gps_coordinates(self):
        return (self.gps_lat, self.gps_lon)

    # === Real-time GPS (ADDED) ===
    def _start_realtime_location(self):
        """Start platform-appropriate GPS sources. Priority: WinRT -> gpsd -> NMEA serial."""
        try:
            started = False
            if IS_WINDOWS and HAVE_WIN_GEO:
                self.run_coro(self._winrt_location_worker_async())
                started = True
            elif platform.system() == "Linux" and HAVE_GPSD:
                threading.Thread(target=self._gpsd_worker, daemon=True).start()
                started = True

            # Serial fallback on all OS (if present)
            if HAVE_SERIAL:
                threading.Thread(target=self._nmea_serial_worker, daemon=True).start()
                started = True or started

            if started:
                self.log("Real-time GPS: watching for updates…")
            else:
                self.log("Real-time GPS not available; use 'Set GPS…' to override.")
        except Exception as e:
            self.log(f"GPS init error: {e}")

    async def _winrt_location_worker_async(self):
        """Windows Location API – event-driven updates."""
        try:
            access = await Geolocator.request_access_async()
            if int(access) != int(GeolocationAccessStatus.ALLOWED):
                self.log(f"Windows location access not allowed (status={access}). "
                         f"Enable Settings > Privacy & security > Location.")
                return

            geo = Geolocator()
            try:
                geo.desired_accuracy = PositionAccuracy.HIGH
            except Exception:
                pass
            try:
                geo.movement_threshold = 1.0  # meters
            except Exception:
                pass
            try:
                geo.report_interval = 1000  # ms (fallback)
            except Exception:
                pass

            # Initial reading
            try:
                pos = await geo.get_geoposition_async()
                self._update_gps_from_geoposition(pos)
            except Exception:
                pass

            # Subscribe to events
            def _onpos(sender, args):
                try:
                    self._update_gps_from_geoposition(args.position)
                except Exception as ex:
                    self.log(f"Geolocation handler error: {ex}")

            def _onstatus(sender, args):
                try:
                    self.log(f"Windows Location status: {args.status}")
                except Exception:
                    pass

            tok1 = geo.add_position_changed(_onpos)
            tok2 = geo.add_status_changed(_onstatus)
            self.winrt_geo = geo
            self.winrt_geo_token = tok1
            self.winrt_geo_status_token = tok2
            self.log("Windows real-time location: ON")
        except Exception as e:
            self.log(f"WinRT geolocation error: {e}")

    def _update_gps_from_geoposition(self, pos):
        """Extract lat/lon from WinRT Geoposition and update app."""
        try:
            coord = pos.coordinate
        except Exception:
            coord = None
        lat = lon = acc = None
        if coord is not None:
            try:
                pt = coord.point.position
                lat = pt.latitude
                lon = pt.longitude
            except Exception:
                try:
                    lat = coord.latitude
                    lon = coord.longitude
                except Exception:
                    pass
            try:
                acc = float(getattr(coord, "accuracy", None) or getattr(coord, "horizontal_accuracy", None))
            except Exception:
                acc = None
        if lat is not None and lon is not None:
            self._update_gps(lat, lon, accuracy_m=acc)

    def _update_gps(self, lat, lon, accuracy_m=None):
        """Central GPS update -> title + 3D overlay refresh (throttled)."""
        try:
            lat = float(lat); lon = float(lon)
        except Exception:
            return
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return

        # Fix tracking origin once, when first real GPS arrives
        if self.origin_lat is None or self.origin_lon is None:
            self.origin_lat, self.origin_lon = lat, lon

        moved = (abs(lat - self.gps_lat) > 1e-6) or (abs(lon - self.gps_lon) > 1e-6)
        self.gps_lat, self.gps_lon = lat, lon

        # Title refresh (geocoding best-effort)
        self.queue.put(lambda: self._update_title_by_gps())

        if moved:
            if accuracy_m is not None:
                self.log(f"GPS update: {lat:.6f}, {lon:.6f} (±{accuracy_m:.1f} m)")
            else:
                self.log(f"GPS update: {lat:.6f}, {lon:.6f}")
            # force overlay reload
            self.map3d["overlay_cache_key"] = None
            self.queue.put(self._schedule_map_refresh)

    def _schedule_map_refresh(self):
        """Throttle redraws so frequent GPS events don't overload the UI."""
        if getattr(self, "_pending_map_refresh", False):
            return
        self._pending_map_refresh = True
        def _do():
            self._pending_map_refresh = False
            if self.map3d["win"] and tk.Toplevel.winfo_exists(self.map3d["win"]):
                self._render_map3d()
        self.root.after(800, _do)

    # Linux gpsd (ADDED)
    def _gpsd_worker(self):
        try:
            gps_socket = gps3.GPSDSocket()
            data_stream = gps3.DataStream()
            gps_socket.connect(); gps_socket.watch()
            self.log("gpsd: watching for TPV reports…")
            for new_data in gps_socket:
                if not new_data:
                    continue
                data_stream.unpack(new_data)
                lat = data_stream.TPV.get('lat', 'n/a')
                lon = data_stream.TPV.get('lon', 'n/a')
                acc = data_stream.TPV.get('eph', None)  # horizontal accuracy meters
                if lat != 'n/a' and lon != 'n/a':
                    self._update_gps(lat, lon, accuracy_m=acc)
        except Exception as e:
            self.log(f"gpsd reader stopped: {e}")

    # NMEA over serial (ADDED)
    def _nmea_serial_worker(self):
        if not HAVE_SERIAL:
            return

        baud_candidates = [9600, 4800, 38400, 115200]

        # Explicitly pinned port
        env_port = os.environ.get("GPS_SERIAL_PORT")
        if env_port:
            for b in baud_candidates:
                try:
                    ser = serial.Serial(env_port, baudrate=b, timeout=1)
                    self.log(f"NMEA: using GPS_SERIAL_PORT={env_port} @ {b}")
                    self._read_nmea_stream(ser)
                    return
                except Exception:
                    continue

        # Auto-detect
        try:
            ports = list(serial.tools.list_ports.comports())
        except Exception:
            ports = []

        def _score(p):
            desc = (p.description or "").lower()
            return int("gps" in desc or "gnss" in desc or "u-blox" in desc or "quectel" in desc)

        for p in sorted(ports, key=_score, reverse=True):
            for b in baud_candidates:
                try:
                    ser = serial.Serial(p.device, baudrate=b, timeout=1)
                except Exception:
                    continue
                try:
                    self.log(f"NMEA: probing {p.device} @ {b}…")
                    self._read_nmea_stream(ser)  # returns on error/disconnect
                    return
                except Exception as e:
                    self.log(f"NMEA error {p.device}: {e}")
                finally:
                    try: ser.close()
                    except Exception: pass

        self.log("NMEA: no serial GPS found. Set GPS_SERIAL_PORT to force a port.")

    def _read_nmea_stream(self, ser):
        while True:
            line = ser.readline()
            if not line:
                continue
            try:
                s = line.decode("ascii", "ignore").strip()
            except Exception:
                continue
            if not s.startswith("$"):
                continue
            latlon = None
            if s.startswith(("$GPRMC", "$GNRMC", "$GPRMA", "$GNRMA")):
                latlon = self._parse_nmea_rmc(s)
            elif s.startswith(("$GPGGA", "$GNGGA")):
                latlon = self._parse_nmea_gga(s)
            if latlon:
                lat, lon = latlon
                self._update_gps(lat, lon)

    def _parse_nmea_rmc(self, s):
        # $GPRMC,hhmmss.sss,A,llll.ll,a,yyyyy.yy,a,...
        try:
            p = s.split(",")
            if len(p) < 7:
                return None
            status = p[2].upper()
            if status != "A":
                return None
            lat = self._nmea_to_deg(p[3], p[4])
            lon = self._nmea_to_deg(p[5], p[6])
            if lat is None or lon is None:
                return None
            return (lat, lon)
        except Exception:
            return None

    def _parse_nmea_gga(self, s):
        # $GPGGA,hhmmss.ss,llll.ll,a,yyyyy.yy,a,fix,...
        try:
            p = s.split(",")
            if len(p) < 6:
                return None
            fixq = p[6] if len(p) > 6 else ""
            if fixq in ("0", ""):
                return None
            lat = self._nmea_to_deg(p[2], p[3])
            lon = self._nmea_to_deg(p[4], p[5])
            if lat is None or lon is None:
                return None
            return (lat, lon)
        except Exception:
            return None

    def _nmea_to_deg(self, v, hemi):
        try:
            if not v:
                return None
            val = float(v)
            deg = int(val // 100)
            minutes = val - deg * 100
            dec = deg + minutes / 60.0
            if str(hemi).upper() in ("S", "W"):
                dec = -dec
            return dec
        except Exception:
            return None

    # ---------- Async loop ----------
    @staticmethod
    def _run_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def run_coro(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    # ---------- DB helpers (thread-safe) ----------
    def _init_db(self):
        try:
            self.db = sqlite3.connect("bt_devices.db", check_same_thread=False)
            with self.db_lock:
                cur = self.db.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS devices (
                        addr TEXT PRIMARY KEY,
                        label TEXT
                    )
                    """
                )
                self.db.commit()
        except Exception as e:
            self.log(f"DB init error: {e}")

    def db_get_label(self, addr: str):
        try:
            with self.db_lock:
                cur = self.db.cursor()
                cur.execute("SELECT label FROM devices WHERE addr=?", (addr,))
                row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            self.log(f"DB read error: {e}")
            return None

    def db_set_label(self, addr: str, label: str):
        try:
            with self.db_lock:
                cur = self.db.cursor()
                cur.execute("INSERT INTO devices(addr,label) VALUES(?,?) ON CONFLICT(addr) DO UPDATE SET label=excluded.label", (addr, label))
                self.db.commit()
        except Exception as e:
            self.log(f"DB write error: {e}")

    def db_clear_label(self, addr: str):
        try:
            with self.db_lock:
                cur = self.db.cursor()
                cur.execute("DELETE FROM devices WHERE addr=?", (addr,))
                self.db.commit()
        except Exception as e:
            self.log(f"DB delete error: {e}")

    # ---------- Logging & queue ----------
    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.queue.put(lambda: self._append_log(log_entry))

    def _append_log(self, text):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def process_queue(self):
        try:
            while True:
                task = self.queue.get_nowait()
                task()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    # ---------- Utilities ----------
    @staticmethod
    def _format_bt_addr_from_ulong(addr_ulong: int) -> str:
        # Convert 64-bit Windows BluetoothAddress to "AA:BB:CC:DD:EE:FF"
        return ":".join(f"{(addr_ulong >> shift) & 0xFF:02X}" for shift in (40, 32, 24, 16, 8, 0))

    # ---------- Distance ----------
    def _heuristic_tx_power(self, addr: str, manufacturer_ids):
        """Prefer adv tx_power; else guess by vendor; else UI default."""
        if manufacturer_ids and any(mid.lower() == "0x004c" for mid in manufacturer_ids):
            return -59.0  # Apple‑like beacons
        return float(self.tx_power_var.get().strip() or -62.0)

    def estimate_distance(self, rssi, tx_power=None, n=None, clamp=True, min_m=None, max_m=None):
        """Log-distance path loss model with clamps and sanity checks."""
        if rssi is None:
            return None
        try:
            tx = float(self.tx_power_var.get().strip()) if tx_power is None else float(tx_power)
        except Exception:
            tx = -59.0
        try:
            n_val = float(self.n_var.get().strip()) if n is None else float(n)
        except Exception:
            n_val = 2.0
        n_val = max(1.5, min(4.0, n_val))
        try:
            dist = 10 ** ((tx - float(rssi)) / (10.0 * n_val))
        except Exception:
            return None
        if clamp:
            dist = self.dist_filter.clamp_distance(dist, min_m=min_m, max_m=max_m)
        return dist

    def _range_bucket(self, d_m: float):
        if d_m is None:
            return "Unknown"
        if d_m < 0.5:
            return "Very close"
        if d_m < 2.0:
            return "Near"
        if d_m < 7.0:
            return "Room"
        if d_m < 15.0:
            return "Far"
        return "Very far"

    # ---------- Scan BLE/Classic ----------
    def start_scan_devices(self):
        self.run_coro(self.scan_devices())

    async def _scan_ble_with_adv(self, scan_time=6.0):
        seen = {}
        def _cb(device, advertisement_data):
            addr = device.address
            rssi = getattr(advertisement_data, "rssi", None)
            ema_rssi = self.dist_filter.push_rssi(addr, rssi)
            seen[addr] = (device, advertisement_data, ema_rssi)
        scanner = BleakScanner(detection_callback=_cb)
        try:
            await scanner.start()
            await asyncio.sleep(scan_time)
        finally:
            try:
                await scanner.stop()
            except Exception:
                pass
        return list(seen.values())

    async def scan_devices(self):
        self.queue.put(lambda: self.device_list.delete(0, tk.END))
        self.devices, self.connection_results, self.ble_meta = [], {}, {}
        # (Wi‑Fi / Cell meta persist; they refresh via their own scans)

        gps_coords = f"{self.get_gps_coordinates()[0]:.6f}, {self.get_gps_coordinates()[1]:.6f}"

        # BLE
        self.log("Starting BLE scan (with adv + smoothing)...")
        ble_results = []
        try:
            if not self.live_ble_scanner_active:
                ble_results = await self._scan_ble_with_adv(scan_time=6.0)
            else:
                self.log("Skipping one-shot BLE scan (live scanner already running).")
        except (BleakError, OSError) as e:
            self.log("BLE scan failed: " + str(e))
        for device, adv, ema_rssi in ble_results:
            addr = device.address
            stored_label = self.db_get_label(addr)
            fallback_name = device.name or getattr(adv, "local_name", None) or "[Unnamed Device]"
            name = stored_label or fallback_name

            rssi = ema_rssi if ema_rssi is not None else getattr(adv, "rssi", None)
            tx_power_adv = getattr(adv, "tx_power", None)
            svc_uuids = list(getattr(adv, "service_uuids", []) or [])
            mfr = getattr(adv, "manufacturer_data", {}) or {}
            mfr_ids = [f"0x{mid:04x}" for mid in mfr.keys()]
            txp_used = tx_power_adv if tx_power_adv is not None else self._heuristic_tx_power(addr, mfr_ids)

            d_m = self.estimate_distance(rssi, txp_used, None, clamp=True)
            qual = self.dist_filter.quality_grade(addr)
            bucket = self._range_bucket(d_m)

            self.ble_meta[addr] = {
                "name": name, "fallback_name": fallback_name,
                "rssi": rssi, "tx_power": txp_used,
                "addr_type": getattr(adv, "address_type", None) or "Unknown",
                "svc_count": len(svc_uuids), "svc_uuids": svc_uuids,
                "mfr_ids": mfr_ids, "gps": gps_coords,
                "distance_m": d_m, "range_label": bucket, "qual": qual,
            }
            self.devices.append(("BLE", device))
            self.connection_results[addr] = "Not Tested"

        self.redraw_device_list()

        # Classic
        if HAVE_PYBLUEZ:
            self.log("Starting Classic Bluetooth scan...")
            for addr, name, device_class in self.scan_classic_devices():
                device_type = self.get_device_type(device_class)
                services = self.get_device_services(addr)
                stored_label = self.db_get_label(addr)
                device_name = stored_label or (name if name else self.lookup_device_name(addr))
                classic_info = {
                    "name": device_name, "fallback_name": name, "addr": addr,
                    "device_class": device_class, "type_str": device_type, "services": services
                }
                self.devices.append(("Classic", classic_info))
                self.connection_results[addr] = "Not Tested"
            self.redraw_device_list(append_only=True)
        else:
            self.log("Skipping Classic scan (PyBluez not available).")

        # Windows paired merge
        if IS_WINDOWS and HAVE_WINRT:
            await self.scan_paired_windows()  # appends + refreshes

    # ---------- Windows paired enumeration ----------
    def start_scan_paired_windows(self):
        if not (IS_WINDOWS and HAVE_WINRT):
            messagebox.showerror("Unavailable", "Paired scan requires Windows + 'winrt' package.")
            return
        self.run_coro(self.scan_paired_windows())

    async def scan_paired_windows(self):
        added = 0
        # Paired BLE
        try:
            selector = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
            infos = await DeviceInformation.find_all_async(selector)
            for di in infos:
                try:
                    bledev = await BluetoothLEDevice.from_id_async(di.id)
                    addr = self._format_bt_addr_from_ulong(int(bledev.bluetooth_address))
                    name = bledev.name or di.name or "[Unnamed Device]"
                    if any((t == "BLE" and getattr(d, "address", None) == addr) or
                           (t == "Classic" and isinstance(d, dict) and d.get("addr") == addr)
                           for t, d in self.devices):
                        self.ble_meta.setdefault(addr, {})["device_id"] = di.id
                        continue
                    simple = type("SimpleBLEProxy", (), {})()
                    simple.address = addr
                    simple.name = name
                    d_m = self.ble_meta.get(addr, {}).get("distance_m")
                    bucket = self.ble_meta.get(addr, {}).get("range_label")
                    qual = self.ble_meta.get(addr, {}).get("qual")
                    self.devices.append(("BLE", simple))
                    meta = self.ble_meta.setdefault(addr, {})
                    meta.setdefault("name", name)
                    meta["paired"] = True
                    meta["device_id"] = di.id
                    if d_m is not None:
                        meta["distance_m"] = d_m
                        meta["range_label"] = bucket or self._range_bucket(d_m)
                        meta["qual"] = qual or self.dist_filter.quality_grade(addr)
                    self.connection_results[addr] = "Paired"
                    added += 1
                except Exception:
                    pass
        except Exception as e:
            self.log(f"Paired BLE enumeration failed: {e}")

        # Paired Classic
        try:
            selector2 = BluetoothDevice.get_device_selector_from_pairing_state(True)
            infos2 = await DeviceInformation.find_all_async(selector2)
            for di in infos2:
                try:
                    btd = await BluetoothDevice.from_id_async(di.id)
                    addr = self._format_bt_addr_from_ulong(int(btd.bluetooth_address))
                    name = btd.name or di.name or "[Unnamed Device]"
                    if any((t == "BLE" and getattr(d, "address", None) == addr) or
                           (t == "Classic" and isinstance(d, dict) and d.get("addr") == addr)
                           for t, d in self.devices):
                        continue
                    classic_info = {
                        "name": name,
                        "fallback_name": name,
                        "addr": addr,
                        "device_class": 0,
                        "type_str": "Phone",
                        "services": "Paired (Windows)",
                        "device_id": di.id,
                    }
                    self.devices.append(("Classic", classic_info))
                    self.connection_results[addr] = "Paired"
                    added += 1
                except Exception:
                    pass
        except Exception as e:
            self.log(f"Paired Classic enumeration failed: {e}")

        if added:
            self.redraw_device_list(append_only=True)
            self.log(f"Merged {added} paired device(s) from Windows (stable IDs).")
        else:
            self.log("No additional paired devices found via Windows.")

    # ---------- Classic helpers ----------
    def scan_classic_devices(self):
        if not HAVE_PYBLUEZ:
            return []
        self.log("Scanning Classic Bluetooth devices...")
        try:
            classic_devices = bluetooth.discover_devices(
                duration=8, lookup_names=True, lookup_class=True, flush_cache=True
            )
        except Exception as e:
            self.log(f"Classic Bluetooth scan failed: {e}")
            classic_devices = []
        return [(addr, name, device_class) for addr, name, device_class in classic_devices]

    def lookup_device_name(self, addr):
        known_devices = {"44:65:0D": "Apple Device", "00:1A:7D": "Parrot Device"}
        for prefix, nm in known_devices.items():
            if addr.upper().startswith(prefix.upper()):
                return nm
        return "[Unnamed Device]"

    def get_device_type(self, device_class):
        if device_class & 0x1F00 == 0x1000: return "Computer"
        elif device_class & 0x1F00 == 0x2000: return "Phone"
        elif device_class & 0x1F00 == 0x4000: return "Audio/Video"
        elif device_class & 0x1F00 == 0x3000: return "LAN/Network Access Point"
        elif device_class & 0x1F00 == 0x5000: return "Peripheral"
        elif device_class & 0x1F00 == 0x7000: return "Wearable"
        elif device_class & 0x1F00 == 0x8000: return "Imaging"
        elif device_class & 0x1F00 == 0x9000: return "Miscellaneous"
        else: return "Unknown"

    def get_device_services(self, addr):
        if not HAVE_PYBLUEZ:
            return "Unavailable"
        try:
            services = bluetooth.find_service(address=addr)
            if services:
                return ", ".join(srv["name"] for srv in services if srv.get("name"))
            else:
                return "No services found"
        except Exception as e:
            self.log(f"Error retrieving services for {addr}: {e}")
            return "Error retrieving services"

    # ---------- Test / Connect ----------
    def start_test_connection(self):
        self.run_coro(self.test_connection())

    async def test_connection(self):
        idxs = self.device_list.curselection()
        if not idxs:
            self.queue.put(lambda: messagebox.showwarning("No Selection", "Please select a device to test."))
            return
        device_type, device_info = self.devices[idxs[0]]

        if device_type == "BLE":
            result = await self.test_ble_connection(device_info)
            addr_key = device_info.address
        elif device_type == "Classic":
            result = self.test_classic_connection(device_info)
            addr_key = device_info["addr"]
        else:
            result = "N/A"
            addr_key = (device_info.get("bssid") if device_type == "WiFi" else device_info.get("cid"))
        self.connection_results[addr_key] = result
        self.queue.put(lambda i=idxs[0], res=result, dev=device_info, typ=device_type:
                       self.update_device_list_entry(i, res, dev, typ))
        self.log(f"Test connection result: {result}")

    async def test_ble_connection(self, device):
        self.log(f"Testing BLE connection for {getattr(device, 'name', None) or '[Unnamed Device]'} ({device.address})")
        try:
            async with timeout(5):
                async with BleakClient(device.address) as client:
                    if client.is_connected:
                        self.log(f"BLE device {device.address} connected successfully.")
                        return "Auto-connect possible"
                    else:
                        raise BleakError("Failed to auto-connect.")
        except asyncio.TimeoutError:
            self.log(f"BLE connection test timed out for {device.address}.")
            return "Timeout"
        except (BleakError, OSError) as e:
            self.log(f"BLE connection test error for {device.address}: {e}")
            return "Permission or adapter issue"

    def test_classic_connection(self, device):
        if not HAVE_PYBLUEZ:
            return "Classic not available"
        name, addr = device["name"], device["addr"]
        sock = None
        try:
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.settimeout(5)
            sock.connect((addr, 1))
            self.log(f"Classic Bluetooth device {name} ({addr}) connected successfully.")
            return "Auto-connect possible"
        except Exception as e:
            self.log(f"Classic connection test error for {name} ({addr}): {e}")
            return "Permission required"
        finally:
            if sock:
                sock.close()

    def row_text_for_ble(self, device, status):
        addr = device.address
        meta = self.ble_meta.get(addr, {})
        name = meta.get("name") or getattr(device, "name", None) or meta.get("fallback_name") or '[Unnamed Device]'
        rssi = meta.get("rssi", "N/A")
        d_m = meta.get("distance_m", None)
        bucket = meta.get("range_label", "Unknown")
        qual = meta.get("qual", "D")
        dist_str = f"{bucket} ~{d_m:.1f} m" if isinstance(d_m, (int, float)) else bucket
        addr_type = meta.get("addr_type", "Unknown")
        svc_cnt = meta.get("svc_count", 0)
        mfr_ids = meta.get("mfr_ids", [])
        gps_coords = meta.get("gps", "N/A")
        dev_id = meta.get("device_id")
        id_tail = f" | OS Id …{dev_id[-8:]}" if dev_id else ""
        apple_tag = " [Apple]" if ("0x004c" in (mfr_ids or [])) else ""
        # If we have a live estimate, show its speed
        tr = self.tracks.get(addr)
        sp = f" | {tr.get('speed',0.0):.1f} m/s" if tr and tr.get("est") else ""
        return (
            f"BLE: {name}{apple_tag} ({addr}) - {status} - RSSI {rssi} dBm (\n"
            f"  {dist_str}, Q:{qual}){sp} - AddrType {addr_type} - SvcUUIDs {svc_cnt} - "
            f"Mfr {', '.join(mfr_ids) if mfr_ids else '—'} - GPS {gps_coords}{id_tail}"
        )

    def row_text_for_classic(self, info, status):
        name = info["name"]; addr = info["addr"]
        type_str = info.get("type_str", "Unknown")
        services = info.get("services", "No services found")
        dev_id = info.get("device_id")
        id_tail = f" | OS Id …{dev_id[-8:]}" if dev_id else ""
        return f"Classic: {name or '[Unnamed Device]'} ({addr}) - {status} - Distance: Unknown (Classic) - Type: {type_str} - Services: {services}{id_tail}"

    def row_text_for_wifi(self, info, status):
        bssid = info["bssid"]
        meta = self.wifi_meta.get(bssid, {})
        ssid = meta.get("ssid") or info.get("ssid") or "[Hidden SSID]"
        rssi = meta.get("rssi", "N/A")
        d_m = meta.get("distance_m")
        bucket = meta.get("range_label", "Unknown")
        qual = meta.get("qual", "D")
        freq = meta.get("freq_mhz", info.get("freq_mhz", ""))
        chan = meta.get("chan", info.get("chan", ""))
        sec = meta.get("security", info.get("security", ""))
        dist_str = f"{bucket} ~{d_m:.1f} m" if isinstance(d_m, (int, float)) else bucket
        # Speed if tracked
        tr = self.tracks.get(bssid)
        sp = f" | {tr.get('speed',0.0):.1f} m/s" if tr and tr.get("est") else ""
        return (
            f"Wi‑Fi: {ssid} ({bssid}) - {status} - RSSI {rssi} dBm (\n"
            f"  {dist_str}, Q:{qual}){sp} - Freq {freq} MHz ch {chan} - Security {sec}"
        )

    def row_text_for_cell(self, info, status):
        cid = info["cid"]
        meta = self.cell_meta.get(cid, {})
        operator = meta.get("operator") or info.get("operator") or "Unknown operator"
        tech = meta.get("tech") or info.get("tech") or "Unknown RAT"
        pct = meta.get("signal_pct")
        rssi = meta.get("rssi_dbm")
        rsrp = meta.get("rsrp_dbm")
        rsrq = meta.get("rsrq_db")
        sinr = meta.get("sinr_db")
        qual_bucket = meta.get("qual_bucket", "Unknown")
        extra = []
        if pct is not None:  extra.append(f"{pct}%")
        if rssi is not None: extra.append(f"RSSI {rssi} dBm")
        if rsrp is not None: extra.append(f"RSRP {rsrp} dBm")
        if rsrq is not None: extra.append(f"RSRQ {rsrq} dB")
        if sinr is not None: extra.append(f"SINR {sinr} dB")
        extras = " | ".join(extra) if extra else "no metrics"
        return f"Cell: {operator} [{tech}] ({cid}) - {status} - Quality: {qual_bucket}  ({extras})"

    def update_device_list_entry(self, index, result, device, device_type):
        if device_type == "BLE":
            text = self.row_text_for_ble(device, result)
        elif device_type == "Classic":
            text = self.row_text_for_classic(device, result)
        elif device_type == "WiFi":
            text = self.row_text_for_wifi(device, result)
        else:
            text = self.row_text_for_cell(device, result)
        self.device_list.delete(index)
        self.device_list.insert(index, text)

    def start_start_connect(self):
        self.run_coro(self.connect_device())

    async def connect_device(self):
        idxs = self.device_list.curselection()
        if not idxs:
            self.queue.put(lambda: messagebox.showwarning("No Selection", "Please select a device to connect."))
            return
        device_type, device_info = self.devices[idxs[0]]

        if device_type == "BLE":
            await self.connect_ble_device(device_info)
            success = (self.ble_client is not None) and self.ble_client.is_connected
        elif device_type == "Classic":
            self.connected_socket = self.connect_classic_device(device_info)
            success = self.connected_socket is not None
        else:
            success = False  # Wi‑Fi/AP and Cellular aren’t connection targets here

        if success:
            self.queue.put(lambda: messagebox.showinfo("Connection Successful", "Connected successfully."))
            self.log("Device connected successfully.")
        else:
            if device_type == "Classic":
                self.queue.put(lambda: messagebox.showerror("Connection Failed", "Failed to connect to Classic device."))

    async def connect_ble_device(self, device):
        self.log(f"Connecting to BLE device: {getattr(device, 'name', None) or '[Unnamed Device]'} ({device.address})")
        try:
            self.ble_client = BleakClient(device.address)
            await self.ble_client.connect()
            if self.ble_client.is_connected:
                self.log(f"Connected to BLE device: {device.address}")
            else:
                raise BleakError("Failed to connect.")
        except (BleakError, OSError) as e:
            self.log(f"Failed to connect to BLE device: {e}")
            self.queue.put(lambda: messagebox.showerror("Connection Failed", f"Could not connect to {getattr(device, 'name', None) or '[Unnamed Device]'}"))
            self.ble_client = None

    def connect_classic_device(self, device):
        if not HAVE_PYBLUEZ:
            self.log("Classic connect requested but PyBluez is unavailable.")
            return None
        name, addr = device["name"], device["addr"]
        try:
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.connect((addr, 1))
            self.log(f"Connected to Classic device: {name} ({addr})")
            return sock
        except Exception as e:
            self.log(f"Failed to connect to Classic device {name} ({addr}): {e}")
            self.queue.put(lambda: messagebox.showerror("Connection Failed", f"Failed to connect to {name} ({addr})."))
            return None

    def disconnect_device(self):
        if self.connected_socket:
            try:
                self.connected_socket.close()
                self.connected_socket = None
                self.log("Classic device disconnected.")
                self.queue.put(lambda: messagebox.showinfo("Disconnected", "Classic Bluetooth device disconnected."))
            except Exception as e:
                self.log(f"Error disconnecting Classic device: {e}")
        elif self.ble_client:
            fut = self.run_coro(self.ble_client.disconnect())
            def _done(_):
                self.log("BLE device disconnected.")
                self.queue.put(lambda: messagebox.showinfo("Disconnected", "BLE device disconnected."))
            fut.add_done_callback(_done)
            self.ble_client = None
        else:
            self.queue.put(lambda: messagebox.showwarning("No Connection", "No device is connected."))

    # ---------- Relabel / DB actions ----------
    def _selected_addr_and_type(self):
        idxs = self.device_list.curselection()
        if not idxs:
            return None, None, None
        typ, dev = self.devices[idxs[0]]
        if typ == "BLE":
            return typ, dev.address, self.ble_meta.get(dev.address, {}).get("name") or getattr(dev, "name", None)
        elif typ == "Classic":
            return typ, dev["addr"], dev["name"]
        elif typ == "WiFi":
            return typ, dev["bssid"], self.wifi_meta.get(dev["bssid"], {}).get("ssid")
        else:  # Cell
            return typ, dev["cid"], self.cell_meta.get(dev["cid"], {}).get("operator")

    def relabel_selected_device(self):
        typ, addr, cur_name = self._selected_addr_and_type()
        if not addr:
            messagebox.showwarning("No Selection", "Select a device first.")
            return
        existing = self.db_get_label(addr) or (cur_name or "")
        new_label = simpledialog.askstring("Relabel", f"Enter a label for {addr}:", initialvalue=existing)
        if new_label is None:
            return
        new_label = new_label.strip()
        if not new_label:
            messagebox.showwarning("Empty Label", "Please enter a non-empty label.")
            return
        self.db_set_label(addr, new_label)
        # apply to in-memory structures
        for i, (t, d) in enumerate(self.devices):
            if t == "BLE" and d.address == addr:
                if d.address in self.ble_meta:
                    self.ble_meta[d.address]["name"] = new_label
                self.update_device_list_entry(i, self.connection_results.get(addr, "Not Tested"), d, "BLE")
            if t == "Classic" and d["addr"] == addr:
                d["name"] = new_label
                self.update_device_list_entry(i, self.connection_results.get(addr, "Not Tested"), d, "Classic")
            if t == "WiFi" and d.get("bssid") == addr:
                self.wifi_meta.setdefault(addr, {})["ssid"] = new_label
                self.update_device_list_entry(i, self.connection_results.get(addr, "Seen"), d, "WiFi")
            if t == "Cell" and d.get("cid") == addr:
                self.cell_meta.setdefault(addr, {})["operator"] = new_label
                self.update_device_list_entry(i, self.connection_results.get(addr, "Seen"), d, "Cell")
        self.log(f"Labeled {addr} as '{new_label}'")

    def clear_label_selected_device(self):
        typ, addr, _ = self._selected_addr_and_type()
        if not addr:
            messagebox.showwarning("No Selection", "Select a device first.")
            return
        self.db_clear_label(addr)
        # revert to fallback names
        for i, (t, d) in enumerate(self.devices):
            if t == "BLE" and d.address == addr:
                meta = self.ble_meta.get(addr, {})
                if meta:
                    meta["name"] = meta.get("fallback_name") or getattr(d, "name", None) or "[Unnamed Device]"
                self.update_device_list_entry(i, self.connection_results.get(addr, "Not Tested"), d, "BLE")
            if t == "Classic" and d["addr"] == addr:
                d["name"] = d.get("fallback_name") or d["name"]
                self.update_device_list_entry(i, self.connection_results.get(addr, "Not Tested"), d, "Classic")
            if t == "WiFi" and d.get("bssid") == addr:
                self.update_device_list_entry(i, self.connection_results.get(addr, "Seen"), d, "WiFi")
            if t == "Cell" and d.get("cid") == addr:
                self.update_device_list_entry(i, self.connection_results.get(addr, "Seen"), d, "Cell")
        self.log(f"Cleared label for {addr}")

    # ---------- Classic send/receive ----------
    def send_data_to_device(self):
        if self.connected_socket:
            try:
                msg = "Hello from Expanded Python!"
                self.connected_socket.send(msg.encode('utf-8'))
                self.log("Data sent successfully to Classic device.")
                self.queue.put(lambda: messagebox.showinfo("Data Sent", "Data sent successfully."))
            except Exception as e:
                self.log(f"Failed to send data: {e}")
                self.queue.put(lambda: messagebox.showerror("Send Failed", f"Failed to send data: {e}"))
        else:
            if HAVE_PYBLUEZ:
                self.queue.put(lambda: messagebox.showwarning("No Connection", "No Classic Bluetooth device connected."))
            else:
                self.queue.put(lambda: messagebox.showwarning("Unavailable", "Classic Bluetooth not available."))

    def receive_data_from_device(self):
        if self.connected_socket:
            try:
                data = self.connected_socket.recv(1024)
                decoded = data.decode('utf-8', errors='replace')
                self.log(f"Data received: {decoded}")
                self.queue.put(lambda: messagebox.showinfo("Data Received", f"Data received: {decoded}"))
            except Exception as e:
                self.log(f"Failed to receive data: {e}")
                self.queue.put(lambda: messagebox.showerror("Receive Failed", f"Failed to receive data: {e}"))
        else:
            if HAVE_PYBLUEZ:
                self.queue.put(lambda: messagebox.showwarning("No Connection", "No Classic Bluetooth device connected."))
            else:
                self.queue.put(lambda: messagebox.showwarning("Unavailable", "Classic Bluetooth not available."))

    # ---------- Advertising (Classic) ----------
    def start_advertising(self):
        threading.Thread(target=self.advertise_service, daemon=True).start()

    def advertise_service(self):
        if not HAVE_PYBLUEZ:
            self.queue.put(lambda: messagebox.showerror("Advertising Error", "PyBluez not available."))
            return
        if IS_WINDOWS:
            self.queue.put(lambda: messagebox.showerror("Advertising Error", "Classic advertising not supported on Windows."))
            return
        service_name = "Bullish"
        try:
            self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.server_sock.bind(("", bluetooth.PORT_ANY))
            self.server_sock.listen(1)
            port = self.server_sock.getsockname()[1]
            bluetooth.advertise_service(self.server_sock, service_name,
                service_classes=[bluetooth.SERIAL_PORT_CLASS],
                profiles=[bluetooth.SERIAL_PORT_PROFILE])
            self.log(f"Advertising service '{service_name}' on port {port}")
            while True:
                try:
                    client_sock, address = self.server_sock.accept()
                    self.log(f"Incoming connection request from {address}")
                    self.queue.put(lambda sock=client_sock, addr=address: self.prompt_user_for_connection(sock, addr))
                except Exception as e:
                    self.log(f"Error accepting connection: {e}")
                    break
        except Exception as e:
            self.log(f"Error during advertising: {e}")
            self.queue.put(lambda: messagebox.showerror("Advertising Error", f"Error during advertising: {e}"))
        finally:
            if self.server_sock:
                self.server_sock.close()
                self.server_sock = None

    def prompt_user_for_connection(self, client_sock, address):
        response = messagebox.askyesno("Connection Request", f"Accept connection from {address}?")
        if response:
            threading.Thread(target=self.handle_client, args=(client_sock, address), daemon=True).start()
        else:
            client_sock.close()

    def handle_client(self, client_sock, address):
        self.log(f"Handling client at {address}")
        try:
            while True:
                data = client_sock.recv(1024)
                if data:
                    decoded = data.decode('utf-8', errors='replace')
                    self.log(f"Received from {address}: {decoded}")
                    response = f"Echo: {decoded}"
                    client_sock.send(response.encode('utf-8'))
                else:
                    self.log(f"No more data from {address}, closing connection.")
                    break
        except Exception as e:
            self.log(f"Client {address} disconnected with error: {e}")
        finally:
            client_sock.close()

    # ---------- BLE Explorer ----------
    def start_explore_ble(self):
        if not self.ble_client or not self.ble_client.is_connected:
            messagebox.showwarning("Not Connected", "Connect to a BLE device first.")
            return
        if self.explorer_win and tk.Toplevel.winfo_exists(self.explorer_win):
            self.explorer_win.lift()
            return
        self.explorer_win = tk.Toplevel(self.root)
        self.explorer_win.title("BLE Explorer – Services & Characteristics")
        self.explorer_text = scrolledtext.ScrolledText(self.explorer_win, width=120, height=30, state="normal")
        self.explorer_text.pack(padx=8, pady=8)
        btn_frame = tk.Frame(self.explorer_win)
        btn_frame.pack(pady=(0, 8))
        tk.Button(btn_frame, text="Refresh Services", command=lambda: self.run_coro(self.populate_ble_services())).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Read All Readable", command=lambda: self.run_coro(self.read_all_readable())).pack(side="left", padx=6)
        self.run_coro(self.populate_ble_services())

    async def populate_ble_services(self):
        try:
            services = await self.ble_client.get_services()
            self.last_services = services
            lines = []
            for svc in services:
                lines.append(f"SERVICE {svc.uuid}  ({svc.description})")
                for ch in svc.characteristics:
                    props = ",".join(sorted(ch.properties))
                    lines.append(f"  CHAR {ch.uuid} [{props}]  ({ch.description})")
                    for d in ch.descriptors:
                        lines.append(f"    DESC {d.uuid} ({d.description})")
            text = "\n".join(lines) if lines else "No services."
            self.queue.put(lambda t=text: self._set_explorer_text(t))
        except Exception as e:
            self.queue.put(lambda: self._set_explorer_text(f"Error reading services: {e}"))

    async def read_all_readable(self):
        if not self.last_services:
            await self.populate_ble_services()
            if not self.last_services:
                return
        out_lines = ["Reading all readable characteristics..."]
        for svc in self.last_services:
            out_lines.append(f"SERVICE {svc.uuid}")
            for ch in svc.characteristics:
                if "read" in ch.properties:
                    try:
                        data = await self.ble_client.read_gatt_char(ch.uuid)
                        hx = binascii.hexlify(data).decode("ascii")
                        try:
                            txt = data.decode("utf-8")
                            safe_txt = txt if all(32 <= ord(c) <= 126 or c in "\r\n\t" for c in txt) else "<non-printable>"
                        except Exception:
                            safe_txt = "<non-utf8>"
                        out_lines.append(f"  CHAR {ch.uuid} -> 0x{hx}   text: {safe_txt}")
                    except Exception as e:
                        out_lines.append(f"  CHAR {ch.uuid} -> <read error: {e}>")
                else:
                    out_lines.append(f"  CHAR {ch.uuid} [not readable]")
        self.queue.put(lambda t="\n".join(out_lines): self._append_explorer_text(t + "\n"))

    def _set_explorer_text(self, text):
        if not self.explorer_text:
            return
        self.explorer_text.configure(state="normal")
        self.explorer_text.delete("1.0", tk.END)
        self.explorer_text.insert(tk.END, text)
        self.explorer_text.configure(state="normal")

    def _append_explorer_text(self, text):
        if not self.explorer_text:
            return
        self.explorer_text.configure(state="normal")
        self.explorer_text.insert(tk.END, text)
        self.explorer_text.see(tk.END)
        self.explorer_text.configure(state="normal")

    # ---------- Tuning ----------
    def apply_tuning(self):
        try:
            tx = float(self.tx_power_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Input", "Tx Power must be a number (e.g., -59).")
            return
        try:
            n = float(self.n_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Input", "Environment n must be a number (e.g., 2.0).")
            return
        if not (1.5 <= n <= 4.0):
            messagebox.showwarning("Adjusted", "Environment n will be clamped to 1.5–4.0.")
            n = max(1.5, min(4.0, n))
        self.tx_power_1m_default = tx
        self.path_loss_n = n
        self.log(f"Applied tuning: TxPower@1m={tx} dBm, n={n}")
        self.redraw_device_list()

    # ---------- Rendering ----------
    def redraw_device_list(self, append_only=False):
        if not append_only:
            self.device_list.delete(0, tk.END)
        for device_type, dev in self.devices:
            if device_type == "BLE":
                status = self.connection_results.get(dev.address, "Not Tested")
                text = self.row_text_for_ble(dev, status)
                addr = dev.address
            elif device_type == "WiFi":
                status = self.connection_results.get(dev["bssid"], "Seen")
                text = self.row_text_for_wifi(dev, status)
                addr = dev["bssid"]
            elif device_type == "Cell":
                status = self.connection_results.get(dev["cid"], "Seen")
                text = self.row_text_for_cell(dev, status)
                addr = dev["cid"]
            else:
                status = self.connection_results.get(dev["addr"], "Not Tested")
                text = self.row_text_for_classic(dev, status)
                addr = dev["addr"]
            if append_only:
                exists = any(addr in self.device_list.get(i) for i in range(self.device_list.size()))
                if exists:
                    continue
            self.device_list.insert(tk.END, text)

    # ---------- OBEX (Classic) File Browser ----------
    def open_obex_browser(self):
        if not (HAVE_PYBLUEZ and HAVE_PYOBEX):
            messagebox.showerror("OBEX Unavailable", "PyBluez and PyOBEX are required for OBEX browsing.")
            return
        idxs = self.device_list.curselection()
        if not idxs:
            messagebox.showwarning("No Selection", "Select a Classic Bluetooth device first.")
            return
        dev_type, info = self.devices[idxs[0]]
        if dev_type != "Classic":
            messagebox.showwarning("Wrong Type", "OBEX browsing is for Classic Bluetooth devices.")
            return
        addr = info["addr"]
        svc = self.find_obex_ftp_service(addr)
        if not svc:
            messagebox.showerror("OBEX FTP Not Found", "The selected device does not advertise OBEX File Transfer.")
            return
        port = svc["port"]

        if self.obex["win"] and tk.Toplevel.winfo_exists(self.obex["win"]):
            try:
                if self.obex["client"]:
                    self.obex["client"].disconnect()
            except Exception:
                pass
            self.obex["win"].destroy()

        top = tk.Toplevel(self.root)
        top.title(f"OBEX Browser – {info['name']} ({addr})")
        path_var = tk.StringVar(value="/")

        path_row = tk.Frame(top); path_row.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(path_row, text="Path:").pack(side="left")
        tk.Entry(path_row, textvariable=path_var, width=80, state="readonly").pack(side="left", padx=6)

        btn_row = tk.Frame(top); btn_row.pack(fill="x", padx=8, pady=8)
        tk.Button(btn_row, text="Refresh", command=lambda: self._obex_thread(self.obex_refresh)).pack(side="left", padx=4)
        tk.Button(btn_row, text="Enter", command=lambda: self._obex_thread(self.obex_enter)).pack(side="left", padx=4)
        tk.Button(btn_row, text="Up", command=lambda: self._obex_thread(self.obex_up)).pack(side="left", padx=4)
        tk.Button(btn_row, text="Download", command=lambda: self._obex_thread(self.obex_download)).pack(side="left", padx=4)
        tk.Button(btn_row, text="Upload", command=lambda: self._obex_thread(self.obex_upload)).pack(side="left", padx=4)
        tk.Button(btn_row, text="Disconnect", command=lambda: self._obex_thread(self.obex_disconnect)).pack(side="left", padx=4)

        lb = tk.Listbox(top, width=100, height=24); lb.pack(padx=8, pady=(0, 8), fill="both", expand=True)

        self.obex.update({"win": top, "list": lb, "path_var": path_var, "client": None, "addr": addr, "port": port, "items": []})
        self._obex_thread(self._obex_connect_and_load)

    def _obex_thread(self, target):
        threading.Thread(target=target, daemon=True).start()

    def _obex_connect_and_load(self):
        addr = self.obex.get("addr")
        port = self.obex.get("port")
        try:
            self.log(f"Connecting OBEX FTP to {addr}:{port} ...")
            client = FTPClient(addr, port)
            client.connect()
            self.obex["client"] = client
            try:
                if hasattr(client, "setpath"):
                    client.setpath(b"/")
            except Exception:
                pass
            self._obex_listdir()
        except Exception as e:
            self.log(f"OBEX connect failed: {e}")
            self.queue.put(lambda: messagebox.showerror("OBEX Connect Failed", f"{e}"))

    def find_obex_ftp_service(self, addr):
        try:
            services = bluetooth.find_service(address=addr)
        except Exception:
            services = []
        chosen = None
        for s in services or []:
            name = (s.get("name") or "").lower()
            classes = [c.lower() for c in (s.get("service-classes") or [])]
            profiles = [p[0].lower() if isinstance(p, (list, tuple)) else str(p).lower() for p in (s.get("profiles") or [])]
            uuid_match = (OBEX_FTP_UUID.lower() in classes) or any(OBEX_FTP_UUID.lower() in p for p in profiles)
            if "obex file transfer" in name or uuid_match:
                chosen = s; break
        return chosen

    def _obex_listdir(self):
        client = self.obex.get("client"); lb = self.obex.get("list")
        if not client or not lb:
            return
        try:
            listing = None
            if hasattr(client, "listdir"):
                listing = client.listdir()
            elif hasattr(client, "list_dir"):
                listing = client.list_dir()
            items = self._parse_folder_listing(listing)
            self.queue.put(lambda: self._obex_render_items(items))
        except Exception as e:
            self.log(f"OBEX list error: {e}")
            self.queue.put(lambda: messagebox.showerror("OBEX Error", f"List directory failed: {e}"))

    def _parse_folder_listing(self, listing):
        """Parse OBEX XML folder listing into a list of dicts."""
        if listing is None:
            return []
        if isinstance(listing, (bytes, bytearray)):
            try:
                txt = listing.decode("utf-8", errors="ignore")
            except Exception:
                txt = str(listing)
        else:
            txt = str(listing)
        txt = txt.strip()
        # Simple fallback
        if not txt.startswith("<?xml") and "<folder-listing" not in txt:
            items = []
            for line in [l.strip() for l in txt.splitlines() if l.strip()]:
                items.append({"name": line, "is_dir": False, "size": 0})
            return items
        try:
            root = ET.fromstring(txt)
            out = []
            for child in root:
                tag = child.tag.lower()
                if tag.endswith("folder"):
                    out.append({"name": child.attrib.get("name", ""), "is_dir": True, "size": 0})
                elif tag.endswith("file"):
                    size = int(child.attrib.get("size", "0")) if child.attrib.get("size") else 0
                    out.append({"name": child.attrib.get("name", ""), "is_dir": False, "size": size})
            return out
        except Exception:
            lines = [l.strip() for l in re.split(r"[<>]", txt) if l and "name=" in l]
            out = []
            for ln in lines:
                m = re.search(r'name="([^"]+)"', ln)
                name = m.group(1) if m else "unknown"
                out.append({"name": name, "is_dir": ("folder" in ln.lower()), "size": 0})
            return out

    def _obex_render_items(self, items):
        self.obex["items"] = items or []
        lb = self.obex.get("list")
        if not lb:
            return
        lb.delete(0, tk.END)
        for it in self.obex["items"]:
            label = f"[DIR] {it['name']}" if it["is_dir"] else f"{it['name']} ({it['size']} bytes)"
            lb.insert(tk.END, label)

    # OBEX actions
    def obex_refresh(self):
        self._obex_listdir()

    def obex_enter(self):
        client = self.obex.get("client")
        lb = self.obex.get("list")
        if not client or not lb:
            return
        idx = lb.curselection()
        if not idx:
            self.queue.put(lambda: messagebox.showwarning("No Selection", "Select a folder or file."))
            return
        item = self.obex["items"][idx[0]]
        try:
            if item["is_dir"]:
                name = item["name"].encode("utf-8", errors="ignore")
                if hasattr(client, "setpath"):
                    client.setpath(name)
                self._obex_listdir()
                pv = self.obex.get("path_var")
                if pv:
                    cur = pv.get()
                    pv.set(os.path.join(cur, item["name"]).replace("\\", "/"))
            else:
                self.obex_download()
        except Exception as e:
            self.log(f"OBEX enter error: {e}")
            self.queue.put(lambda: messagebox.showerror("OBEX Error", f"Enter failed: {e}"))

    def obex_up(self):
        client = self.obex.get("client")
        if not client:
            return
        try:
            if hasattr(client, "setpath"):
                client.setpath(b"..")
            self._obex_listdir()
            pv = self.obex.get("path_var")
            if pv:
                cur = pv.get()
                parent = os.path.dirname(cur.rstrip("/")) or "/"
                pv.set(parent)
        except Exception as e:
            self.log(f"OBEX up error: {e}")
            self.queue.put(lambda: messagebox.showerror("OBEX Error", f"Up failed: {e}"))

    def obex_download(self):
        client = self.obex.get("client"); lb = self.obex.get("list")
        if not client or not lb:
            return
        idx = lb.curselection()
        if not idx:
            self.queue.put(lambda: messagebox.showwarning("No Selection", "Select a file to download."))
            return
        item = self.obex["items"][idx[0]]
        if item["is_dir"]:
            self.queue.put(lambda: messagebox.showwarning("Folder Selected", "Pick a file to download."))
            return
        dest = filedialog.asksaveasfilename(initialfile=item["name"])
        if not dest:
            return
        try:
            data = None
            if hasattr(client, "getfile"):
                data = client.getfile(item["name"])
            else:
                resp = client.get(name=item["name"].encode("utf-8", errors="ignore"))
                if isinstance(resp, tuple) and len(resp) == 3:
                    data = resp[2]
                elif hasattr(resp, "body"):
                    data = resp.body
            if data is None:
                raise RuntimeError("Empty response")
            with open(dest, "wb") as f:
                f.write(data)
            self.log(f"Downloaded {item['name']} -> {dest}")
            self.queue.put(lambda: messagebox.showinfo("Downloaded", f"Saved to:\n{dest}"))
        except Exception as e:
            self.log(f"OBEX download error: {e}")
            self.queue.put(lambda: messagebox.showerror("OBEX Error", f"Download failed: {e}"))

    def obex_upload(self):
        client = self.obex.get("client")
        if not client:
            return
        src = filedialog.askopenfilename()
        if not src:
            return
        try:
            name = os.path.basename(src).encode("utf-8", errors="ignore")
            with open(src, "rb") as f:
                data = f.read()
            if hasattr(client, "putfile"):
                client.putfile(name, data)
            else:
                client.put(name=name, data=data)
            self.log(f"Uploaded {src}")
            self.queue.put(lambda: messagebox.showinfo("Uploaded", f"Uploaded:\n{src}"))
            self._obex_listdir()
        except Exception as e:
            self.log(f"OBEX upload error: {e}")
            self.queue.put(lambda: messagebox.showerror("OBEX Error", f"Upload failed: {e}"))

    def obex_disconnect(self):
        client = self.obex.get("client")
        if not client:
            return
        try:
            client.disconnect()
            self.obex["client"] = None
            self.log("OBEX disconnected.")
            self.queue.put(lambda: messagebox.showinfo("Disconnected", "OBEX disconnected."))
        except Exception as e:
            self.log(f"OBEX disconnect error: {e}")

    # ---------- Contacts (PBAP / FTP fallback) ----------
    def open_contacts_browser(self):
        if not (HAVE_PYBLUEZ and HAVE_PYOBEX):
            messagebox.showerror("Contacts Unavailable", "PyBluez and PyOBEX are required for PBAP/FTP contacts.")
            return
        idxs = self.device_list.curselection()
        if not idxs:
            messagebox.showwarning("No Selection", "Select a Classic Bluetooth phone first.")
            return
        dev_type, info = self.devices[idxs[0]]
        if dev_type != "Classic":
            messagebox.showwarning("Wrong Type", "Contacts are fetched over Classic PBAP/FTP.")
            return

        if self.contacts["win"] and tk.Toplevel.winfo_exists(self.contacts["win"]):
            self.contacts["win"].destroy()

        top = tk.Toplevel(self.root)
        top.title(f"Contacts – {info['name']} ({info['addr']})")
        btn_row = tk.Frame(top); btn_row.pack(fill="x", padx=8, pady=8)
        tk.Button(btn_row, text="Fetch via PBAP", command=lambda: threading.Thread(target=self._fetch_contacts_pbap, args=(info["addr"],), daemon=True).start()).pack(side="left", padx=6)
        tk.Button(btn_row, text="Fetch via FTP Fallback", command=lambda: threading.Thread(target=self._fetch_contacts_ftp, args=(info["addr"],), daemon=True).start()).pack(side="left", padx=6)
        tk.Button(btn_row, text="Save CSV", command=self._save_contacts_csv).pack(side="left", padx=6)

        lb = tk.Listbox(top, width=100, height=24); lb.pack(padx=8, pady=(0, 8), fill="both", expand=True)
        log = scrolledtext.ScrolledText(top, width=100, height=6, state="disabled"); log.pack(padx=8, pady=(0, 8))

        self.contacts.update({"win": top, "list": lb, "log": log, "data": []})

    def _contacts_log(self, msg):
        log = self.contacts.get("log")
        if not log: return
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        log.configure(state="normal")
        log.insert(tk.END, f"[{ts}] {msg}\n")
        log.see(tk.END)
        log.configure(state="disabled")

    def _fetch_contacts_pbap(self, addr):
        if not (HAVE_PYBLUEZ and HAVE_PYOBEX):
            self._contacts_log("PBAP not available.")
            return
        self._contacts_log("Trying PBAP (Phone Book Access Profile)...")
        try:
            port = self._find_service_port(addr, PBAP_PSE_UUID)
            if not port:
                self._contacts_log("PBAP service not found on device.")
                return
            client = OBEXClient(addr, port)
            try:
                client.connect([OBEX_HEADERS.Target(PBAP_TARGET_UUID_BYTES)])
            except Exception:
                client.connect()
            headers = [OBEX_HEADERS.Type(b"x-bt/phonebook")]
            resp = client.get(name=b"telecom/pb.vcf", headers=headers)
            data = None
            if isinstance(resp, tuple) and len(resp) == 3:
                data = resp[2]
            elif hasattr(resp, "body"):
                data = resp.body
            client.disconnect()
            if not data:
                self._contacts_log("PBAP returned no data.")
                return
            self._contacts_from_vcf_bytes(data, source="PBAP")
        except Exception as e:
            self._contacts_log(f"PBAP failed: {e}")

    def _fetch_contacts_ftp(self, addr):
        if not (HAVE_PYBLUEZ and HAVE_PYOBEX):
            self._contacts_log("OBEX FTP not available.")
            return
        self._contacts_log("Trying OBEX FTP fallback (telecom/pb.vcf)...")
        try:
            svc = self.find_obex_ftp_service(addr)
            if not svc:
                self._contacts_log("OBEX FTP service not found on device.")
                return
            port = svc["port"]
            ftp = FTPClient(addr, port); ftp.connect()
            try:
                if hasattr(ftp, "setpath"):
                    ftp.setpath(b"/"); ftp.setpath(b"telecom")
            except Exception:
                pass
            vcf_bytes = None
            try:
                if hasattr(ftp, "getfile"):
                    vcf_bytes = ftp.getfile("pb.vcf")
                else:
                    resp = ftp.get(name=b"pb.vcf")
                    if isinstance(resp, tuple) and len(resp) == 3:
                        vcf_bytes = resp[2]
                    elif hasattr(resp, "body"):
                        vcf_bytes = resp.body
            except Exception as e:
                self._contacts_log(f"FTP get pb.vcf failed: {e}")
            ftp.disconnect()
            if not vcf_bytes:
                self._contacts_log("No pb.vcf found via FTP.")
                return
            self._contacts_from_vcf_bytes(vcf_bytes, source="FTP")
        except Exception as e:
            self._contacts_log(f"FTP fallback failed: {e}")

    def _contacts_from_vcf_bytes(self, data, source=""):
        try:
            contacts = self._parse_vcards(data)
            self.contacts["data"] = contacts
            lb = self.contacts.get("list")
            if lb:
                lb.delete(0, tk.END)
                for c in contacts:
                    nums = ", ".join(c.get("phones", [])) if c.get("phones") else "-"
                    lb.insert(tk.END, f"{c.get('name','(no name)')}  |  {nums}")
            self._contacts_log(f"Loaded {len(contacts)} contact(s) from {source}.")
        except Exception as e:
            self._contacts_log(f"Failed to parse vCard: {e}")

    def _save_contacts_csv(self):
        if not self.contacts.get("data"):
            self._contacts_log("No contacts to save.")
            return
        dest = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not dest:
            return
        try:
            with open(dest, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Name", "Phone(s)"])
                for c in self.contacts["data"]:
                    w.writerow([c.get("name",""), "; ".join(c.get("phones", []))])
            self._contacts_log(f"Saved CSV to {dest}")
        except Exception as e:
            self._contacts_log(f"CSV save failed: {e}")

    def _parse_vcards(self, vcf_bytes):
        """Minimal vCard parser for names and telephone numbers."""
        if not isinstance(vcf_bytes, (bytes, bytearray)):
            vcf_bytes = bytes(vcf_bytes or b"")
        text = vcf_bytes.decode("utf-8", errors="ignore")
        # Unfold continuations
        lines = []
        for ln in text.splitlines():
            if ln.startswith((" ", "\t")) and lines:
                lines[-1] += ln[1:]
            else:
                lines.append(ln)
        cards, cur = [], []
        for ln in lines:
            if ln.upper().startswith("BEGIN:VCARD"):
                cur = []
            cur.append(ln)
            if ln.upper().startswith("END:VCARD"):
                cards.append("\n".join(cur)); cur = []
        out = []
        for card in cards:
            name = ""
            phones = []
            for ln in card.splitlines():
                up = ln.upper()
                if up.startswith("FN:"):
                    name = ln[3:].strip()
                elif up.startswith("N:") and not name:
                    parts = ln[2:].split(";")
                    given = parts[1].strip() if len(parts) > 1 else ""
                    family = parts[0].strip()
                    cand = " ".join(p for p in [given, family] if p)
                    if cand:
                        name = cand
                elif up.startswith("TEL"):
                    m = re.search(r"TEL[^:]*:(.+)$", ln, flags=re.IGNORECASE)
                    if m:
                        num = m.group(1).strip()
                        num = re.sub(r"[^\d+]+", " ", num).strip()
                        if num:
                            phones.append(num)
            if name or phones:
                out.append({"name": name or "(no name)", "phones": phones})
        return out

    def _find_service_port(self, addr, uuid_str):
        try:
            services = bluetooth.find_service(address=addr, uuid=uuid_str)
            if services:
                return services[0].get("port")
        except Exception:
            return None
        return None

    # ============ 3D Seeds Map ============
    def open_map3d_popup(self):
        if self.map3d["win"] and tk.Toplevel.winfo_exists(self.map3d["win"]):
            self.map3d["win"].lift()
            return

        win = tk.Toplevel(self.root)
        win.title("3D Map – Radios (direction from ID, depth from distance)")

        # Controls row
        ctrl = tk.Frame(win); ctrl.pack(fill="x", padx=8, pady=6)
        self.map3d["animate_var"] = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Seeds Mode (grow)", variable=self.map3d["animate_var"],
                       command=self._toggle_seed_animation).pack(side="left", padx=6)

        # Satellite overlay toggle
        self.map3d["sat_overlay_var"] = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Overlay Satellite (3D)",
                       variable=self.map3d["sat_overlay_var"],
                       command=self._toggle_sat_overlay).pack(side="left", padx=6)
        tk.Button(ctrl, text="Set GPS…", command=self.prompt_set_gps_coordinates).pack(side="left", padx=6)
        tk.Button(ctrl, text="Refresh From Scan", command=self._render_map3d).pack(side="left", padx=6)
        tk.Button(ctrl, text="Close", command=lambda: self._close_map3d()).pack(side="right", padx=6)

        # Status label
        self.map3d["sat_status"] = tk.StringVar(value="")
        tk.Label(win, textvariable=self.map3d["sat_status"]).pack(anchor="w", padx=10)

        # Figure
        fig = Figure(figsize=(8.8, 6.2))
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Depth (m)")  # z = -distance
        ax.set_title("Radios as trees (direction from ID, depth from distance)")

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        # Scroll zoom binding
        if self.map3d["cid_scroll"] is not None:
            try:
                fig.canvas.mpl_disconnect(self.map3d["cid_scroll"])
            except Exception:
                pass
        cid = fig.canvas.mpl_connect('scroll_event', self._on_map3d_scroll)
        self.map3d["cid_scroll"] = cid

        self.map3d.update({"win": win, "fig": fig, "ax": ax, "canvas": canvas,
                           "trees": [], "targets": [], "bases": [], "labels": []})
        self._render_map3d()

    def _close_map3d(self):
        self._stop_seed_animation()
        if self.map3d["win"] and tk.Toplevel.winfo_exists(self.map3d["win"]):
            self.map3d["win"].destroy()
        self.map3d["win"] = None

    def _toggle_seed_animation(self):
        on = bool(self.map3d["animate_var"].get())
        if on:
            self._start_seed_animation()
        else:
            self._stop_seed_animation()

    def _start_seed_animation(self):
        if self.map3d["anim_on"]:
            return
        self.map3d["anim_on"] = True
        self._seed_anim_tick()

    def _stop_seed_animation(self):
        self.map3d["anim_on"] = False
        if self.map3d["timer"] is not None:
            try:
                self.root.after_cancel(self.map3d["timer"])
            except Exception:
                pass
            self.map3d["timer"] = None

    def _seed_anim_tick(self):
        if not self.map3d["anim_on"]:
            return
        updated = False
        for i, line in enumerate(self.map3d["trees"]):
            x0, y0, z0 = self.map3d["bases"][i]
            _, _, z1 = line.get_data_3d()
            current_top = z1[-1]
            target = self.map3d["targets"][i]
            step = self.map3d["growth_rate"]
            if current_top < target:
                new_top = min(target, current_top + step)
                line.set_data_3d([x0, x0], [y0, y0], [z0, new_top])
                updated = True
        if updated and self.map3d["canvas"]:
            self.map3d["canvas"].draw_idle()
        self.map3d["timer"] = self.root.after(50, self._seed_anim_tick)

    def _on_map3d_scroll(self, event):
        """Mouse wheel zoom (uniform) around current axes center."""
        if not (self.map3d["ax"] and self.map3d["canvas"]):
            return
        ax = self.map3d["ax"]
        try:
            factor = 1.1 if (getattr(event, "button", "") == "up" or getattr(event, "step", 0) > 0) else 0.9
            def _scale(lims, f):
                c = (lims[0] + lims[1]) / 2.0
                r = (lims[1] - lims[0]) / 2.0
                r *= f
                return c - r, c + r
            ax.set_xlim(_scale(ax.get_xlim(), factor))
            ax.set_ylim(_scale(ax.get_ylim(), factor))
            ax.set_zlim(_scale(ax.get_zlim(), factor))
            self.map3d["canvas"].draw_idle()
        except Exception:
            pass

    def _angle_for_addr(self, addr: str) -> float:
        """Stable pseudo-direction from an ID. Returns radians [0, 2π)."""
        try:
            h = int(hashlib.sha1(addr.encode("utf-8")).hexdigest()[:8], 16)
        except Exception:
            h = abs(hash(addr))
        deg = h % 360
        return math.radians(deg)

    def _collect_positions(self):
        """Return seeds with approx position and target heights."""
        seeds = []
        # BLE
        for typ, dev in self.devices:
            if typ != "BLE": continue
            addr = dev.address
            meta = self.ble_meta.get(addr, {})
            name = (meta.get("name") or getattr(dev, "name", None) or meta.get("fallback_name") or "[Unnamed Device]").strip()
            # prefer tracked (x,y)
            tr = self.tracks.get(addr)
            if tr and tr.get("est"):
                x = tr["est"]["x"]; y = tr["est"]["y"]; d_m = math.hypot(x, y)
            else:
                d_m = meta.get("distance_m", None)
                if not isinstance(d_m, (int, float)) or d_m <= 0:
                    continue
                theta = self._angle_for_addr(addr)
                r = d_m * self.map3d["radial_scale"]
                x = r * math.cos(theta); y = r * math.sin(theta)
            z = - (meta.get("distance_m") if isinstance(meta.get("distance_m"), (int, float)) else math.hypot(x, y))
            target_height = max(0.5, 5.0 - 0.3 * max(0.1, math.hypot(x, y)))
            seeds.append({"type": "BLE", "name": name, "addr": addr, "x": x, "y": y, "z": z, "target": z + target_height})
        # Classic
        for typ, dev in self.devices:
            if typ != "Classic": continue
            addr = dev["addr"]; name = dev["name"]
            dist = self.map3d["classic_default_dist"]
            theta = self._angle_for_addr(addr)
            r = dist * self.map3d["radial_scale"]
            x = r * math.cos(theta); y = r * math.sin(theta); z = -dist
            target_height = max(0.5, 5.0 - 0.3 * dist)
            seeds.append({"type": "Classic", "name": name, "addr": addr, "x": x, "y": y, "z": z, "target": z + target_height})
        # Wi‑Fi
        for typ, dev in self.devices:
            if typ != "WiFi": continue
            bssid = dev["bssid"]
            meta = self.wifi_meta.get(bssid, {})
            ssid = meta.get("ssid") or dev.get("ssid") or "[Hidden SSID]"
            tr = self.tracks.get(bssid)
            if tr and tr.get("est"):
                x = tr["est"]["x"]; y = tr["est"]["y"]; d_m = math.hypot(x, y)
            else:
                d_m = meta.get("distance_m")
                if not isinstance(d_m, (int, float)) or d_m <= 0:
                    d_m = self.map3d["wifi_default_dist"]
                theta = self._angle_for_addr(bssid)
                r = d_m * self.map3d["radial_scale"]
                x = r * math.cos(theta); y = r * math.sin(theta)
            z = -d_m
            target_height = max(0.5, 5.0 - 0.3 * d_m)
            seeds.append({"type": "WiFi", "name": ssid, "addr": bssid, "x": x, "y": y, "z": z, "target": z + target_height})
        # Cellular
        for typ, dev in self.devices:
            if typ != "Cell": continue
            cid = dev["cid"]
            meta = self.cell_meta.get(cid, {})
            label = f"{meta.get('operator','Cell')}-{meta.get('tech','')}".strip("-")
            d_m = self.map3d["cell_default_dist"]
            theta = self._angle_for_addr(cid)
            r = d_m * self.map3d["radial_scale"]
            x = r * math.cos(theta); y = r * math.sin(theta); z = -d_m
            target_height = max(0.5, 5.0 - 0.3 * d_m)
            seeds.append({"type": "Cell", "name": label, "addr": cid, "x": x, "y": y, "z": z, "target": z + target_height})
        return seeds

    def _render_map3d(self):
        if not self.map3d["win"] or not tk.Toplevel.winfo_exists(self.map3d["win"]):
            return
        ax = self.map3d["ax"]; canvas = self.map3d["canvas"]
        old_xlim = ax.get_xlim(); old_ylim = ax.get_ylim(); old_zlim = ax.get_zlim()

        ax.clear()
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Depth (m)")
        ax.set_title("Radios as trees (direction from ID, depth from distance)")

        # Optional satellite overlay plane
        if self.map3d["sat_overlay_var"] and self.map3d["sat_overlay_var"].get():
            ok = self._ensure_sat_overlay_loaded()
            if ok and self.map3d["overlay_img"] is not None and self.map3d["overlay_extent"] is not None:
                try:
                    self._draw_overlay_plane(ax, self.map3d["overlay_img"], self.map3d["overlay_extent"], z=-0.2, alpha=0.9)
                except Exception as e:
                    self.log(f"Overlay draw error: {e}")

        seeds = self._collect_positions()

        ax.plot([0], [0], [0], marker="o", markersize=5, color="k")
        ax.text(0, 0, 0, "Origin", fontsize=8)

        self.map3d["trees"].clear(); self.map3d["targets"].clear()
        self.map3d["bases"].clear(); self.map3d["labels"].clear()

        xs_ble, ys_ble, zs_ble = [], [], []
        xs_cla, ys_cla, zs_cla = [], [], []
        xs_wifi, ys_wifi, zs_wifi = [], [], []
        xs_cell, ys_cell, zs_cell = [], [], []

        for s in seeds:
            x, y, z = s["x"], s["y"], s["z"]
            if s["type"] == "BLE":
                xs_ble.append(x); ys_ble.append(y); zs_ble.append(z); color = "#2e7d32"
            elif s["type"] == "WiFi":
                xs_wifi.append(x); ys_wifi.append(y); zs_wifi.append(z); color = "#8e24aa"
            elif s["type"] == "Cell":
                xs_cell.append(x); ys_cell.append(y); zs_cell.append(z); color = "#c62828"
            else:
                xs_cla.append(x); ys_cla.append(y); zs_cla.append(z); color = "#1565c0"

            line, = ax.plot([x, x], [y, y], [z, z], linewidth=3, color=color)
            self.map3d["trees"].append(line)
            self.map3d["targets"].append(s["target"])
            self.map3d["bases"].append((x, y, z))
            lbl = ax.text(x, y, z, f"{s['name']}\n{s['addr']}", fontsize=7)
            self.map3d["labels"].append(lbl)

        if xs_ble:  ax.scatter(xs_ble, ys_ble, zs_ble, s=30, marker="o", color="#66bb6a", label="BLE")
        if xs_wifi: ax.scatter(xs_wifi, ys_wifi, zs_wifi, s=30, marker="s", color="#ba68c8", label="Wi‑Fi")
        if xs_cell: ax.scatter(xs_cell, ys_cell, zs_cell, s=30, marker="x", color="#ef5350", label="Cellular")
        if xs_cla:  ax.scatter(xs_cla, ys_cla, zs_cla, s=30, marker="^", color="#64b5f6", label="Classic")

        # Default bounds: include overlay extent if present
        all_x = (xs_ble + xs_cla + xs_wifi + xs_cell) or [0]
        all_y = (ys_ble + ys_cla + ys_wifi + ys_cell) or [0]
        all_z = (zs_ble + zs_cla + zs_wifi + zs_cell) or [0]
        if self.map3d["overlay_extent"] is not None:
            xmin, xmax, ymin, ymax = self.map3d["overlay_extent"]
            all_x += [xmin, xmax]; all_y += [ymin, ymax]; all_z += [-0.2]
        max_range = max(5.0, max(abs(min(all_x)), abs(max(all_x)),
                                 abs(min(all_y)), abs(max(all_y)),
                                 abs(min(all_z)), abs(max(all_z))))
        ax.set_xlim(-max_range, max_range)
        ax.set_ylim(-max_range, max_range)
        ax.set_zlim(-max_range, max_range * 0.6)

        # Restore prior zoom if any
        if old_xlim != (0.0, 1.0) or old_ylim != (0.0, 1.0):
            try:
                ax.set_xlim(old_xlim); ax.set_ylim(old_ylim); ax.set_zlim(old_zlim)
            except Exception:
                pass

        ax.legend(loc="upper right", fontsize=8)
        canvas.draw_idle()

        if self.map3d["animate_var"] and self.map3d["animate_var"].get():
            self._stop_seed_animation(); self._start_seed_animation()
        else:
            self._stop_seed_animation()

    def _toggle_sat_overlay(self):
        if self.map3d["sat_overlay_var"].get():
            threading.Thread(target=self._load_sat_overlay_async, daemon=True).start()
        else:
            self.map3d["overlay_img"] = None
            self.map3d["overlay_extent"] = None
            self.map3d["sat_status"].set("")
            self._render_map3d()

    def _load_sat_overlay_async(self):
        self.map3d["sat_status"].set("Loading satellite tiles…")
        ok = self._ensure_sat_overlay_loaded()
        self.map3d["sat_status"].set("" if ok else "Satellite overlay not available.")
        self._render_map3d()

    def _ensure_sat_overlay_loaded(self):
        lat, lon = self.get_gps_coordinates()
        z = int(self.map3d["sat_zoom"]); tiles = int(self.map3d["sat_tiles"])
        cache_key = (round(lat, 6), round(lon, 6), z, tiles)
        if self.map3d["overlay_cache_key"] == cache_key and self.map3d["overlay_img"] is not None:
            return True
        try:
            img, extent = self._sat_tiles_mosaic(lat, lon, z, tiles)
            if img is None:
                return False
            self.map3d["overlay_img"] = img
            self.map3d["overlay_extent"] = extent  # (xmin, xmax, ymin, ymax) in meters around origin
            self.map3d["overlay_cache_key"] = cache_key
            return True
        except Exception as e:
            self.log(f"Satellite overlay load error: {e}")
            return False

    # ---- Satellite tile helpers ----
    def _sat_tiles_mosaic(self, lat, lon, zoom=18, tiles=3, tile_size=256):
        """
        Fetch a tiles x tiles mosaic centered at lat/lon.
        Uses Esri World_Imagery, falls back to OSM if needed.
        Returns (PIL.Image, (xmin, xmax, ymin, ymax) in meters) or (None, None).
        """
        assert tiles % 2 == 1, "tiles must be odd (3, 5, …)"
        n = 2 ** zoom
        xt = (lon + 180.0) / 360.0 * n
        lat_rad = math.radians(lat)
        yt = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
        x0 = int(math.floor(xt))
        y0 = int(math.floor(yt))

        half = tiles // 2
        mosaic = Image.new("RGB", (tiles * tile_size, tiles * tile_size))
        got_any = False

        def _fetch_tile(z, x, y):
            urls = [
                f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            ]
            for u in urls:
                try:
                    req = urllib.request.Request(u, headers={"User-Agent": "RadioMapper/1.0"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        data = resp.read()
                    im = Image.open(io.BytesIO(data)).convert("RGB")
                    return im
                except Exception:
                    continue
            return None

        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                x = (x0 + dx) % n
                y = y0 + dy
                if y < 0 or y >= n:
                    continue
                im = _fetch_tile(zoom, x, y)
                if im is None:
                    continue
                got_any = True
                px = (dx + half) * tile_size
                py = (dy + half) * tile_size
                mosaic.paste(im.resize((tile_size, tile_size)), (px, py))

        if not got_any:
            return None, None

        # Compute meter extent (Web Mercator meters per pixel at latitude)
        mpp = 156543.03392 * math.cos(lat_rad) / (2 ** zoom)
        width_m = mosaic.size[0] * mpp
        height_m = mosaic.size[1] * mpp
        xmin = -width_m / 2.0
        xmax = +width_m / 2.0
        ymin = -height_m / 2.0
        ymax = +height_m / 2.0

        return mosaic, (xmin, xmax, ymin, ymax)

    def _draw_overlay_plane(self, ax, img: Image.Image, extent, z=-0.2, alpha=0.9, max_side=256):
        xmin, xmax, ymin, ymax = extent
        # Downsample to keep plotting fast
        w, h = img.size
        scale = max(1, int(max(w, h) / max_side))
        img2 = img.resize((max(1, w // scale), max(1, h // scale)))
        arr = np.asarray(img2).astype(np.float32) / 255.0
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        if arr.shape[2] == 3:
            alpha_layer = np.full(arr.shape[:2] + (1,), float(alpha), dtype=np.float32)
            arr = np.concatenate([arr, alpha_layer], axis=-1)

        ny, nx = arr.shape[0], arr.shape[1]
        xs = np.linspace(xmin, xmax, nx)
        ys = np.linspace(ymin, ymax, ny)
        X, Y = np.meshgrid(xs, ys)
        Z = np.full_like(X, float(z))

        # facecolors expect (ny-1, nx-1, 4)
        fc = arr[:-1, :-1, :]
        ax.plot_surface(X, Y, Z, rstride=1, cstride=1, facecolors=fc, shade=False)

    # ---------- Wi‑Fi Scanning ----------
    def start_scan_wifi(self):
        threading.Thread(target=lambda: self.queue.put(lambda nets=self.scan_wifi_sync(): self._merge_wifi_in_main(nets)),
                         daemon=True).start()

    def _merge_wifi_in_main(self, nets):
        added = 0
        for n in nets:
            bssid = n["bssid"]
            self.wifi_meta[bssid] = {
                "ssid": n.get("ssid") or "[Hidden SSID]",
                "rssi": n.get("rssi"),
                "freq_mhz": n.get("freq_mhz"),
                "chan": n.get("chan"),
                "security": n.get("security"),
                "distance_m": n.get("distance_m"),
                "range_label": n.get("range_label"),
                "qual": n.get("qual"),
            }
            exists = any((t == "WiFi" and d.get("bssid") == bssid) for t, d in self.devices)
            if not exists:
                self.devices.append(("WiFi", {"bssid": bssid, "ssid": n.get("ssid"),
                                              "freq_mhz": n.get("freq_mhz"), "chan": n.get("chan"),
                                              "security": n.get("security")}))
                self.connection_results[bssid] = "Seen"
                added += 1
        if added:
            self.redraw_device_list(append_only=True)
        else:
            self.redraw_device_list(append_only=False)

    def scan_wifi_sync(self):
        """Return list of Wi‑Fi networks with distance & quality."""
        try:
            if IS_WINDOWS:
                nets = self._scan_wifi_windows()
            elif platform.system() == "Darwin":
                nets = self._scan_wifi_macos()
            else:
                nets = self._scan_wifi_linux()
        except Exception as e:
            self.log(f"Wi‑Fi scan error: {e}")
            nets = []
        out = []
        for n in nets:
            bssid = n["bssid"]
            rssi = n.get("rssi")
            key = f"WIFI:{bssid}"
            ema = self.dist_filter.push_rssi(key, rssi) if rssi is not None else None
            use_rssi = ema if ema is not None else rssi
            txp = self._heuristic_tx_power_wifi(n.get("freq_mhz"))
            d_m = self.estimate_distance(use_rssi, txp, None, clamp=True, min_m=0.5, max_m=60.0) if use_rssi is not None else None
            qual = self.dist_filter.quality_grade(key)
            bucket = self._range_bucket(d_m)
            n.update({"distance_m": d_m, "range_label": bucket, "qual": qual})
            # Feed live tracker
            if isinstance(d_m, (int, float)):
                self._track_push_sample(bssid, d_m, rssi=rssi, source="WiFi")
            out.append(n)
        return out

    def _heuristic_tx_power_wifi(self, freq_mhz):
        """Rough Tx @1m reference: ~-41 dBm for 2.4 GHz, ~-46 dBm for 5/6 GHz."""
        try:
            f = float(freq_mhz or 0)
        except Exception:
            f = 0.0
        return -41.0 if f and f < 3000 else -46.0

    def _channel_to_freq_mhz(self, ch):
        try:
            ch = int(str(ch).split(",")[0].strip())
        except Exception:
            return None
        if 1 <= ch <= 14:
            return 2412 + (ch - 1) * 5
        if 32 <= ch <= 196:
            return 5000 + ch * 5
        # 6 GHz (approx)
        if 1 <= ch <= 233:
            return 5950 + ch * 5
        return None

    # ----- Windows (netsh) -----
    def _scan_wifi_windows(self):
        if not shutil.which("netsh"):
            return []
        out = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, text=True, errors="ignore"
        ).stdout
        ssid = None
        security = ""
        nets = []
        for line in out.splitlines():
            ln = line.strip()
            if not ln:
                continue
            low = ln.lower()
            if low.startswith("ssid "):
                parts = ln.split(":", 1)
                ssid = (parts[1].strip() if len(parts) > 1 else "") or ""
            elif low.startswith("authentication"):
                security = ln.split(":", 1)[1].strip() if ":" in ln else ""
            elif low.startswith("bssid"):
                bssid = ln.split(":", 1)[1].strip().lower()
                nets.append({"ssid": ssid or "", "bssid": bssid, "security": security})
            elif low.startswith("signal"):
                if nets:
                    try:
                        pct = int(re.sub(r"[^\d]", "", ln) or "0")
                    except Exception:
                        pct = 0
                    dbm = (pct / 2.0) - 100.0
                    nets[-1]["rssi"] = round(dbm, 1)
            elif low.startswith("channel"):
                if nets:
                    try:
                        ch = int(re.sub(r"[^\d]", "", ln) or "0")
                    except Exception:
                        ch = 0
                    nets[-1]["chan"] = ch
                    nets[-1]["freq_mhz"] = self._channel_to_freq_mhz(ch)
        return [n for n in nets if "bssid" in n and n.get("rssi") is not None]

    # ----- macOS (airport) -----
    def _scan_wifi_macos(self):
        airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport"
        if not os.path.exists(airport):
            airport = shutil.which("airport") or airport
        if not airport:
            return []
        out = subprocess.run([airport, "-s"], capture_output=True, text=True, errors="ignore").stdout
        lines = [l for l in out.splitlines() if l.strip()]
        if not lines:
            return []
        # Skip header
        lines = lines[1:]
        nets = []
        for ln in lines:
            m = re.search(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})", ln)
            if not m:
                continue
            bssid = m.group(1).lower()
            left = ln[:m.start()].rstrip()
            right = ln[m.end():].strip()
            ssid = left.strip() or ""
            cols = re.split(r"\s+", right)
            if len(cols) < 3:
                continue
            try:
                rssi = float(cols[0])  # airport outputs dBm
            except Exception:
                continue
            chan_raw = cols[1]
            try:
                ch = int(str(chan_raw).split(",")[0])
            except Exception:
                ch = None
            freq = self._channel_to_freq_mhz(ch) if ch else None
            security = " ".join(cols[3:]) if len(cols) > 3 else ""
            nets.append({"ssid": ssid, "bssid": bssid, "rssi": rssi, "chan": ch, "freq_mhz": freq, "security": security})
        return nets

    # ----- Linux (nmcli) -----
    def _scan_wifi_linux(self):
        if not shutil.which("nmcli"):
            return []
        out = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,BSSID,CHAN,SIGNAL,FREQ,SECURITY", "dev", "wifi", "list"],
            capture_output=True, text=True, errors="ignore"
        ).stdout
        nets = []
        for ln in out.splitlines():
            if not ln.strip():
                continue
            parts = ln.split(":")
            if len(parts) < 6:
                continue
            ssid = parts[0].replace(r"\:", ":").strip()
            bssid = parts[1].lower()
            chan = parts[2].strip()
            try:
                pct = float(parts[3])
                rssi = (pct / 2.0) - 100.0  # approx
            except Exception:
                rssi = None
            try:
                freq = float(parts[4])
            except Exception:
                freq = self._channel_to_freq_mhz(chan)
            security = parts[5].strip()
            nets.append({
                "ssid": ssid, "bssid": bssid, "chan": int(chan) if chan.isdigit() else chan,
                "rssi": round(rssi, 1) if rssi is not None else None,
                "freq_mhz": freq, "security": security
            })
        return [n for n in nets if "bssid" in n and n.get("rssi") is not None]

    # ---------- Cellular Scanning ----------
    def start_scan_cell(self):
        threading.Thread(target=lambda: self.queue.put(lambda cells=self.scan_cell_sync(): self._merge_cell_in_main(cells)),
                         daemon=True).start()

    def _merge_cell_in_main(self, cells):
        added = 0
        for c in cells:
            cid = c["cid"]
            self.cell_meta[cid] = {
                "operator": c.get("operator"),
                "tech": c.get("tech"),
                "signal_pct": c.get("signal_pct"),
                "rssi_dbm": c.get("rssi_dbm"),
                "rsrp_dbm": c.get("rsrp_dbm"),
                "rsrq_db": c.get("rsrq_db"),
                "sinr_db": c.get("sinr_db"),
                "qual_bucket": c.get("qual_bucket"),
            }
            exists = any((t == "Cell" and d.get("cid") == cid) for t, d in self.devices)
            if not exists:
                self.devices.append(("Cell", {"cid": cid, "operator": c.get("operator"), "tech": c.get("tech")}))
                self.connection_results[cid] = "Seen"
                added += 1
        if added:
            self.redraw_device_list(append_only=True)
        else:
            self.redraw_device_list(append_only=False)

    def scan_cell_sync(self):
        """Return list of cellular signal snapshots (best-effort, OS-specific)."""
        try:
            if IS_WINDOWS:
                cells = self._scan_cell_windows()
            elif platform.system() == "Darwin":
                cells = self._scan_cell_macos()
            else:
                cells = self._scan_cell_linux()
        except Exception as e:
            self.log(f"Cellular scan error: {e}")
            cells = []
        for c in cells:
            if not c.get("qual_bucket"):
                c["qual_bucket"] = self._cell_quality_bucket(c)
        return cells

    def _cell_quality_bucket(self, c):
        rsrp = c.get("rsrp_dbm")
        rssi = c.get("rssi_dbm")
        pct = c.get("signal_pct")
        if rsrp is not None:
            v = rsrp
            if v >= -80: return "Excellent"
            if v >= -90: return "Good"
            if v >= -100: return "Fair"
            if v >= -110: return "Poor"
            return "Very poor"
        if rssi is not None:
            v = rssi
            if v >= -70: return "Excellent"
            if v >= -85: return "Good"
            if v >= -100: return "Fair"
            if v >= -110: return "Poor"
            return "Very poor"
        if pct is not None:
            p = float(pct)
            if p >= 80: return "Excellent"
            if p >= 60: return "Good"
            if p >= 40: return "Fair"
            if p >= 20: return "Poor"
            return "Very poor"
        return "Unknown"

    # ----- Windows (netsh mbn) -----
    def _scan_cell_windows(self):
        if not shutil.which("netsh"):
            return []
        ifaces_out = subprocess.run(
            ["netsh", "mbn", "show", "interfaces"],
            capture_output=True, text=True, errors="ignore"
        ).stdout
        interfaces = []
        cur = {}
        for ln in ifaces_out.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.lower().startswith("interface name"):
                if cur:
                    interfaces.append(cur); cur = {}
                cur["name"] = s.split(":", 1)[1].strip().strip('"')
            elif s.lower().startswith("device id"):
                cur["device_id"] = s.split(":", 1)[1].strip()
            elif s.lower().startswith("subscriber id"):
                cur["subscriber_id"] = s.split(":", 1)[1].strip()
        if cur:
            interfaces.append(cur)

        cells = []
        for iface in interfaces or [{"name": "Cellular"}]:
            name = iface.get("name") or "Cellular"
            try:
                sig_out = subprocess.run(
                    ["netsh", "mbn", "show", "signal", f'interface="{name}"'],
                    capture_output=True, text=True, errors="ignore", timeout=5
                ).stdout
            except Exception:
                sig_out = ""
            pct = None; operator = None; tech = None
            for ln in sig_out.splitlines():
                s = ln.strip(); lower = s.lower()
                if lower.startswith("signal") and "%" in s:
                    try:
                        pct = int(re.search(r"(\d+)\s*%", s).group(1))
                    except Exception:
                        pass
                elif lower.startswith("system type") or lower.startswith("network type"):
                    tech = s.split(":", 1)[1].strip()
                elif lower.startswith("registered provider"):
                    operator = s.split(":", 1)[1].strip().strip('"')
            cid = f'WINIF:{name}'
            cells.append({
                "cid": cid, "operator": operator, "tech": tech,
                "signal_pct": pct, "rssi_dbm": None, "rsrp_dbm": None, "rsrq_db": None, "sinr_db": None,
                "qual_bucket": None
            })
        return cells

    # ----- macOS (placeholder) -----
    def _scan_cell_macos(self):
        if not shutil.which("scutil"):
            return []
        out = subprocess.run(["scutil", "--nc", "list"], capture_output=True, text=True, errors="ignore").stdout
        cells = []
        for ln in out.splitlines():
            if "WWAN" in ln or "Cellular" in ln or "Mobile" in ln:
                svc = ln.strip()
                cid = f"MACWWAN:{hashlib.sha1(svc.encode()).hexdigest()[:8]}"
                cells.append({"cid": cid, "operator": None, "tech": "WWAN",
                              "signal_pct": None, "rssi_dbm": None, "rsrp_dbm": None,
                              "rsrq_db": None, "sinr_db": None, "qual_bucket": "Unknown"})
        return cells

    # ----- Linux (ModemManager: mmcli) -----
    def _scan_cell_linux(self):
        if not shutil.which("mmcli"):
            return []
        out = subprocess.run(["mmcli", "-L"], capture_output=True, text=True, errors="ignore").stdout
        paths = []
        for ln in out.splitlines():
            m = re.search(r"(\/org\/freedesktop\/ModemManager1\/Modem\/\d+)", ln)
            if m:
                paths.append(m.group(1))
        cells = []
        for path in paths:
            info = subprocess.run(["mmcli", "-m", path, "-K"], capture_output=True, text=True, errors="ignore").stdout
            operator = None; tech = None
            for ln in info.splitlines():
                if "modem.generic.operator-name" in ln:
                    operator = ln.split(":", 1)[1].strip()
                if "modem.generic.access-technologies" in ln:
                    techs = ln.split(":", 1)[1].strip()
                    tech = techs.split(",")[0].strip() if techs else None
            sig = subprocess.run(["mmcli", "-m", path, "--signal-get", "--timeout", "5"],
                                 capture_output=True, text=True, errors="ignore").stdout
            rssi = None; rsrp = None; rsrq = None; sinr = None
            for ln in sig.splitlines():
                s = ln.strip().lower()
                if "rssi" in s and "dbm" in s and rssi is None:
                    try: rssi = float(re.search(r"(-?\d+\.?\d*)\s*dBm", ln, re.I).group(1))
                    except Exception: pass
                if "rsrp" in s and rsrp is None:
                    try: rsrp = float(re.search(r"(-?\d+\.?\d*)\s*dBm", ln, re.I).group(1))
                    except Exception: pass
                if "rsrq" in s and rsrq is None:
                    try: rsrq = float(re.search(r"(-?\d+\.?\d*)\s*dB", ln, re.I).group(1))
                    except Exception: pass
                if "sinr" in s and sinr is None:
                    try: sinr = float(re.search(r"(-?\d+\.?\d*)\s*dB", ln, re.I).group(1))
                    except Exception: pass
            cid = f"MMCLI:{path.split('/')[-1]}"
            cells.append({"cid": cid, "operator": operator, "tech": tech, "signal_pct": None,
                          "rssi_dbm": rssi, "rsrp_dbm": rsrp, "rsrq_db": rsrq, "sinr_db": sinr,
                          "qual_bucket": None})
        return cells

    # ---------- Interactive Map (Folium) ----------
    def open_interactive_map(self):
        if not HAVE_FOLIUM:
            messagebox.showerror("Map Unavailable", "Install 'folium' to enable the interactive map.\n\npip install folium")
            return
        try:
            path = self._generate_interactive_map()
            webbrowser.open(f"file://{os.path.abspath(path)}")
            self.log(f"Opened interactive map: {path}")
        except Exception as e:
            self.log(f"Map error: {e}")
            messagebox.showerror("Map Error", str(e))

    def _generate_interactive_map(self, out_path="radio_map.html"):
        lat, lon = self.get_gps_coordinates()
        m = folium.Map(location=[lat, lon], zoom_start=18, tiles=None, control_scale=True)
        # Satellite + OSM layers
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery", name="Satellite"
        ).add_to(m)
        folium.TileLayer("OpenStreetMap", name="OSM").add_to(m)
        folium.LayerControl().add_to(m)

        # Click to get lat/lon popup
        folium.LatLngPopup().add_to(m)
        if HAVE_MOUSEPOS:
            MousePosition(position="topright", separator=" | ", empty_string="",
                          num_digits=6, prefix="Lat/Lon").add_to(m)

        # "You are here"
        folium.Marker([lat, lon], tooltip="GPS Origin", icon=folium.Icon(color="blue", icon="home")).add_to(m)

        # Draw device tracks (if any)
        for key, tr in self.tracks.items():
            if tr.get("trail"):
                latlons = [_TrackerMath.xy_to_latlon(self.origin_lat, self.origin_lon, x, y)[:2]
                           for (x, y, _) in tr["trail"]]
                latlons = latlons[-200:]
                try:
                    folium.PolyLine(latlons, weight=3, opacity=0.7).add_to(m)
                except Exception:
                    pass
            est = tr.get("est")
            if est:
                elat, elon = _TrackerMath.xy_to_latlon(self.origin_lat, self.origin_lon, est["x"], est["y"])
                folium.CircleMarker([elat, elon], radius=5, weight=2, fill=True,
                                    popup=f"{key}  {tr.get('speed',0.0):.1f} m/s").add_to(m)

        # Draw uncertainty/range circles per radio
        def add_circle(radius_m, color, popup):
            if radius_m is None: return
            if not isinstance(radius_m, (int, float)): return
            if radius_m <= 0: return
            folium.Circle(location=[lat, lon], radius=float(radius_m),
                          color=color, weight=2, fill=True, fill_opacity=0.15,
                          popup=popup).add_to(m)

        # BLE & Wi‑Fi circles (distance estimates)
        for typ, dev in self.devices:
            if typ == "BLE":
                meta = self.ble_meta.get(dev.address, {})
                d_m = meta.get("distance_m")
                name = meta.get("name") or dev.name or "[BLE]"
                add_circle(d_m, "#2e7d32", f"BLE: {name} (~{d_m:.1f} m)" if isinstance(d_m, (int, float)) else f"BLE: {name}")
            elif typ == "WiFi":
                bssid = dev["bssid"]; meta = self.wifi_meta.get(bssid, {})
                d_m = meta.get("distance_m"); ssid = meta.get("ssid") or "[Wi‑Fi]"
                add_circle(d_m, "#8e24aa", f"Wi‑Fi: {ssid} (~{d_m:.1f} m)" if isinstance(d_m, (int, float)) else f"Wi‑Fi: {ssid}")
            elif typ == "Cell":
                add_circle(self.map3d["cell_default_dist"], "#c62828", "Cellular approx range")

        m.save(out_path)
        return out_path

    # ---------- Export / Download ----------
    def download_info(self):
        """
        Save either the selected item's info (if any) or the entire displayed list.
        File format is chosen by the user: CSV, JSON or TXT.
        """
        try:
            total = self.device_list.size()
            idxs = self.device_list.curselection()
            if total == 0:
                self.queue.put(lambda: messagebox.showwarning("Nothing to export", "No entries are displayed yet. Try scanning first."))
                return

            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            initial = ("selected_info_" if idxs else "device_list_") + ts + ".csv"
            dest = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile=initial,
                filetypes=[("CSV", "*.csv"), ("JSON", "*.json"), ("Text", "*.txt")]
            )
            if not dest:
                return

            if dest.lower().endswith(".json"):
                self._export_json(dest, idxs)
            elif dest.lower().endswith(".txt"):
                self._export_text(dest, idxs)
            else:
                self._export_csv(dest, idxs)

            self.queue.put(lambda: messagebox.showinfo("Saved", f"Saved to:\n{dest}"))
            self.log(f"Exported info -> {dest}")

        except Exception as e:
            self.log(f"Download/export error: {e}")
            self.queue.put(lambda: messagebox.showerror("Export Failed", f"Could not save file:\n{e}"))

    def _export_text(self, dest, idxs):
        """Write human-readable summary lines (selected or whole list) to TXT."""
        lines = []
        if idxs:
            try:
                lines.append(self.device_list.get(idxs[0]))
            except Exception:
                typ, id_, _ = self._selected_addr_and_type()
                if typ and id_:
                    lines.append(self._row_text_by_id(typ, id_))
        else:
            lines = self._get_displayed_list_lines()

        with open(dest, "w", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln.rstrip("\n") + "\n")

    def _export_csv(self, dest, idxs):
        """
        CSV:
          • Selected -> structured one-row CSV with typed columns.
          • No selection -> single 'summary' column for the displayed list.
        """
        if idxs:
            typ, id_, _ = self._selected_addr_and_type()
            if not (typ and id_):
                self._export_text(dest, idxs)
                return
            rec = self._build_struct_for(typ, id_)
            keys_pref = [
                "type", "id", "name", "status", "summary",
                "rssi_dbm", "tx_power_ref_dbm", "distance_m", "range_label", "quality_grade",
                "addr_type", "service_uuid_count", "service_uuids", "manufacturer_ids",
                "gps", "paired", "device_id",
                "ssid", "freq_mhz", "channel", "security",
                "operator", "tech", "signal_pct", "rsrp_dbm", "rsrq_db", "sinr_db", "quality_bucket",
                "timestamp"
            ]
            cols = [k for k in keys_pref if k in rec]
            for k in rec.keys():
                if k not in cols:
                    cols.append(k)
            with open(dest, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerow(rec)
        else:
            lines = self._get_displayed_list_lines()
            with open(dest, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["summary"])
                for ln in lines:
                    w.writerow([ln])

    def _export_json(self, dest, idxs):
        """
        JSON:
          • Selected -> list with one structured object (plus 'summary').
          • No selection -> list of {'summary': <text>} objects mirroring the list UI.
        """
        if idxs:
            typ, id_, _ = self._selected_addr_and_type()
            if not (typ and id_):
                data = [{"summary": self.device_list.get(idxs[0])}] if idxs else [{"summary": ln} for ln in self._get_displayed_list_lines()]
            else:
                data = [self._build_struct_for(typ, id_)]
        else:
            data = [{"summary": ln} for ln in self._get_displayed_list_lines()]

        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_displayed_list_lines(self):
        """Return exactly what's visible in the Listbox (the 'displayed list')."""
        try:
            return list(self.device_list.get(0, tk.END))
        except Exception:
            return []

    def _build_struct_for(self, typ, id_):
        """
        Build a structured dictionary for a single selected item.
        """
        now_iso = datetime.datetime.now().isoformat(timespec="seconds")
        base = {"type": typ, "id": id_, "timestamp": now_iso}

        if typ == "WiFi" or typ == "Cell":
            status = self.connection_results.get(id_, "Seen")
        else:
            status = self.connection_results.get(id_, "Not Tested")
        base["status"] = status

        if typ == "BLE":
            m = self.ble_meta.get(id_, {}) or {}
            tr = self.tracks.get(id_)
            base.update({
                "name": m.get("name") or m.get("fallback_name") or "[Unnamed Device]",
                "summary": self._row_text_by_id("BLE", id_),
                "rssi_dbm": m.get("rssi"),
                "tx_power_ref_dbm": m.get("tx_power"),
                "distance_m": m.get("distance_m"),
                "range_label": m.get("range_label"),
                "quality_grade": m.get("qual"),
                "addr_type": m.get("addr_type"),
                "service_uuid_count": m.get("svc_count"),
                "service_uuids": m.get("svc_uuids"),
                "manufacturer_ids": m.get("mfr_ids"),
                "gps": m.get("gps"),
                "paired": bool(m.get("paired")) if m.get("paired") is not None else False,
                "device_id": m.get("device_id"),
                "speed_mps": tr.get("speed") if tr else None
            })
        elif typ == "Classic":
            info = None
            for t, d in self.devices:
                if t == "Classic" and isinstance(d, dict) and d.get("addr") == id_:
                    info = d
                    break
            info = info or {}
            base.update({
                "name": info.get("name") or "[Unnamed Device]",
                "summary": self._row_text_by_id("Classic", id_),
                "device_class": info.get("device_class"),
                "type_str": info.get("type_str"),
                "services": info.get("services"),
                "device_id": info.get("device_id"),
            })
        elif typ == "WiFi":
            m = self.wifi_meta.get(id_, {}) or {}
            tr = self.tracks.get(id_)
            base.update({
                "name": m.get("ssid") or "[Hidden SSID]",
                "summary": self._row_text_by_id("WiFi", id_),
                "ssid": m.get("ssid"),
                "rssi_dbm": m.get("rssi"),
                "distance_m": m.get("distance_m"),
                "range_label": m.get("range_label"),
                "quality_grade": m.get("qual"),
                "freq_mhz": m.get("freq_mhz"),
                "channel": m.get("chan"),
                "security": m.get("security"),
                "speed_mps": tr.get("speed") if tr else None
            })
        else:  # Cell
            m = self.cell_meta.get(id_, {}) or {}
            base.update({
                "name": f"{m.get('operator','Unknown operator')} [{m.get('tech','Unknown RAT')}]",
                "summary": self._row_text_by_id("Cell", id_),
                "operator": m.get("operator"),
                "tech": m.get("tech"),
                "signal_pct": m.get("signal_pct"),
                "rssi_dbm": m.get("rssi_dbm"),
                "rsrp_dbm": m.get("rsrp_dbm"),
                "rsrq_db": m.get("rsrq_db"),
                "sinr_db": m.get("sinr_db"),
                "quality_bucket": m.get("qual_bucket"),
            })
        return base

    def _row_text_by_id(self, typ, id_):
        try:
            if typ == "BLE":
                dev = None
                for t, d in self.devices:
                    if t == "BLE" and getattr(d, "address", None) == id_:
                        dev = d; break
                status = self.connection_results.get(id_, "Not Tested")
                if dev is not None:
                    return self.row_text_for_ble(dev, status)
                m = self.ble_meta.get(id_, {}) or {}
                name = m.get("name") or "[Unnamed Device]"
                rssi = m.get("rssi", "N/A")
                d_m = m.get("distance_m"); bucket = m.get("range_label", "Unknown"); qual = m.get("qual", "D")
                dist_str = f"{bucket} ~{d_m:.1f} m" if isinstance(d_m, (int, float)) else bucket
                return f"BLE: {name} ({id_}) - {status} - RSSI {rssi} dBm (\n  {dist_str}, Q:{qual})"
            elif typ == "Classic":
                info = None
                for t, d in self.devices:
                    if t == "Classic" and isinstance(d, dict) and d.get("addr") == id_:
                        info = d; break
                status = self.connection_results.get(id_, "Not Tested")
                if info is not None:
                    return self.row_text_for_classic(info, status)
                return f"Classic: ({id_}) - {status}"
            elif typ == "WiFi":
                info = None
                for t, d in self.devices:
                    if t == "WiFi" and isinstance(d, dict) and d.get("bssid") == id_:
                        info = d; break
                status = self.connection_results.get(id_, "Seen")
                if info is not None:
                    return self.row_text_for_wifi(info, status)
                ssid = (self.wifi_meta.get(id_) or {}).get("ssid", "[Hidden SSID]")
                return f"Wi‑Fi: {ssid} ({id_}) - {status}"
            else:
                info = None
                for t, d in self.devices:
                    if t == "Cell" and isinstance(d, dict) and d.get("cid") == id_:
                        info = d; break
                status = self.connection_results.get(id_, "Seen")
                if info is not None:
                    return self.row_text_for_cell(info, status)
                return f"Cell: ({id_}) - {status}"
        except Exception:
            return f"{typ}: ({id_})"

    # ---------- Tracking helpers (NEW) ----------
    def _set_tracking_origin_if_needed(self):
        if self.origin_lat is None or self.origin_lon is None:
            self.origin_lat, self.origin_lon = self.get_gps_coordinates()

    def _track_get(self, key):
        tr = self.tracks.get(key)
        if tr is None:
            tr = {"samples": deque(maxlen=600), "trail": deque(maxlen=400), "est": None, "last_t": 0.0, "speed": 0.0}
            self.tracks[key] = tr
        return tr

    def _track_push_sample(self, key, dist_m, rssi=None, source="BLE"):
        if not self.tracking_enabled_var.get():
            return
        if dist_m is None or not isinstance(dist_m, (int, float)) or dist_m <= 0:
            return
        self._set_tracking_origin_if_needed()
        lat, lon = self.get_gps_coordinates()
        x, y = _TrackerMath.latlon_to_xy(self.origin_lat, self.origin_lon, lat, lon)
        t = time.time()
        tr = self._track_get(key)
        tr["samples"].append({"t": t, "x": x, "y": y, "r": float(dist_m), "rssi": rssi, "src": source})
        self._update_estimate_for_track(key, tr)
        now = time.time()
        if now >= self._next_list_refresh_ts:
            self._next_list_refresh_ts = now + 0.75
            self.queue.put(lambda: self.redraw_device_list(append_only=False))
        self._schedule_map_refresh()
        self._schedule_tracker_refresh()

    def _update_estimate_for_track(self, key, tr):
        now = time.time()
        recent = [s for s in list(tr["samples"])[-120:] if now - s["t"] <= TRACK_SAMPLE_TTL_SEC]
        if len(recent) < TRACK_MIN_SAMPLES:
            return
        guess = _TrackerMath.linear_initial_guess(recent)
        if guess is None:
            if tr.get("est"):
                guess = (tr["est"]["x"], tr["est"]["y"])
            else:
                guess = (recent[-1]["x"], recent[-1]["y"])
        x, y = _TrackerMath.gauss_newton(recent, guess[0], guess[1], iters=6)
        last = tr["est"]
        speed = tr.get("speed", 0.0)
        if last:
            dt = max(1e-3, now - last["t"])
            dx = x - last["x"]; dy = y - last["y"]
            v = math.hypot(dx, dy) / dt
            speed = 0.4 * v + 0.6 * speed
        tr["est"] = {"x": x, "y": y, "t": now}
        tr["speed"] = speed
        tr["trail"].append((x, y, now))

    def _tracker_housekeeping(self):
        cutoff = time.time() - TRACK_SAMPLE_TTL_SEC
        for k, tr in list(self.tracks.items()):
            tr["samples"] = deque([s for s in tr["samples"] if s["t"] >= cutoff], maxlen=600)
            tr["trail"] = deque([p for p in tr["trail"] if p[2] >= cutoff], maxlen=400)
            if not tr["samples"] and not tr["trail"]:
                self.tracks.pop(k, None)
        self._schedule_tracker_refresh()
        self.root.after(3000, self._tracker_housekeeping)

    def _schedule_tracker_refresh(self):
        tv = self._tracker_view
        if not tv["win"] or not tk.Toplevel.winfo_exists(tv["win"]):
            return
        now = time.time()
        if now - tv["last_draw"] > 0.20:  # ~5 fps
            tv["last_draw"] = now
            self.root.after(0, self._render_tracker_view)

    def _wifi_poll_timer(self):
        if self.tracking_enabled_var.get():
            try:
                self.start_scan_wifi()
            except Exception:
                pass
        self.root.after(6000, self._wifi_poll_timer)

    # ---------- BLE live scanner (NEW) ----------
    async def _ble_live_scanner(self):
        """Single persistent scanner so we can track movement in near real-time."""
        try:
            def _cb(device, advertisement_data):
                try:
                    self._ble_ingest_adv(device, advertisement_data)
                except Exception as e:
                    self.log(f"BLE adv ingest error: {e}")
            scanner = BleakScanner(detection_callback=_cb)
            await scanner.start()
            self.live_ble_scanner_active = True
            self.log("BLE live scanner: ON")
            while True:
                await asyncio.sleep(3600)  # keep running
        except Exception as e:
            self.live_ble_scanner_active = False
            self.log(f"BLE live scanner stopped: {e}")

    def _ble_ingest_adv(self, device, adv):
        addr = device.address
        rssi = getattr(adv, "rssi", None)
        ema_rssi = self.dist_filter.push_rssi(addr, rssi) if rssi is not None else None
        txp = getattr(adv, "tx_power", None)
        mfr = getattr(adv, "manufacturer_data", {}) or {}
        mfr_ids = [f"0x{mid:04x}" for mid in mfr.keys()]
        if txp is None:
            txp = self._heuristic_tx_power(addr, mfr_ids)

        d_m = None
        if ema_rssi is not None:
            d_m = self.estimate_distance(ema_rssi, txp, None, clamp=True)

        gps_coords = f"{self.get_gps_coordinates()[0]:.6f}, {self.get_gps_coordinates()[1]:.6f}"
        svc_uuids = list(getattr(adv, "service_uuids", []) or [])
        fallback_name = device.name or getattr(adv, "local_name", None) or "[Unnamed Device]"
        stored_label = self.db_get_label(addr)
        name = stored_label or fallback_name
        qual = self.dist_filter.quality_grade(addr)
        bucket = self._range_bucket(d_m) if isinstance(d_m, (int, float)) else "Unknown"
        self.ble_meta[addr] = {
            "name": name, "fallback_name": fallback_name,
            "rssi": ema_rssi if ema_rssi is not None else rssi,
            "tx_power": txp,
            "addr_type": getattr(adv, "address_type", None) or "Unknown",
            "svc_count": len(svc_uuids), "svc_uuids": svc_uuids,
            "mfr_ids": mfr_ids, "gps": gps_coords,
            "distance_m": d_m, "range_label": bucket, "qual": qual
        }

        # Ensure device present in list
        if not any((t == "BLE" and getattr(d, "address", None) == addr) for t, d in self.devices):
            simple = type("SimpleBLEProxy", (), {})()
            simple.address = addr
            simple.name = name
            self.devices.append(("BLE", simple))
            self.connection_results[addr] = self.connection_results.get(addr, "Not Tested")

        # Push into the tracker (so it moves)
        if isinstance(d_m, (int, float)):
            self._track_push_sample(addr, d_m, rssi=rssi, source="BLE")

    # ---------- Tracker View (NEW) ----------
    def open_tracker_view(self):
        tv = self._tracker_view
        if tv["win"] and tk.Toplevel.winfo_exists(tv["win"]):
            tv["win"].lift(); return
        win = tk.Toplevel(self.root); tv["win"] = win
        win.title("Live Tracker (meters around GPS origin)")

        top = tk.Frame(win); top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="Zoom:").pack(side="left")
        zoom_var = tk.DoubleVar(value=1.0)
        tv["zoom_var"] = zoom_var
        def on_zoom(_=None):
            tv["zoom"] = max(0.2, min(5.0, float(zoom_var.get())))
            self._schedule_tracker_refresh()
        tk.Scale(top, from_=0.2, to=5.0, resolution=0.1, orient="horizontal",
                 length=180, variable=zoom_var, command=lambda _ : on_zoom()).pack(side="left", padx=6)
        tk.Checkbutton(top, text="Show range rings", variable=tv["show_rings"],
                       command=self._schedule_tracker_refresh).pack(side="left", padx=12)
        tk.Button(top, text="Center on origin", command=self._schedule_tracker_refresh).pack(side="left", padx=6)

        canvas = tk.Canvas(win, width=680, height=520, bg="#101418")
        canvas.pack(fill="both", expand=True, padx=6, pady=6)
        tv["canvas"] = canvas
        tv["zoom"] = 1.0
        tv["last_draw"] = 0.0
        self._render_tracker_view()

    def _render_tracker_view(self):
        tv = self._tracker_view
        if not tv["win"] or not tk.Toplevel.winfo_exists(tv["win"]) or not tv["canvas"]:
            return
        c = tv["canvas"]
        w = c.winfo_width() or 680
        h = c.winfo_height() or 520
        c.delete("all")
        pts = [(0.0, 0.0)]
        for tr in self.tracks.values():
            for x, y, _ in list(tr["trail"])[-120:]:
                pts.append((x, y))
        if len(pts) < 2:
            rng = 10.0
        else:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            maxr = max(10.0, max(abs(min(xs)), abs(max(xs)), abs(min(ys)), abs(max(ys))))
            rng = maxr * 1.2
        rng /= tv.get("zoom", 1.0)
        def mapxy(x, y):
            sx = (x / (rng+1e-9)) * (w*0.45) + w/2
            sy = h/2 - (y / (rng+1e-9)) * (h*0.45)
            return sx, sy
        # axes
        c.create_line(w/2, 10, w/2, h-10, fill="#22303a")
        c.create_line(10, h/2, w-10, h/2, fill="#22303a")
        # origin
        ox, oy = mapxy(0, 0)
        c.create_oval(ox-4, oy-4, ox+4, oy+4, fill="#4fc3f7", outline="")

        for key, tr in self.tracks.items():
            src = None
            if tr["samples"]:
                src = tr["samples"][-1]["src"]
            color = "#66bb6a" if src == "BLE" else ("#ba68c8" if src == "WiFi" else "#ef5350")
            # trail
            trail = list(tr["trail"])[-200:]
            if len(trail) >= 2:
                for i in range(1, len(trail)):
                    x0, y0, _ = trail[i-1]; x1, y1, _ = trail[i]
                    p0 = mapxy(x0, y0); p1 = mapxy(x1, y1)
                    c.create_line(p0[0], p0[1], p1[0], p1[1], fill=color)
            # current
            est = tr.get("est")
            if est:
                x, y = est["x"], est["y"]
                ex, ey = mapxy(x, y)
                c.create_oval(ex-5, ey-5, ex+5, ey+5, fill=color, outline="")
                sp = tr.get("speed", 0.0)
                c.create_text(ex+8, ey-8, anchor="sw", fill="#cfd8dc",
                              text=f"{key}  {sp:.1f} m/s", font=("TkDefaultFont", 8))
            # rings (optional)
            if tv["show_rings"].get() and tr["samples"]:
                for s in list(tr["samples"])[-6:]:
                    cx, cy = mapxy(s["x"], s["y"])
                    r = s["r"]
                    rx, ry = mapxy(s["x"] + r, s["y"] + r)
                    rr = max(2, abs(rx - cx))
                    c.create_oval(cx-rr, cy-rr, cx+rr, cy+rr, outline="#33434f")

    # ---------- Window close / cleanup ----------
    def on_close(self):
        self._close_map3d()

        # Stop WinRT geolocation listeners
        try:
            if self.winrt_geo and self.winrt_geo_token:
                self.winrt_geo.remove_position_changed(self.winrt_geo_token)
            if self.winrt_geo and self.winrt_geo_status_token:
                self.winrt_geo.remove_status_changed(self.winrt_geo_status_token)
        except Exception:
            pass

        try:
            if self.obex.get("client"):
                self.obex["client"].disconnect()
        except Exception:
            pass
        try:
            if self.connected_socket:
                self.connected_socket.close()
        except Exception:
            pass
        try:
            if self.ble_client and self.ble_client.is_connected:
                fut = self.run_coro(self.ble_client.disconnect())
                fut.result(timeout=3)
        except Exception:
            pass
        try:
            if self.db:
                with self.db_lock:
                    self.db.close()
        except Exception:
            pass
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.loop_thread.join(timeout=2)
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = BluetoothApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()