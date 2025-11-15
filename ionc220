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
from collections import deque
import statistics
import subprocess
import shutil
import tempfile

import ioncore_branding

# matplotlib (3D seeds map)
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (import activates 3D)

# Optional: reverse geocoding
try:
    from geopy.geocoders import Nominatim
    HAVE_GEOPY = True
except Exception:
    Nominatim = None
    HAVE_GEOPY = False

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
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

# UUIDs
OBEX_FTP_UUID = "00001106-0000-1000-8000-00805f9b34fb"
PBAP_PSE_UUID = "0000112f-0000-1000-8000-00805f9b34fb"  # Phonebook Access - Server (on phone)
PBAP_TARGET_UUID_BYTES = bytes.fromhex("796135F0F0C511D809660800200C9A66")

# Path to Apple's airport tool (macOS)
AIRPORT_BIN = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"


# ---------------- Range Qualification & Smoothing -----------------
class DistanceFilter:
    """Per-device RSSI smoother with outlier rejection and distance clamps."""
    def __init__(self, window=12, ema_alpha=0.30, min_m=0.25, max_m=40.0):
        self.window = int(window)
        self.ema_alpha = float(ema_alpha)
        self.min_m = float(min_m)
        self.max_m = float(max_m)
        self.buffers = {}   # key -> deque of recent RSSI (key may be BLE addr, WIFI:BSSID, CELL:*)
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

    def clamp_distance(self, d_m: float):
        if d_m is None:
            return None
        return max(self.min_m, min(self.max_m, float(d_m)))


class BluetoothApp:
    def __init__(self, root):
        self.root = root
        self.branding = ioncore_branding.apply_ioncore_branding(root)
        self.root.title("Ioncore Device Orchestrator")

        self.branding_header = ioncore_branding.build_branding_header(
            root,
            self.branding,
            title="Ioncore Device Orchestrator",
            subtitle="Unified Bluetooth, Wi‑Fi, and cellular intelligence in the Ioncore Index style.",
        )
        self.branding_header.pack(fill="x", padx=18, pady=(18, 12))

        # ---------- Async loop (single, persistent) ----------
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._run_loop, args=(self.loop,), daemon=True)
        self.loop_thread.start()

        # ---------- DB (labels) ----------
        self.db = None
        self._init_db()

        # ---------- UI: device list and controls ----------
        self.device_frame = tk.Frame(root)
        self.device_frame.pack(fill="x", padx=18, pady=(0, 14))

        self.device_list = tk.Listbox(self.device_frame, width=120, height=14)
        self.device_list.grid(row=0, column=0, columnspan=11, padx=5, pady=5)

        self.scan_button = tk.Button(self.device_frame, text="Scan Devices", command=self.start_scan_devices)
        self.scan_button.grid(row=1, column=0, padx=5, pady=5)

        self.test_button = tk.Button(self.device_frame, text="Test Connection", command=self.start_test_connection)
        self.test_button.grid(row=1, column=1, padx=5, pady=5)

        self.connect_button = tk.Button(self.device_frame, text="Connect Device", command=self.start_start_connect)
        self.connect_button.grid(row=1, column=2, padx=5, pady=5)

        self.disconnect_button = tk.Button(self.device_frame, text="Disconnect Device", command=self.disconnect_device)
        self.disconnect_button.grid(row=1, column=3, padx=5, pady=5)

        self.explore_button = tk.Button(self.device_frame, text="Explore Connected (BLE)", command=self.start_explore_ble)
        self.explore_button.grid(row=1, column=4, padx=5, pady=5)

        self.obex_button = tk.Button(self.device_frame, text="Browse Files (Classic OBEX)", command=self.open_obex_browser)
        self.obex_button.grid(row=1, column=5, padx=5, pady=5)

        self.pbap_button = tk.Button(self.device_frame, text="Fetch Contacts (PBAP/FTP)", command=self.open_contacts_browser)
        self.pbap_button.grid(row=1, column=6, padx=5, pady=5)

        self.map3d_button = tk.Button(self.device_frame, text="3D Map (Seeds)", command=self.open_map3d_popup)
        self.map3d_button.grid(row=1, column=7, padx=5, pady=5)

        self.relabel_button = tk.Button(self.device_frame, text="Relabel Device", command=self.relabel_selected_device)
        self.relabel_button.grid(row=1, column=8, padx=5, pady=5)

        self.clearlabel_button = tk.Button(self.device_frame, text="Clear Label", command=self.clear_label_selected_device)
        self.clearlabel_button.grid(row=1, column=9, padx=5, pady=5)

        # Optional explicit button (kept, but we'll also run this automatically):
        self.scan_paired_button = tk.Button(
            self.device_frame, text="Scan Paired (Windows)", command=self.start_scan_paired_windows
        )
        self.scan_paired_button.grid(row=1, column=10, padx=5, pady=5)

        self.send_button = tk.Button(self.device_frame, text="Send Data", command=self.send_data_to_device)
        self.send_button.grid(row=2, column=0, padx=5, pady=5)

        self.receive_button = tk.Button(self.device_frame, text="Receive Data", command=self.receive_data_from_device)
        self.receive_button.grid(row=2, column=1, padx=5, pady=5)

        self.advertise_button = tk.Button(self.device_frame, text="Advertise as 'Bullish'",
                                          command=self.start_advertising)
        self.advertise_button.grid(row=2, column=2, padx=5, pady=5)

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

        # ---------- Wi‑Fi & Cellular panel ----------
        self.wifi_frame = tk.LabelFrame(root, text="Wi‑Fi & Cellular")
        self.wifi_frame.pack(fill="x", padx=18, pady=(0, 14))

        self.wifi_list = tk.Listbox(self.wifi_frame, width=120, height=10)
        self.wifi_list.grid(row=0, column=0, columnspan=6, padx=5, pady=5, sticky="we")

        self.scan_wifi_btn = tk.Button(self.wifi_frame, text="Scan Wi‑Fi", command=self.start_scan_wifi)
        self.scan_wifi_btn.grid(row=1, column=0, padx=5, pady=5)

        self.connect_wifi_btn = tk.Button(self.wifi_frame, text="Connect to Wi‑Fi", command=self.connect_wifi_selected)
        self.connect_wifi_btn.grid(row=1, column=1, padx=5, pady=5)

        self.scan_cell_btn = tk.Button(self.wifi_frame, text="Scan Cellular", command=self.start_scan_cellular)
        self.scan_cell_btn.grid(row=1, column=2, padx=5, pady=5)

        self.cell_list = tk.Listbox(self.wifi_frame, width=120, height=6)
        self.cell_list.grid(row=2, column=0, columnspan=6, padx=5, pady=(0,5), sticky="we")

        # ---------- Tuning panel (distance model) ----------
        self.tuner_frame = tk.Frame(root)
        self.tuner_frame.pack(fill="x", padx=18, pady=(0, 14))

        # Row 0: BLE + env n
        tk.Label(self.tuner_frame, text="BLE Tx Power @1m (dBm):").grid(row=0, column=0, sticky="e", padx=4)
        tk.Label(self.tuner_frame, text="Environment n (1.5–4.0):").grid(row=0, column=2, sticky="e", padx=4)

        self.tx_power_1m_default = -59.0
        self.path_loss_n = 2.0

        self.tx_power_var = tk.StringVar(value=str(self.tx_power_1m_default))
        self.n_var = tk.StringVar(value=str(self.path_loss_n))

        self.tx_power_entry = tk.Entry(self.tuner_frame, width=8, textvariable=self.tx_power_var)
        self.n_entry = tk.Entry(self.tuner_frame, width=8, textvariable=self.n_var)

        self.tx_power_entry.grid(row=0, column=1, sticky="w", padx=4)
        self.n_entry.grid(row=0, column=3, sticky="w", padx=4)

        # Row 1: Wi‑Fi + Cellular reference powers
        tk.Label(self.tuner_frame, text="Wi‑Fi Tx @1m (dBm):").grid(row=1, column=0, sticky="e", padx=4)
        tk.Label(self.tuner_frame, text="Cell Tx @1m (dBm):").grid(row=1, column=2, sticky="e", padx=4)

        self.wifi_tx_power_var = tk.StringVar(value="-45.0")  # typical ~-40 to -50 perceived @1m
        self.cell_tx_power_var = tk.StringVar(value="-35.0")  # very rough reference

        tk.Entry(self.tuner_frame, width=8, textvariable=self.wifi_tx_power_var).grid(row=1, column=1, sticky="w", padx=4)
        tk.Entry(self.tuner_frame, width=8, textvariable=self.cell_tx_power_var).grid(row=1, column=3, sticky="w", padx=4)

        self.apply_button = tk.Button(self.tuner_frame, text="Apply Tuning", command=self.apply_tuning)
        self.apply_button.grid(row=0, column=4, rowspan=2, padx=(10, 0))

        # ---------- Log ----------
        self.log_text = scrolledtext.ScrolledText(root, width=120, height=10, state='disabled')
        self.log_text.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        ioncore_branding.style_card(self.device_frame, self.branding)
        ioncore_branding.style_label_frame(self.wifi_frame, self.branding)
        ioncore_branding.style_card(self.tuner_frame, self.branding)
        ioncore_branding.style_widget(self.log_text, self.branding)

        # ---------- Data ----------
        self.devices = []           # [("BLE", bleak_device or proxy) | ("Classic", dict)]
        self.connection_results = {}
        self.connected_socket = None
        self.ble_client = None
        self.server_sock = None

        self.ble_meta = {}          # addr -> {rssi, tx_power, ...}
        self.wifi_networks = []     # list[dict]
        self.wifi_meta = {}         # bssid -> metadata (distance, qual, etc.)
        self.cell_infos = []        # list[dict]

        # BLE Explorer
        self.explorer_win = None
        self.explorer_text = None
        self.last_services = None

        # OBEX Browser state
        self.obex = {"win": None, "list": None, "path_var": None, "client": None, "addr": None, "port": None, "items": []}

        # Contacts window state
        self.contacts = {"win": None, "list": None, "log": None, "data": []}

        # 3D Seeds Map state
        self.map3d = {
            "win": None, "fig": None, "ax": None, "canvas": None,
            "animate_var": None, "anim_on": False, "timer": None,
            "trees": [], "targets": [], "bases": [], "labels": [],
            "radial_scale": 1.0,          # meters -> meters on plot (1:1)
            "classic_default_dist": 8.0,  # default meters when we can't estimate Classic distance
            "growth_rate": 0.06,          # meters per tick
            "cid_scroll": None            # mpl scroll callback id
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
        if not HAVE_WINRT and IS_WINDOWS:
            self.log("winrt not installed; paired-device enumeration (stable iPhone IDs) disabled.")

        # Set title with geocoded location (best-effort)
        gps_coords = self.get_gps_coordinates()
        lat, lon = gps_coords
        title = f"Ioncore Device Orchestrator – GPS {lat:.6f}, {lon:.6f}"
        if HAVE_GEOPY:
            try:
                geolocator = Nominatim(user_agent="expanded_bluetooth_manager")
                loc = geolocator.reverse(f"{lat},{lon}")
                if loc and getattr(loc, "address", None):
                    title = f"Ioncore Device Orchestrator – {loc.address}"
            except Exception:
                pass
        self.root.title(title)

        # === Range qualification / smoothing ===
        self.dist_filter = DistanceFilter(window=12, ema_alpha=0.30, min_m=0.25, max_m=40.0)

        # === Auto-scan on launch ===
        self.root.after(600, self.start_scan_devices)
        self.root.after(900, self.start_scan_wifi)

    # ---------- Async loop ----------
    @staticmethod
    def _run_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def run_coro(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    # ---------- DB helpers ----------
    def _init_db(self):
        try:
            self.db = sqlite3.connect("bt_devices.db")
            cur = self.db.cursor()
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
            cur = self.db.cursor()
            cur.execute("SELECT label FROM devices WHERE addr= ?", (addr,))
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            self.log(f"DB read error: {e}")
            return None

    def db_set_label(self, addr: str, label: str):
        try:
            cur = self.db.cursor()
            cur.execute("INSERT INTO devices(addr,label) VALUES(?,?) ON CONFLICT(addr) DO UPDATE SET label=excluded.label", (addr, label))
            self.db.commit()
        except Exception as e:
            self.log(f"DB write error: {e}")

    def db_clear_label(self, addr: str):
        try:
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

    # ---------- Utility ----------
    def get_gps_coordinates(self):
        # Replace with real GPS if available
        return (40.730610, -73.935242)

    @staticmethod
    def _format_bt_addr_from_ulong(addr_ulong: int) -> str:
        # Convert 64-bit Windows BluetoothAddress to "AA:BB:CC:DD:EE:FF"
        return ":".join(f"{(addr_ulong >> shift) & 0xFF:02X}" for shift in (40, 32, 24, 16, 8, 0))

    # ---------- Distance ----------
    def _heuristic_tx_power(self, addr: str, manufacturer_ids):
        """Prefer adv tx_power; else guess by vendor; else UI default."""
        if manufacturer_ids and any(mid.lower() == "0x004c" for mid in manufacturer_ids):
            return -59.0
        return float(self.tx_power_var.get().strip() or -62.0)

    def estimate_distance(self, rssi, tx_power=None, n=None, clamp=True):
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
            dist = self.dist_filter.clamp_distance(dist)
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

    # ---------- Scan (Bluetooth) ----------
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

        gps_coords = f"{self.get_gps_coordinates()[0]:.6f}, {self.get_gps_coordinates()[1]:.6f}"

        # BLE (active advertising)
        self.log("Starting BLE device scan (with adv data + smoothing)...")
        ble_results = []
        try:
            ble_results = await self._scan_ble_with_adv(scan_time=6.0)
        except (BleakError, OSError) as e:
            self.log("BLE scan failed: " + str(e))
        for device, adv, ema_rssi in ble_results:
            addr = device.address
            stored_label = self.db_get_label(addr)
            fallback_name = device.name or getattr(adv, "local_name", None) or "[Unnamed Device]"
            name = stored_label or fallback_name

            # Prefer smoothed RSSI; fall back to last raw value
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

        # Classic (active discovery)
        if HAVE_PYBLUEZ:
            self.log("Starting Classic Bluetooth device scan...")
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

        # Windows: merge **paired** devices (iPhones often show up reliably here)
        if IS_WINDOWS and HAVE_WINRT:
            await self.scan_paired_windows()  # appends + refreshes

    # ---------- Windows paired enumeration (auto + optional button) ----------
    def start_scan_paired_windows(self):
        if not (IS_WINDOWS and HAVE_WINRT):
            messagebox.showerror("Unavailable", "Paired scan requires Windows + 'winrt' package.")
            return
        self.run_coro(self.scan_paired_windows())

    async def scan_paired_windows(self):
        added = 0

        # ----- Paired BLE -----
        try:
            selector = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
            infos = await DeviceInformation.find_all_async(selector)
            for di in infos:
                try:
                    bledev = await BluetoothLEDevice.from_id_async(di.id)
                    addr = self._format_bt_addr_from_ulong(int(bledev.bluetooth_address))
                    name = bledev.name or di.name or "[Unnamed Device]"

                    # Skip if already listed
                    if any((t == "BLE" and getattr(d, "address", None) == addr) or
                           (t == "Classic" and isinstance(d, dict) and d.get("addr") == addr)
                           for t, d in self.devices):
                        # still store OS Id in metadata
                        self.ble_meta.setdefault(addr, {})["device_id"] = di.id
                        continue

                    # proxy object with required fields for list rendering
                    simple = type("SimpleBLEProxy", (), {})()
                    simple.address = addr
                    simple.name = name

                    # Smoothing / qualification data may already exist
                    d_m = self.ble_meta.get(addr, {}).get("distance_m")
                    bucket = self.ble_meta.get(addr, {}).get("range_label")
                    qual = self.ble_meta.get(addr, {}).get("qual")

                    self.devices.append(("BLE", simple))
                    meta = self.ble_meta.setdefault(addr, {})
                    meta.setdefault("name", name)
                    meta["paired"] = True
                    meta["device_id"] = di.id   # stable Windows OS Id
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

        # ----- Paired Classic -----
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

    # ---------- Test / Connect (Bluetooth) ----------
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
        else:
            result = self.test_classic_connection(device_info)
            addr_key = device_info["addr"]

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
        txp = meta.get("tx_power", None)
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
        return (
            f"BLE: {name}{apple_tag} ({addr}) - {status} - RSSI {rssi} dBm (\n"
            f"  {dist_str}, Q:{qual}) - AddrType {addr_type} - SvcUUIDs {svc_cnt} - "
            f"Mfr {', '.join(mfr_ids) if mfr_ids else '—'} - GPS {gps_coords}{id_tail}"
        )

    def row_text_for_classic(self, info, status):
        name = info["name"]; addr = info["addr"]
        type_str = info.get("type_str", "Unknown")
        services = info.get("services", "No services found")
        dev_id = info.get("device_id")
        id_tail = f" | OS Id …{dev_id[-8:]}" if dev_id else ""
        return f"Classic: {name or '[Unnamed Device]'} ({addr}) - {status} - Distance: Unknown (Classic) - Type: {type_str} - Services: {services}{id_tail}"

    def update_device_list_entry(self, index, result, device, device_type):
        text = self.row_text_for_ble(device, result) if device_type == "BLE" else self.row_text_for_classic(device, result)
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
        else:
            self.connected_socket = self.connect_classic_device(device_info)
            success = self.connected_socket is not None

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
        else:
            return typ, dev["addr"], dev["name"]

    def relabel_selected_device(self):
        typ, addr, cur_name = self._selected_addr_and_type()
        if not addr:
            messagebox.showwarning("No Selection", "Select a device first.")
            return
        existing = self.db_get_label(addr) or (cur_name or "")
        new_label = simpledialog.askstring("Relabel Device", f"Enter a label for {addr}:", initialvalue=existing)
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
        self.log(f"Cleared label for {addr}")

    # ---------- Classic send/receive ----------
    def send_data_to_device(self):
        if self.connected_socket:
            try:
                msg = "Hello from Ioncore Python!"
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
            messagebox.showerror("Invalid Input", "BLE Tx Power must be a number (e.g., -59).")
            return
        try:
            n = float(self.n_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Input", "Environment n must be a number (e.g., 2.0).")
            return
        if not (1.5 <= n <= 4.0):
            messagebox.showwarning("Adjusted", "Environment n will be clamped to 1.5–4.0.")
            n = max(1.5, min(4.0, n))
        # Validate Wi‑Fi & Cell refs
        try:
            float(self.wifi_tx_power_var.get().strip())
            float(self.cell_tx_power_var.get().strip())
        except ValueError:
            messagebox.showwarning("Adjusted", "Wi‑Fi/Cell Tx@1m should be numeric; keeping previous values.")
        self.tx_power_1m_default = tx
        self.path_loss_n = n
        self.log(f"Applied tuning: BLE TxPower@1m={tx} dBm, n={n}, Wi‑Fi Tx@1m={self.wifi_tx_power_var.get()}, Cell Tx@1m={self.cell_tx_power_var.get()}")
        self.redraw_device_list()
        self.redraw_wifi_list()

    # ---------- Rendering (Bluetooth list) ----------
    def redraw_device_list(self, append_only=False):
        if not append_only:
            self.device_list.delete(0, tk.END)
        for device_type, dev in self.devices:
            if device_type == "BLE":
                status = self.connection_results.get(dev.address, "Not Tested")
                text = self.row_text_for_ble(dev, status)
                addr = dev.address
            else:
                status = self.connection_results.get(dev["addr"], "Not Tested")
                text = self.row_text_for_classic(dev, status)
                addr = dev["addr"]
            if append_only:
                exists = any(addr in self.device_list.get(i) for i in range(self.device_list.size()))
                if exists:
                    continue
            self.device_list.insert(tk.END, text)

    # ---------- Wi‑Fi & Cellular ----------
    def start_scan_wifi(self):
        threading.Thread(target=self._scan_wifi_thread, daemon=True).start()

    def _scan_wifi_thread(self):
        try:
            nets = []
            if IS_WINDOWS:
                nets = self._scan_wifi_windows()
            elif IS_MAC and os.path.exists(AIRPORT_BIN):
                nets = self._scan_wifi_macos()
            elif IS_LINUX:
                nets = self._scan_wifi_linux()
            else:
                self.log("Wi‑Fi scanning not supported on this OS.")
                nets = []
            # qualify distances & store
            qualified = []
            for nfo in nets:
                bssid = nfo.get('bssid') or f"SSID:{nfo.get('ssid','')}"
                key = f"WIFI:{bssid}"
                rssi = nfo.get('rssi')
                ema = self.dist_filter.push_rssi(key, rssi) if rssi is not None else None
                used_rssi = ema if ema is not None else rssi
                try:
                    tx_wifi = float(self.wifi_tx_power_var.get().strip())
                except Exception:
                    tx_wifi = -45.0
                d_m = self.estimate_distance(used_rssi, tx_power=tx_wifi, clamp=True)
                qual = self.dist_filter.quality_grade(key)
                bucket = self._range_bucket(d_m)
                nfo.update({
                    'rssi_smoothed': used_rssi,
                    'distance_m': d_m,
                    'range_label': bucket,
                    'qual': qual,
                })
                qualified.append(nfo)
            self.wifi_networks = qualified
            self.queue.put(self.redraw_wifi_list)
            self.log(f"Wi‑Fi scan complete: {len(self.wifi_networks)} network(s).")
        except Exception as e:
            self.log(f"Wi‑Fi scan failed: {e}")

    def _wifi_hotspot_guess(self, ssid):
        if not ssid:
            return False
        low = ssid.lower()
        markers = ["iphone", "android", "hotspot", "mobile", "pixel", "galaxy", "mi phone"]
        return any(m in low for m in markers)

    def _scan_wifi_windows(self):
        cmd = ["netsh", "wlan", "show", "networks", "mode=bssid"]
        try:
            out = subprocess.check_output(cmd, text=True, errors='ignore')
        except Exception as e:
            self.log(f"netsh wlan failed: {e}")
            return []
        nets = []
        current = {"ssid": "", "ntype": "", "auth": "", "encr": ""}
        ssid_re = re.compile(r"^SSID\s+\d+\s*:\s*(.*)$", re.I)
        bssid_re = re.compile(r"^\s*BSSID\s+\d+\s*:\s*([0-9A-Fa-f:]{17})")
        sig_re = re.compile(r"^\s*Signal\s*:\s*(\d+)%")
        chan_re = re.compile(r"^\s*Channel\s*:\s*(\d+)")
        ntype_re = re.compile(r"^\s*Network type\s*:\s*(.*)$")
        auth_re = re.compile(r"^\s*Authentication\s*:\s*(.*)$")
        encr_re = re.compile(r"^\s*Encryption\s*:\s*(.*)$")
        bssid_block = None
        for line in out.splitlines():
            m = ssid_re.match(line)
            if m:
                current = {"ssid": m.group(1).strip(), "ntype": "", "auth": "", "encr": ""}
                continue
            m = ntype_re.match(line)
            if m:
                current["ntype"] = m.group(1).strip(); continue
            m = auth_re.match(line)
            if m:
                current["auth"] = m.group(1).strip(); continue
            m = encr_re.match(line)
            if m:
                current["encr"] = m.group(1).strip(); continue
            m = bssid_re.match(line)
            if m:
                # start a new bssid block
                if bssid_block:
                    nets.append(bssid_block)
                bssid_block = {
                    "ssid": current.get("ssid",""),
                    "bssid": m.group(1).upper(),
                    "auth": current.get("auth",""),
                    "encr": current.get("encr",""),
                    "channel": None,
                    "signal_pct": None,
                }
                continue
            if bssid_block:
                m = sig_re.match(line)
                if m:
                    pct = int(m.group(1))
                    # Rough conversion: RSSI ~= (quality/2) - 100  (100->-50 dBm)
                    rssi = (pct / 2.0) - 100.0
                    bssid_block["signal_pct"] = pct
                    bssid_block["rssi"] = rssi
                    continue
                m = chan_re.match(line)
                if m:
                    bssid_block["channel"] = int(m.group(1))
                    continue
        if bssid_block:
            nets.append(bssid_block)
        # enrich
        for n in nets:
            ch = n.get("channel") or 0
            band = "5G" if ch and ch > 14 else "2.4G"
            n["band"] = band
            n["security"] = (n.get("auth") or "") + ("/" + n.get("encr") if n.get("encr") else "")
            n["hotspot"] = self._wifi_hotspot_guess(n.get("ssid",""))
        return nets

    def _scan_wifi_macos(self):
        try:
            out = subprocess.check_output([AIRPORT_BIN, "-s"], text=True, errors='ignore')
        except Exception as e:
            self.log(f"airport -s failed: {e}")
            return []
        nets = []
        # airport output: SSID BSSID RSSI CHANNEL HT CC SECURITY
        header = True
        for line in out.splitlines():
            if header:
                header = False
                continue
            if not line.strip():
                continue
            # Collapse multiple spaces; SSID may include spaces, so parse via regex
            m = re.match(r"^\s*(.*?)\s+([0-9A-Fa-f:]{17})\s+(-?\d+)\s+([\d,]+)\s+\S+\s+\S+\s+(.*)$", line)
            if not m:
                # fallback split
                parts = re.split(r"\s+", line.strip())
                if len(parts) < 4:
                    continue
                ssid = parts[0]
                bssid = parts[1]
                rssi = float(parts[2]) if parts[2].lstrip("-+").isdigit() else None
                ch = parts[3]
                sec = " ".join(parts[6:]) if len(parts) > 6 else ""
            else:
                ssid = m.group(1).strip()
                bssid = m.group(2).upper()
                rssi = float(m.group(3))
                ch = m.group(4)
                sec = m.group(5).strip()
            try:
                ch_int = int(str(ch).split(",")[0])
            except Exception:
                ch_int = None
            band = "5G" if (ch_int and ch_int > 14) else "2.4G"
            nets.append({
                "ssid": ssid,
                "bssid": bssid,
                "rssi": rssi,
                "channel": ch_int,
                "band": band,
                "security": sec,
                "hotspot": self._wifi_hotspot_guess(ssid)
            })
        return nets

    def _scan_wifi_linux(self):
        nets = []
        if shutil.which("nmcli"):
            try:
                # terse output: fields separated by ':'; SSID may be empty
                out = subprocess.check_output(["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,SECURITY,CHAN", "dev", "wifi", "list"], text=True, errors='ignore')
                for line in out.splitlines():
                    if not line.strip():
                        continue
                    parts = line.split(":")
                    # nmcli may emit extra ':' inside SSID if SSID contains ':'; handle conservatively
                    if len(parts) < 5:
                        continue
                    # last 3 fields are always SIGNAL, SECURITY, CHAN
                    ssid = ":".join(parts[:-4+1]) if len(parts) > 5 else parts[0]
                    # Better: recompute indexes from end
                    ssid = parts[0]
                    bssid = parts[1].upper()
                    signal_pct = parts[2]
                    security = parts[3]
                    try:
                        chan = int(parts[4])
                    except Exception:
                        chan = None
                    try:
                        pct = int(signal_pct)
                        rssi = (pct / 2.0) - 100.0
                    except Exception:
                        rssi = None
                    band = "5G" if (chan and chan > 14) else "2.4G"
                    nets.append({
                        "ssid": ssid,
                        "bssid": bssid,
                        "signal_pct": int(signal_pct) if signal_pct.isdigit() else None,
                        "rssi": rssi,
                        "channel": chan,
                        "band": band,
                        "security": security,
                        "hotspot": self._wifi_hotspot_guess(ssid)
                    })
            except Exception as e:
                self.log(f"nmcli scan failed: {e}")
        elif shutil.which("iwlist"):
            # fallback parser for iwlist
            try:
                out = subprocess.check_output(["iwlist", "scan"], text=True, errors='ignore')
                block = {}
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("Cell ") and "Address:" in line:
                        if block:
                            nets.append(block)
                        m = re.search(r"Address: ([0-9A-Fa-f:]{17})", line)
                        block = {"bssid": m.group(1).upper() if m else None}
                    elif "ESSID:" in line:
                        ssid = line.split("ESSID:",1)[1].strip().strip('"')
                        block["ssid"] = ssid
                    elif "Channel" in line and "Channel:" in line:
                        try:
                            ch = int(line.split("Channel:",1)[1].strip())
                        except Exception:
                            ch = None
                        block["channel"] = ch
                    elif "Signal level=" in line:
                        m = re.search(r"Signal level=(-?\d+) dBm", line)
                        if m:
                            block["rssi"] = float(m.group(1))
                if block:
                    nets.append(block)
                for n in nets:
                    ch = n.get("channel") or 0
                    n["band"] = "5G" if ch and ch > 14 else "2.4G"
                    n["security"] = n.get("security", "?")
                    n["hotspot"] = self._wifi_hotspot_guess(n.get("ssid",""))
            except Exception as e:
                self.log(f"iwlist scan failed: {e}")
        else:
            self.log("No nmcli/iwlist found for Wi‑Fi scanning.")
        return nets

    def redraw_wifi_list(self):
        self.wifi_list.delete(0, tk.END)
        for n in self.wifi_networks:
            ssid = n.get('ssid') or '(hidden)'
            bssid = n.get('bssid','??')
            rssi = n.get('rssi_smoothed', n.get('rssi'))
            pct = n.get('signal_pct')
            ch = n.get('channel')
            band = n.get('band','?')
            sec = n.get('security','?')
            bucket = n.get('range_label','Unknown')
            d_m = n.get('distance_m')
            qual = n.get('qual','D')
            hot = ' 🔥hotspot' if n.get('hotspot') else ''
            sig_str = f"{pct}%" if isinstance(pct,(int,float)) else (f"{rssi:.0f} dBm" if isinstance(rssi,(int,float)) else "?")
            dist_str = f"~{d_m:.1f} m" if isinstance(d_m,(int,float)) else "~? m"
            row = f"Wi‑Fi: {ssid}{hot} ({bssid}) – Signal {sig_str} – Ch {ch} {band} – Sec {sec} – {bucket} {dist_str} Q:{qual}"
            self.wifi_list.insert(tk.END, row)

    def connect_wifi_selected(self):
        idxs = self.wifi_list.curselection()
        if not idxs:
            messagebox.showwarning("No Selection", "Select a Wi‑Fi network first.")
            return
        net = self.wifi_networks[idxs[0]]
        ssid = net.get('ssid')
        if not ssid:
            messagebox.showerror("Hidden SSID", "Connecting to hidden SSIDs is not supported in this quick connect.")
            return
        pwd = simpledialog.askstring("Wi‑Fi Password (optional)", f"Enter password for SSID '{ssid}' (leave blank if open):", show='*')
        threading.Thread(target=self._connect_wifi_os, args=(ssid, pwd or ""), daemon=True).start()

    def _connect_wifi_os(self, ssid: str, password: str):
        try:
            if IS_WINDOWS:
                # Try simple connect (requires existing profile)
                try:
                    subprocess.check_call(["netsh", "wlan", "connect", f"ssid={ssid}", f"name={ssid}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.log(f"Requested connection to Wi‑Fi SSID '{ssid}' (Windows profile).")
                    return
                except Exception:
                    if not password:
                        self.log("No existing profile and no password provided.")
                        messagebox.showinfo("Windows Wi‑Fi", "Windows requires a saved profile or a password.")
                        return
                    # Create a temporary WPA2 profile XML and add it
                    profile_xml = f"""<?xml version=\"1.0\"?>
<WLANProfile xmlns=\"http://www.microsoft.com/networking/WLAN/profile/v1\">
  <name>{ssid}</name>
  <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>manual</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
      <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>{password}</keyMaterial>
      </sharedKey>
    </security>
  </MSM>
</WLANProfile>"""
                    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.xml') as tmp:
                        tmp.write(profile_xml)
                        tmp_path = tmp.name
                    try:
                        subprocess.check_call(["netsh", "wlan", "add", "profile", f"filename={tmp_path}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.check_call(["netsh", "wlan", "connect", f"ssid={ssid}", f"name={ssid}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        self.log(f"Added profile and requested connection to '{ssid}'.")
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
            elif IS_LINUX and shutil.which("nmcli"):
                args = ["nmcli", "dev", "wifi", "connect", ssid]
                if password:
                    args += ["password", password]
                try:
                    out = subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)
                    self.log(out.strip())
                except subprocess.CalledProcessError as e:
                    self.log(f"nmcli connect failed: {e.output}")
                    messagebox.showerror("Wi‑Fi connect", f"nmcli failed:\n{e.output}")
            elif IS_MAC:
                # find Wi‑Fi device name
                try:
                    hw = subprocess.check_output(["networksetup", "-listallhardwareports"], text=True)
                    dev = None
                    cur = {}
                    for ln in hw.splitlines():
                        if ln.startswith("Hardware Port: "):
                            cur = {"port": ln.split(": ",1)[1].strip()}
                        elif ln.startswith("Device: "):
                            cur["device"] = ln.split(": ",1)[1].strip()
                        elif not ln.strip() and cur:
                            if cur.get("port") == "Wi-Fi" and cur.get("device"):
                                dev = cur.get("device"); break
                            cur = {}
                    if not dev:
                        dev = "en0"
                    args = ["networksetup", "-setairportnetwork", dev, ssid]
                    if password:
                        args.append(password)
                    subprocess.check_call(args)
                    self.log(f"Requested connection to '{ssid}' on {dev}.")
                except Exception as e:
                    self.log(f"macOS connect failed: {e}")
                    messagebox.showerror("Wi‑Fi connect", f"macOS connect failed: {e}")
            else:
                messagebox.showinfo("Wi‑Fi", "Programmatic Wi‑Fi connect not supported on this OS.")
        except Exception as e:
            self.log(f"Wi‑Fi connect error: {e}")

    def start_scan_cellular(self):
        threading.Thread(target=self._scan_cellular_thread, daemon=True).start()

    def _scan_cellular_thread(self):
        infos = []
        try:
            if IS_WINDOWS:
                try:
                    # Show interfaces (signal bars) & visible providers
                    out = subprocess.check_output(["netsh", "mbn", "show", "interfaces"], text=True, errors='ignore')
                    cur = {}
                    for ln in out.splitlines():
                        if ln.strip().startswith("Name            :"):
                            if cur:
                                infos.append(cur); cur = {}
                            cur["name"] = ln.split(":",1)[1].strip()
                        elif ln.strip().startswith("State           :"):
                            cur["state"] = ln.split(":",1)[1].strip()
                        elif ln.strip().startswith("Signal          :"):
                            cur["signal_bars"] = ln.split(":",1)[1].strip()
                        elif ln.strip().startswith("Provider Name   :"):
                            cur["provider"] = ln.split(":",1)[1].strip()
                    if cur:
                        infos.append(cur)
                except Exception as e:
                    self.log(f"netsh mbn interfaces failed: {e}")
                try:
                    out = subprocess.check_output(["netsh", "mbn", "show", "visible"], text=True, errors='ignore')
                    # This lists visible providers; append as sighting entries
                    provs = []
                    for m in re.finditer(r"Provider Name\s*:\s*(.*)", out):
                        provs.append(m.group(1).strip())
                    if provs:
                        infos.append({"visible_providers": ", ".join(sorted(set(provs)))})
                except Exception:
                    pass
            elif IS_LINUX and shutil.which("mmcli"):
                try:
                    out = subprocess.check_output(["mmcli", "-L"], text=True, errors='ignore')
                    for m in re.finditer(r"/Modem/(\d+)", out):
                        mid = m.group(1)
                        try:
                            sig = subprocess.check_output(["mmcli", "-m", mid, "--signal-get"], text=True, errors='ignore')
                            rsrp = re.search(r"lte\s*\|\s*rsrp:\s*(-?\d+)", sig)
                            rssi = re.search(r"rssi:\s*(-?\d+)", sig)
                            infos.append({"modem": mid, "rsrp": rsrp.group(1) if rsrp else None, "rssi": rssi.group(1) if rssi else None})
                        except Exception:
                            pass
                except Exception as e:
                    self.log(f"mmcli failed: {e}")
            elif IS_MAC:
                try:
                    out = subprocess.check_output(["system_profiler", "SPWWANDataType"], text=True, errors='ignore')
                    # very verbose; extract a few fields
                    cur = {}
                    for ln in out.splitlines():
                        if ln.strip().startswith("Carrier:"):
                            cur["provider"] = ln.split(":",1)[1].strip()
                        if ln.strip().startswith("Current Network:"):
                            cur["network"] = ln.split(":",1)[1].strip()
                        if ln.strip().startswith("Signal Strength:") or ln.strip().startswith("RSSI:"):
                            cur["signal"] = ln.split(":",1)[1].strip()
                    if cur:
                        infos.append(cur)
                except Exception as e:
                    self.log(f"system_profiler SPWWANDataType failed: {e}")
        finally:
            self.cell_infos = infos
            self.queue.put(self.redraw_cell_list)
            self.log(f"Cellular scan complete: {len(infos)} record(s).")

    def redraw_cell_list(self):
        self.cell_list.delete(0, tk.END)
        if not self.cell_infos:
            self.cell_list.insert(tk.END, "(No cellular info found / not available)")
            return
        for ci in self.cell_infos:
            if 'visible_providers' in ci:
                self.cell_list.insert(tk.END, f"Visible providers: {ci['visible_providers']}")
                continue
            parts = []
            if ci.get('name'): parts.append(ci['name'])
            if ci.get('provider'): parts.append(ci['provider'])
            if ci.get('network'): parts.append(ci['network'])
            if ci.get('signal_bars'): parts.append(f"Signal {ci['signal_bars']}")
            if ci.get('rssi'): parts.append(f"RSSI {ci['rssi']} dBm")
            if ci.get('rsrp'): parts.append(f"RSRP {ci['rsrp']} dBm")
            self.cell_list.insert(tk.END, "Cell: " + " – ".join(parts) if parts else "Cell: (unknown)")

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

        # Build window
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

    # OBEX actions (run in background thread wrapper)
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
        if not HAVE_PYBLUEZ or not HAVE_PYOBEX:
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
                    ftp.setpath(b"/")
                    ftp.setpath(b"telecom")
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
        text = vcf_bytes.decode("utf-8", errors='ignore')
        # Unfold continuations
        lines = []
        for ln in text.splitlines():
            if ln.startswith((" ", "\t")) and lines:
                lines[-1] += ln[1:]
            else:
                lines.append(ln)
        cards = []
        cur = []
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
        win.title("3D Seeds Map – Direction & Depth")

        # Controls row
        ctrl = tk.Frame(win); ctrl.pack(fill="x", padx=8, pady=6)
        self.map3d["animate_var"] = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Seeds Mode (grow)", variable=self.map3d["animate_var"],
                       command=self._toggle_seed_animation).pack(side="left", padx=6)

        tk.Button(ctrl, text="Refresh From Scan", command=self._render_map3d).pack(side="left", padx=6)
        tk.Button(ctrl, text="Close", command=lambda: self._close_map3d()).pack(side="right", padx=6)

        # Figure
        fig = Figure(figsize=(8.5, 6.0))
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Depth (m)")  # z = -distance
        ax.set_title("Nearby signals as trees (direction from ID hash, depth from distance)")

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
        """Stable pseudo-direction from identifier. Returns radians [0, 2π)."""
        try:
            h = int(hashlib.sha1(addr.encode("utf-8")).hexdigest()[:8], 16)
        except Exception:
            h = abs(hash(addr))
        deg = h % 360
        return math.radians(deg)

    def _collect_positions(self):
        """Return seeds with approx position and target heights (BLE + Classic + Wi‑Fi)."""
        seeds = []
        # BLE
        for typ, dev in self.devices:
            if typ == "BLE":
                addr = dev.address
                meta = self.ble_meta.get(addr, {})
                name = (meta.get("name") or getattr(dev, "name", None) or meta.get("fallback_name") or "[Unnamed Device]").strip()
                d_m = meta.get("distance_m", None)
                if not isinstance(d_m, (int, float)) or d_m <= 0:
                    continue
                theta = self._angle_for_addr(addr)
                r = d_m * self.map3d["radial_scale"]
                x = r * math.cos(theta)
                y = r * math.sin(theta)
                z = -d_m
                target_height = max(0.5, 5.0 - 0.3 * d_m)
                seeds.append({"type": "BLE", "name": name, "addr": addr, "x": x, "y": y, "z": z,
                              "target": z + target_height})
            else:
                # Classic plotted with default range
                info = dev
                addr = info["addr"]
                name = info["name"]
                dist = self.map3d["classic_default_dist"]
                theta = self._angle_for_addr(addr)
                r = dist * self.map3d["radial_scale"]
                x = r * math.cos(theta)
                y = r * math.sin(theta)
                z = -dist
                target_height = max(0.5, 5.0 - 0.3 * dist)
                seeds.append({"type": "Classic", "name": name, "addr": addr, "x": x, "y": y, "z": z,
                              "target": z + target_height})
        # Wi‑Fi (per BSSID)
        for n in self.wifi_networks:
            bssid = n.get('bssid') or n.get('ssid') or 'wifi'
            d_m = n.get('distance_m')
            if not isinstance(d_m,(int,float)) or d_m <= 0:
                continue
            theta = self._angle_for_addr(bssid)
            r = d_m * self.map3d["radial_scale"]
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            z = -d_m
            target_height = max(0.5, 5.0 - 0.25 * d_m)
            name = (n.get('ssid') or '(hidden)') + (" 🔥" if n.get('hotspot') else "")
            seeds.append({"type": "Wi‑Fi", "name": name, "addr": bssid, "x": x, "y": y, "z": z,
                          "target": z + target_height})
        return seeds

    def _render_map3d(self):
        if not self.map3d["win"] or not tk.Toplevel.winfo_exists(self.map3d["win"]):
            return
        ax = self.map3d["ax"]
        canvas = self.map3d["canvas"]
        # preserve current limits to keep zoom level on refresh
        old_xlim = ax.get_xlim()
        old_ylim = ax.get_ylim()
        old_zlim = ax.get_zlim()

        ax.clear()
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Depth (m)")
        ax.set_title("Nearby signals as trees (direction from ID, depth from distance)")

        seeds = self._collect_positions()

        ax.plot([0], [0], [0], marker="o", markersize=5, color="k")
        ax.text(0, 0, 0, "Origin", fontsize=8)

        self.map3d["trees"].clear()
        self.map3d["targets"].clear()
        self.map3d["bases"].clear()
        self.map3d["labels"].clear()

        xs_ble, ys_ble, zs_ble = [], [], []
        xs_cla, ys_cla, zs_cla = [], [], []
        xs_wifi, ys_wifi, zs_wifi = [], [], []

        for s in seeds:
            x, y, z = s["x"], s["y"], s["z"]
            if s["type"] == "BLE":
                xs_ble.append(x); ys_ble.append(y); zs_ble.append(z)
                color = "#2e7d32"
            elif s["type"] == "Wi‑Fi":
                xs_wifi.append(x); ys_wifi.append(y); zs_wifi.append(z)
                color = "#ef6c00"
            else:
                xs_cla.append(x); ys_cla.append(y); zs_cla.append(z)
                color = "#1565c0"

            line, = ax.plot([x, x], [y, y], [z, z], linewidth=3, color=color)
            self.map3d["trees"].append(line)
            self.map3d["targets"].append(s["target"])
            self.map3d["bases"].append((x, y, z))
            lbl = ax.text(x, y, z, f"{s['name']}\n{s['addr']}", fontsize=7)
            self.map3d["labels"].append(lbl)

        if xs_ble:
            ax.scatter(xs_ble, ys_ble, zs_ble, s=30, marker="o", color="#66bb6a", label="BLE (seed)")
        if xs_wifi:
            ax.scatter(xs_wifi, ys_wifi, zs_wifi, s=30, marker="s", color="#ffb74d", label="Wi‑Fi (seed)")
        if xs_cla:
            ax.scatter(xs_cla, ys_cla, zs_cla, s=30, marker="^", color="#64b5f6", label="Classic (seed)")

        # Default bounds from data
        all_x = (xs_ble + xs_cla + xs_wifi) or [0]
        all_y = (ys_ble + ys_cla + ys_wifi) or [0]
        all_z = (zs_ble + zs_cla + zs_wifi) or [0]
        max_range = max(5.0, max(abs(min(all_x)), abs(max(all_x)),
                                 abs(min(all_y)), abs(max(all_y)),
                                 abs(min(all_z)), abs(max(all_z))))
        ax.set_xlim(-max_range, max_range)
        ax.set_ylim(-max_range, max_range)
        ax.set_zlim(-max_range, max_range * 0.6)

        # If user had zoomed before, restore their view
        if old_xlim != (0.0, 1.0) or old_ylim != (0.0, 1.0):
            try:
                ax.set_xlim(old_xlim)
                ax.set_ylim(old_ylim)
                ax.set_zlim(old_zlim)
            except Exception:
                pass

        ax.legend(loc="upper right", fontsize=8)
        canvas.draw_idle()

        # restart animation if toggle is on
        if self.map3d["animate_var"] and self.map3d["animate_var"].get():
            self._stop_seed_animation()
            self._start_seed_animation()
        else:
            self._stop_seed_animation()

    # ---------- Window close / cleanup ----------
    def on_close(self):
        self._close_map3d()
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

