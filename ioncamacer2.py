#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macer2.py — GUI-first MAC/BLE inspector
- Launches a Tkinter app by default.
- Open file/folder/zip, auto-scans, parses MACs, classifies them, and explains.
- Robust MAC detection (colon, hyphen, Cisco dotted, contiguous 12-hex) + OCR fixes.
- Optional vendor lookup (mac-vendor-lookup) and local ARP/ND enrichment.

Optional installs:
  pip install mac-vendor-lookup pandas openpyxl

Branding sync: index.html & webpage.html (2024-06-05) for brochure-aligned visuals.
"""

import argparse
import csv
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import zipfile
from typing import Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk

from ioncore_branding import (
    apply_ioncore_branding,
    brand_subtitle,
    brand_title,
)


# ---------------- Ioncore Branding -----------------
IONCORE_LOGO_SVG = """<svg width=\"160\" height=\"160\" viewBox=\"0 0 160 160\" xmlns=\"http://www.w3.org/2000/svg\">\n  <defs>\n    <linearGradient id=\"ioncoreGradient\" x1=\"0%\" y1=\"0%\" x2=\"100%\" y2=\"100%\">\n      <stop offset=\"0%\" stop-color=\"#00E0FF\"/>\n      <stop offset=\"100%\" stop-color=\"#4DFF9D\"/>\n    </linearGradient>\n  </defs>\n  <circle cx=\"80\" cy=\"80\" r=\"74\" fill=\"url(#ioncoreGradient)\"/>\n  <circle cx=\"80\" cy=\"80\" r=\"46\" fill=\"#060B1A\" opacity=\"0.94\"/>\n  <path d=\"M40 80c0-22.091 17.909-40 40-40s40 17.909 40 40-17.909 40-40 40S40 102.091 40 80zm52 0a12 12 0 10-24 0 12 12 0 0024 0z\" fill=\"#F4F9FF\" opacity=\"0.88\"/>\n  <path d=\"M34 64a60 60 0 0092 0\" stroke=\"#00E0FF\" stroke-width=\"6\" stroke-linecap=\"round\" fill=\"none\"/>\n  <path d=\"M34 96a60 60 0 0092 0\" stroke=\"#4DFF9D\" stroke-width=\"6\" stroke-linecap=\"round\" fill=\"none\"/>\n</svg>"""


def get_default_theme_mode(default: str = "dark") -> str:
    """Return the preferred Ioncore theme, honoring environment overrides."""
    mode = os.environ.get("IONCORE_THEME_MODE", "").strip().lower()
    if mode in {"light", "dark"}:
        return mode
    return default


def _hex_to_rgb(hex_color: str):
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
    start_rgb = _hex_to_rgb("#00E0FF")
    end_rgb = _hex_to_rgb("#4DFF9D")

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
        fill="#00E0FF",
    )
    draw.arc(
        [center - orbit_radius, center - orbit_radius, center + orbit_radius, center + orbit_radius],
        start=35,
        end=145,
        width=orbit_width,
        fill="#4DFF9D",
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
        fill="#00E0FF",
    )
    draw.rounded_rectangle(
        [center - bar_width * 0.9, center - bar_width * 0.9, center + bar_width * 0.9, center - bar_width * 0.35],
        radius=bar_radius,
        fill="#4DFF9D",
    )

    return ImageTk.PhotoImage(canvas)



# --------------------------- Robust MAC extraction ---------------------------

MAC_PATTERNS = [
    re.compile(r'(?:\b|^)(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?:\b|$)'),  # AA:BB:... or AA-BB-...
    re.compile(r'(?:\b|^)[0-9A-Fa-f]{4}(?:\.[0-9A-Fa-f]{4}){2}(?:\b|$)'),     # AABB.CCDD.EEFF
    re.compile(r'(?:\b|^)[0-9A-Fa-f]{12}(?:\b|$)'),                           # AABBCCDDEEFF
]
HEX12 = re.compile(r'^[0-9A-Fa-f]{12}$')

def _ocr_fix(s: str) -> str:
    table = str.maketrans({
        'O': '0', 'o': '0',
        'I': '1', 'l': '1',
        'S': '5', 's': '5',
        'B': '8',
    })
    return s.translate(table)

def normalize_mac_any(s: str) -> Optional[str]:
    if not isinstance(s, str):
        return None
    s = _ocr_fix(s)
    hexonly = re.sub(r'[^0-9A-Fa-f]', '', s)
    if len(hexonly) != 12 or not HEX12.fullmatch(hexonly):
        return None
    return ':'.join(hexonly[i:i+2].upper() for i in range(0, 12, 2))

def extract_macs_from_text(text: str) -> List[str]:
    hits: List[str] = []
    for pat in MAC_PATTERNS:
        for m in pat.findall(text or ""):
            mac = normalize_mac_any(m)
            if mac:
                hits.append(mac)
    seen, out = set(), []
    for mac in hits:
        if mac not in seen:
            seen.add(mac); out.append(mac)
    return out

# ------------------------------- Analysis ------------------------------------

def mac_bytes(mac: str) -> List[int]:
    return [int(p, 16) for p in mac.split(':')]

def ig_bit(b0: int) -> int:  # 0=unicast, 1=multicast
    return b0 & 0x01

def ul_bit(b0: int) -> int:  # 0=global/OUI, 1=local
    return (b0 >> 1) & 0x01

def first_octet_bits(b0: int) -> str:
    return f"{b0:08b}"

def ble_random_class(b0: int) -> Optional[str]:
    msb2 = (b0 >> 6) & 0b11
    return {
        0b11: "BLE Static Random (MSBs=11)",
        0b01: "BLE Resolvable Private (MSBs=01)",
        0b00: "BLE Non-Resolvable Private (MSBs=00)",
        0b10: "BLE Reserved/Uncommon (MSBs=10)"
    }.get(msb2)

def mac_to_int(mac: str) -> int:
    return int(mac.replace(':', ''), 16)

def vendor_lookup(mac: str, update: bool=False) -> Optional[str]:
    try:
        from mac_vendor_lookup import MacLookup  # optional
        ml = MacLookup()
        if update:
            ml.update_vendors()
        return ml.lookup(mac)
    except Exception:
        return None

KNOWN_TAGS = {
    "00:05:69":"VMware","00:50:56":"VMware","00:1C:14":"VMware","00:0C:29":"VMware",
    "52:54:00":"QEMU/KVM","00:16:3E":"Xen","08:00:27":"VirtualBox","02:42:AC":"Docker (172.* seed)",
    "F4:F5:D8":"Google (Nest/Cast)","3C:5A:B4":"Amazon (Echo/Fire)","B8:27:EB":"Raspberry Pi",
    "DC:A6:32":"Apple","F0:99:B6":"Apple",
}

def heuristic_tags(oui: str, vendor: Optional[str], locally_admin: bool) -> List[str]:
    tags: List[str] = []
    if locally_admin: tags.append("locally-administered")
    if oui in KNOWN_TAGS: tags.append(KNOWN_TAGS[oui])
    if vendor:
        v = vendor.lower()
        for key in ("apple","samsung","google","hon hai","murata","bose","tp-link","intel","raspberry"):
            if key in v:
                tags.append(key); break
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t); out.append(t)
    return out

def analyze_one(mac: str, use_vendor=False, update_vendors=False) -> Dict[str, Optional[str]]:
    b0 = mac_bytes(mac)[0]
    is_multicast = ig_bit(b0) == 1
    is_local = ul_bit(b0) == 1
    oui = ':'.join(mac.split(':')[:3])
    nic = ':'.join(mac.split(':')[3:])
    ble_hint = ble_random_class(b0)
    vend = vendor_lookup(mac, update=update_vendors) if use_vendor else None
    conf = "oui_match" if (vend and not is_local) else ("low (locally administered)" if (vend and is_local) else None)

    return {
        "mac": mac,
        "valid": "yes",
        "unicast_or_multicast": "multicast/group" if is_multicast else "unicast/individual",
        "admin": "locally administered" if is_local else "universally administered (OUI)",
        "locally_administered": "yes" if is_local else "no",
        "first_octet_hex": f"{b0:02X}",
        "first_octet_bits": first_octet_bits(b0),
        "ig_bit": str(ig_bit(b0)),
        "ul_bit": str(ul_bit(b0)),
        "ble_random_hint": ble_hint,
        "address_kind": "local/random" if is_local else "public (OUI)",
        "vendor": vend,
        "vendor_guess_confidence": conf,
        "oui": oui,
        "nic": nic,
        "mac_int": str(mac_to_int(mac)),
        "tags": ','.join(heuristic_tags(oui, vend, is_local)) or None,
        "ip": None,
        "iface": None,
    }

# -------------------------- Local enrichment (optional) -----------------------

def run_cmd(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""

def enrich_local_mac_map() -> Dict[str, Dict[str,str]]:
    out: Dict[str, Dict[str,str]] = {}
    sysname = platform.system().lower()

    def add(mac: str, ip: str, iface: str):
        m = normalize_mac_any(mac)
        if m: out[m] = {'ip': ip, 'iface': iface}

    if 'linux' in sysname or 'darwin' in sysname:
        txt = run_cmd(["ip", "neigh"])
        for line in txt.splitlines():
            m = re.search(r'(?P<ip>\d+\.\d+\.\d+\.\d+)\s+dev\s+(?P<if>\S+).*?lladdr\s+(?P<mac>[0-9a-f:]{17})', line, re.I)
            if m: add(m.group('mac'), m.group('ip'), m.group('if'))
        txt = run_cmd(["arp","-a"])
        for line in txt.splitlines():
            m = re.search(r'\((?P<ip>\d+\.\d+\.\d+\.\d+)\)\s+at\s+(?P<mac>[0-9a-f:]{17}).*?\s+on\s+(?P<if>\S+)', line, re.I)
            if m: add(m.group('mac'), m.group('ip'), m.group('if'))
        txt = run_cmd(["ndp","-an"])
        for line in txt.splitlines():
            m = re.search(r'(?P<ip>\d+\.\d+\.\d+\.\d+)\s+linklayer\s+(?P<mac>[0-9a-f:]{17})\s+.*(?P<if>en\d+)', line, re.I)
            if m: add(m.group('mac'), m.group('ip'), m.group('if'))
    elif 'windows' in sysname:
        txt = run_cmd(["arp","-a"])
        current_if = "unknown"
        for line in txt.splitlines():
            m_if = re.search(r'^Interface:\s+(\d+\.\d+\.\d+\.\d+)', line)
            if m_if:
                current_if = m_if.group(1); continue
            m = re.search(r'(?P<ip>\d+\.\d+\.\d+\.\d+)\s+(?P<mac>[0-9a-f\-]{17})\s+.*', line, re.I)
            if m:
                add(m.group('mac').replace('-', ':'), m.group('ip'), current_if)
    return out

# -------------------------- Reader: files/folders/zips ------------------------

def read_paths(paths: List[str]) -> List[Tuple[str, str]]:
    """
    Return list of (source_name, mac)
    - paths may be files, folders, or zip archives.
    - scans text-like files and CSV/JSON as raw text.
    """
    out: List[Tuple[str, str]] = []

    def scan_text(source: str, text: str):
        for mac in extract_macs_from_text(text):
            out.append((source, mac))

    def scan_file(path: str):
        low = path.lower()
        if low.endswith(('.txt','.log','.csv','.json','.tsv')):
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
                try:
                    txt = raw.decode('utf-8')
                except UnicodeDecodeError:
                    txt = raw.decode('latin-1', errors='ignore')
                scan_text(os.path.basename(path), txt)
            except Exception:
                pass
        elif low.endswith(('.xlsx','.xls')):
            try:
                import pandas as pd
                df = pd.read_excel(path, dtype=str)
                for col in df.columns:
                    series = df[col].astype(str).fillna("")
                    scan_text(os.path.basename(path), "\n".join(series.tolist()))
            except Exception:
                pass
        elif low.endswith('.zip'):
            try:
                with zipfile.ZipFile(path, 'r') as z:
                    for name in z.namelist():
                        nlow = name.lower()
                        if nlow.endswith(('.txt','.log','.csv','.json','.tsv')):
                            try:
                                data = z.read(name)
                                try:
                                    txt = data.decode('utf-8')
                                except UnicodeDecodeError:
                                    txt = data.decode('latin-1', errors='ignore')
                                scan_text(name, txt)
                            except Exception:
                                pass
                        # (Excel inside zip is skipped; unzip first if needed)
            except Exception:
                pass
        else:
            # Unknown type: attempt raw text
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
                try:
                    txt = raw.decode('utf-8')
                except UnicodeDecodeError:
                    txt = raw.decode('latin-1', errors='ignore')
                scan_text(os.path.basename(path), txt)
            except Exception:
                pass

    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for name in files:
                    scan_file(os.path.join(root, name))
        else:
            scan_file(p)

    seen, uniq = set(), []
    for src, mac in out:
        key = (src, mac)
        if key not in seen:
            seen.add(key); uniq.append((src, mac))
    return uniq

# ------------------------------ Explanations ----------------------------------

BLE_MAP = {
    "BLE Static Random (MSBs=11)": "Static Random: stable until device resets; fixed identity during a session.",
    "BLE Resolvable Private (MSBs=01)": "RPA: rotates; resolvable by paired devices via IRK keys.",
    "BLE Non-Resolvable Private (MSBs=00)": "NRPA: rotates frequently; not resolvable; used for anonymity.",
    "BLE Reserved/Uncommon (MSBs=10)": "Reserved/uncommon pattern.",
}

def explain_row(r: Dict[str, Optional[str]]) -> str:
    mac = r.get("mac","")
    uni = r.get("unicast_or_multicast","")
    adm = r.get("admin","")
    la  = r.get("locally_administered","")
    bhex = r.get("first_octet_hex","")
    bbits= r.get("first_octet_bits","")
    ig  = r.get("ig_bit","")
    ul  = r.get("ul_bit","")
    ble = r.get("ble_random_hint","") or ""
    ven = r.get("vendor") or "Unknown"
    oui = r.get("oui","")
    nic = r.get("nic","")
    macint = r.get("mac_int","")
    tags = r.get("tags") or ""
    ip   = r.get("ip") or ""
    iface= r.get("iface") or ""

    def bw(v: Optional[str]) -> str:
        return "Yes" if isinstance(v, str) and v.lower().startswith('y') else ("No" if isinstance(v, str) else "Unknown")

    ble_expl = BLE_MAP.get(ble, "Not identified as a BLE random address by first-octet MSBs.")
    lines = []
    lines.append(f"Address: {mac}")
    lines.append(f"Identity: {uni} | {adm} (Locally Administered: {bw(la)})")
    lines.append(f"First Octet: 0x{bhex} (bits {bbits}) → IG={ig} (0=unicast,1=multicast), UL={ul} (0=OUI,1=local)")
    lines.append(f"BLE Random Hint: {ble or 'none'} — {ble_expl if ble else ''}".strip())
    lines.append(f"OUI (vendor slice): {oui} | NIC (device slice): {nic or '(unknown)'}")
    lines.append(f"Vendor: {ven}  (confidence: {r.get('vendor_guess_confidence') or 'n/a'})")
    lines.append(f"Integer form: {macint or '(n/a)'}")
    if tags: lines.append(f"Tags: {tags}")
    if ip or iface: lines.append(f"Local mapping: IP={ip or '—'}, Interface={iface or '—'}")
    lines.append("Note: MACs are identifiers; not decryptable into private data.")
    return "\n".join(lines)

# --------------------------------- Exports -----------------------------------

def export_csv(rows: List[Dict[str, Optional[str]]], path: str):
    if not rows: return
    keys = list(rows[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

def export_json(rows: List[Dict[str, Optional[str]]], path: str):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

def export_sqlite(rows: List[Dict[str, Optional[str]]], db_path: str):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            mac TEXT PRIMARY KEY,
            valid TEXT,
            unicast_or_multicast TEXT,
            admin TEXT,
            locally_administered TEXT,
            first_octet_hex TEXT,
            first_octet_bits TEXT,
            ig_bit TEXT,
            ul_bit TEXT,
            ble_random_hint TEXT,
            address_kind TEXT,
            vendor TEXT,
            vendor_guess_confidence TEXT,
            oui TEXT,
            nic TEXT,
            mac_int TEXT,
            tags TEXT,
            ip TEXT,
            iface TEXT,
            source TEXT
        )
    """)
    cur.executemany("""
        INSERT INTO addresses(
            mac, valid, unicast_or_multicast, admin, locally_administered,
            first_octet_hex, first_octet_bits, ig_bit, ul_bit, ble_random_hint,
            address_kind, vendor, vendor_guess_confidence, oui, nic, mac_int,
            tags, ip, iface, source
        ) VALUES (
            :mac, :valid, :unicast_or_multicast, :admin, :locally_administered,
            :first_octet_hex, :first_octet_bits, :ig_bit, :ul_bit, :ble_random_hint,
            :address_kind, :vendor, :vendor_guess_confidence, :oui, :nic, :mac_int,
            :tags, :ip, :iface, :source
        )
        ON CONFLICT(mac) DO UPDATE SET
            valid=excluded.valid,
            unicast_or_multicast=excluded.unicast_or_multicast,
            admin=excluded.admin,
            locally_administered=excluded.locally_administered,
            first_octet_hex=excluded.first_octet_hex,
            first_octet_bits=excluded.first_octet_bits,
            ig_bit=excluded.ig_bit,
            ul_bit=excluded.ul_bit,
            ble_random_hint=excluded.ble_random_hint,
            address_kind=excluded.address_kind,
            vendor=excluded.vendor,
            vendor_guess_confidence=excluded.vendor_guess_confidence,
            oui=excluded.oui,
            nic=excluded.nic,
            mac_int=excluded.mac_int,
            tags=excluded.tags,
            ip=excluded.ip,
            iface=excluded.iface,
            source=excluded.source
    """, rows)
    con.commit()
    con.close()

# ---------------------------------- GUI --------------------------------------

def launch_gui(auto_open_dialog=True):
    COLUMNS = [
        ("mac","MAC"),("unicast_or_multicast","Uni/Multicast"),("admin","Admin"),
        ("ble_random_hint","BLE"),("vendor","Vendor"),("oui","OUI"),
        ("ip","IP"),("iface","Interface"),("tags","Tags"),
    ]

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title(brand_title("MAC Atlas • Batch Inspector"))
            self.geometry("1200x720")
            self.minsize(1000, 640)

            self.theme_mode = get_default_theme_mode()
            self.branding = apply_ioncore_branding(self, mode=self.theme_mode)
            self.style = ttk.Style(self)
            try:
                self.style.theme_use("clam")
            except Exception:
                pass

            self.logo_large = self.branding.logo or create_ioncore_logo_image(120)
            self.logo_small = create_ioncore_logo_image(48)
            try:
                self.iconphoto(False, self.logo_small)
            except Exception:
                pass

            self._init_branding()

            top = ttk.Frame(self, padding=8); top.pack(side=tk.TOP, fill=tk.X)
            ttk.Label(top, text="Paste addresses (any format) or Open file/folder/zip:").pack(anchor="w")
            self.input_txt = tk.Text(top, height=5); self.input_txt.pack(fill=tk.X, pady=4)

            opts = ttk.Frame(top); opts.pack(fill=tk.X, pady=4)
            self.var_vendor = tk.BooleanVar(value=False)
            self.var_update = tk.BooleanVar(value=False)
            self.var_enrich = tk.BooleanVar(value=False)
            ttk.Button(opts, text="Open…", command=self.on_open).pack(side=tk.LEFT, padx=2)
            ttk.Button(opts, text="Open folder…", command=self.on_open_folder).pack(side=tk.LEFT, padx=2)
            ttk.Button(opts, text="Analyze", command=self.on_analyze).pack(side=tk.LEFT, padx=2)
            ttk.Checkbutton(opts, text="Vendor lookup", variable=self.var_vendor).pack(side=tk.RIGHT, padx=6)
            ttk.Checkbutton(opts, text="Refresh vendor DB", variable=self.var_update).pack(side=tk.RIGHT)
            ttk.Checkbutton(opts, text="Local enrichment (ARP/ND)", variable=self.var_enrich).pack(side=tk.RIGHT, padx=6)

            split = ttk.Panedwindow(self, orient=tk.HORIZONTAL); split.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            left = ttk.Frame(split); split.add(left, weight=3)
            self.tree = ttk.Treeview(left, columns=[c[0] for c in COLUMNS], show="headings")
            for key, title in COLUMNS:
                self.tree.heading(key, text=title); self.tree.column(key, width=120, stretch=True)
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=vsb.set); vsb.pack(side=tk.RIGHT, fill=tk.Y)
            self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

            right = ttk.Frame(split); split.add(right, weight=2)
            ttk.Label(right, text="Selected address details:").pack(anchor="w")
            self.details = tk.Text(right, height=18, wrap="word"); self.details.configure(state="disabled"); self.details.pack(fill=tk.BOTH, expand=False, pady=(2,8))
            ttk.Label(right, text="Summary:").pack(anchor="w")
            self.summary = tk.Text(right, height=12, wrap="word"); self.summary.configure(state="disabled"); self.summary.pack(fill=tk.BOTH, expand=True)

            self.status = tk.StringVar(value="Ready")
            self.status_label = tk.Label(self, textvariable=self.status, anchor="w", padx=10, pady=6)
            self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
            self.rows: List[Dict[str, Optional[str]]] = []

            # Auto-open dialog on start (so you can just pick and go)
            if auto_open_dialog:
                self.after(300, self.on_open)

            self.apply_theme()
            self.status.set(f"Ready ({self.theme_mode.title()} Mode)")

        def _init_branding(self):
            self.brand_frame = tk.Frame(self, bd=0, highlightthickness=0)
            self.brand_frame.pack(fill="x", pady=(12, 6))

            self.brand_logo = tk.Label(self.brand_frame, image=self.logo_large, borderwidth=0, highlightthickness=0)
            self.brand_logo.grid(row=0, column=0, rowspan=2, padx=(14, 20), pady=4, sticky="w")

            self.brand_title = tk.Label(
                self.brand_frame,
                text="Ioncore MAC Atlas",
                font=self.branding.fonts.get("title"),
                anchor="w",
            )
            self.brand_title.grid(row=0, column=1, sticky="w")

            tagline = brand_subtitle(
                "High-volume MAC intelligence for rapid Bluetooth and vendor discovery."
            )
            self.brand_tagline = tk.Label(
                self.brand_frame,
                text=tagline,
                font=self.branding.fonts.get("subtitle"),
                anchor="w",
                wraplength=720,
                justify="left",
            )
            self.brand_tagline.grid(row=1, column=1, sticky="w")

            self.theme_status = tk.Label(
                self.brand_frame,
                text="Dark Mode" if self.theme_mode == "dark" else "Light Mode",
                font=self.branding.fonts.get("small"),
                anchor="e",
            )
            self.theme_status.grid(row=0, column=2, sticky="e", padx=(16, 14))

            self.theme_button = tk.Button(
                self.brand_frame,
                text="Switch Theme",
                command=self.toggle_theme,
                padx=16,
                pady=6,
                relief="flat",
                cursor="hand2",
                bd=0,
                font=self.branding.fonts.get("button"),
            )
            self.theme_button.grid(row=1, column=2, sticky="e", padx=(16, 14), pady=(2, 4))

            self.brand_frame.columnconfigure(1, weight=1)

        def apply_theme(self):
            self.branding = apply_ioncore_branding(self, mode=self.theme_mode)
            colors = self.branding.colors
            if self.branding.logo is not None:
                self.logo_large = self.branding.logo
                self.brand_logo.configure(image=self.logo_large)
            self.brand_title.configure(font=self.branding.fonts.get("title"))
            self.brand_tagline.configure(font=self.branding.fonts.get("subtitle"))
            self.theme_status.configure(font=self.branding.fonts.get("small"))
            self.theme_button.configure(font=self.branding.fonts.get("button"))
            self.configure(bg=colors["bg"])

            self.brand_frame.configure(bg=colors["surface_alt"])
            self.brand_logo.configure(bg=colors["surface_alt"])
            self.brand_title.configure(bg=colors["surface_alt"], fg=colors["text"])
            self.brand_tagline.configure(bg=colors["surface_alt"], fg=colors["muted_text"])
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

            self.style.configure("TFrame", background=colors["surface"])
            self.style.configure("TLabelframe", background=colors["surface"])
            self.style.configure("TLabel", background=colors["surface"], foreground=colors["text"])
            self.style.configure("TCheckbutton", background=colors["surface"], foreground=colors["text"])
            self.style.map("TCheckbutton", background=[("active", colors["surface_alt"])], foreground=[("active", colors["text"])])
            self.style.configure("TButton", background=colors["accent"], foreground=colors["accent_fg"], padding=6)
            self.style.map(
                "TButton",
                background=[("active", colors["accent_alt"]), ("pressed", colors["accent_alt"])],
                foreground=[("active", colors["accent_fg"]), ("pressed", colors["accent_fg"])],
            )
            self.style.configure(
                "Treeview",
                background=colors["surface"],
                fieldbackground=colors["surface"],
                foreground=colors["text"],
                borderwidth=0,
                rowheight=24,
            )
            self.style.map("Treeview", background=[("selected", colors["accent"])], foreground=[("selected", colors["accent_fg"])])
            self.style.configure("Treeview.Heading", background=colors["surface_alt"], foreground=colors["text"], borderwidth=0)
            self.style.configure("TScrollbar", background=colors["surface"], troughcolor=colors["surface_alt"])

            for widget in (self.input_txt, self.details, self.summary):
                widget.configure(
                    bg=colors["entry_bg"],
                    fg=colors["entry_fg"],
                    insertbackground=colors["accent"],
                    highlightbackground=colors["border"],
                    highlightcolor=colors["accent"],
                )

            self.status_label.configure(bg=colors["surface_alt"], fg=colors["muted_text"])

            self.theme_button.configure(text="Switch to Light Mode" if self.theme_mode == "dark" else "Switch to Dark Mode")
            self.theme_status.configure(text="Dark Mode" if self.theme_mode == "dark" else "Light Mode")

            self.update_idletasks()

        def toggle_theme(self):
            self.theme_mode = "light" if self.theme_mode == "dark" else "dark"
            self.apply_theme()
            self.set_status(f"Ioncore theme switched to {self.theme_mode.title()} mode")

        def set_status(self, msg: str):
            self.status.set(msg); self.update_idletasks()

        def on_open(self):
            path = filedialog.askopenfilename(title="Open file", filetypes=[("All supported","*.txt *.log *.csv *.json *.tsv *.xlsx *.xls *.zip"), ("All files","*.*")])
            if not path: return
            addrs = [mac for _, mac in read_paths([path])]
            if not addrs:
                messagebox.showwarning("No MACs found", "File did not contain recognizable MAC addresses.")
                return
            self.input_txt.delete("1.0", tk.END); self.input_txt.insert("1.0", "\n".join(addrs))
            # Auto analyze after selecting a file
            self.on_analyze()

        def on_open_folder(self):
            folder = filedialog.askdirectory(title="Open folder")
            if not folder: return
            addrs = [mac for _, mac in read_paths([folder])]
            if not addrs:
                messagebox.showwarning("No MACs found", "Folder did not contain recognizable MAC addresses.")
                return
            self.input_txt.delete("1.0", tk.END); self.input_txt.insert("1.0", "\n".join(addrs))
            self.on_analyze()

        def parse_free_text(self, s: str) -> List[str]:
            return extract_macs_from_text(s or "")

        def analyze_list(self, addrs: List[str]) -> List[Dict[str, Optional[str]]]:
            use_vendor = bool(self.var_vendor.get() or self.var_update.get())
            update_vendors = bool(self.var_update.get())
            rows = [analyze_one(a, use_vendor=use_vendor, update_vendors=update_vendors) for a in addrs]
            if self.var_enrich.get():
                local = enrich_local_mac_map()
                for r in rows:
                    hit = local.get(r["mac"])
                    if hit:
                        r["ip"] = hit.get("ip"); r["iface"] = hit.get("iface")
            return rows

        def on_analyze(self):
            addrs = self.parse_free_text(self.input_txt.get("1.0", tk.END))
            if not addrs:
                return
            self.set_status(f"Analyzing {len(addrs)} address(es)…")
            self.rows = self.analyze_list(addrs)
            for item in self.tree.get_children(): self.tree.delete(item)
            for r in self.rows:
                self.tree.insert("", "end", values=[r.get(c[0],"") or "" for c in COLUMNS])
            self._update_summary(); self.set_status(f"Done. Rows: {len(self.rows)}")

        def on_row_select(self, event=None):
            sel = self.tree.selection()
            if not sel: return
            idx = self.tree.index(sel[0])
            if idx >= len(self.rows): return
            r = self.rows[idx]
            text = explain_row(r)
            self.details.configure(state="normal")
            self.details.delete("1.0", "end")
            self.details.insert("1.0", text)
            self.details.configure(state="disabled")

        def _update_summary(self):
            total = len(self.rows)
            by_admin = {"OUI/global":0, "local/random":0}
            by_ble = {}
            vendors = {}
            for r in self.rows:
                if r.get("locally_administered") == "yes": by_admin["local/random"] += 1
                else: by_admin["OUI/global"] += 1
                ble = r.get("ble_random_hint") or "none"; by_ble[ble] = by_ble.get(ble,0)+1
                v = r.get("vendor") or "Unknown"; vendors[v] = vendors.get(v,0)+1
            top_ven = sorted(vendors.items(), key=lambda kv: kv[1], reverse=True)[:8]
            lines = [
                f"Total addresses: {total}",
                f"Admin: OUI/global={by_admin['OUI/global']}, local/random={by_admin['local/random']}",
                "BLE types: " + ", ".join(f"{k}={v}" for k,v in by_ble.items() if v>0),
                "Top vendors: " + ", ".join(f"{k} ({v})" for k,v in top_ven)
            ]
            self.summary.configure(state="normal")
            self.summary.delete("1.0", "end")
            self.summary.insert("1.0", "\n".join(lines))
            self.summary.configure(state="disabled")

    App().mainloop()

# ----------------------------------- CLI -------------------------------------

def main():
    ap = argparse.ArgumentParser(description="GUI-first MAC/BLE inspector. Run without args to open the app.")
    ap.add_argument("paths", nargs="*", help="(Optional) Files/folders/zips to scan via CLI mode.")
    ap.add_argument("--cli", action="store_true", help="Use CLI mode instead of GUI.")
    ap.add_argument("-o", "--output", help="Output file (.csv or .json) for CLI mode.")
    ap.add_argument("--sqlite", help="Write/merge into SQLite DB at this path (CLI mode).")
    ap.add_argument("--vendor", action="store_true", help="Attempt vendor/OUI lookup (CLI mode).")
    ap.add_argument("--update-vendors", action="store_true", help="Refresh OUI DB (requires internet). Implies --vendor.")
    ap.add_argument("--enrich-local", action="store_true", help="Local IP/iface mapping via ARP/ND (CLI mode).")
    args = ap.parse_args()

    # Default to GUI unless --cli is provided
    if not args.cli:
        launch_gui(auto_open_dialog=True)
        return 0

    # --- CLI path (only if --cli is set) ---
    sources: List[Tuple[str, str]] = []
    if args.paths:
        sources += read_paths(args.paths)
    if not sources:
        print("No recognizable MAC addresses found (CLI). Use GUI (default) or provide paths.", file=sys.stderr)
        return 2

    seen_mac, uniq_macs, mac_src = set(), [], {}
    for src, mac in sources:
        if mac not in seen_mac:
            seen_mac.add(mac)
            uniq_macs.append(mac)
            mac_src[mac] = src

    use_vendor = bool(args.vendor or args.update_vendors)
    update_vendors = bool(args.update_vendors)
    rows = [analyze_one(m, use_vendor=use_vendor, update_vendors=update_vendors) for m in uniq_macs]

    local = enrich_local_mac_map() if args.enrich_local else {}
    for r in rows:
        r["source"] = mac_src.get(r["mac"])
        if r["mac"] in local:
            r["ip"] = local[r["mac"]].get("ip"); r["iface"] = local[r["mac"]].get("iface")

    if args.output:
        (export_json if args.output.lower().endswith(".json") else export_csv)(rows, args.output)
        print(f"[+] Wrote {len(rows)} rows to {args.output}")
    if args.sqlite:
        export_sqlite(rows, args.sqlite)
        print(f"[+] Upserted {len(rows)} rows into {args.sqlite} (table 'addresses')")

    if not args.output and not args.sqlite:
        cols = ["mac","unicast_or_multicast","admin","ble_random_hint","vendor","oui","ip","iface","tags","source"]
        print(" | ".join(c.ljust(24) for c in cols))
        for r in rows:
            print(" | ".join([(r.get(c) or "").ljust(24) for c in cols]))

    return 0

if __name__ == "__main__":
    sys.exit(main())
