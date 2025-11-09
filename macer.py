#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI for MAC/BLE inspection.
- Paste addresses (newline, comma, or space separated)
- Or open a .xlsx/.xls/.csv/.txt file (uses 'address' column or first column)
- Toggle vendor lookup and local enrichment
- Analyze -> view results in a table
- Export to CSV/JSON

Optional installs:
  pip install pandas openpyxl mac-vendor-lookup
"""

import os, re, json, csv, platform, subprocess, sqlite3, sys
from typing import List, Dict, Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ------------- Core analysis helpers (dependency-light) -------------

MAC12 = re.compile(r'^[0-9A-Fa-f]{12}$')

def normalize_mac(addr: str) -> Optional[str]:
    if not isinstance(addr, str): return None
    s = re.sub(r'[^0-9A-Fa-f]', '', addr.strip())
    if not MAC12.fullmatch(s): return None
    return ':'.join(s[i:i+2].upper() for i in range(0, 12, 2))

def mac_bytes(mac: str) -> List[int]:
    return [int(p, 16) for p in mac.split(':')]

def ig_bit(b0: int) -> int:      # Individual/Group (LSB)
    return b0 & 0x01

def ul_bit(b0: int) -> int:      # Universal/Local (2nd LSB)
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
    # Common VM/cloud
    "00:05:69": "VMware", "00:50:56": "VMware", "00:1C:14": "VMware", "00:0C:29": "VMware",
    "52:54:00": "QEMU/KVM", "00:16:3E": "Xen", "08:00:27": "VirtualBox",
    "02:42:AC": "Docker (172.* seed)",
    # Consumer-ish
    "F4:F5:D8": "Google (Nest/Cast)", "3C:5A:B4": "Amazon (Echo/Fire)", "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Apple", "F0:99:B6": "Apple",
}

def heuristic_tags(oui: str, vendor: Optional[str], locally_admin: bool) -> List[str]:
    tags = []
    if locally_admin:
        tags.append("locally-administered")
    if oui in KNOWN_TAGS:
        tags.append(KNOWN_TAGS[oui])
    if vendor:
        v = vendor.lower()
        for key in ("apple","samsung","google","hon hai","murata","bose","tp-link","intel","raspberry"):
            if key in v:
                tags.append(key)
                break
    # unique & sorted
    out, seen = [], set()
    for t in tags:
        if t not in seen:
            out.append(t); seen.add(t)
    return out

def run_cmd(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""

def enrich_local_mac_map() -> Dict[str, Dict[str,str]]:
    out: Dict[str, Dict[str,str]] = {}
    sysname = platform.system().lower()

    def add(mac: str, ip: str, iface: str):
        macn = normalize_mac(mac)
        if macn:
            out[macn] = {'ip': ip, 'iface': iface}

    if 'linux' in sysname or 'darwin' in sysname:
        txt = run_cmd(["ip","neigh"])
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

def analyze_one(mac: str, use_vendor=False, update_vendors=False) -> Dict[str, Optional[str]]:
    b = mac_bytes(mac); b0 = b[0]
    is_multicast = ig_bit(b0) == 1
    is_local     = ul_bit(b0) == 1
    oui = ':'.join(mac.split(':')[:3])
    nic = ':'.join(mac.split(':')[3:])
    ble_hint = ble_random_class(b0)
    vend = vendor_lookup(mac, update=update_vendors) if use_vendor else None
    conf = "oui_match" if (vend and not is_local) else ("low (locally administered)" if (vend and is_local) else None)
    return {
        "mac": mac,
        "canonical": mac,
        "valid": "yes",
        "unicast_or_multicast": "multicast/group" if is_multicast else "unicast/individual",
        "multicast": "yes" if is_multicast else "no",
        "locally_administered": "yes" if is_local else "no",
        "admin": "locally administered" if is_local else "universally administered (OUI)",
        "first_octet_hex": f"{b0:02X}",
        "first_octet_bits": first_octet_bits(b0),
        "ig_bit": str(ig_bit(b0)),
        "ul_bit": str(ul_bit(b0)),
        "ble_random_hint": ble_hint,
        "address_kind": "public (OUI)" if not is_local else "local/random",
        "vendor": vend,
        "vendor_guess_confidence": conf,
        "oui": oui,
        "nic": nic,
        "mac_int": str(mac_to_int(mac)),
        "tags": ",".join(heuristic_tags(oui, vend, is_local)) or "",
        "ip": "",
        "iface": "",
    }

def parse_free_text(s: str) -> List[str]:
    # Accept comma, space, or newline separated values
    raw = re.split(r'[\s,;]+', s.strip())
    addrs = []
    for item in raw:
        mac = normalize_mac(item)
        if mac:
            addrs.append(mac)
    # dedupe preserve order
    seen, uniq = set(), []
    for a in addrs:
        if a not in seen:
            uniq.append(a); seen.add(a)
    return uniq

def read_file_addrs(path: str) -> List[str]:
    ext = os.path.splitext(path)[1].lower()
    addrs: List[str] = []
    try:
        import pandas as pd
        if ext in ('.xlsx','.xls'):
            df = pd.read_excel(path, dtype=str)
        elif ext in ('.csv','.txt'):
            try:
                df = pd.read_csv(path, dtype=str, engine='python')
            except Exception:
                df = pd.read_csv(path, dtype=str)
        else:
            raise RuntimeError(f"Unsupported file: {ext}")
        col = None
        for c in df.columns:
            if str(c).strip().lower() == 'address':
                col = c; break
        if col is None:
            col = df.columns[0]
        for v in df[col].tolist():
            mac = normalize_mac(v) if isinstance(v, str) else None
            if mac:
                addrs.append(mac)
    except Exception:
        # fallback csv/txt first-column
        if ext in ('.csv','.txt'):
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    cell = line.strip().split(',')[0]
                    mac = normalize_mac(cell)
                    if mac:
                        addrs.append(mac)
        else:
            raise
    # dedupe
    seen, uniq = set(), []
    for a in addrs:
        if a not in seen:
            uniq.append(a); seen.add(a)
    return uniq

# ------------- GUI -------------

COLUMNS = [
    ("mac","MAC"),
    ("unicast_or_multicast","Uni/Multicast"),
    ("admin","Admin"),
    ("ble_random_hint","BLE"),
    ("vendor","Vendor"),
    ("oui","OUI"),
    ("ip","IP"),
    ("iface","Interface"),
    ("tags","Tags"),
]

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MAC / BLE Inspector")
        self.geometry("1000x640")
        self.minsize(900, 560)

        # Top controls
        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Addresses (paste: newline/comma/space separated) or load file:").pack(anchor="w")

        self.input_txt = tk.Text(top, height=6)
        self.input_txt.pack(fill=tk.X, pady=4)

        btnrow = ttk.Frame(top)
        btnrow.pack(fill=tk.X, pady=4)
        ttk.Button(btnrow, text="Open File…", command=self.on_open_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btnrow, text="Analyze", command=self.on_analyze).pack(side=tk.LEFT, padx=2)
        ttk.Button(btnrow, text="Export CSV…", command=self.on_export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(btnrow, text="Export JSON…", command=self.on_export_json).pack(side=tk.LEFT, padx=2)

        self.var_vendor = tk.BooleanVar(value=False)
        self.var_update = tk.BooleanVar(value=False)
        self.var_enrich = tk.BooleanVar(value=False)
        ttk.Checkbutton(btnrow, text="Vendor lookup", variable=self.var_vendor).pack(side=tk.RIGHT, padx=6)
        ttk.Checkbutton(btnrow, text="Refresh vendor DB", variable=self.var_update).pack(side=tk.RIGHT)
        ttk.Checkbutton(btnrow, text="Local enrichment (ARP/ND)", variable=self.var_enrich).pack(side=tk.RIGHT, padx=6)

        # Table
        table_frame = ttk.Frame(self, padding=6)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(table_frame, columns=[c[0] for c in COLUMNS], show="headings", height=12)
        for key, title in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=120, stretch=True)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(8,4)).pack(side=tk.BOTTOM, fill=tk.X)

        # Data storage
        self.rows: List[Dict[str,str]] = []

    def set_status(self, msg: str):
        self.status.set(msg)
        self.update_idletasks()

    def on_open_file(self):
        path = filedialog.askopenfilename(
            title="Open addresses file",
            filetypes=[("Spreadsheet/CSV/TXT","*.xlsx *.xls *.csv *.txt"), ("All files","*.*")]
        )
        if not path:
            return
        try:
            addrs = read_file_addrs(path)
        except Exception as e:
            messagebox.showerror("Open failed", f"Could not read {os.path.basename(path)}:\n{e}")
            return
        if not addrs:
            messagebox.showwarning("No addresses", "No valid MAC addresses found in this file.")
            return
        # Put into textbox (one per line)
        self.input_txt.delete("1.0", tk.END)
        self.input_txt.insert("1.0", "\n".join(addrs))

    def analyze_addrs(self, addrs: List[str]) -> List[Dict[str,str]]:
        use_vendor = bool(self.var_vendor.get() or self.var_update.get())
        update_vendors = bool(self.var_update.get())
        rows = [analyze_one(m, use_vendor=use_vendor, update_vendors=update_vendors) for m in addrs]
        if self.var_enrich.get():
            local = enrich_local_mac_map()
            for r in rows:
                if r["mac"] in local:
                    r["ip"] = local[r["mac"]].get("ip","")
                    r["iface"] = local[r["mac"]].get("iface","")
        # Cast all to str for table ease
        for r in rows:
            for k, v in list(r.items()):
                r[k] = "" if v is None else str(v)
        return rows

    def on_analyze(self):
        raw = self.input_txt.get("1.0", tk.END)
        addrs = parse_free_text(raw)
        if not addrs:
            messagebox.showwarning("No valid addresses", "Paste some MAC/BLE addresses or open a file.")
            return
        self.set_status(f"Analyzing {len(addrs)} address(es)…")
        self.rows = self.analyze_addrs(addrs)
        # Update table
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in self.rows:
            values = [r.get(k[0], "") for k in COLUMNS]
            self.tree.insert("", tk.END, values=values)
        self.set_status(f"Done. Rows: {len(self.rows)}")

    def _ensure_rows(self) -> bool:
        if not self.rows:
            messagebox.showinfo("No results", "Run Analyze first.")
            return False
        return True

    def on_export_csv(self):
        if not self._ensure_rows(): return
        path = filedialog.asksaveasfilename(title="Save CSV", defaultextension=".csv",
                                            filetypes=[("CSV","*.csv")])
        if not path: return
        keys = list(self.rows[0].keys())
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(self.rows)
            self.set_status(f"Saved CSV: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save CSV:\n{e}")

    def on_export_json(self):
        if not self._ensure_rows(): return
        path = filedialog.asksaveasfilename(title="Save JSON", defaultextension=".json",
                                            filetypes=[("JSON","*.json")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.rows, f, ensure_ascii=False, indent=2)
            self.set_status(f"Saved JSON: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save JSON:\n{e}")

if __name__ == "__main__":
    try:
        import tkinter  # make sure Tk is available
    except Exception as e:
        print("Tkinter is required for the GUI. On Windows it is included with Python; "
              "on Linux you may need python3-tk.", file=sys.stderr)
        sys.exit(1)
    App().mainloop()
