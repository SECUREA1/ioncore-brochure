#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macer3.py — GUI-first MAC/BLE inspector with deep selection inspector
- Open file/folder/zip, auto-scans, classifies, enriches, and shows EVERYTHING.
- NEW: Right-side tabbed inspector (Overview, Metrics, Raw Context, Key/Value).
- NEW: Live filter, sortable columns, quick look popup, copy MAC, filtered export.

Optional installs:
  pip install mac-vendor-lookup pandas openpyxl

Branding sync: index.html & webpage.html (2024-06-05) for brochure-matched visuals.
"""

import argparse, csv, json, os, platform, re, sqlite3, subprocess, sys, zipfile
from statistics import mean
from typing import Dict, List, Optional, Tuple, Any
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk


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


IONCORE_THEMES = {
    "dark": {
        "bg": "#060B1A",
        "surface": "#101D38",
        "surface_alt": "#16254A",
        "accent": "#00E0FF",
        "accent_alt": "#4DFF9D",
        "accent_fg": "#041221",
        "text": "#F4F9FF",
        "muted_text": "#7FA7D9",
        "border": "#1E2A4A",
        "entry_bg": "#0F1F3A",
        "entry_fg": "#FFFFFF",
        "log_bg": "#0F1F3A",
        "log_fg": "#96E7FF",
    },
    "light": {
        "bg": "#F5F8FC",
        "surface": "#FFFFFF",
        "surface_alt": "#EEF4FF",
        "accent": "#007BFF",
        "accent_alt": "#34C759",
        "accent_fg": "#FFFFFF",
        "text": "#13233C",
        "muted_text": "#5B6D89",
        "border": "#CAD7EF",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#13233C",
        "log_bg": "#FFFFFF",
        "log_fg": "#0A3356",
    },
}

# --------------------------- Robust MAC extraction ---------------------------

MAC_PATTERNS = [
    re.compile(r'(?:\b|^)(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?:\b|$)'),
    re.compile(r'(?:\b|^)[0-9A-Fa-f]{4}(?:\.[0-9A-Fa-f]{4}){2}(?:\b|$)'),
    re.compile(r'(?:\b|^)[0-9A-Fa-f]{12}(?:\b|$)'),
]
HEX12 = re.compile(r'^[0-9A-Fa-f]{12}$')

def _ocr_fix(s: str) -> str:
    table = str.maketrans({'O':'0','o':'0','I':'1','l':'1','S':'5','s':'5','B':'8'})
    return s.translate(table)

def normalize_mac_any(s: str) -> Optional[str]:
    if not isinstance(s, str): return None
    s = _ocr_fix(s)
    hexonly = re.sub(r'[^0-9A-Fa-f]', '', s)
    if len(hexonly) != 12 or not HEX12.fullmatch(hexonly): return None
    return ':'.join(hexonly[i:i+2].upper() for i in range(0, 12, 2))

def extract_macs_from_text(text: str) -> List[str]:
    hits: List[str] = []
    for pat in MAC_PATTERNS:
        for m in pat.findall(text or ""):
            mac = normalize_mac_any(m)
            if mac: hits.append(mac)
    seen, out = set(), []
    for mac in hits:
        if mac not in seen:
            seen.add(mac); out.append(mac)
    return out

# ------------------------------- Analysis core --------------------------------

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
        from mac_vendor_lookup import MacLookup
        ml = MacLookup()
        if update: ml.update_vendors()
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
    # unique preserve order
    seen, out = set(), []
    for t in tags:
        if t not in seen: seen.add(t); out.append(t)
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

# --------------------------- Local enrichment (optional) ----------------------

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
            if m_if: current_if = m_if.group(1); continue
            m = re.search(r'(?P<ip>\d+\.\d+\.\d+\.\d+)\s+(?P<mac>[0-9a-f\-]{17})\s+.*', line, re.I)
            if m: add(m.group('mac').replace('-', ':'), m.group('ip'), current_if)
    return out

# --------------------- Radio export/log enrichment (parsers) ------------------

RE_TIME = re.compile(r'\b(?:time(?:stamp)?|ts)\s*[:=]\s*([0-9T:\-\.Z/\s]+)', re.I)
RE_RSSI = re.compile(r'\brssi\b\s*[:=]\s*(-?\d+)', re.I)
RE_TXP  = re.compile(r'\btx(?:\s*power|power|pwr)?\b\s*[:=]\s*(-?\d+)', re.I)
RE_CH   = re.compile(r'\bch(?:annel)?\b\s*[:=]\s*(\d+)', re.I)
RE_NAME = re.compile(r'\b(name|dev(?:ice)?\s*name)\b\s*[:=]\s*("?)([^\n",]+)\2', re.I)
RE_ADV  = re.compile(r'\b(ADV[_\-\s]?(IND|NONCONN_IND|SCAN_IND|SCAN_RSP)|SCAN[_\-\s]?RSP|CONNECT[_\-\s]?REQ)\b', re.I)
RE_UUID = re.compile(r'\b(?:uuid|service(?:\s*uuid)?s?)\b\s*[:=]\s*(\[?[0-9a-f,\-\s\{\}x]+\]?)', re.I)
RE_COID = re.compile(r'\b(?:company|manuf(?:acturer)?)\b\s*[:=]\s*([A-Za-z0-9\-\s\(\)]+|0x[0-9A-Fa-f]{4})', re.I)
RE_IBEACON = re.compile(r'\bi\s*beacon\b', re.I)
RE_EDDYST  = re.compile(r'\beddy\s*stone\b', re.I)
RE_KV = re.compile(r'\b([A-Za-z][A-Za-z0-9_\-/ ]{1,20})\s*[:=]\s*([^\s,;|]+)')

def _safe_add(s: set, v: Any):
    if v is None: return
    v = str(v).strip()
    if v: s.add(v)

def _append_num(lst: list, v: Optional[str]):
    if v is None: return
    try: lst.append(int(v))
    except Exception: pass

def enrich_from_text_blocks(blocks: List[Tuple[str, str]]) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate per-MAC with many fields merged AND keep raw context lines.
    """
    per: Dict[str, Dict[str, Any]] = {}
    def ensure(mac: str) -> Dict[str, Any]:
        if mac not in per:
            per[mac] = {
                "_count": 0,
                "first_seen": None, "last_seen": None,
                "sources": set(), "rssi_vals": [], "txp_vals": [],
                "adv_types": set(), "channels": set(),
                "device_names": set(), "service_uuids": set(),
                "company_ids": set(), "frames": set(),
                "kv": {},          # generic k:v
                "ctx_lines": set() # raw lines where mac appeared
            }
        return per[mac]

    for src, text in blocks:
        for line in (text or "").splitlines():
            macs = extract_macs_from_text(line)
            if not macs: continue
            ts  = (RE_TIME.search(line) or [None,None])[1] if RE_TIME.search(line) else None
            rssi= (RE_RSSI.search(line) or [None,None])[1] if RE_RSSI.search(line) else None
            txp = (RE_TXP.search(line)  or [None,None])[1] if RE_TXP.search(line)  else None
            ch  = (RE_CH.search(line)   or [None,None])[1] if RE_CH.search(line)   else None
            name_m = RE_NAME.search(line)
            name = name_m.group(3).strip() if name_m else None
            adv_m = RE_ADV.findall(line)
            advs = [a[0].upper().replace(' ', '_').replace('-', '_') for a in adv_m] if adv_m else []
            uuids_m = RE_UUID.search(line)
            uuids_raw = uuids_m.group(1) if uuids_m else None
            company_m = RE_COID.search(line)
            company = company_m.group(1).strip() if company_m else None
            ibeacon = bool(RE_IBEACON.search(line))
            eddy    = bool(RE_EDDYST.search(line))
            kvs = RE_KV.findall(line)

            for mac in macs:
                d = ensure(mac)
                d["_count"] += 1
                _safe_add(d["sources"], src)
                _safe_add(d["ctx_lines"], line.strip())
                if ts:
                    if d["first_seen"] is None: d["first_seen"] = ts
                    d["last_seen"] = ts
                _append_num(d["rssi_vals"], rssi)
                _append_num(d["txp_vals"], txp)
                if ch: _safe_add(d["channels"], ch)
                if name: _safe_add(d["device_names"], name)
                for a in advs: _safe_add(d["adv_types"], a)
                if uuids_raw:
                    for piece in re.split(r'[\s,\[\]\{\}]+', uuids_raw):
                        piece = piece.strip()
                        if piece and (re.fullmatch(r'(0x)?[0-9A-Fa-f\-]{4,36}', piece) or len(piece) >= 4):
                            _safe_add(d["service_uuids"], piece.upper())
                if company: _safe_add(d["company_ids"], company)
                if ibeacon: _safe_add(d["frames"], "iBeacon")
                if eddy:    _safe_add(d["frames"], "Eddystone")
                for k, v in kvs:
                    k = k.strip().lower()
                    if len(k) < 2: continue
                    per[mac]["kv"].setdefault(k, set())
                    _safe_add(per[mac]["kv"][k], v)

    # finalize
    out: Dict[str, Dict[str, Any]] = {}
    for mac, d in per.items():
        summ: Dict[str, Any] = {
            "source": ",".join(sorted(d["sources"])) if d["sources"] else None,
            "first_seen": d["first_seen"], "last_seen": d["last_seen"],
            "observation_count": d["_count"],
            "rssi_min": min(d["rssi_vals"]) if d["rssi_vals"] else None,
            "rssi_max": max(d["rssi_vals"]) if d["rssi_vals"] else None,
            "rssi_avg": int(round(mean(d["rssi_vals"]))) if d["rssi_vals"] else None,
            "rssi_series": ",".join(str(x) for x in d["rssi_vals"]) if d["rssi_vals"] else None,
            "txp_values": ",".join(str(x) for x in sorted(set(d["txp_vals"]))) if d["txp_vals"] else None,
            "adv_types": ",".join(sorted(d["adv_types"])) if d["adv_types"] else None,
            "channels": ",".join(sorted(d["channels"])) if d["channels"] else None,
            "device_names": ",".join(sorted(d["device_names"])) if d["device_names"] else None,
            "service_uuids": ",".join(sorted(d["service_uuids"])) if d["service_uuids"] else None,
            "company_ids": ",".join(sorted(d["company_ids"])) if d["company_ids"] else None,
            "frames": ",".join(sorted(d["frames"])) if d["frames"] else None,
            "raw_context": "\n".join(sorted(d["ctx_lines"])) if d["ctx_lines"] else None,
        }
        for k, vals in d["kv"].items():
            summ[f"kv_{k.replace(' ','_')}"] = ",".join(sorted(str(x) for x in vals))
        out[mac] = summ
    return out

# -------------------------- Reader: files/folders/zips ------------------------

def _open_as_text(path: str) -> Optional[str]:
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        try: return raw.decode('utf-8')
        except UnicodeDecodeError: return raw.decode('latin-1', errors='ignore')
    except Exception:
        return None

def read_paths(paths: List[str]) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    sources: List[Tuple[str, str]] = []
    blocks:  List[Tuple[str, str]] = []

    def scan_text(source: str, text: str):
        if not text: return
        blocks.append((source, text))
        for mac in extract_macs_from_text(text):
            sources.append((source, mac))

    def scan_file(path: str):
        low = path.lower(); base = os.path.basename(path)
        if low.endswith(('.txt','.log','.csv','.json','.tsv')):
            txt = _open_as_text(path);
            if txt: scan_text(base, txt)
        elif low.endswith(('.xlsx','.xls')):
            try:
                import pandas as pd
                df = pd.read_excel(path, dtype=str)
                txt = "\n".join("\t".join(map(str,row)) for row in df.fillna("").astype(str).itertuples(index=False, name=None))
                scan_text(base, txt)
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
                                try: txt = data.decode('utf-8')
                                except UnicodeDecodeError: txt = data.decode('latin-1', errors='ignore')
                                scan_text(name, txt)
                            except Exception:
                                pass
                        # excel-in-zip skipped (unzip first if needed)
            except Exception:
                pass
        else:
            txt = _open_as_text(path)
            if txt: scan_text(base, txt)

    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for name in files: scan_file(os.path.join(root, name))
        else:
            scan_file(p)

    # de-dupe (source,mac)
    seen, uniq = set(), []
    for src, mac in sources:
        key = (src, mac)
        if key not in seen:
            seen.add(key); uniq.append((src, mac))
    return uniq, blocks

# ------------------------------ Explanations ----------------------------------

BLE_MAP = {
    "BLE Static Random (MSBs=11)": "Static Random: stable until device resets.",
    "BLE Resolvable Private (MSBs=01)": "RPA: rotates; resolvable with IRK by paired devices.",
    "BLE Non-Resolvable Private (MSBs=00)": "NRPA: rotates and is not resolvable.",
    "BLE Reserved/Uncommon (MSBs=10)": "Reserved/uncommon pattern.",
}

def explain_row(r: Dict[str, Optional[str]]) -> str:
    def bw(v: Optional[str]) -> str:
        return "Yes" if isinstance(v, str) and v.lower().startswith('y') else ("No" if isinstance(v, str) else "Unknown")
    lines = []
    lines.append(f"Address: {r.get('mac','')}")
    if r.get("unicast_or_multicast") or r.get("admin"):
        lines.append(f"Identity: {r.get('unicast_or_multicast','')} | {r.get('admin','')} (Locally Administered: {bw(r.get('locally_administered'))})")
    if r.get("first_octet_hex") and r.get("first_octet_bits"):
        lines.append(f"First Octet: 0x{r['first_octet_hex']} (bits {r['first_octet_bits']}) → IG={r.get('ig_bit','?')}, UL={r.get('ul_bit','?')}")
    if r.get("ble_random_hint"):
        lines.append(f"BLE Random Hint: {r['ble_random_hint']} — {BLE_MAP.get(r['ble_random_hint'], '')}")
    if r.get("oui") or r.get("nic"):
        lines.append(f"OUI: {r.get('oui','')} | NIC: {r.get('nic','')}")
    if r.get("vendor"):
        lines.append(f"Vendor: {r['vendor']} (confidence: {r.get('vendor_guess_confidence') or 'n/a'})")
    if r.get("mac_int"): lines.append(f"Integer form: {r['mac_int']}")
    if r.get("tags"): lines.append(f"Tags: {r['tags']}")
    if r.get("ip") or r.get("iface"):
        lines.append(f"Local mapping: IP={r.get('ip') or '—'}, Interface={r.get('iface') or '—'}")
    for k in ("first_seen","last_seen","observation_count","rssi_min","rssi_max","rssi_avg",
              "txp_values","adv_types","channels","device_names","service_uuids","company_ids","frames","source"):
        if r.get(k): lines.append(f"{k.replace('_',' ').title()}: {r[k]}")
    for key in sorted(r.keys()):
        if key.startswith("kv_") and r.get(key):
            lines.append(f"{key[3:].replace('_',' ').title()}: {r[key]}")
    lines.append("Note: MACs are identifiers; not decryptable into private data.")
    return "\n".join(lines)

# ------------------------------ UI: helpers ----------------------------------

def _sparkline_from_series(s: Optional[str]) -> str:
    # basic unicode sparkline from comma-separated ints (RSSI)
    if not s: return ""
    try:
        data = [int(x) for x in s.split(',') if x.strip()]
        if not data: return ""
        mn, mx = min(data), max(data)
        blocks = "▁▂▃▄▅▆▇█"
        span = (mx - mn) or 1
        idx = [int((x - mn) * (len(blocks)-1) / span) for x in data]
        return "".join(blocks[i] for i in idx)
    except Exception:
        return ""

# --------------------------------- Exports -----------------------------------

def export_csv(rows: List[Dict[str, Optional[str]]], path: str):
    if not rows: return
    all_keys = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k); all_keys.append(k)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=all_keys)
        w.writeheader()
        for r in rows: w.writerow({k: r.get(k) for k in all_keys})

def export_json(rows: List[Dict[str, Optional[str]]], path: str):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

def export_json_filtered(rows: List[Dict[str, Optional[str]]], columns: List[str], path: str):
    trimmed = [{k: r.get(k) for k in columns} for r in rows]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)

# ---------------------------------- GUI --------------------------------------

def launch_gui(auto_open_dialog=True):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Ioncore MAC Atlas • Deep Inspector")
            self.geometry("1380x820")
            self.minsize(1180, 720)

            self.theme_mode = get_default_theme_mode()
            self.style = ttk.Style(self)
            try:
                self.style.theme_use("clam")
            except Exception:
                pass

            self.logo_large = create_ioncore_logo_image(120)
            self.logo_small = create_ioncore_logo_image(48)
            try:
                self.iconphoto(False, self.logo_small)
            except Exception:
                pass

            self._init_branding()

            # Top bar
            top = ttk.Frame(self, padding=8); top.pack(side=tk.TOP, fill=tk.X)
            ttk.Label(top, text="Open file/folder/zip — auto-analysis. Paste is also supported.").pack(anchor="w")
            self.input_txt = tk.Text(top, height=3); self.input_txt.pack(fill=tk.X, pady=4)

            opts = ttk.Frame(top); opts.pack(fill=tk.X, pady=4)
            self.var_vendor = tk.BooleanVar(value=False)
            self.var_update = tk.BooleanVar(value=False)
            self.var_enrich = tk.BooleanVar(value=False)
            ttk.Button(opts, text="Open…", command=self.on_open).pack(side=tk.LEFT, padx=2)
            ttk.Button(opts, text="Open folder…", command=self.on_open_folder).pack(side=tk.LEFT, padx=2)
            ttk.Button(opts, text="Analyze", command=self.on_analyze).pack(side=tk.LEFT, padx=2)
            ttk.Button(opts, text="Export CSV…", command=self.on_export_csv).pack(side=tk.LEFT, padx=2)
            ttk.Button(opts, text="Export JSON (filtered)…", command=self.on_export_json_filtered).pack(side=tk.LEFT, padx=2)
            ttk.Checkbutton(opts, text="Vendor lookup", variable=self.var_vendor).pack(side=tk.RIGHT, padx=6)
            ttk.Checkbutton(opts, text="Refresh vendor DB", variable=self.var_update).pack(side=tk.RIGHT)
            ttk.Checkbutton(opts, text="Local enrichment (ARP/ND)", variable=self.var_enrich).pack(side=tk.RIGHT, padx=6)

            # Split layout
            self.split = ttk.Panedwindow(self, orient=tk.HORIZONTAL); self.split.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            self.left = ttk.Frame(self.split); self.split.add(self.left, weight=3)
            self.right = ttk.Frame(self.split); self.split.add(self.right, weight=2)

            # Filter + table
            fbar = ttk.Frame(self.left); fbar.pack(fill=tk.X, pady=(0,6))
            ttk.Label(fbar, text="Filter:").pack(side=tk.LEFT)
            self.filter_var = tk.StringVar()
            self.filter_var.trace_add("write", lambda *_: self._apply_filter())
            ttk.Entry(fbar, textvariable=self.filter_var, width=40).pack(side=tk.LEFT, padx=(6,10))
            self.tree = ttk.Treeview(self.left, show="headings")
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.vsb = ttk.Scrollbar(self.left, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=self.vsb.set); self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
            self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
            self.tree.bind("<Double-1>", self.on_quick_look)
            for ev in ("<Control-c>", "<Command-c>"): self.bind_all(ev, self.on_copy_mac)

            # Right: tabbed inspector
            self.tabs = ttk.Notebook(self.right); self.tabs.pack(fill=tk.BOTH, expand=True)
            # Overview
            self.tab_overview = ttk.Frame(self.tabs); self.tabs.add(self.tab_overview, text="Overview")
            self.over_txt = tk.Text(self.tab_overview, wrap="word"); self.over_txt.configure(state="disabled")
            self.over_txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            # Metrics
            self.tab_metrics = ttk.Frame(self.tabs); self.tabs.add(self.tab_metrics, text="Metrics")
            self.met_grid = ttk.Treeview(self.tab_metrics, columns=("k","v"), show="headings", height=10)
            self.met_grid.heading("k", text="Metric"); self.met_grid.heading("v", text="Value")
            self.met_grid.column("k", width=200); self.met_grid.column("v", width=560)
            self.met_grid.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6,0))
            self.spark_lbl = ttk.Label(self.tab_metrics, text="", anchor="w"); self.spark_lbl.pack(fill=tk.X, padx=6, pady=6)
            # Raw Context
            self.tab_raw = ttk.Frame(self.tabs); self.tabs.add(self.tab_raw, text="Raw Context")
            self.raw_txt = tk.Text(self.tab_raw, wrap="none")
            self.raw_txt.configure(state="disabled"); self.raw_txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            # Key/Value
            self.tab_kv = ttk.Frame(self.tabs); self.tabs.add(self.tab_kv, text="Key/Value")
            self.kv_grid = ttk.Treeview(self.tab_kv, columns=("k","v"), show="headings")
            self.kv_grid.heading("k", text="Key"); self.kv_grid.heading("v", text="Value")
            self.kv_grid.column("k", width=240); self.kv_grid.column("v", width=520)
            self.kv_grid.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

            self.status = tk.StringVar(value="Ready")
            self.status_label = tk.Label(self, textvariable=self.status, anchor="w", padx=10, pady=6)
            self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

            self.all_rows: List[Dict[str, Optional[str]]] = []   # full results
            self.view_rows: List[Dict[str, Optional[str]]] = []  # filtered view
            self.blocks: List[Tuple[str,str]] = []

            if auto_open_dialog: self.after(300, self.on_open)

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
                font=("Segoe UI", 23, "bold"),
                anchor="w",
            )
            self.brand_title.grid(row=0, column=1, sticky="w")

            self.brand_tagline = tk.Label(
                self.brand_frame,
                text="Enterprise-grade MAC intelligence with adaptive analytics and vendor insights.",
                font=("Segoe UI", 11),
                anchor="w",
                wraplength=820,
                justify="left",
            )
            self.brand_tagline.grid(row=1, column=1, sticky="w")

            self.theme_status = tk.Label(
                self.brand_frame,
                text="Dark Mode" if self.theme_mode == "dark" else "Light Mode",
                font=("Segoe UI", 10, "bold"),
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
            )
            self.theme_button.grid(row=1, column=2, sticky="e", padx=(16, 14), pady=(2, 4))

            self.brand_frame.columnconfigure(1, weight=1)

        def apply_theme(self):
            colors = IONCORE_THEMES[self.theme_mode]
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
            self.style.configure("TEntry", fieldbackground=colors["entry_bg"], foreground=colors["entry_fg"], bordercolor=colors["border"], insertcolor=colors["accent"])
            self.style.map("TEntry", fieldbackground=[("focus", colors["entry_bg"])] )
            self.style.configure("TNotebook", background=colors["surface"], tabmargins=(6, 4, 6, 0))
            self.style.configure("TNotebook.Tab", background=colors["surface_alt"], foreground=colors["text"], padding=(12, 6))
            self.style.map(
                "TNotebook.Tab",
                background=[("selected", colors["accent"]), ("active", colors["accent_alt"])],
                foreground=[("selected", colors["accent_fg"]), ("active", colors["accent_fg"])]
            )
            self.style.configure("Treeview", background=colors["surface"], fieldbackground=colors["surface"], foreground=colors["text"], borderwidth=0, rowheight=24)
            self.style.map("Treeview", background=[("selected", colors["accent"])], foreground=[("selected", colors["accent_fg"])])
            self.style.configure("Treeview.Heading", background=colors["surface_alt"], foreground=colors["text"], borderwidth=0)
            self.style.configure("TScrollbar", background=colors["surface"], troughcolor=colors["surface_alt"])
            self.style.configure("TPanedwindow", background=colors["surface"], sashrelief="flat")

            for widget in (self.input_txt, self.over_txt, self.raw_txt):
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

        # ----------------- small utils -----------------
        def set_status(self, msg: str): self.status.set(msg); self.update_idletasks()
        def _set_overview_text(self, s: str):
            self.over_txt.configure(state="normal"); self.over_txt.delete("1.0","end"); self.over_txt.insert("1.0", s); self.over_txt.configure(state="disabled")
        def _set_raw_text(self, s: str):
            self.raw_txt.configure(state="normal"); self.raw_txt.delete("1.0","end"); self.raw_txt.insert("1.0", s); self.raw_txt.configure(state="disabled")
        def _fill_grid(self, tv: ttk.Treeview, data: List[Tuple[str,str]]):
            for i in tv.get_children(): tv.delete(i)
            for k,v in data: tv.insert("", "end", values=(k, v))

        # ----------------- open / analyze -----------------
        def on_open(self):
            path = filedialog.askopenfilename(title="Open file", filetypes=[("All supported","*.txt *.log *.csv *.json *.tsv *.xlsx *.xls *.zip"), ("All files","*.*")])
            if not path: return
            sources, blocks = read_paths([path])
            if not sources and not blocks:
                messagebox.showwarning("No data found", "File did not contain recognizable MAC addresses or text.")
                return
            self.blocks = blocks
            addrs = [mac for _, mac in sources]
            self.input_txt.delete("1.0","end"); self.input_txt.insert("1.0","\n".join(addrs))
            self.on_analyze()

        def on_open_folder(self):
            folder = filedialog.askdirectory(title="Open folder")
            if not folder: return
            sources, blocks = read_paths([folder])
            if not sources and not blocks:
                messagebox.showwarning("No data found", "Folder did not contain recognizable MAC addresses or text.")
                return
            self.blocks = blocks
            addrs = [mac for _, mac in sources]
            self.input_txt.delete("1.0","end"); self.input_txt.insert("1.0","\n".join(addrs))
            self.on_analyze()

        def parse_free_text(self, s: str) -> List[str]:
            return extract_macs_from_text(s or "")

        def enrich_from_blocks(self) -> Dict[str, Dict[str, Any]]:
            return enrich_from_text_blocks(self.blocks)

        def analyze_list(self, addrs: List[str]) -> List[Dict[str, Optional[str]]]:
            use_vendor = bool(self.var_vendor.get() or self.var_update.get())
            update_vendors = bool(self.var_update.get())
            rows = [analyze_one(a, use_vendor=use_vendor, update_vendors=update_vendors) for a in addrs]
            if self.var_enrich.get():
                local = enrich_local_mac_map()
                for r in rows:
                    hit = local.get(r["mac"])
                    if hit: r["ip"] = hit.get("ip"); r["iface"] = hit.get("iface")
            radio = self.enrich_from_blocks() if self.blocks else {}
            for r in rows:
                extra = radio.get(r["mac"])
                if extra: r.update({k:v for k,v in extra.items() if v not in (None,"",[])})
            return rows

        def _set_columns(self, rows: List[Dict[str, Any]]):
            all_keys = set()
            for r in rows: all_keys.update(r.keys())
            preferred = [
                "mac","device_names","unicast_or_multicast","admin","locally_administered",
                "ble_random_hint","vendor","oui","ip","iface","tags","first_seen","last_seen",
                "observation_count","rssi_min","rssi_max","rssi_avg","adv_types","service_uuids",
                "company_ids","frames","channels","source"
            ]
            ordered = [k for k in preferred if k in all_keys]
            for k in sorted(all_keys - set(ordered)): ordered.append(k)
            # rebuild
            self.tree["columns"] = ordered
            for c in self.tree["columns"]:
                self.tree.heading(c, text=c, command=lambda col=c: self._sort_by(col))
                self.tree.column(c, width=150, stretch=True)

        def _render_table(self, rows: List[Dict[str, Any]]):
            for item in self.tree.get_children(): self.tree.delete(item)
            for r in rows:
                vals = [r.get(c,"") if r.get(c) is not None else "" for c in self.tree["columns"]]
                self.tree.insert("", "end", values=vals)

        def on_analyze(self):
            addrs = self.parse_free_text(self.input_txt.get("1.0","end"))
            if not addrs and not self.blocks: return
            self.set_status("Analyzing…")
            self.all_rows = self.analyze_list(addrs) or []
            if not self.all_rows and self.blocks:
                radio = self.enrich_from_blocks()
                addrs2 = list(radio.keys())
                self.all_rows = self.analyze_list(addrs2) or []
            if not self.all_rows:
                self.set_status("No MACs found."); return
            self._set_columns(self.all_rows)
            self.view_rows = list(self.all_rows)
            self._render_table(self.view_rows)
            self._update_summary()
            self.set_status(f"Done. Rows: {len(self.view_rows)}")

        # ----------------- inspector rendering -----------------
        def on_row_select(self, event=None):
            sel = self.tree.selection()
            if not sel: return
            idx = self.tree.index(sel[0])
            if idx >= len(self.view_rows): return
            r = self.view_rows[idx]
            # Overview
            self._set_overview_text(explain_row(r))
            # Metrics
            metrics = []
            for k in ("observation_count","rssi_min","rssi_max","rssi_avg","txp_values","adv_types","channels"):
                if r.get(k) not in (None,""): metrics.append((k.replace("_"," ").title(), str(r.get(k))))
            for k in ("device_names","service_uuids","company_ids","frames"):
                if r.get(k) not in (None,""): metrics.append((k.replace("_"," ").title(), str(r.get(k))))
            self._fill_grid(self.met_grid, metrics or [("No metrics","—")])
            # Sparkline (RSSI trend)
            spark = _sparkline_from_series(r.get("rssi_series"))
            self.spark_lbl.configure(text=("RSSI trend: " + spark) if spark else "RSSI trend: —")
            # Raw Context
            raw = r.get("raw_context") or "No raw context captured for this address."
            self._set_raw_text(raw)
            # Key/Value grid
            kv_items = []
            for key in sorted(r.keys()):
                if key.startswith("kv_") and r.get(key):
                    kv_items.append((key[3:].replace("_"," ").title(), str(r[key])))
            self._fill_grid(self.kv_grid, kv_items or [("No dynamic keys","—")])

        # ----------------- filter / sort / clipboard -----------------
        def _apply_filter(self):
            needle = (self.filter_var.get() or "").strip().lower()
            if not needle:
                self.view_rows = list(self.all_rows)
            else:
                cols = self.tree["columns"]
                def row_match(r):
                    for c in cols:
                        v = r.get(c)
                        if v and needle in str(v).lower(): return True
                    return False
                self.view_rows = [r for r in self.all_rows if row_match(r)]
            self._render_table(self.view_rows)

        def _sort_by(self, col: str):
            # simple ascending toggle
            try:
                self.view_rows.sort(key=lambda r: (r.get(col) is None, str(r.get(col))))
            except Exception:
                self.view_rows.sort(key=lambda r: str(r.get(col)))
            self._render_table(self.view_rows)

        def on_copy_mac(self, event=None):
            sel = self.tree.selection()
            if not sel: return
            idx = self.tree.index(sel[0])
            if idx >= len(self.view_rows): return
            mac = self.view_rows[idx].get("mac","")
            if not mac: return
            self.clipboard_clear(); self.clipboard_append(mac); self.set_status(f"Copied MAC: {mac}")

        def on_quick_look(self, event=None):
            sel = self.tree.selection()
            if not sel: return
            idx = self.tree.index(sel[0])
            if idx >= len(self.view_rows): return
            r = self.view_rows[idx]
            self._popup_quick_look(r)

        def _popup_quick_look(self, r: Dict[str, Any]):
            win = tk.Toplevel(self); win.title(r.get("mac","(device)")); win.geometry("800x600")
            nb = ttk.Notebook(win); nb.pack(fill=tk.BOTH, expand=True)
            t1 = ttk.Frame(nb); nb.add(t1, text="Overview")
            t2 = ttk.Frame(nb); nb.add(t2, text="Raw Context")
            t3 = ttk.Frame(nb); nb.add(t3, text="Key/Value")
            txt1 = tk.Text(t1, wrap="word"); txt1.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            txt1.insert("1.0", explain_row(r))
            txt2 = tk.Text(t2, wrap="none"); txt2.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            txt2.insert("1.0", r.get("raw_context") or "No raw context.")
            kv = ttk.Treeview(t3, columns=("k","v"), show="headings"); kv.heading("k", text="Key"); kv.heading("v", text="Value")
            kv.column("k", width=240); kv.column("v", width=480); kv.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            for key in sorted(r.keys()):
                if key.startswith("kv_") and r.get(key):
                    kv.insert("", "end", values=(key[3:].replace("_"," ").title(), str(r[key])))

        # ----------------- summary + exports -----------------
        def _update_summary(self):
            total = len(self.view_rows)
            by_admin = {"OUI/global":0, "local/random":0}
            by_ble = {}; vendors = {}
            for r in self.view_rows:
                if r.get("locally_administered") == "yes": by_admin["local/random"] += 1
                else: by_admin["OUI/global"] += 1
                ble = r.get("ble_random_hint") or "none"; by_ble[ble] = by_ble.get(ble,0)+1
                v = r.get("vendor") or "Unknown"; vendors[v] = vendors.get(v,0)+1
            top_ven = sorted(vendors.items(), key=lambda kv: kv[1], reverse=True)[:8]
            txt = f"Total: {total} | Admin OUI={by_admin['OUI/global']} Local={by_admin['local/random']} | " \
                  f"BLE: " + ", ".join(f"{k}={v}" for k,v in by_ble.items() if v>0) + " | " \
                  f"Top vendors: " + ", ".join(f"{k} ({v})" for k,v in top_ven)
            self.set_status(txt)

        def on_export_csv(self):
            if not self.view_rows:
                messagebox.showinfo("No results", "Analyze first."); return
            path = filedialog.asksaveasfilename(title="Save CSV", defaultextension=".csv", filetypes=[("CSV","*.csv")])
            if not path: return
            try:
                export_csv(self.view_rows, path); self.set_status(f"Saved CSV (filtered): {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Save failed", str(e))

        def on_export_json_filtered(self):
            if not self.view_rows:
                messagebox.showinfo("No results", "Analyze first."); return
            path = filedialog.asksaveasfilename(title="Save JSON", defaultextension=".json", filetypes=[("JSON","*.json")])
            if not path: return
            try:
                export_json(self.view_rows, path); self.set_status(f"Saved JSON (filtered): {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Save failed", str(e))

    App().mainloop()

# ----------------------------------- CLI -------------------------------------

def main():
    ap = argparse.ArgumentParser(description="GUI-first MAC/BLE inspector with deep inspector.")
    ap.add_argument("paths", nargs="*", help="(Optional) Files/folders/zips to scan via CLI mode.")
    ap.add_argument("--cli", action="store_true", help="Use CLI mode instead of GUI.")
    ap.add_argument("-o", "--output", help="Output file (.csv or .json) for CLI mode.")
    ap.add_argument("--vendor", action="store_true", help="Attempt vendor/OUI lookup (CLI mode).")
    ap.add_argument("--update-vendors", action="store_true", help="Refresh OUI DB (requires internet). Implies --vendor.")
    ap.add_argument("--enrich-local", action="store_true", help="Local IP/iface mapping via ARP/ND (CLI mode).")
    args = ap.parse_args()

    if not args.cli:
        launch_gui(auto_open_dialog=True)
        return 0

    # CLI path (unchanged; still prints/exports)
    sources, blocks = read_paths(args.paths) if args.paths else ([], [])
    if not sources and not blocks:
        print("No recognizable MAC addresses found (CLI). Use GUI (default) or provide paths.", file=sys.stderr)
        return 2

    seen_mac, uniq, srcmap = set(), [], {}
    for src, mac in sources:
        if mac not in seen_mac: seen_mac.add(mac); uniq.append(mac); srcmap[mac] = src

    use_vendor = bool(args.vendor or args.update_vendors)
    update_vendors = bool(args.update_vendors)
    rows = [analyze_one(m, use_vendor=use_vendor, update_vendors=update_vendors) for m in uniq]

    if args.enrich_local:
        local = enrich_local_mac_map()
        for r in rows:
            if r["mac"] in local:
                r["ip"] = local[r["mac"]].get("ip"); r["iface"] = local[r["mac"]].get("iface")

    if blocks:
        radio = enrich_from_text_blocks(blocks)
        for r in rows:
            extra = radio.get(r["mac"])
            if extra: r.update({k:v for k,v in extra.items() if v not in (None,"",[])})

    if args.output:
        (export_json if args.output.lower().endswith(".json") else export_csv)(rows, args.output)
        print(f"[+] Wrote {len(rows)} rows to {args.output}")
    else:
        common = ["mac","device_names","unicast_or_multicast","admin","ble_random_hint","vendor","oui","first_seen","last_seen","rssi_avg","adv_types","service_uuids","company_ids","frames","source"]
        cols = [c for c in common if any(r.get(c) for r in rows)] or ["mac"]
        print(" | ".join(c.ljust(22) for c in cols))
        for r in rows:
            print(" | ".join([(str(r.get(c,"")) if r.get(c) is not None else "").ljust(22) for c in cols]))
    return 0

if __name__ == "__main__":
    sys.exit(main())

