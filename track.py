import os
import sys
import time
import io
import cv2
import numpy as np
import face_recognition
import tkinter as tk
from tkinter import messagebox, filedialog, StringVar, OptionMenu, ttk, simpledialog
from PIL import Image, ImageTk
import random
import json
import logging
import secrets
from collections import defaultdict, OrderedDict
import threading
from typing import Optional, Dict, Any
from html import escape
import webbrowser
from http import HTTPStatus

# NEW for notifications & image hosting
import urllib.request, urllib.parse, ssl
import socket, base64, http.server, socketserver
import requests

############################
# Logging Configuration
############################
logging.basicConfig(
    level=logging.DEBUG,
    format="(%(asctime)s) [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger()


def _fatal_messagebox(title: str, message: str) -> None:
    """Display a fatal error message via Tk (with console fallback)."""
    logger.error("%s: %s", title, message)
    try:
        root_temp = tk.Tk()
        root_temp.withdraw()
        messagebox.showerror(title, message)
        root_temp.destroy()
    except Exception:
        print(f"{title}: {message}", file=sys.stderr)


############################
# NFT Gating Configuration
############################
NFT_GATE_ENABLED = os.getenv("NFT_GATE_ENABLED", "false").lower() not in {"0", "false", "no"}
NFT_GATE_CONTRACT = os.getenv("NFT_GATE_CONTRACT_ADDRESS")
NFT_GATE_API_KEY = os.getenv("NFT_GATE_ALCHEMY_API_KEY")
NFT_GATE_NETWORK = os.getenv("NFT_GATE_NETWORK", "eth-mainnet")
NFT_GATE_CHAIN_DEFAULT = os.getenv("NFT_GATE_CHAIN", "evm").strip().lower()
NFT_GATE_SOLANA_MINT = os.getenv("NFT_GATE_SOLANA_MINT_ADDRESS")
NFT_GATE_SOLANA_RPC = os.getenv(
    "NFT_GATE_SOLANA_RPC", "https://api.mainnet-beta.solana.com"
)
NFT_GATE_WALLET_CHAIN = os.getenv("NFT_GATE_WALLET_CHAIN")


class NFTGateError(Exception):
    """Raised when NFT gate verification fails in a recoverable way."""

    def __init__(self, title: str, message: str) -> None:
        super().__init__(message)
        self.title = title
        self.message = message


class _WalletConnectServer:
    """Serve a lightweight wallet-connect bridge for browser wallets."""

    def __init__(self) -> None:
        self._server: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._event = threading.Event()
        self.state_token = secrets.token_urlsafe(16)
        self.address: Optional[str] = None
        self.chain: Optional[str] = None

    def _build_handler(self) -> type:
        parent = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def _send_bytes(self, payload: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:  # type: ignore[override]
                if self.path != "/":
                    self._send_bytes(b"Not found", HTTPStatus.NOT_FOUND)
                    return

                html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <title>Ioncore Wallet Connect</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
        body {{ font-family: Arial, sans-serif; background: #030712; color: #e2e8f0; margin: 0; padding: 24px; }}
        h1 {{ color: #38bdf8; }}
        button {{ background: #22d3ee; color: #030712; border: none; border-radius: 6px; padding: 12px 18px; margin: 8px 0; font-size: 16px; cursor: pointer; }}
        button:hover {{ background: #0ea5e9; color: white; }}
        .card {{ max-width: 520px; margin: 0 auto; background: rgba(15, 23, 42, 0.85); border-radius: 12px; padding: 24px; box-shadow: 0 18px 48px rgba(8, 47, 73, 0.3); }}
        .status {{ margin-top: 18px; padding: 12px; border-radius: 8px; background: rgba(148, 163, 184, 0.12); }}
        .success {{ color: #4ade80; }}
        .error {{ color: #f87171; }}
        code {{ color: #facc15; }}
    </style>
</head>
<body>
    <div class=\"card\">
        <h1>Ioncore Wallet Connect</h1>
        <p>Select your wallet provider to continue. Once connected your address will be securely relayed back to the Sentinel desktop.</p>
        <button onclick=\"connectEvm()\">Connect MetaMask / EVM Wallet</button>
        <button onclick=\"connectPhantom()\">Connect Phantom (Solana)</button>
        <div id=\"status\" class=\"status\">Awaiting wallet connection…</div>
    </div>
    <script>
    const stateToken = "{parent.state_token}";

    async function postWallet(address, chain) {{
        const payload = {{ address, chain, state: stateToken }};
        const response = await fetch('/wallet-callback', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(payload)
        }});
        if (!response.ok) {{
            throw new Error('Bridge rejected wallet connection.');
        }}
        return response.json();
    }}

    function updateStatus(message, tone) {{
        const status = document.getElementById('status');
        status.textContent = message;
        status.classList.remove('success', 'error');
        if (tone) {{ status.classList.add(tone); }}
    }}

    async function connectEvm() {{
        try {{
            if (!window.ethereum) {{
                updateStatus('MetaMask or another EVM wallet is required in this browser.', 'error');
                return;
            }}
            const accounts = await window.ethereum.request({{ method: 'eth_requestAccounts' }});
            const address = accounts && accounts[0];
            if (!address) {{
                updateStatus('No account was shared by the wallet.', 'error');
                return;
            }}
            await postWallet(address, 'evm');
            updateStatus('EVM wallet connected: ' + address, 'success');
        }} catch (err) {{
            console.error(err);
            updateStatus('Failed to connect MetaMask: ' + err.message, 'error');
        }}
    }}

    async function connectPhantom() {{
        try {{
            const provider = window.solana;
            if (!provider || !provider.isPhantom) {{
                updateStatus('Phantom wallet extension is required for Solana access.', 'error');
                return;
            }}
            const resp = await provider.connect();
            const address = resp && resp.publicKey ? resp.publicKey.toString() : null;
            if (!address) {{
                updateStatus('No Solana account returned by Phantom.', 'error');
                return;
            }}
            await postWallet(address, 'solana');
            updateStatus('Phantom wallet connected: ' + address, 'success');
        }} catch (err) {{
            console.error(err);
            updateStatus('Failed to connect Phantom: ' + err.message, 'error');
        }}
    }}
    </script>
</body>
</html>"""

                self._send_bytes(html.encode("utf-8"))

            def do_POST(self) -> None:  # type: ignore[override]
                if self.path != "/wallet-callback":
                    self._send_bytes(b"Not found", HTTPStatus.NOT_FOUND)
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                payload = self.rfile.read(length or 0)
                try:
                    data = json.loads(payload.decode("utf-8"))
                except Exception:
                    self._send_bytes(b"Invalid payload", HTTPStatus.BAD_REQUEST)
                    return

                if not isinstance(data, dict) or data.get("state") != parent.state_token:
                    self._send_bytes(b"Unauthorized", HTTPStatus.FORBIDDEN)
                    return

                address = (data.get("address") or "").strip()
                chain = (data.get("chain") or "").strip().lower()
                if not address:
                    self._send_bytes(b"Missing address", HTTPStatus.BAD_REQUEST)
                    return

                parent.address = address
                parent.chain = chain or None
                parent._event.set()

                response = json.dumps({"status": "ok"}).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, format: str, *args: Any) -> None:
                # Silence default HTTP server logging to avoid noise.
                logger.debug("Wallet bridge: " + format, *args)

        return _Handler

    def start(self) -> None:
        if self._server:
            return

        handler = self._build_handler()

        class _TCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        server = _TCPServer(("127.0.0.1", 0), handler)
        server.timeout = 0.5
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            try:
                self._server.server_close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._server = None
        self._thread = None

    @property
    def url(self) -> Optional[str]:
        if not self._server:
            return None
        host, port = self._server.server_address
        return f"http://{host}:{port}/"

    def is_running(self) -> bool:
        return self._server is not None

    def pop_wallet(self) -> Optional[Dict[str, str]]:
        if not self._event.is_set() or not self.address:
            return None
        self._event.clear()
        result = {
            "address": self.address,
            "chain": (self.chain or "").lower() or "evm",
        }
        return result



def _prompt_wallet_address() -> Optional[Dict[str, str]]:
    connector = _WalletConnectServer()
    result: Optional[Dict[str, str]] = None

    try:
        root_temp = tk.Tk()
        root_temp.title("Ioncore Wallet Verification")
        root_temp.configure(bg="#05070e")
        root_temp.resizable(False, False)

        card = tk.Frame(
            root_temp,
            bg="#0b1627",
            padx=24,
            pady=24,
            highlightbackground="#38bdf8",
            highlightcolor="#38bdf8",
            highlightthickness=1,
        )
        card.pack(fill="both", expand=True, padx=18, pady=18)

        heading = tk.Label(
            card,
            text="Secure Wallet Authentication",
            font=("Montserrat", 14, "bold"),
            fg="#38bdf8",
            bg="#0b1627",
        )
        heading.pack(anchor="center", pady=(0, 8))

        blurb = tk.Label(
            card,
            text=(
                "Connect a wallet or enter an address manually to confirm ownership of the required access token."
            ),
            wraplength=420,
            justify=tk.LEFT,
            font=("Montserrat", 10),
            fg="#cbd5f5",
            bg="#0b1627",
        )
        blurb.pack(fill="x", pady=(0, 16))

        chain_var = tk.StringVar(value=NFT_GATE_CHAIN_DEFAULT or "evm")
        address_var = tk.StringVar()
        status_var = tk.StringVar(value="No wallet connected yet.")

        form = tk.Frame(card, bg="#0b1627")
        form.pack(fill="x")

        tk.Label(
            form,
            text="Wallet Address",
            font=("Montserrat", 10, "bold"),
            fg="#48ffe2",
            bg="#0b1627",
        ).pack(anchor="w")

        address_entry = tk.Entry(
            form,
            textvariable=address_var,
            font=("Montserrat", 12),
            relief=tk.FLAT,
            bg="#030712",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            width=48,
        )
        address_entry.pack(fill="x", pady=(4, 12))

        tk.Label(
            form,
            text="Wallet Network",
            font=("Montserrat", 10, "bold"),
            fg="#48ffe2",
            bg="#0b1627",
        ).pack(anchor="w")

        chain_options = [
            ("Ethereum / EVM (MetaMask)", "evm"),
            ("Solana (Phantom)", "solana"),
        ]

        chain_menu = ttk.Combobox(
            form,
            values=[label for label, _ in chain_options],
            state="readonly",
        )
        chain_menu.pack(fill="x", pady=(4, 12))

        def _sync_chain(event=None) -> None:
            index = chain_menu.current()
            if 0 <= index < len(chain_options):
                chain_var.set(chain_options[index][1])

        chain_menu.current(0 if (chain_var.get() or "evm") == "evm" else 1)
        chain_menu.bind("<<ComboboxSelected>>", _sync_chain)
        _sync_chain()

        status_label = tk.Label(
            card,
            textvariable=status_var,
            font=("Montserrat", 10),
            fg="#94a3b8",
            bg="#12223a",
            wraplength=420,
            justify=tk.LEFT,
            padx=12,
            pady=10,
        )
        status_label.pack(fill="x", pady=(0, 12))

        button_row = tk.Frame(card, bg="#0b1627")
        button_row.pack(fill="x", pady=(4, 0))

        def _connect_wallet() -> None:
            try:
                connector.start()
                url = connector.url
                if not url:
                    raise RuntimeError("Wallet bridge unavailable")
                webbrowser.open(url)
                status_var.set("Wallet bridge opened in browser. Complete the connection there.")
                status_label.configure(fg="#94a3b8")
            except Exception as exc:
                status_var.set(f"Unable to open wallet bridge: {exc}")
                status_label.configure(fg="#ff4976")

        def _poll_wallet() -> None:
            info = connector.pop_wallet()
            if info:
                address_var.set(info.get("address", ""))
                chain = info.get("chain", "")
                if chain == "solana":
                    chain_menu.current(1)
                else:
                    chain_menu.current(0)
                _sync_chain()
                status_var.set(f"Wallet connected: {info['address']}")
                status_label.configure(fg="#6aff3b")
            if connector.is_running():  # Continue polling while running
                root_temp.after(750, _poll_wallet)

        connect_button = tk.Button(
            button_row,
            text="Connect Wallet",
            command=_connect_wallet,
            font=("Montserrat", 11, "bold"),
            bg="#22d3ee",
            fg="#030712",
            activebackground="#0ea5e9",
            activeforeground="#f8fafc",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        )
        connect_button.pack(side=tk.LEFT)

        def _confirm() -> None:
            nonlocal result
            address = address_var.get().strip()
            if not address:
                messagebox.showerror("Wallet Required", "A wallet address is required to continue.")
                return
            result = {"address": address, "chain": chain_var.get() or "evm"}
            root_temp.quit()
            root_temp.destroy()

        confirm_button = tk.Button(
            button_row,
            text="Verify Access",
            command=_confirm,
            font=("Montserrat", 11, "bold"),
            bg="#38bdf8",
            fg="#030712",
            activebackground="#0ea5e9",
            activeforeground="#f8fafc",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        )
        confirm_button.pack(side=tk.RIGHT)

        def _on_close() -> None:
            root_temp.quit()
            root_temp.destroy()

        root_temp.protocol("WM_DELETE_WINDOW", _on_close)

        address_entry.focus_set()
        root_temp.after(750, _poll_wallet)
        root_temp.mainloop()

    except Exception:
        # Fallback to console prompt if Tk dialogs are unavailable.
        try:
            wallet = input("Wallet address required for NFT verification: ").strip()
        except EOFError:
            wallet = ""
        if not wallet:
            return None
        chain = input(
            "Wallet network (evm/solana) [default evm]: "
        ).strip().lower()
        chain = chain or "evm"
        return {"address": wallet, "chain": chain}
    finally:
        connector.stop()

    return result


def _verify_evm_wallet(address: str) -> bool:
    params = {
        "owner": address,
        "contractAddresses[]": NFT_GATE_CONTRACT,
        "withMetadata": "false",
        "pageSize": "1",
    }
    url = f"https://{NFT_GATE_NETWORK}.g.alchemy.com/nft/v2/{NFT_GATE_API_KEY}/getNFTs"
    logger.debug("Verifying EVM NFT access for wallet %s via %s", address, url)
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    owned_nfts = data.get("ownedNfts") or []
    total = data.get("totalCount")
    return bool(owned_nfts or (isinstance(total, int) and total > 0))


def _verify_solana_wallet(address: str) -> bool:
    if not NFT_GATE_SOLANA_MINT:
        raise RuntimeError("NFT_GATE_SOLANA_MINT_ADDRESS environment variable is required for Solana checks.")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            address,
            {"mint": NFT_GATE_SOLANA_MINT},
            {"encoding": "jsonParsed"},
        ],
    }
    logger.debug("Verifying Solana token access for wallet %s via %s", address, NFT_GATE_SOLANA_RPC)
    response = requests.post(NFT_GATE_SOLANA_RPC, json=payload, timeout=20)
    response.raise_for_status()
    data = response.json()
    result = data.get("result") or {}
    value = result.get("value") or []
    return bool(value)


def _handle_gate_error(title: str, message: str, fatal: bool) -> None:
    if fatal:
        _fatal_messagebox(title, message)
        sys.exit(1)
    raise NFTGateError(title, message)


def enforce_nft_gate(
    wallet_info: Optional[Dict[str, str]] = None,
    *,
    fatal: bool = True,
) -> Optional[Dict[str, str]]:
    """Ensure the user holds the required NFT before continuing."""
    if not NFT_GATE_ENABLED:
        logger.info("NFT gate disabled via NFT_GATE_ENABLED environment flag.")
        return None

    if not NFT_GATE_CONTRACT and not NFT_GATE_SOLANA_MINT:
        logger.warning(
            "NFT gate misconfigured. Missing contract/mint configuration. Proceeding without enforcement."
        )
        return None

    if NFT_GATE_CONTRACT and not NFT_GATE_API_KEY:
        logger.warning(
            "NFT gate misconfigured. Missing NFT_GATE_ALCHEMY_API_KEY. Proceeding without NFT enforcement."
        )
        return None

    if wallet_info is None:
        wallet_env = os.getenv("NFT_GATE_WALLET_ADDRESS")
        if wallet_env:
            wallet_info = {
                "address": wallet_env.strip(),
                "chain": (NFT_GATE_WALLET_CHAIN or NFT_GATE_CHAIN_DEFAULT or "evm"),
            }
        else:
            wallet_info = _prompt_wallet_address()

    if not wallet_info or not wallet_info.get("address"):
        _handle_gate_error(
            "NFT Access Denied",
            "A wallet address is required to verify NFT ownership.",
            fatal,
        )
        return None

    wallet_address = wallet_info.get("address", "").strip()
    wallet_chain = (wallet_info.get("chain") or NFT_GATE_CHAIN_DEFAULT or "evm").lower()
    if wallet_chain not in {"evm", "solana"}:
        wallet_chain = "evm"
        wallet_info["chain"] = wallet_chain

    if wallet_chain == "solana" and not NFT_GATE_SOLANA_MINT:
        _handle_gate_error(
            "NFT Verification Error",
            "Solana wallet selected but NFT_GATE_SOLANA_MINT_ADDRESS is not configured.",
            fatal,
        )
        return None
    if wallet_chain == "evm" and not NFT_GATE_CONTRACT:
        _handle_gate_error(
            "NFT Verification Error",
            "EVM wallet selected but NFT_GATE_CONTRACT_ADDRESS is not configured.",
            fatal,
        )
        return None

    try:
        if wallet_chain == "solana":
            has_access = _verify_solana_wallet(wallet_address)
            contract_display = NFT_GATE_SOLANA_MINT or "specified Solana mint"
        else:
            has_access = _verify_evm_wallet(wallet_address)
            contract_display = NFT_GATE_CONTRACT or "specified contract"
    except requests.RequestException as exc:
        _handle_gate_error(
            "NFT Verification Error",
            f"Unable to verify token ownership due to a network/API error: {exc}",
            fatal,
        )
        return None
    except ValueError:
        _handle_gate_error(
            "NFT Verification Error",
            "Received an unexpected response from the verification endpoint.",
            fatal,
        )
        return None
    except RuntimeError as exc:
        _handle_gate_error("NFT Verification Error", str(exc), fatal)
        return None

    if has_access:
        logger.info(
            "NFT gate verified: wallet %s holds required asset (%s).",
            wallet_address,
            contract_display,
        )
        return {"address": wallet_address, "chain": wallet_chain}

    _handle_gate_error(
        "NFT Access Denied",
        (
            "Wallet "
            + wallet_address
            + " does not appear to hold the required token ("
            + contract_display
            + ")."
        ),
        fatal,
    )
    return None

############################
# Startup Access
############################

# Open startup: launch the dashboard directly without displaying the former
# credential/wallet login gate. NFT gating remains controlled separately by
# NFT_GATE_ENABLED for deployments that explicitly enable it.
if NFT_GATE_ENABLED:
    enforce_nft_gate()
else:
    logger.info("Access gating disabled. Launching without login or NFT checks.")

############################
# Configuration (defaults)
############################
KNOWN_FACES_DIR = "known_faces"
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

# YOLO files
yolo_weights = "yolov3.weights"
yolo_config = "yolov3.cfg"
yolo_labels = "coco.names"

# Thresholds & Timers (Tk vars created later)
DETECTION_CONF_THRESH = 0.5
NMS_THRESH = 0.4
AUTO_PLACE_TIMEOUT = 5.0
HELD_LOG_INTERVAL = 1.0
PERSON_LOG_COOLDOWN = 120.0
PERSON_COLOR_LOG_COOLDOWN = 45.0  # NEW: shirt color-only cooldown

# Snapshot rate limits
SNAPSHOT_COOLDOWN_FACE = 0.2
SNAPSHOT_COOLDOWN_VEHICLE = 0.2

# Unknown person snapshots (requires persistence)
UNKNOWN_PERSON_PERSISTENCE = 1.0
UNKNOWN_PERSON_SNAPSHOT_COOLDOWN = 0.4

# Movement-idle thresholds
VEHICLE_IDLE_FRAC = 0.15
UNKNOWN_PERSON_IDLE_FRAC = 0.15

# Face re-ID tolerance for unknown buckets
UNKNOWN_MATCH_TOLERANCE = 0.60

# Stream controls
FEED_W, FEED_H = 320, 240
FPS_CAP = 33            # loop delay (ms) for UI/detection cycle
FRAME_SKIP = 0
FACE_MODEL = "hog"      # "hog" or "cnn"

# Camera toggles
MAX_CAMERAS = 8

# ---------------------------------------
# Spot re-tag suppression (people/vehicles)
# ---------------------------------------
RETAG_HOLD_SECONDS = 10.0
SPOT_LOCKS_MAX_PER_KEY = 8
spot_locks = defaultdict(list)

############################
# Check YOLO files
############################
if not all(os.path.exists(f) for f in [yolo_weights, yolo_config, yolo_labels]):
    _fatal_messagebox(
        "YOLO Files Missing",
        "Please ensure YOLO weight, config, and labels files are present.",
    )
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
# Data Structures
############################
known_encodings, known_names = [], []
unknown_encodings, unknown_ids = [], []
unknown_id_counter = 0

# Unified review queue: (enc_or_None, bgr_image, uid, camera_tag, kind)
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

# NEW: shirt-color tracking for persons
person_last_color_logged = {}
person_current_shirt_color = {}  # name -> {"rgb":(r,g,b),"hex":"#RRGGBB","name":"Blue","ts":...}

current_detections = []
camera_live_logs = defaultdict(list)
MAX_LIVE_LOG_LINES = 2000

# Camera runtime (thread-based for multi-cam)
camera_vars = {}
cam_toggle_text = {}  # NEW: ON/OFF text per camera toggle
camera_cells = {}
camera_windows = OrderedDict()  # idx -> (worker, camera_name, label widget)
camera_workers = {}             # idx -> CameraWorker

# RL / throttles
last_face_enqueue_ts_by_uid = {}
unknown_person_presence_start_by_key = defaultdict(float)
last_unknownperson_enqueue_ts_by_key = defaultdict(float)
last_unknownperson_snapshot_box_by_key = {}
last_vehicle_enqueue_ts_by_camlabel = defaultdict(float)
last_vehicle_snapshot_box_by_camlabel = defaultdict(float)

unknown_person_id_counter = 0
vehicle_id_counter = 0

############################
# Vehicle DB (local)
############################
VEHICLE_DB_FILE = "vehicle_db.json"
VEHICLE_SNAPSHOT_DIR = "vehicle_snaps"
os.makedirs(VEHICLE_SNAPSHOT_DIR, exist_ok=True)
vehicle_db = {}  # visual-hash -> entry

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
        "id": vid,
        "first_seen": ts,
        "make": None,
        "model": None,
        "plate": None,
        "fleet_id": None,
        "nicknames": [],
        "color_name": None,
        "color_hex": None,
        "snapshots": [],
        "sightings": []
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

# === Recall snapshots (for Person/Object recall popups) ===
RECALL_DIR = "recall_snaps"
OBJECT_RECALL_DIR = os.path.join(RECALL_DIR, "objects")
PERSON_RECALL_DIR = os.path.join(RECALL_DIR, "persons")
os.makedirs(OBJECT_RECALL_DIR, exist_ok=True)
os.makedirs(PERSON_RECALL_DIR, exist_ok=True)

def _save_recall_jpeg(dir_path: str, prefix: str, img_bgr) -> Optional[str]:
    """Save a small JPEG snapshot to disk and return its path."""
    try:
        if img_bgr is None or getattr(img_bgr, "size", 0) == 0:
            return None
        ts = int(time.time() * 1000)
        fn = f"{prefix}_{ts}_{random.randint(1000,9999)}.jpg"
        fp = os.path.join(dir_path, fn)
        ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            return None
        with open(fp, "wb") as f:
            f.write(bytearray(buf))
        return fp
    except Exception as e:
        logger.debug(f"Recall snapshot save failed: {e}")
        return None

############################
# Notifications (persisted)
############################
NOTIFY_FILE = "notify.json"
NOTIFY_COOLDOWN_SECONDS = 60.0
NOTIFY_MEDIA_DIR = "notify_media"
os.makedirs(NOTIFY_MEDIA_DIR, exist_ok=True)

notify_config = {
    "channel": "none",  # "none" | "pushover" | "telegram" | "webhook" | "twilio_sms"
    "attach_images": 1,
    "pushover": {"token": "", "user": ""},
    "telegram": {"bot_token": "", "chat_id": ""},
    "webhook": {"url": ""},
    "twilio": {"sid": "", "token": "", "from": "", "to": ""},
    "media_hosting": {
        "mode": "none",  # "none" | "builtin" | "static_url_prefix"
        "port": 8765,
        "base_url": ""
    }
}
notify_subscriptions = {"persons": [], "objects": [], "vehicle_labels": []}
_notify_last_sent = defaultdict(float)

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

# Media hosting for Twilio
_media_server = None
_media_server_thread = None


def _format_bytes(num: float) -> str:
    if num <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(num)} {unit}"
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def _format_timestamp(ts: float) -> str:
    try:
        return time.strftime("%b %d, %Y · %I:%M %p", time.localtime(ts))
    except (ValueError, OSError):
        return "Unknown timestamp"


class _MediaHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        rel = path.lstrip("/")
        rel_path = rel.split("..")[0]
        return os.path.join(NOTIFY_MEDIA_DIR, os.path.basename(rel_path))

    def list_directory(self, path):
        try:
            entries = os.listdir(path)
        except OSError:
            self.send_error(404, "Unable to list directory")
            return None

        entries = [e for e in entries if not e.startswith(".")]
        entries.sort(key=lambda name: os.path.getmtime(os.path.join(path, name)), reverse=True)

        cards = []
        for entry in entries:
            full_path = os.path.join(path, entry)
            display_name = escape(entry)
            href = urllib.parse.quote(entry)
            is_dir = os.path.isdir(full_path)
            is_file = os.path.isfile(full_path)
            file_ext = os.path.splitext(entry)[1].lower()
            is_image = is_file and file_ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}

            modified_ts = os.path.getmtime(full_path)
            meta_parts = [_format_timestamp(modified_ts)]
            if is_file:
                meta_parts.append(_format_bytes(os.path.getsize(full_path)))
            meta_html = escape(" • ".join(meta_parts))

            if is_image:
                preview = f'<div class="card__media"><img src="{href}" alt="{display_name} preview"></div>'
                btn_class = "btn btn-primary"
                action_label = "View snapshot"
                download_attr = " download"
            elif is_dir:
                preview = (
                    '<div class="card__media card__media--icon">'
                    '<span class="card__icon" aria-hidden="true">📁</span>'
                    "</div>"
                )
                btn_class = "btn btn-outline"
                action_label = "Open collection"
                download_attr = ""
            else:
                preview = (
                    '<div class="card__media card__media--icon">'
                    '<span class="card__icon" aria-hidden="true">⬇️</span>'
                    "</div>"
                )
                btn_class = "btn btn-primary"
                action_label = "Download file"
                download_attr = " download"

            cards.append(
                f"""
                <article class=\"card\">
                  {preview}
                  <div class=\"card__content\">
                    <h2 class=\"card__title\"><a href=\"{href}\">{display_name}</a></h2>
                    <p class=\"card__meta\">{meta_html}</p>
                    <div class=\"card__actions\">
                      <a class=\"{btn_class}\" href=\"{href}\"{download_attr}>{action_label}</a>
                    </div>
                  </div>
                </article>
                """
            )

        if not cards:
            cards_markup = (
                "<div class=\"empty-state\">"
                "<h2>No snapshots yet</h2>"
                "<p>Images and media captured during alerts will appear here automatically.</p>"
                "</div>"
            )
        else:
            cards_markup = "\n".join(cards)

        html_content = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Ioncore Energy | Sentinel Media Vault</title>
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
  <link href=\"https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">
  <style>
    :root {{
      color-scheme: dark;
      --brand: #6aff3b;
      --brand-secondary: #21b085;
      --bg: #020409;
      --bg-accent: #041219;
      --card-bg: rgba(7, 14, 18, 0.92);
      --card-border: rgba(106, 255, 59, 0.18);
      --text-muted: rgba(255, 255, 255, 0.65);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background:
        radial-gradient(780px circle at 12% 20%, rgba(106,255,59,0.16), transparent 62%),
        radial-gradient(620px circle at 88% 12%, rgba(33,176,133,0.18), transparent 60%),
        linear-gradient(135deg, rgba(3,18,25,0.94), rgba(2,4,9,0.98));
      color: #f7f7f7;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      position: relative;
      overflow-x: hidden;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      background:
        radial-gradient(460px circle at 18% 78%, rgba(106,255,59,0.12), transparent 62%),
        radial-gradient(360px circle at 82% 76%, rgba(33,176,133,0.14), transparent 66%),
        linear-gradient(120deg, rgba(255,255,255,0.05), transparent 70%);
      opacity: 0.85;
      pointer-events: none;
      z-index: -2;
    }}
    body::after {{
      content: "";
      position: fixed;
      inset: 0;
      background-image: linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
      background-size: 120px 120px;
      mix-blend-mode: overlay;
      opacity: 0.25;
      pointer-events: none;
      z-index: -1;
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1.5rem clamp(1.25rem, 4vw, 3rem);
      backdrop-filter: blur(18px);
      background: linear-gradient(120deg, rgba(5, 12, 18, 0.85), rgba(5, 18, 12, 0.75));
      border-bottom: 1px solid rgba(106,255,59,0.18);
      position: sticky;
      top: 0;
      z-index: 10;
      box-shadow: 0 24px 60px rgba(0,0,0,0.35);
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      color: inherit;
      text-decoration: none;
      font-weight: 700;
      font-size: 1.1rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .brand__mark {{
      width: 46px;
      height: 46px;
      border-radius: 14px;
      background: radial-gradient(circle at 30% 20%, rgba(106,255,59,0.92), rgba(33,176,133,0.8));
      border: 1px solid rgba(255,255,255,0.25);
      box-shadow: 0 10px 25px rgba(33,176,133,0.35);
      display: grid;
      place-items: center;
      color: #031509;
      font-weight: 800;
      letter-spacing: 0.06em;
    }}
    .brand__text {{
      display: grid;
      gap: 0.1rem;
    }}
    .brand__text strong {{ display: block; color: var(--brand); letter-spacing: 0.04em; }}
    .brand__line {{
      text-transform: uppercase;
      letter-spacing: 0.26em;
      font-size: 0.78rem;
    }}
    .brand__subtitle {{
      font-size: 0.72rem;
      font-weight: 500;
      color: var(--text-muted);
      margin-top: 0.2rem;
      letter-spacing: 0.18em;
    }}
    .header-actions {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    .header__badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.35rem 0.85rem;
      border-radius: 999px;
      background: rgba(106,255,59,0.1);
      color: rgba(255,255,255,0.72);
      font-size: 0.72rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      border-radius: 999px;
      padding: 0.5rem 1.25rem;
      text-decoration: none;
      font-weight: 600;
      transition: all 0.25s ease;
      font-size: 0.9rem;
    }}
    .btn-primary {{
      background: linear-gradient(135deg, var(--brand), rgba(106,255,59,0.75));
      color: #041104;
      box-shadow: 0 14px 32px rgba(106,255,59,0.28);
      border: 1px solid rgba(106,255,59,0.35);
    }}
    .btn-primary:hover {{
      background: linear-gradient(135deg, #87ff6d, rgba(106,255,59,0.85));
      transform: translateY(-2px);
      box-shadow: 0 18px 36px rgba(106,255,59,0.36);
    }}
    .btn-outline {{
      border: 1px solid rgba(106,255,59,0.28);
      color: rgba(255,255,255,0.92);
      background: rgba(255,255,255,0.03);
    }}
    .btn-outline:hover {{
      border-color: var(--brand);
      color: var(--brand);
      background: rgba(106,255,59,0.08);
    }}
    main {{
      width: min(1180px, 92vw);
      margin: 3.5rem auto;
      flex: 1;
      position: relative;
    }}
    main::before {{
      content: "";
      position: absolute;
      inset: -80px 5% auto;
      height: 180px;
      background: linear-gradient(120deg, rgba(106,255,59,0.12), transparent 65%);
      filter: blur(80px);
      z-index: -1;
    }}
    .hero {{
      margin-bottom: 3.25rem;
      display: grid;
      gap: 1.25rem;
      position: relative;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto 0 -3rem;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(106,255,59,0.4), transparent);
    }}
    .hero__badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.35rem 0.85rem;
      border-radius: 999px;
      border: 1px solid rgba(106,255,59,0.25);
      background: rgba(6, 40, 24, 0.65);
      text-transform: uppercase;
      letter-spacing: 0.28em;
      font-size: 0.66rem;
      color: rgba(255,255,255,0.78);
      width: fit-content;
    }}
    .hero h1 {{
      font-size: clamp(2.4rem, 4.4vw, 3.4rem);
      margin: 0;
      line-height: 1.15;
    }}
    .hero p {{
      max-width: 720px;
      margin: 0;
      color: var(--text-muted);
      line-height: 1.6;
    }}
    .hero__brand {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      align-items: stretch;
    }}
    .hero__seal {{
      padding: 1.1rem 1.25rem;
      border-radius: 18px;
      background: rgba(10, 24, 17, 0.9);
      border: 1px solid rgba(106,255,59,0.22);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);
      display: grid;
      gap: 0.35rem;
    }}
    .hero__seal span {{
      font-size: 0.75rem;
      letter-spacing: 0.28em;
      color: rgba(255,255,255,0.58);
      text-transform: uppercase;
    }}
    .hero__seal strong {{
      font-size: 1.35rem;
      letter-spacing: 0.12em;
      color: var(--brand);
      text-transform: uppercase;
    }}
    .hero__seal small {{
      font-size: 0.75rem;
      letter-spacing: 0.24em;
      text-transform: uppercase;
      color: rgba(255,255,255,0.55);
    }}
    .hero__meta {{
      margin: 0;
      padding: 1.1rem 1.25rem;
      border-radius: 18px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(106,255,59,0.16);
      display: grid;
      gap: 0.6rem;
      list-style: none;
    }}
    .hero__meta li {{
      display: flex;
      align-items: baseline;
      gap: 0.55rem;
      font-size: 0.95rem;
      color: rgba(255,255,255,0.75);
    }}
    .hero__meta strong {{
      color: var(--brand);
      font-size: 0.75rem;
      letter-spacing: 0.22em;
      text-transform: uppercase;
    }}
    .hero__meta span {{
      flex: 1;
      line-height: 1.5;
      color: rgba(255,255,255,0.68);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.75rem;
      position: relative;
    }}
    .card {{
      display: flex;
      flex-direction: column;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      overflow: hidden;
      min-height: 320px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.5);
      transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
    }}
    .card:hover {{
      transform: translateY(-6px);
      border-color: rgba(106,255,59,0.45);
      box-shadow: 0 28px 55px rgba(0,0,0,0.55);
    }}
    .card__media {{
      position: relative;
      aspect-ratio: 16 / 10;
      background: rgba(255,255,255,0.04);
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .card__media img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .card__media--icon {{
      font-size: 2.5rem;
      color: rgba(106,255,59,0.65);
    }}
    .card__content {{
      padding: 1.4rem 1.6rem 1.75rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      flex: 1;
    }}
    .card__title {{
      margin: 0;
      font-size: 1.1rem;
      font-weight: 600;
    }}
    .card__title a {{
      color: inherit;
      text-decoration: none;
    }}
    .card__title a:hover {{
      color: var(--brand);
    }}
    .card__meta {{
      margin: 0;
      font-size: 0.9rem;
      color: var(--text-muted);
    }}
    .card__actions {{
      margin-top: auto;
    }}
    .empty-state {{
      padding: 3.5rem 2rem;
      border-radius: 24px;
      border: 1px dashed rgba(255,255,255,0.2);
      background: rgba(255,255,255,0.03);
      text-align: center;
      display: grid;
      gap: 0.75rem;
      place-items: center;
    }}
    .empty-state h2 {{
      margin: 0;
      font-size: 1.6rem;
    }}
    .empty-state p {{
      margin: 0;
      color: var(--text-muted);
      max-width: 420px;
    }}
    footer {{
      text-align: center;
      color: var(--text-muted);
      padding: 2.5rem 0 3.5rem;
      font-size: 0.85rem;
      border-top: 1px solid rgba(106,255,59,0.18);
      background: linear-gradient(180deg, rgba(3,12,10,0.4), rgba(2,4,9,0.9));
    }}
    @media (max-width: 640px) {{
      header {{
        flex-direction: column;
        align-items: flex-start;
        gap: 1rem;
      }}
      .header-actions {{
        width: 100%;
        justify-content: flex-start;
      }}
      .hero__brand {{
        grid-template-columns: 1fr;
      }}
      .hero__badge {{
        letter-spacing: 0.18em;
        font-size: 0.62rem;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <a class=\"brand\" href=\"#\" aria-label=\"Ioncore Energy Sentinel media vault\">
      <span class=\"brand__mark\">IE</span>
      <span class=\"brand__text\"><strong>Ioncore Energy</strong><span class=\"brand__line\">Sentinel Command</span><div class=\"brand__subtitle\">Security Media Vault</div></span>
    </a>
    <div class=\"header-actions\">
      <span class=\"header__badge\">Sentinel Security Network</span>
      <a class=\"btn btn-outline\" href=\"mailto:ioncoreenergy@gmail.com\">Contact Ioncore</a>
      <a class=\"btn btn-primary\" href=\"/\">Refresh feed</a>
    </div>
  </header>
  <main>
    <section class=\"hero\">
      <span class=\"hero__badge\">Ioncore Energy • Sentinel Security Cloud</span>
      <h1>Real-time alert snapshots &amp; intelligence drops</h1>
      <p>Review the media artifacts captured by Ioncore Sentinel automations. Each card surfaces the freshest snapshots, complete with capture time and asset size, ready for escalation or archival.</p>
      <div class=\"hero__brand\">
        <div class=\"hero__seal\">
          <span>Ioncore Energy</span>
          <strong>Sentinel</strong>
          <small>Autonomous Response</small>
        </div>
        <ul class=\"hero__meta\">
          <li><strong>Zero Lag</strong><span>Edge-computed signal routing keeps every camera feed synchronized with Command.</span></li>
          <li><strong>Quantum Secure</strong><span>Ioncore encryption hardens telemetry, preserving integrity across the Sentinel mesh.</span></li>
          <li><strong>Always On</strong><span>Resilient storage ensures alerts and media vault assets persist through any event horizon.</span></li>
        </ul>
      </div>
    </section>
    <section class=\"grid\">
      {cards_markup}
    </section>
  </main>
  <footer>© {time.strftime("%Y")} Ioncore Energy. Engineered intelligence for autonomous resilience.</footer>
</body>
</html>
"""

        encoded = html_content.encode("utf-8", "surrogateescape")
        f = io.BytesIO()
        f.write(encoded)
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return f

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
    """
    Estimate shirt color by sampling a region below the head.
    Priority: face_box (precise), else central torso stripe from person_box.
    """
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
    return (abs(cx2 - cx1) <= thrx) and (abs(cy2 - cy1) <= thry)

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

    logger.debug(f"YOLO: raw={len(boxes)} afterNMS={len(filtered_boxes)}")
    return filtered_boxes, filtered_cids, filtered_conf

def rate_detection(label, confidence, x, y, frame):
    if confidence > 0.85: rating = "Excellent"
    elif confidence > 0.7: rating = "Good"
    elif confidence > 0.5: rating = "Average"
    else: rating = "Poor"
    cv2.putText(frame, f"Rating: {rating}", (x, max(0, y - 25)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

############################
# Person logging (faces) — includes shirt fields + snapshot support
############################
def record_person_event(name, box, camera, shirt_rgb=None, shirt_hex=None, shirt_name=None, snapshot_bgr=None):
    """
    Log a person sighting (respects PERSON_LOG_COOLDOWN). If snapshot_bgr is provided,
    we also save a recall snapshot and attach it to the event as 'snapshot'.
    """
    current_time = time.time()
    last_logged = person_last_logged.get(name, 0)
    if current_time - last_logged < PERSON_LOG_COOLDOWN:
        if shirt_name or shirt_hex or shirt_rgb:
            person_current_shirt_color[name] = {
                "rgb": shirt_rgb, "hex": shirt_hex, "name": shirt_name, "ts": current_time
            }
        logger.debug(f"[{camera}] Skip frequent log for '{name}' ({current_time - last_logged:.1f}s).")
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

    # Save optional snapshot for recall
    snap_path = None
    try:
        if snapshot_bgr is not None and getattr(snapshot_bgr, "size", 0) > 0:
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-")[:60] or "person"
            snap_path = _save_recall_jpeg(PERSON_RECALL_DIR, safe_name, snapshot_bgr)
    except Exception:
        pass
    if snap_path:
        event["snapshot"] = snap_path

    person_memory[name].append(event)
    save_person_memory()
    update_person_dropdown()
    logger.info(f"[{camera}] Person log: {name}"
                f"{' | shirt '+str(shirt_name)+' '+str(shirt_hex) if shirt_hex else ''}"
                f"{' | snapshot saved' if snap_path else ''}")

def record_person_shirt_event(name, box, camera, shirt_rgb, shirt_hex, shirt_name, snapshot_bgr=None):
    now = time.time()
    last = person_last_color_logged.get(name, 0.0)
    if (now - last) < PERSON_COLOR_LOG_COOLDOWN:
        return
    person_last_color_logged[name] = now
    record_person_event(name, box, camera, shirt_rgb=shirt_rgb, shirt_hex=shirt_hex,
                        shirt_name=shirt_name, snapshot_bgr=snapshot_bgr)

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
    logger.info(f"Assigned new Unknown ID: {uid}")
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
    logger.info(f"Removed Unknown ID from pool: {unknown_id}")

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
    logger.info(f"Renamed person: '{old_name}' -> '{new_name}'")

def identify_faces(frame, camera_tag):
    """
    Detect faces and assign names; sample shirt color below each head.
    Returns list of tuples: (top, right, bottom, left, name, shirt_name, shirt_hex, shirt_rgb)
    """
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

        face_crop = frame[max(0, top):max(0, bottom), max(0, left):max(0, right)].copy() \
            if bottom > top and right > left else None

        if name == "Unknown":
            uid = assign_unknown_id(enc)
            name = uid
            record_person_event(name, box_dict, camera=camera_tag,
                                shirt_rgb=s_rgb, shirt_hex=s_hex, shirt_name=s_name,
                                snapshot_bgr=face_crop)

            last_ts = last_face_enqueue_ts_by_uid.get(uid, 0.0)
            if (now - last_ts) >= SNAPSHOT_COOLDOWN_FACE:
                if face_crop is not None and face_crop.size > 0:
                    unknown_faces_queue.append((enc, face_crop, uid, camera_tag, "face"))
                    while len(unknown_faces_queue) > UNKNOWN_FACE_QUEUE_MAX:
                        unknown_faces_queue.pop(0)
                    last_face_enqueue_ts_by_uid[uid] = now
                    logger.info(f"[{camera_tag}] Queued UNKNOWN FACE (rl {SNAPSHOT_COOLDOWN_FACE:.1f}s): {uid}")
        else:
            record_person_event(name, box_dict, camera=camera_tag,
                                shirt_rgb=s_rgb, shirt_hex=s_hex, shirt_name=s_name,
                                snapshot_bgr=face_crop)
            _notify_maybe_person(name, camera_tag, image_bgr=face_crop)

        labeled_faces.append((top, right, bottom, left, name, s_name, s_hex, s_rgb))
        log_camera_event(camera_tag, f"Face: {name} at (x={left}, y={top}, w={right-left}, h={bottom-top})"
                         f"{' | shirt '+str(s_name)+' '+str(s_hex) if s_hex else ''}")

    logger.debug(f"[{camera_tag}] Faces: {len(labeled_faces)}")
    return labeled_faces

############################
# Object events (with snapshot support)
############################
def record_event(display_label, status, box, person=None, held_duration=None, yolo_label=None, camera=None,
                 color_rgb=None, color_hex=None, color_name=None, snapshot_bgr=None):
    """
    Append an object event to memory. Optionally save a recall snapshot if provided.
    """
    if display_label not in object_memory:
        object_memory[display_label] = []
    evt = {
        "time": time.time(),
        "box": box,
        "status": status,
        "person": person,
        "held_duration": held_duration,
        "yolo": yolo_label,
        "camera": camera,
        "color_rgb": color_rgb,
        "color_hex": color_hex,
        "color_name": color_name,
    }

    # Save snapshot only for meaningful state changes
    snap_path = None
    try:
        if snapshot_bgr is not None and getattr(snapshot_bgr, "size", 0) > 0 and status in ("Picked Up", "Placed"):
            safe_label = "".join(c for c in display_label if c.isalnum() or c in " _-")[:60] or "object"
            snap_path = _save_recall_jpeg(OBJECT_RECALL_DIR, safe_label, snapshot_bgr)
    except Exception:
        pass
    if snap_path:
        evt["snapshot"] = snap_path

    object_memory[display_label].append(evt)
    tracked_objects.add(display_label)
    refresh_tracked_objects_list()
    update_object_dropdown()

    x, y, w, h = box
    held_str = f" | Held {held_duration:.2f}s" if held_duration is not None else ""
    color_str = f" | Color {color_name or ''} {color_hex or ''}".strip()
    info = (f"[{camera}] Object: '{display_label}' => {status} (person={person}) "
            f"held={held_duration} yolo={yolo_label}{' '+color_str if color_hex else ''}")
    if snap_path:
        info += " | snapshot saved"
    logger.info(info)
    log_camera_event(camera, f"Object '{display_label}' {status} by {person or 'No one'} at (x={x}, y={y}, w={w}, h={h})"
                    f"{held_str}{(' | '+color_str) if color_hex else ''}")

    try:
        _update_tracked_recall_label(display_label)
    except Exception:
        pass

def update_object_events(display_label, yolo_label, box, person, last_event, camera_tag,
                         color_rgb, color_hex, color_name, snapshot_bgr=None):
    """
    Update per-object state machine and emit events; pass through snapshot_bgr for 'Picked Up'/'Placed'.
    Returns 'Picked Up' | 'Held' | 'Placed' | None
    """
    event_emitted = None
    now = time.time()
    first_seen = display_label not in object_states
    if first_seen:
        object_states[display_label] = {
            'state': 'Placed',
            'last_seen': now,
            'person': None,
            'box': box,
            'picked_up_time': None,
            'last_hold_log': None,
            'yolo': yolo_label,
            'camera': camera_tag,
            'color_rgb': color_rgb,
            'color_hex': color_hex,
            'color_name': color_name,
        }
        record_event(display_label, "Placed", box, person=None, held_duration=None,
                     yolo_label=yolo_label, camera=camera_tag,
                     color_rgb=color_rgb, color_hex=color_hex, color_name=color_name,
                     snapshot_bgr=snapshot_bgr)
        return "Placed"

    st = object_states[display_label]
    prev_state = st['state']
    prev_person = st['person']

    st['last_seen'] = now
    st['box'] = box
    st['yolo'] = yolo_label
    st['camera'] = camera_tag
    st['color_rgb'] = color_rgb
    st['color_hex'] = color_hex
    st['color_name'] = color_name

    if person:
        if prev_state == 'Placed' or (prev_state in ['Picked Up', 'Held'] and prev_person != person):
            st['state'] = 'Picked Up'
            st['person'] = person
            st['picked_up_time'] = now
            st['last_hold_log'] = None
            record_event(display_label, "Picked Up", box, person=person, held_duration=None,
                         yolo_label=yolo_label, camera=camera_tag,
                         color_rgb=color_rgb, color_hex=color_hex, color_name=color_name,
                         snapshot_bgr=snapshot_bgr)
            event_emitted = "Picked Up"
        else:
            st['state'] = 'Held'
            st['person'] = person
            last_hold_log = st['last_hold_log']
            if (last_hold_log is None) or (now - last_hold_log >= HELD_LOG_INTERVAL):
                start_time = st['picked_up_time'] if st['picked_up_time'] else (last_hold_log or now)
                held_duration = max(0.0, now - start_time)
                record_event(display_label, "Held", box, person=person, held_duration=held_duration,
                             yolo_label=yolo_label, camera=camera_tag,
                             color_rgb=color_rgb, color_hex=color_hex, color_name=color_name,
                             snapshot_bgr=None)
                st['last_hold_log'] = now
                event_emitted = "Held"
    else:
        if prev_state in ['Picked Up', 'Held']:
            picked_up_time = st['picked_up_time'] or st['last_seen']
            held_duration = max(0.0, now - picked_up_time)
            record_event(display_label, "Placed", box, person=prev_person, held_duration=held_duration,
                         yolo_label=yolo_label, camera=camera_tag,
                         color_rgb=color_rgb, color_hex=color_hex, color_name=color_name,
                         snapshot_bgr=snapshot_bgr)
            st['state'] = 'Placed'
            st['person'] = None
            st['picked_up_time'] = None
            st['last_hold_log'] = None
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
        try: cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
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
            logger.info(f"{camera_name(idx)} opened via API {api}.")
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
            try: self.cap.release()
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
VEHICLE_LABELS = set([
    "car", "bus", "truck", "motorbike", "bicycle",
    "train", "boat", "aeroplane", "airplane"
])

def process_frame(frame, camera_tag):
    boxes, cids, confs = yolo_detect(frame, DETECTION_CONF_THRESH, NMS_THRESH)
    face_labels = identify_faces(frame, camera_tag)
    now = time.time()

    # Draw faces (includes shirt color info)
    for (ftop, fright, fbottom, fleft, fname, sname, shex, srgb) in face_labels:
        fx, fy, fw, fh = fleft, ftop, (fright - fleft), (fbottom - ftop)
        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 255, 0), 2)
        label = f"{fname} [face] [{camera_tag}]"
        if sname:
            label += f" | shirt {sname} {shex or ''}"
        cv2.putText(frame, label, (fx, max(0, fy - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        if srgb:
            color_swatches_on_frame(frame, fx, fy, srgb)
        current_detections.append((camera_tag, f"face:{fname}" + (f" [shirt {sname}]" if sname else ""),
                                   fx, fy, fw, fh, 1.0))

    # Person boxes
    people = []
    seen_unknown_keys_this_frame = set()

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
            if s_name:
                label_str += f" | shirt {s_name} {s_hex or ''}"
            cv2.putText(frame, label_str, (x, max(0, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if s_rgb:
                color_swatches_on_frame(frame, x, y, s_rgb)

            current_detections.append((camera_tag,
                                       f"person:{person_name}" + (f" [shirt {s_name}]" if s_name else ""),
                                       x, y, w, h, confs[i]))
            people.append(((x, y, w, h), person_name))
            log_camera_event(camera_tag, f"Person: {person_name} at (x={x}, y={y}, w={w}, h={h}) conf={confs[i]:.2f}"
                                         f"{' | shirt '+s_name+' '+s_hex if s_hex else ''}")

            if person_name != "Unknown Person" and s_name:
                box_dict = {"left": int(x), "top": int(y), "right": int(x + w), "bottom": int(y + h)}
                p_crop = frame[max(0, y):max(0, y+h), max(0, x):max(0, x+w)].copy() if h>0 and w>0 else None
                record_person_shirt_event(person_name, box_dict, camera_tag, s_rgb, s_hex, s_name, snapshot_bgr=p_crop)

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
                                logger.info(f"[{camera_tag}] Queued UNKNOWN PERSON (persist {UNKNOWN_PERSON_PERSISTENCE:.1f}s, idle>{int(UNKNOWN_PERSON_IDLE_FRAC*100)}%, rl {UNKNOWN_PERSON_SNAPSHOT_COOLDOWN:.1f}s): {uid}")
                        else:
                            if idle:
                                logger.debug(f"[{camera_tag}] Unknown person idle; not queued.")
                            elif spot_locked:
                                logger.debug(f"[{camera_tag}] Unknown person suppressed by spot lock; not queued.")

    for key in list(unknown_person_presence_start_by_key.keys()):
        cam, _ = key
        if cam == camera_tag and key not in seen_unknown_keys_this_frame:
            unknown_person_presence_start_by_key[key] = 0.0

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
            log_camera_event(camera_tag, f"Object: {display_label_color} at (x={x}, y={y}, w={w}, h={h}) conf={conf:.2f} HEX={color_hex}")

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
                        logger.info(f"[{camera_tag}] Queued VEHICLE (moved>{int(VEHICLE_IDLE_FRAC*100)}%, rl {SNAPSHOT_COOLDOWN_VEHICLE:.1f}s): {vuid}")
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
                camera_tag=camera_tag,
                color_rgb=dom_rgb, color_hex=color_hex, color_name=color_name,
                snapshot_bgr=roi
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
            # Try to crop a current ROI for snapshot
            roi_auto = None
            try:
                xx, yy, ww, hh = st['box']
                xa, ya, xb, yb = max(0, xx), max(0, yy), max(0, xx+ww), max(0, yy+hh)
                roi_auto = frame[ya:yb, xa:xb].copy()
            except Exception:
                pass
            record_event(
                display_label, "Placed", st['box'], person=st['person'],
                held_duration=held_duration, yolo_label=st.get('yolo'), camera=st.get('camera'),
                color_rgb=st.get('color_rgb'), color_hex=st.get('color_hex'), color_name=st.get('color_name'),
                snapshot_bgr=roi_auto
            )
            _notify_maybe_object(display_label, "Placed", st.get('camera'), image_bgr=None)
            st['state'] = 'Placed'
            st['person'] = None
            st['picked_up_time'] = None
            st['last_hold_log'] = None
            logger.info(f"[{st.get('camera')}] Auto-placed '{display_label}' after timeout.")

    return frame

############################
# Tkinter GUI
############################

BRAND_FONT_FAMILY = "Segoe UI"
_BRACED_FAMILY = f"{{{BRAND_FONT_FAMILY}}}"
FONT_BASE = f"{_BRACED_FAMILY} 10"
FONT_SMALL = f"{_BRACED_FAMILY} 9"
FONT_SECTION = f"{_BRACED_FAMILY} 11 bold"
FONT_TITLE = f"{_BRACED_FAMILY} 18 bold"

BRAND_BG = "#040a15"
BRAND_SURFACE = "#0b1627"
BRAND_SURFACE_ALT = "#10213a"
BRAND_SURFACE_STRONG = "#0f1d33"
BRAND_BORDER = "#12304a"
BRAND_ACCENT = "#48ffe2"
BRAND_ACCENT_ALT = "#f5c978"
BRAND_TEXT = "#e2f6ff"

# Ioncore header branding
IONCORE_GREEN = "#6dff7a"
IONCORE_SILVER = "#d1dae4"
IONCORE_LOGO_SVG = """
<svg width=\"96\" height=\"96\" viewBox=\"0 0 96 96\" xmlns=\"http://www.w3.org/2000/svg\">
  <defs>
    <linearGradient id=\"ioncoreGradient\" x1=\"0%\" y1=\"0%\" x2=\"100%\" y2=\"100%\">
      <stop offset=\"0%\" stop-color=\"#6dff7a\"/>
      <stop offset=\"100%\" stop-color=\"#8df2c4\"/>
    </linearGradient>
  </defs>
  <rect x=\"6\" y=\"6\" width=\"84\" height=\"84\" rx=\"18\" ry=\"18\" fill=\"none\" stroke=\"#d1dae4\" stroke-width=\"6\"/>
  <path d=\"M25 69 L48 21 L71 69 Z\" fill=\"url(#ioncoreGradient)\"/>
  <circle cx=\"48\" cy=\"52\" r=\"12\" fill=\"#0b1627\" stroke=\"#d1dae4\" stroke-width=\"4\"/>
  <circle cx=\"48\" cy=\"52\" r=\"6\" fill=\"#6dff7a\"/>
</svg>
"""
ioncore_logo_image = None
BRAND_MUTED = "#94a3b8"
BUTTON_BG = "#152941"
BUTTON_ACTIVE_BG = "#1f3856"

_DEFAULT_BGS = {
    "SystemButtonFace",
    "SystemWindow",
    "SystemWindowBody",
    "#F0F0F0",
    "white",
    "#ffffff",
    "gray85",
    "gray95",
    "",
}
_DEFAULT_FGS = {"SystemButtonText", "black", "#000000"}


def _maybe_config(widget, **kwargs):
    try:
        widget.configure(**kwargs)
    except tk.TclError:
        pass


def apply_branding(widget):
    cls = widget.winfo_class()
    try:
        current_bg = widget.cget("bg")
    except tk.TclError:
        current_bg = None

    if cls in ("Tk", "Toplevel"):
        _maybe_config(widget, bg=BRAND_BG)
        current_bg = BRAND_BG

    if cls in ("Frame", "Labelframe", "TFrame", "Canvas"):
        if current_bg in _DEFAULT_BGS or current_bg is None:
            target_bg = BRAND_SURFACE
            if cls == "Canvas":
                target_bg = BRAND_SURFACE_ALT
            _maybe_config(widget, bg=target_bg)
            current_bg = target_bg

    if cls == "Labelframe":
        _maybe_config(
            widget,
            fg=BRAND_ACCENT,
            font=FONT_SECTION,
            labelanchor="w",
            bd=0,
            highlightthickness=1,
            highlightbackground=BRAND_BORDER,
            highlightcolor=BRAND_BORDER,
            padx=10,
            pady=8,
        )

    if cls == "Label":
        if current_bg in _DEFAULT_BGS or current_bg is None:
            parent_bg = BRAND_SURFACE
            try:
                parent_bg = widget.master.cget("bg")
            except Exception:
                pass
            _maybe_config(widget, bg=parent_bg)
        try:
            current_fg = widget.cget("fg")
        except tk.TclError:
            current_fg = None
        if current_fg in _DEFAULT_FGS or current_fg is None:
            _maybe_config(widget, fg=BRAND_TEXT)
        _maybe_config(widget, font=FONT_BASE)

    if cls in ("Button", "Checkbutton", "Radiobutton"):
        _maybe_config(widget, font=FONT_BASE, borderwidth=0, relief=tk.FLAT)
        if current_bg in _DEFAULT_BGS or current_bg in {None, "", "SystemButtonFace"}:
            _maybe_config(
                widget,
                bg=BUTTON_BG,
                fg=BRAND_TEXT,
                activebackground=BUTTON_ACTIVE_BG,
                activeforeground=BRAND_TEXT,
            )
        else:
            _maybe_config(widget, activeforeground=BRAND_TEXT)
        _maybe_config(
            widget,
            highlightthickness=1,
            highlightbackground=BRAND_BORDER,
            highlightcolor=BRAND_BORDER,
        )
        if cls in ("Checkbutton", "Radiobutton") and (
            current_bg in _DEFAULT_BGS or current_bg in {None, "", "SystemButtonFace"}
        ):
            _maybe_config(widget, selectcolor=BRAND_SURFACE_ALT)

    if cls in ("Entry", "Spinbox"):
        if current_bg in _DEFAULT_BGS or current_bg in {"white", "#ffffff"}:
            _maybe_config(widget, bg=BRAND_SURFACE_STRONG)
        _maybe_config(
            widget,
            fg=BRAND_TEXT,
            insertbackground=BRAND_ACCENT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BRAND_BORDER,
            highlightcolor=BRAND_BORDER,
            font=FONT_BASE,
        )

    if cls == "Listbox":
        _maybe_config(
            widget,
            bg=BRAND_SURFACE_STRONG,
            fg=BRAND_TEXT,
            selectbackground=BRAND_ACCENT,
            selectforeground=BRAND_BG,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=BRAND_BORDER,
            relief=tk.FLAT,
            font=FONT_SMALL,
        )

    if cls == "Scrollbar":
        _maybe_config(widget, bg=BRAND_SURFACE_ALT, troughcolor=BRAND_SURFACE_STRONG, activebackground=BUTTON_ACTIVE_BG)

    if cls == "Menubutton":
        _maybe_config(
            widget,
            bg=BRAND_SURFACE_ALT,
            fg=BRAND_TEXT,
            activebackground=BUTTON_ACTIVE_BG,
            activeforeground=BRAND_TEXT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=BRAND_BORDER,
            highlightcolor=BRAND_BORDER,
            relief=tk.FLAT,
            font=FONT_BASE,
        )

    if cls == "Canvas" and widget.cget("highlightthickness") != 0:
        _maybe_config(widget, highlightthickness=0)

    if cls == "Text":
        _maybe_config(
            widget,
            bg=BRAND_SURFACE_STRONG,
            fg=BRAND_TEXT,
            insertbackground=BRAND_ACCENT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BRAND_BORDER,
            highlightcolor=BRAND_BORDER,
            font=FONT_SMALL,
        )

    for child in widget.winfo_children():
        apply_branding(child)


root = tk.Tk()
root.title("Multi-Camera Recognition (Feeds • Notifications • Vehicle DB)")
root.geometry("1366x900")
root.configure(bg=BRAND_BG)

root.option_add("*Font", f"{_BRACED_FAMILY} 10")
root.option_add("*Label*Foreground", BRAND_TEXT)
root.option_add("*Label*Background", BRAND_SURFACE)
root.option_add("*LabelFrame*Font", f"{_BRACED_FAMILY} 11 bold")
root.option_add("*LabelFrame*Foreground", BRAND_ACCENT)
root.option_add("*Entry*Background", BRAND_SURFACE_STRONG)
root.option_add("*Entry*Foreground", BRAND_TEXT)
root.option_add("*Spinbox*Background", BRAND_SURFACE_STRONG)
root.option_add("*Spinbox*Foreground", BRAND_TEXT)
root.option_add("*Listbox*Background", BRAND_SURFACE_STRONG)
root.option_add("*Listbox*Foreground", BRAND_TEXT)
root.option_add("*Menu.background", BRAND_SURFACE_STRONG)
root.option_add("*Menu.foreground", BRAND_TEXT)
root.option_add("*Menu.activeBackground", BUTTON_ACTIVE_BG)
root.option_add("*Menu.activeForeground", BRAND_TEXT)

style = ttk.Style()
try:
    style.theme_use("clam")
except tk.TclError:
    pass
style.configure("TFrame", background=BRAND_SURFACE)
style.configure("TLabelframe", background=BRAND_SURFACE, borderwidth=0)
style.configure("TLabelframe.Label", background=BRAND_SURFACE, foreground=BRAND_ACCENT, font=FONT_SECTION)
style.configure("TLabel", background=BRAND_SURFACE, foreground=BRAND_TEXT, font=FONT_BASE)
style.configure("TNotebook", background=BRAND_SURFACE, borderwidth=0, padding=0)
style.configure("TNotebook.Tab", background=BRAND_SURFACE_ALT, foreground=BRAND_MUTED, padding=(14, 8))
style.map("TNotebook.Tab", background=[("selected", BRAND_SURFACE_STRONG)], foreground=[("selected", BRAND_TEXT)])
try:
    style.configure(
        "TCombobox",
        fieldbackground=BRAND_SURFACE_STRONG,
        background=BRAND_SURFACE_STRONG,
        foreground=BRAND_TEXT,
        bordercolor=BRAND_BORDER,
        darkcolor=BRAND_BORDER,
        lightcolor=BRAND_BORDER,
        arrowcolor=BRAND_ACCENT,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", BRAND_SURFACE_STRONG)],
        foreground=[("readonly", BRAND_TEXT)],
        background=[("readonly", BRAND_SURFACE_STRONG)],
    )
except tk.TclError:
    pass
style.configure("TButton", background=BUTTON_BG, foreground=BRAND_TEXT, font=FONT_BASE)
style.map("TButton", background=[("active", BUTTON_ACTIVE_BG)])

# Grid config
for c in range(3):
    root.columnconfigure(c, weight=1, uniform="cols")
root.rowconfigure(0, weight=0)  # brand header
root.rowconfigure(1, weight=1)  # feeds
root.rowconfigure(2, weight=2)  # upper row
root.rowconfigure(3, weight=2)  # middle row
root.rowconfigure(4, weight=2)  # lower row
root.rowconfigure(5, weight=0)  # bottom toolbar

brand_header = tk.Frame(
    root,
    bg=BRAND_SURFACE,
    highlightbackground=BRAND_BORDER,
    highlightcolor=BRAND_BORDER,
    highlightthickness=1,
    bd=0,
    padx=18,
    pady=16,
)
brand_header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 6))
brand_header.columnconfigure(0, weight=1)

status_text_var = tk.StringVar(value="Review the media artifacts captured by Sentinel automations. Real-time alert snapshots & intelligence drops.")


def _refresh_command_center():
    try:
        refresh_tracked_objects_list()
    except Exception:
        pass
    try:
        refresh_tracked_persons_list()
    except Exception:
        pass
    try:
        refresh_live_logs_ui()
    except Exception:
        pass
    try:
        update_unknown_count()
    except Exception:
        pass
    status_text_var.set(f"Command center refreshed • {time.strftime('%H:%M:%S')}")


def _contact_ioncore():
    try:
        webbrowser.open("mailto:ioncoreenergy@gmail.com")
    except Exception:
        messagebox.showinfo("Contact", "Email ioncoreenergy@gmail.com")


def _launch_media_vault():
    _start_media_server_if_needed()
    try:
        port = int(notify_config.get("media_hosting", {}).get("port", 8765))
        url = f"http://{_get_local_ip()}:{port}/"
    except Exception:
        url = "http://127.0.0.1:8765/"
    try:
        webbrowser.open(url)
    except Exception:
        messagebox.showinfo("Media Vault", f"Open the Sentinel media vault at {url}")


header_bar = tk.Frame(brand_header, bg=BRAND_SURFACE)
header_bar.grid(row=0, column=0, sticky="ew")
header_bar.columnconfigure(0, weight=1)
header_bar.columnconfigure(1, weight=0)

logo_wrap = tk.Frame(header_bar, bg=BRAND_SURFACE)
logo_wrap.grid(row=0, column=0, sticky="w")


def _load_ioncore_logo():
    global ioncore_logo_image
    if ioncore_logo_image is not None:
        return ioncore_logo_image
    try:
        import cairosvg

        png_bytes = cairosvg.svg2png(
            bytestring=IONCORE_LOGO_SVG.encode("utf-8"), output_width=72, output_height=72
        )
        ioncore_logo_image = ImageTk.PhotoImage(Image.open(io.BytesIO(png_bytes)))
        return ioncore_logo_image
    except Exception as exc:
        logger.debug("Falling back to canvas logo: %s", exc)
        ioncore_logo_image = None
        return None


logo_image = _load_ioncore_logo()
if logo_image is not None:
    logo_label = tk.Label(logo_wrap, image=logo_image, bg=BRAND_SURFACE)
    logo_label.image = logo_image
    logo_label.pack(side=tk.LEFT, padx=(0, 12))
else:
    logo_canvas = tk.Canvas(
        logo_wrap,
        width=60,
        height=60,
        bg=BRAND_SURFACE,
        highlightthickness=0,
    )
    logo_canvas.pack(side=tk.LEFT, padx=(0, 12))
    logo_canvas.create_oval(6, 6, 54, 54, fill=IONCORE_GREEN, outline=IONCORE_SILVER, width=3)
    logo_canvas.create_text(30, 30, text="IC", fill=BRAND_BG, font=f"{_BRACED_FAMILY} 16 bold")

logo_text = tk.Frame(logo_wrap, bg=BRAND_SURFACE)
logo_text.pack(side=tk.LEFT)
tk.Label(
    logo_text,
    text="IONCORE SENTINEL",
    font=f"{_BRACED_FAMILY} 16 bold",
    fg=IONCORE_GREEN,
    bg=BRAND_SURFACE,
).pack(anchor="w")
tk.Label(
    logo_text,
    text="Security Media Vault Dashboard",
    font=f"{_BRACED_FAMILY} 11",
    fg=IONCORE_SILVER,
    bg=BRAND_SURFACE,
).pack(anchor="w")

brand_body = tk.Frame(brand_header, bg=BRAND_SURFACE)
brand_body.grid(row=1, column=0, sticky="ew", pady=(12, 0))
brand_body.columnconfigure(0, weight=1)
brand_body.columnconfigure(1, weight=0)

brand_left = tk.Frame(brand_body, bg=BRAND_SURFACE)
brand_left.grid(row=0, column=0, sticky="nw")
brand_left.grid_columnconfigure(0, weight=1)

status_label = tk.Label(
    brand_left,
    textvariable=status_text_var,
    font=f"{_BRACED_FAMILY} 11",
    fg=BRAND_TEXT,
    bg=BRAND_SURFACE,
    wraplength=560,
    justify="left",
)
status_label.grid(row=0, column=0, sticky="w")

badge_row = tk.Frame(brand_left, bg=BRAND_SURFACE)
badge_row.grid(row=1, column=0, sticky="w", pady=(14, 0))

for title, subtitle in (
    ("Zero Lag", "Edge-computed routing keeps every feed synchronized with Command."),
    ("Quantum Secure", "Ioncore encryption hardens telemetry across the Sentinel mesh."),
    ("Always On", "Resilient storage preserves alerts through any event horizon."),
):
    card = tk.Frame(
        badge_row,
        bg=BRAND_SURFACE_ALT,
        highlightbackground=BRAND_BORDER,
        highlightcolor=BRAND_BORDER,
        highlightthickness=1,
        bd=0,
        padx=14,
        pady=10,
    )
    card.pack(side=tk.LEFT, padx=(0, 12))
    tk.Label(card, text=title, font=f"{_BRACED_FAMILY} 10 bold", fg=BRAND_ACCENT, bg=BRAND_SURFACE_ALT).pack(anchor="w")
    tk.Label(
        card,
        text=subtitle,
        font=f"{_BRACED_FAMILY} 9",
        fg=BRAND_MUTED,
        bg=BRAND_SURFACE_ALT,
        wraplength=160,
        justify="left",
    ).pack(anchor="w", pady=(4, 0))

brand_right = tk.Frame(brand_body, bg=BRAND_SURFACE)
brand_right.grid(row=0, column=1, sticky="ne", padx=(24, 0))

tk.Label(
    brand_right,
    text="Sentinel Security Network",
    font=f"{_BRACED_FAMILY} 11 bold",
    bg=BRAND_SURFACE_ALT,
    fg=IONCORE_SILVER,
    padx=14,
    pady=8,
).pack(anchor="e")
tk.Label(
    brand_right,
    text="Powered by Ioncore Intelligence",
    font=f"{_BRACED_FAMILY} 10",
    bg=BRAND_SURFACE,
    fg=BRAND_MUTED,
).pack(anchor="e", pady=(8, 0))

header_collapsed = tk.BooleanVar(value=False)


def _toggle_brand_header():
    collapsed = header_collapsed.get()
    if collapsed:
        brand_body.grid()
        brand_header.configure(pady=16)
        toggle_btn.configure(text="Minimize Header")
    else:
        brand_body.grid_remove()
        brand_header.configure(pady=10)
        toggle_btn.configure(text="Expand Header")
    header_collapsed.set(not collapsed)


actions = tk.Frame(header_bar, bg=BRAND_SURFACE)
actions.grid(row=0, column=1, sticky="e")

contact_btn = tk.Button(actions, text="Contact Ioncore", command=_contact_ioncore, bg=BRAND_SURFACE_ALT, fg=BRAND_ACCENT)
contact_btn.pack(side=tk.LEFT, padx=6)
contact_btn.configure(activebackground=BUTTON_ACTIVE_BG, activeforeground=BRAND_TEXT)
vault_btn = tk.Button(actions, text="Open Media Vault", command=_launch_media_vault, bg=BRAND_ACCENT, fg=BRAND_BG)
vault_btn.pack(side=tk.LEFT, padx=6)
vault_btn.configure(activebackground=BRAND_ACCENT_ALT, activeforeground=BRAND_BG)
refresh_btn = tk.Button(actions, text="Refresh Command Center", command=_refresh_command_center)
refresh_btn.pack(side=tk.LEFT, padx=6)
toggle_btn = tk.Button(actions, text="Minimize Header", command=_toggle_brand_header, bg=BRAND_SURFACE_ALT, fg=IONCORE_SILVER)
toggle_btn.pack(side=tk.LEFT, padx=(12, 0))

############################
# Row 1 (FULL WIDTH): Video Feeds with horizontal scroll
############################
video_feed_frame = tk.LabelFrame(root, text="Live Sentinel Feeds")
video_feed_frame.grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="nsew")

video_canvas = tk.Canvas(video_feed_frame, highlightthickness=0, bg=BRAND_SURFACE_ALT)
h_scroll = tk.Scrollbar(video_feed_frame, orient="horizontal", command=video_canvas.xview)
video_canvas.configure(xscrollcommand=h_scroll.set)
video_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

video_strip = tk.Frame(video_canvas, bg=BRAND_SURFACE_ALT)
video_canvas.create_window((0, 0), window=video_strip, anchor="nw")

def _update_video_strip_scrollregion(event=None):
    try:
        video_canvas.configure(scrollregion=video_canvas.bbox("all"))
    except Exception:
        pass
video_strip.bind("<Configure>", _update_video_strip_scrollregion)

def make_camera_cell(parent, title):
    cell = tk.Frame(
        parent,
        bd=0,
        bg=BRAND_SURFACE_ALT,
        highlightbackground=BRAND_BORDER,
        highlightcolor=BRAND_BORDER,
        highlightthickness=1,
        padx=6,
        pady=6,
    )
    tk.Label(
        cell,
        text=title,
        anchor="w",
        bg=BRAND_SURFACE_ALT,
        fg=BRAND_MUTED,
        font=f"{_BRACED_FAMILY} 10 bold",
    ).pack(fill=tk.X, pady=(0, 4))
    img_lbl = tk.Label(cell, bg="#050b12")
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
        x = (sw - ww)//2
        y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1000x700")

    header = tk.Frame(win)
    header.pack(side=tk.TOP, fill=tk.X)
    for line in (header_lines or []):
        tk.Label(header, text=line, anchor="w", justify="left").pack(side=tk.TOP, anchor="w", padx=8, pady=2)

    body = tk.Frame(win)
    body.pack(fill=tk.BOTH, expand=True)
    lb = tk.Listbox(body)
    sb = tk.Scrollbar(body, orient=tk.VERTICAL, command=lb.yview)
    lb.config(yscrollcommand=sb.set)
    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    for r in rows or []:
        lb.insert(tk.END, r)
    lb.see(tk.END)

    def _export_txt():
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            initialfile=title.replace(" ", "_") + ".txt"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            if header_lines:
                for hl in header_lines:
                    f.write(hl + "\n")
                f.write("\n")
            for r in rows or []:
                f.write(r + "\n")
        messagebox.showinfo("Saved", f"Saved to {path}")

    footer = tk.Frame(win)
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    tk.Button(footer, text="Save as .txt", command=_export_txt).pack(side=tk.LEFT, padx=6, pady=6)
    tk.Button(footer, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=6, pady=6)
    apply_branding(win)

############################
# LEFT COLUMN STACK (rows 1–3): Controls + Panel (Objects/Persons) + Tuner Overlay
############################
col0_stack = tk.Frame(root, bg=BRAND_SURFACE)
col0_stack.grid(row=2, column=0, rowspan=3, padx=12, pady=(0, 12), sticky="nsew")
col0_stack.rowconfigure(0, weight=0)
col0_stack.rowconfigure(1, weight=1)
col0_stack.columnconfigure(0, weight=1)

# Controls
controls_frame = tk.LabelFrame(col0_stack, text="Controls (Cameras • Snapshots • Display)")
controls_frame.grid(row=0, column=0, sticky="ew")
controls_frame.columnconfigure(0, weight=1)

cam_ctrl_frame = tk.LabelFrame(controls_frame, text="Cameras")
cam_ctrl_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6,3))

# Row: Camera toggles (flip style)
toggle_bar = tk.Frame(cam_ctrl_frame)
toggle_bar.pack(fill="x")

def on_toggle(idx):
    if camera_vars[idx].get() == 1:
        enable_camera(idx)
    else:
        disable_camera(idx)
    try:
        cam_toggle_text[idx].set(f"{camera_name(idx)} {'ON' if camera_vars[idx].get()==1 else 'OFF'}")
    except Exception:
        pass

for i in range(MAX_CAMERAS):
    var = tk.IntVar(value=0)
    camera_vars[i] = var
    cam_toggle_text[i] = tk.StringVar(value=f"{camera_name(i)} OFF")
    cb = tk.Checkbutton(toggle_bar, textvariable=cam_toggle_text[i], variable=var,
                        indicatoron=False, command=lambda ii=i: on_toggle(ii))
    cb.pack(side=tk.LEFT, padx=3, pady=2)

# Row: Panel mode (Objects/Persons) + Tuner toggle
panel_row = tk.Frame(cam_ctrl_frame)
panel_row.pack(fill="x", padx=6, pady=(4,3))

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

# Tuner flip toggle (Open/Close overlay)
TUNER_SWITCH_VAR = tk.IntVar(value=0)
def on_tuner_switch():
    if TUNER_SWITCH_VAR.get() == 1:
        show_tuner_overlay()
    else:
        hide_tuner_overlay()
tk.Checkbutton(panel_row, text="Tuner", variable=TUNER_SWITCH_VAR,
               indicatoron=False, command=on_tuner_switch).pack(side=tk.RIGHT, padx=4)

# Snapshot toggles (flip style)
snap_frame = tk.LabelFrame(controls_frame, text="Snapshot Toggles")
snap_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=(3,3))

ENABLE_VEHICLE_SNAPSHOTS_VAR = tk.IntVar(value=1)
ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR = tk.IntVar(value=1)
veh_snap_text = tk.StringVar(value="Vehicle Snapshots: ON")
unk_snap_text = tk.StringVar(value="Unknown Person Snapshots: ON")

def _update_snap_text():
    veh_snap_text.set(f"Vehicle Snapshots: {'ON' if ENABLE_VEHICLE_SNAPSHOTS_VAR.get()==1 else 'OFF'}")
    unk_snap_text.set(f"Unknown Person Snapshots: {'ON' if ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR.get()==1 else 'OFF'}")

tk.Checkbutton(snap_frame, textvariable=veh_snap_text,
               variable=ENABLE_VEHICLE_SNAPSHOTS_VAR, indicatoron=False,
               command=_update_snap_text).pack(side=tk.LEFT, padx=4, pady=2)
tk.Checkbutton(snap_frame, textvariable=unk_snap_text,
               variable=ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR, indicatoron=False,
               command=_update_snap_text).pack(side=tk.LEFT, padx=4, pady=2)

# Display toggle (flip style)
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

#########################################
# LEFT lower area (panel): Objects or Persons
#########################################
lower_area = tk.Frame(col0_stack)
lower_area.grid(row=1, column=0, sticky="nsew")
lower_area.rowconfigure(0, weight=1)
lower_area.columnconfigure(0, weight=1)

# --- Objects panel (default) ---
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
    tracked_objects_listbox.delete(0, tk.END)
    for obj in sorted(tracked_objects):
        tracked_objects_listbox.insert(tk.END, obj)
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

# Refined: keep only History here (Tuner moved up; Refresh removed)
tk.Button(btn_tracked_row, text="Show Selected Object History",
          command=show_selected_history).pack(side=tk.LEFT, padx=3)

tracked_recall_label = tk.Label(btn_tracked_row, text="", fg="blue", anchor="w")
tracked_recall_label.pack(side=tk.LEFT, padx=6, pady=2, fill="x", expand=True)

def _update_tracked_recall_label(obj=None):
    try:
        if obj is None:
            sel = tracked_objects_listbox.curselection()
            obj = tracked_objects_listbox.get(sel[0]) if sel else None
        if not obj or obj not in object_memory or not object_memory[obj]:
            tracked_recall_label.config(text="")
            return
        last_event = object_memory[obj][-1]
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_event["time"]))
        x, y, w, h = last_event["box"]
        status = last_event["status"]
        person = last_event["person"] if last_event["person"] else "No one"
        cam = last_event.get("camera", "Unknown")
        held_str = f" | Held {last_event['held_duration']:.2f}s" if last_event["held_duration"] is not None else ""
        color_part = ""
        if last_event.get("color_hex"):
            color_part = f" | Color {last_event.get('color_name','')} {last_event.get('color_hex','')}"
        tracked_recall_label.config(text=f"[{cam}] Last {obj}: {status} by {person} @ {t_str}{held_str}{color_part}")
    except Exception:
        pass

tracked_objects_listbox.bind('<Double-1>', lambda e: show_selected_history())
tracked_objects_listbox.bind('<<ListboxSelect>>', lambda e: _update_tracked_recall_label())

# --- Persons panel (togglable) ---
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
    tracked_persons_listbox.delete(0, tk.END)
    for p in sorted(person_memory.keys()):
        tracked_persons_listbox.insert(tk.END, p)
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

tk.Button(p_btn_row, text="Show Selected Person History",
          command=show_selected_person_history).pack(side=tk.LEFT, padx=3)

p_last_label = tk.Label(p_btn_row, text="", fg="green", anchor="w")
p_last_label.pack(side=tk.LEFT, padx=6, pady=2, fill="x", expand=True)

def _update_tracked_person_recall_label(name=None):
    try:
        if name is None:
            sel = tracked_persons_listbox.curselection()
            name = tracked_persons_listbox.get(sel[0]) if sel else None
        if not name or name not in person_memory or not person_memory[name]:
            p_last_label.config(text="")
            return
        last_event = person_memory[name][-1]
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_event["time"]))
        b = last_event["box"]
        x, y = b["left"], b["top"]
        w, h = b["right"] - b["left"], b["bottom"] - b["top"]
        cam = last_event.get("camera", "Unknown")
        shirt = ""
        if last_event.get("shirt_color_hex"):
            shirt = f" | Shirt {last_event.get('shirt_color_name','')} {last_event.get('shirt_color_hex','')}"
        p_last_label.config(text=f"[{cam}] Last {name}: {t_str} (x={x},y={y},w={w},h={h}){shirt}")
    except Exception:
        pass

tracked_persons_listbox.bind('<Double-1>', lambda e: show_selected_person_history())
tracked_persons_listbox.bind('<<ListboxSelect>>', lambda e: _update_tracked_person_recall_label())

# start with persons panel hidden (Objects is default)
tracked_persons_frame.grid_remove()

#########################################
# Tuner Overlay (covering entire left panel area)
#########################################
tuner_overlay = None
tuner_overlay_state = {"visible": False}

# Tuning vars
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

    logger.info(f"Vehicle idle {VEHICLE_IDLE_FRAC*100:.1f}%, Unknown idle {UNKNOWN_PERSON_IDLE_FRAC*100:.1f}% | Retag hold {RETAG_HOLD_SECONDS:.1f}s")

    for idx, (worker, name, lbl) in camera_windows.items():
        worker.set_resolution(new_w, new_h)
        worker.set_fps_cap(FPS_CAP)

    global FEED_W, FEED_H
    FEED_W, FEED_H = new_w, new_h
    _update_video_strip_scrollregion()

    messagebox.showinfo("Tuning Applied", "Updated settings.")

def apply_and_close_tuner():
    apply_tuning()
    hide_tuner_overlay()

def build_tuner_overlay():
    # container overlay that covers the entire left lower area
    ov = tk.Frame(
        lower_area,
        bd=0,
        bg=BRAND_SURFACE,
        highlightbackground=BRAND_BORDER,
        highlightcolor=BRAND_BORDER,
        highlightthickness=1,
    )
    ov.place(in_=lower_area, relx=0, rely=0, relwidth=1, relheight=1)

    # Top bar
    top = tk.Frame(ov, bg=BRAND_SURFACE_ALT)
    top.pack(side=tk.TOP, fill="x")
    tk.Label(
        top,
        text="Tuning (Recognition & Idle Thresholds)",
        fg=BRAND_TEXT,
        bg=BRAND_SURFACE_ALT,
        font=f"{_BRACED_FAMILY} 11 bold",
    ).pack(side=tk.LEFT, padx=8, pady=6)
    tk.Button(top, text="Close", command=hide_tuner_overlay).pack(side=tk.RIGHT, padx=6, pady=6)

    # Scrollable body
    body_wrap = tk.Frame(ov, bg=BRAND_SURFACE)
    body_wrap.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    canvas = tk.Canvas(body_wrap, highlightthickness=0, bg=BRAND_SURFACE)
    vbar = tk.Scrollbar(body_wrap, orient=tk.VERTICAL, command=canvas.yview)
    inner = tk.Frame(canvas, bg=BRAND_SURFACE)

    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=vbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)

    form = tk.LabelFrame(inner, text="Parameters")
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

    # Footer buttons
    fbar = tk.Frame(inner, bg=BRAND_SURFACE)
    fbar.grid(row=1, column=0, sticky="ew", padx=6, pady=(10,0))
    tk.Button(fbar, text="Apply & Close", command=apply_and_close_tuner).pack(side=tk.LEFT, padx=4)
    tk.Button(fbar, text="Cancel", command=hide_tuner_overlay).pack(side=tk.LEFT, padx=4)

    # allow mousewheel scroll
    def _on_mousewheel(event):
        try:
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except Exception:
            pass
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    apply_branding(ov)
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
# Optional: compact tuning popup (unchanged)
#########################################
def open_tuning_popup():
    win = tk.Toplevel(root)
    win.title("Tuning")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = 520, 560
        x = (sw - ww)//2
        y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("520x560+120+80")

    grid = tk.Frame(win)
    grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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
    apply_branding(win)

############################
# Row 1 Column 1: REVIEW QUEUE
############################
unknown_face_frame = tk.LabelFrame(root, text="Review Queue (Faces / Persons / Vehicles)")
unknown_face_frame.grid(row=2, column=1, padx=12, pady=(0, 12), sticky="nsew")
unknown_face_frame.columnconfigure(0, weight=1)
unknown_face_frame.rowconfigure(7, weight=1)

label_info = tk.Label(unknown_face_frame, text="Double-click preview for full-size. Save only if FACE. Use vehicle form below for VEHICLE.")
label_info.grid(row=0, column=0, sticky="w", padx=4, pady=(4,2))

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
    win.title(f"Queue Item: {uid} | {kind.upper()} | {cam}")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = int(sw*0.7), int(sh*0.7)
        x = (sw - ww)//2
        y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1200x800")

    top_bar = tk.Frame(win)
    top_bar.pack(side=tk.TOP, fill=tk.X)
    tk.Label(top_bar, text=f"{uid}  |  {kind.upper()}  |  {cam}").pack(side=tk.LEFT, padx=8, pady=6)

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
                title_lbl.config(text=f"{uid2}  |  {kind2.upper()}  |  {cam2}")
            else:
                win.destroy()
        except Exception:
            win.destroy()

    tk.Button(top_bar, text="Reject & Next", command=_reject_and_next).pack(side=tk.RIGHT, padx=6)
    tk.Button(top_bar, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=6)
    title_lbl = tk.Label(top_bar, text="")
    title_lbl.pack_forget()

    canvas_frame = tk.Frame(win)
    canvas_frame.pack(fill=tk.BOTH, expand=True)

    vbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
    hbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
    canvas = tk.Canvas(canvas_frame, background="black",
                       yscrollcommand=vbar.set, xscrollcommand=hbar.set)
    vbar.config(command=canvas.yview); hbar.config(command=canvas.xview)
    vbar.pack(side=tk.RIGHT, fill=tk.Y); hbar.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    imgtk = ImageTk.PhotoImage(pil)
    canvas.create_image(0, 0, anchor="nw", image=imgtk)
    canvas.image = imgtk
    canvas.config(scrollregion=(0, 0, pil.width, pil.height))

    win.bind("<Escape>", lambda e: win.destroy())
    win.bind("r", lambda e: _reject_and_next())
    apply_branding(win)

tk.Button(button_frame, text="Open Full Size", command=open_fullsize_window).grid(row=0, column=0, padx=4, pady=2, sticky="ew")
tk.Button(button_frame, text="Save Face", command=save_face_callback).grid(row=0, column=1, padx=4, pady=2, sticky="ew")
tk.Button(button_frame, text="Reject", command=reject_face_callback).grid(row=0, column=2, padx=4, pady=2, sticky="ew")

entry_name = tk.Entry(unknown_face_frame)
entry_name.grid(row=2, column=0, sticky="ew", padx=4, pady=2)

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
    x_off = (box_w - new_w) // 2
    y_off = (box_h - new_h) // 2
    canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
    return canvas

def show_unknown_face_image():
    if unknown_faces_queue:
        _, img, uid, cam, kind = unknown_faces_queue[0]
        disp = img.copy()
        cv2.putText(disp, f"{uid} | {cam} | {kind.upper()}", (6, 22),
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

# VEHICLE SAVE AREA (unchanged)
veh_form = tk.LabelFrame(unknown_face_frame, text="Save Vehicle (active when current item is VEHICLE)")
veh_form.grid(row=4, column=0, sticky="ew", padx=4, pady=4)
for c in range(6):
    veh_form.columnconfigure(c, weight=1)

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
        messagebox.showinfo("No item", "Review queue is empty.")
        return
    enc0, img_bgr, uid0, cam0, kind0 = unknown_faces_queue[0]
    if kind0 != "vehicle":
        messagebox.showinfo("Not a vehicle", "Current queue item is not a VEHICLE.")
        return
    make = veh_make_var.get().strip()
    model = veh_model_var.get().strip()
    plate = veh_plate_var.get().strip()
    fleet = veh_fleet_var.get().strip()
    nick = veh_nick_var.get().strip()

    color_name, color_hex = _peek_vehicle_color_from_current(img_bgr)
    if color_name and color_hex:
        veh_color_show_var.set(f"{color_name} {color_hex}")
    else:
        veh_color_show_var.set("(unknown)")

    h, w = img_bgr.shape[:2]
    box = (0, 0, w, h)
    vid = register_vehicle_sighting(
        img_bgr, make, model, plate, fleet, nick,
        color_name, color_hex, cam0, box, assoc_person=None
    )
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
# Row 1 Column 2: Right-top — Detections + Notifications + Vehicles
############################
right_top_tabs = ttk.Notebook(root)
right_top_tabs.grid(row=2, column=2, padx=12, pady=(0, 12), sticky="nsew")

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
        messagebox.showinfo("No selection", "Please select a detection to label.")
        return
    new_label_base = detection_label_entry.get().strip()
    if not new_label_base:
        messagebox.showwarning("Invalid Label", "Please enter a valid label first.")
        return
    idx = sel[0]
    cam, label, *_ = current_detections[idx]
    if label.startswith("person:") or label.startswith("face:"):
        messagebox.showinfo("Not Applicable", "Custom labeling applies to objects, not persons/faces.")
        return
    st = object_states.get(label)
    if not st:
        messagebox.showwarning("Unavailable", "Underlying object state not found yet. Try after the object is seen.")
        return
    yolo_label = st.get("yolo")
    color_name = st.get("color_name")
    if yolo_label and color_name:
        custom_labels_by_yolo_and_color[(yolo_label, color_name)] = new_label_base
        new_display = get_display_label(yolo_label, color_name=color_name)
    else:
        custom_labels_by_yolo[yolo_label] = new_label_base
        new_display = new_label_base
    _rename_object_everywhere(label, new_display)
    detection_label_entry.delete(0, tk.END)
    refresh_current_detections_list()

tk.Button(
    tab_detections,
    text="Save Custom Label for Selected Detection",
    command=custom_label_selected_detection
).grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 6))

# Tab: Notifications
tab_notify = tk.Frame(right_top_tabs)
right_top_tabs.add(tab_notify, text="Notifications")
for r in range(6):
    tab_notify.rowconfigure(r, weight=0)
tab_notify.rowconfigure(5, weight=1)
tab_notify.columnconfigure(0, weight=1)
tab_notify.columnconfigure(1, weight=1)

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
for c in range(4):
    cred_frame.columnconfigure(c, weight=1)

pushover_token_var = StringVar()
pushover_user_var = StringVar()
telegram_bot_var = StringVar()
telegram_chat_var = StringVar()
webhook_url_var = StringVar()
tw_sid_var = StringVar()
tw_token_var = StringVar()
tw_from_var = StringVar()
tw_to_var = StringVar()

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
for c in range(4):
    host_frame.columnconfigure(c, weight=1)
tk.Label(host_frame, text="Mode").grid(row=0, column=0, sticky="w", padx=4, pady=2)
ttk.Combobox(host_frame, textvariable=hosting_mode_var, values=["none","builtin","static_url_prefix"], width=16).grid(row=0, column=1, sticky="w", padx=4, pady=2)
tk.Label(host_frame, text="Port (builtin)").grid(row=0, column=2, sticky="w", padx=4, pady=2)
tk.Spinbox(host_frame, from_=1024, to=65535, textvariable=hosting_port_var, width=8).grid(row=0, column=3, sticky="w", padx=4, pady=2)
tk.Label(host_frame, text="Base URL (static)").grid(row=1, column=0, sticky="w", padx=4, pady=2)
tk.Entry(host_frame, textvariable=hosting_baseurl_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=4, pady=2)

subs_frame = tk.LabelFrame(tab_notify, text="Subscriptions")
subs_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
for c in range(6):
    subs_frame.columnconfigure(c, weight=1)
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

def notify_send_test():
    _pull_ui_to_config()
    test_img = None
    for _, (worker, cam_name, _) in camera_windows.items():
        fr = worker.get_frame()
        if fr is not None and fr.size > 0:
            test_img = fr
            break
    ok = send_notification("Test Notification", "This is a test from the app.", key_for_cooldown=None, image_bgr=test_img)
    if ok:
        messagebox.showinfo("Notifications", "Test sent.")
    else:
        messagebox.showwarning("Notifications", "Test failed. Check credentials and channel.")

btns = tk.Frame(tab_notify)
btns.grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
tk.Button(btns, text="Save", command=save_notify_ui).pack(side=tk.LEFT, padx=4)
tk.Button(btns, text="Test", command=notify_send_test).pack(side=tk.LEFT, padx=4)

# Tab: Vehicles (unchanged)
tab_vehicles = tk.Frame(right_top_tabs)
right_top_tabs.add(tab_vehicles, text="Vehicles (Search & Manage)")
for r in range(4):
    tab_vehicles.rowconfigure(r, weight=0)
tab_vehicles.rowconfigure(3, weight=1)
for c in range(4):
    tab_vehicles.columnconfigure(c, weight=1)

tk.Label(tab_vehicles, text="Color contains").grid(row=0, column=0, sticky="w", padx=4, pady=2)
tk.Label(tab_vehicles, text="Plate contains").grid(row=0, column=1, sticky="w", padx=4, pady=2)
tk.Label(tab_vehicles, text="Nickname contains").grid(row=0, column=2, sticky="w", padx=4, pady=2)

veh_search_color_var = StringVar()
veh_search_plate_var = StringVar()
veh_search_nick_var = StringVar()

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
    vehicle_results_list.delete(0, tk.END)
    vehicle_search_cache.clear()
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
        messagebox.showinfo("No selection", "Select a vehicle in the list first.")
        return
    entry = vehicle_search_cache[sel[0]]
    snaps = entry.get("snapshots", [])
    if not snaps:
        messagebox.showinfo("No snapshots", "This vehicle has no snapshots saved.")
        return
    last_path = snaps[-1]
    if not os.path.exists(last_path):
        messagebox.showwarning("Missing file", f"Snapshot not found:\n{last_path}")
        return

    img_bgr = cv2.imread(last_path)
    if img_bgr is None or img_bgr.size == 0:
        messagebox.showwarning("Load error", "Could not load snapshot image.")
        return

    win = tk.Toplevel(root)
    win.title(f"Vehicle {entry['id'][:8]}… | Last Snapshot")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = int(sw*0.7), int(sh*0.7)
        x = (sw - ww)//2
        y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1200x800")

    canvas = tk.Canvas(win, background="black")
    canvas.pack(fill=tk.BOTH, expand=True)

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    imgtk = ImageTk.PhotoImage(pil)
    canvas.create_image(0, 0, anchor="nw", image=imgtk)
    canvas.image = imgtk
    canvas.config(scrollregion=(0, 0, pil.width, pil.height))
    win.bind("<Escape>", lambda e: win.destroy())
    apply_branding(win)
    apply_branding(win)

def show_vehicle_details():
    sel = vehicle_results_list.curselection()
    if not sel:
        messagebox.showinfo("No selection", "Select a vehicle in the list first.")
        return
    entry = vehicle_search_cache[sel[0]]
    msg = json.dumps(entry, indent=2)
    messagebox.showinfo("Vehicle details", msg)

btn_row_vehicle = tk.Frame(tab_vehicles)
btn_row_vehicle.grid(row=2, column=0, columnspan=4, sticky="ew", padx=4, pady=2)
tk.Button(btn_row_vehicle, text="Search", command=search_vehicles).pack(side=tk.LEFT, padx=3)
tk.Button(btn_row_vehicle, text="Open Last Snap", command=open_vehicle_last_snap).pack(side=tk.LEFT, padx=3)
tk.Button(btn_row_vehicle, text="Details", command=show_vehicle_details).pack(side=tk.LEFT, padx=3)

############################
# Row 3 Column 2: OBJECT RECALL & HISTORY
############################
object_history_frame = tk.LabelFrame(root, text="Object Recall & History")
object_history_frame.grid(row=3, column=2, padx=12, pady=(0, 12), sticky="nsew")
object_history_frame.rowconfigure(4, weight=1)
object_history_frame.columnconfigure(0, weight=1)

tk.Label(object_history_frame, text="Select object:").grid(row=0, column=0, sticky="w", padx=4, pady=2)

object_dropdowns = []
object_var = StringVar(root)
object_var.set("No objects logged")
object_dropdown = OptionMenu(object_history_frame, object_var, "No objects logged")
object_dropdown.grid(row=1, column=0, sticky="ew", padx=4, pady=2)
object_dropdowns.append(object_dropdown)

btn_row = tk.Frame(object_history_frame)
btn_row.grid(row=2, column=0, sticky="ew", padx=4, pady=2)
tk.Button(btn_row, text="Recall (Window)", command=lambda: open_object_recall_window(object_var.get())).pack(side=tk.LEFT, padx=3)
tk.Button(btn_row, text="Show History (Window)", command=lambda: open_object_history_window(object_var.get())).pack(side=tk.LEFT, padx=3)

recall_label = tk.Label(object_history_frame, text="", fg="blue")
recall_label.grid(row=3, column=0, sticky="w", padx=4, pady=2)

history_listbox = tk.Listbox(object_history_frame)
history_listbox.grid(row=4, column=0, sticky="nsew", padx=4, pady=(2,4))
history_scrollbar = tk.Scrollbar(object_history_frame, orient=tk.VERTICAL, command=history_listbox.yview)
history_scrollbar.grid(row=4, column=1, sticky="ns")
history_listbox.config(yscrollcommand=history_scrollbar.set)

def open_object_history_window(obj_label=None):
    obj_label = obj_label or object_var.get()
    if not obj_label or obj_label == "No objects logged" or obj_label not in object_memory or not object_memory[obj_label]:
        messagebox.showinfo("No history", f"No history for {obj_label or 'object'}.")
        return
    events = object_memory[obj_label]
    last_event = events[-1]
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_event["time"]))
    x, y, w, h = last_event["box"]
    status = last_event["status"]
    person = last_event["person"] if last_event["person"] else "No one"
    cam = last_event.get("camera", "Unknown")
    held_str = f" | Held {last_event['held_duration']:.2f}s" if last_event["held_duration"] is not None else ""
    color_part = ""
    if last_event.get("color_hex"):
        color_part = f" | Color {last_event.get('color_name','')} {last_event.get('color_hex','')}"
    header_lines = [
        f"Object: {obj_label}",
        f"Last [{cam}] {t_str}: {status} by {person} (x={x}, y={y}, w={w}, h={h}){held_str}{color_part}"
    ]
    rows = []
    for evt in events:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(evt["time"]))
        x, y, w, h = evt["box"]
        status = evt["status"]
        person = evt["person"] if evt["person"] else "No one"
        cam = evt.get("camera", "Unknown")
        held = f" | Held {evt['held_duration']:.2f}s" if evt["held_duration"] is not None else ""
        color_part = ""
        if evt.get("color_hex"):
            color_part = f" | Color {evt.get('color_name','')} {evt.get('color_hex','')}"
        rows.append(f"[{cam}] {t}: {obj_label} {status} by {person} at (x={x}, y={y}, w={w}, h={h}){held}{color_part}")
    _open_scrolling_window(f"History — {obj_label}", header_lines, rows)

try:
    recall_label.grid_remove()
    history_listbox.grid_remove()
    history_scrollbar.grid_remove()
except Exception:
    pass

############################
# Row 4 Column 2: PERSON RECALL & HISTORY
############################
person_history_frame = tk.LabelFrame(root, text="Person Recall & History")
person_history_frame.grid(row=4, column=2, padx=12, pady=(0, 12), sticky="nsew")
person_history_frame.rowconfigure(4, weight=1)
person_history_frame.columnconfigure(0, weight=1)

tk.Label(person_history_frame, text="Select person:").grid(row=0, column=0, sticky="w", padx=4, pady=2)

person_dropdowns = []
person_var = StringVar(root)
person_var.set("No persons logged")
person_dropdown = OptionMenu(person_history_frame, person_var, "No persons logged")
person_dropdown.grid(row=1, column=0, sticky="ew", padx=4, pady=2)
person_dropdowns.append(person_dropdown)

pbtn_row = tk.Frame(person_history_frame)
pbtn_row.grid(row=2, column=0, sticky="ew", padx=4, pady=2)
tk.Button(pbtn_row, text="Recall Person (Window)", command=lambda: open_person_recall_window(person_var.get())).pack(side=tk.LEFT, padx=3)
tk.Button(pbtn_row, text="Show History (Window)", command=lambda: open_person_history_window(person_var.get())).pack(side=tk.LEFT, padx=3)

person_recall_label = tk.Label(person_history_frame, text="", fg="green")
person_recall_label.grid(row=3, column=0, sticky="w", padx=4, pady=2)

person_history_listbox = tk.Listbox(person_history_frame)
person_history_listbox.grid(row=4, column=0, sticky="nsew", padx=4, pady=(2,4))
person_history_scrollbar = tk.Scrollbar(person_history_frame, orient=tk.VERTICAL, command=person_history_listbox.yview)
person_history_scrollbar.grid(row=4, column=1, sticky="ns")
person_history_listbox.config(yscrollcommand=person_history_scrollbar.set)

def open_person_history_window(name=None):
    name = name or person_var.get()
    if not name or name == "No persons logged" or name not in person_memory or not person_memory[name]:
        messagebox.showinfo("No history", f"No history for {name or 'person'}.")
        return

    events = person_memory[name]
    last_event = events[-1]
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_event["time"]))
    b = last_event["box"]
    x, y, w, h = b["left"], b["top"], b["right"] - b["left"], b["bottom"] - b["top"]
    cam = last_event.get("camera", "Unknown")
    shirt = ""
    if last_event.get("shirt_color_hex"):
        shirt = f" | Shirt {last_event.get('shirt_color_name','')} {last_event.get('shirt_color_hex','')}"

    header_lines = [
        f"Person: {name}",
        f"Last seen [{cam}] {t_str} at (x={x}, y={y}, w={w}, h={h}){shirt}"
    ]

    rows = []
    for evt in events:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(evt["time"]))
        bb = evt["box"]
        xx, yy = bb["left"], bb["top"]
        ww, hh = bb["right"] - bb["left"], bb["bottom"] - bb["top"]
        cam = evt.get("camera", "Unknown")
        s = ""
        if evt.get("shirt_color_hex"):
            s = f" | Shirt {evt.get('shirt_color_name','')} {evt.get('shirt_color_hex','')}"
        rows.append(f"[{cam}] {t}: (x={xx}, y={yy}, w={ww}, h={hh}){s}")

    _open_scrolling_window(f"History — {name}", header_lines, rows)

try:
    person_recall_label.grid_remove()
    person_history_listbox.grid_remove()
    person_history_scrollbar.grid_remove()
except Exception:
    pass

############################
# Recall popups with snapshots
############################
def _display_bgr_in_canvas(win_title: str, img_bgr):
    """Generic full-size viewer for a BGR image."""
    if img_bgr is None or getattr(img_bgr, "size", 0) == 0:
        messagebox.showinfo("No image", "No snapshot available to display.")
        return
    win = tk.Toplevel(root)
    win.title(win_title)
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = int(sw*0.7), int(sh*0.7)
        x = (sw - ww)//2; y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1200x800")
    canvas = tk.Canvas(win, background="black")
    canvas.pack(fill=tk.BOTH, expand=True)
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    imgtk = ImageTk.PhotoImage(pil)
    canvas.create_image(0, 0, anchor="nw", image=imgtk)
    canvas.image = imgtk
    canvas.config(scrollregion=(0, 0, pil.width, pil.height))
    win.bind("<Escape>", lambda e: win.destroy())

def open_object_recall_window(obj_label=None):
    obj_label = obj_label or object_var.get()
    if not obj_label or obj_label == "No objects logged" or obj_label not in object_memory or not object_memory[obj_label]:
        messagebox.showinfo("No history", f"No history for {obj_label or 'object'}.")
        return
    last_evt = object_memory[obj_label][-1]
    cam = last_evt.get("camera", "Unknown")
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_evt["time"]))
    status = last_evt.get("status","?")
    person = last_evt.get("person") or "No one"
    color = ""
    if last_evt.get("color_hex"):
        color = f" | Color {last_evt.get('color_name','')} {last_evt.get('color_hex','')}"
    snap_path = last_evt.get("snapshot")

    # Try best-effort preview:
    preview = None
    if snap_path and os.path.exists(snap_path):
        img = cv2.imread(snap_path)
        if img is not None and img.size > 0:
            preview = img
    if preview is None:
        # Cropping the current frame (may be stale)
        try:
            box = last_evt["box"]
            x, y, w, h = [int(v) for v in box]
            for _, (worker, cam_name, _) in camera_windows.items():
                if cam_name == cam:
                    fr = worker.get_frame()
                    if fr is not None and fr.size > 0 and w>0 and h>0:
                        preview = fr[max(0,y):max(0,y+h), max(0,x):max(0,x+w)].copy()
                    break
        except Exception:
            preview = None

    # Window
    win = tk.Toplevel(root)
    win.title(f"Recall — {obj_label}")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = 900, 640
        x = (sw - ww)//2; y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("900x640")

    top = tk.Frame(win); top.pack(side=tk.TOP, fill="x")
    tk.Label(top, text=f"Object: {obj_label}").pack(side=tk.LEFT, padx=8, pady=6)
    tk.Label(top, text=f"[{cam}] {t_str} — {status} by {person}{color}").pack(side=tk.LEFT, padx=12)

    btns = tk.Frame(win); btns.pack(side=tk.TOP, fill="x")
    tk.Button(btns, text="Open Full History", command=lambda: open_object_history_window(obj_label)).pack(side=tk.LEFT, padx=4, pady=4)

    def _save_as():
        if preview is None:
            messagebox.showinfo("No image", "No snapshot available to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".jpg",
                                            filetypes=[("JPEG", "*.jpg"), ("PNG","*.png")],
                                            initialfile=f"{obj_label.replace(' ','_')}_{int(time.time())}.jpg")
        if not path:
            return
        ok = cv2.imwrite(path, preview)
        if ok:
            messagebox.showinfo("Saved", f"Saved to:\n{path}")

    def _open_folder():
        if not snap_path or not os.path.exists(snap_path):
            messagebox.showinfo("Not found", "No saved snapshot file on disk for this object.")
            return
        try:
            folder = os.path.dirname(snap_path)
            os.startfile(folder)  # Windows
        except Exception:
            pass

    tk.Button(btns, text="Save Snapshot As…", command=_save_as).pack(side=tk.LEFT, padx=4)
    tk.Button(btns, text="Open Containing Folder", command=_open_folder).pack(side=tk.LEFT, padx=4)

    # Preview
    panel = tk.Frame(win); panel.pack(fill=tk.BOTH, expand=True)
    if preview is not None:
        rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(pil)
        lbl = tk.Label(panel, image=imgtk, bg="black"); lbl.pack(fill=tk.BOTH, expand=True)
        lbl.image = imgtk
        lbl.bind('<Double-1>', lambda e: _display_bgr_in_canvas(f"{obj_label} — Full", preview))
    else:
        tk.Label(panel, text="(No snapshot available)").pack(pady=20)
    apply_branding(win)

def open_person_recall_window(name=None):
    name = name or person_var.get()
    if not name or name == "No persons logged" or name not in person_memory or not person_memory[name]:
        messagebox.showinfo("No history", f"No history for {name or 'person'}.")
        return
    last_evt = person_memory[name][-1]
    cam = last_evt.get("camera", "Unknown")
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_evt["time"]))
    shirt = ""
    if last_evt.get("shirt_color_hex"):
        shirt = f" | Shirt {last_evt.get('shirt_color_name','')} {last_evt.get('shirt_color_hex','')}"
    snap_path = last_evt.get("snapshot")

    preview = None
    if snap_path and os.path.exists(snap_path):
        img = cv2.imread(snap_path)
        if img is not None and img.size > 0:
            preview = img
    if preview is None:
        try:
            bb = last_evt["box"]
            x, y, w, h = int(bb["left"]), int(bb["top"]), int(bb["right"] - bb["left"]), int(bb["bottom"] - bb["top"])
            for _, (worker, cam_name, _) in camera_windows.items():
                if cam_name == cam:
                    fr = worker.get_frame()
                    if fr is not None and fr.size > 0 and w>0 and h>0:
                        preview = fr[max(0,y):max(0,y+h), max(0,x):max(0,x+w)].copy()
                    break
        except Exception:
            preview = None

    win = tk.Toplevel(root)
    win.title(f"Recall — {name}")
    try:
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = 900, 640
        x = (sw - ww)//2; y = (sh - wh)//2
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("900x640")

    top = tk.Frame(win); top.pack(side=tk.TOP, fill="x")
    tk.Label(top, text=f"Person: {name}").pack(side=tk.LEFT, padx=8, pady=6)
    tk.Label(top, text=f"[{cam}] {t_str}{shirt}").pack(side=tk.LEFT, padx=12)

    btns = tk.Frame(win); btns.pack(side=tk.TOP, fill="x")
    tk.Button(btns, text="Open Full History", command=lambda: open_person_history_window(name)).pack(side=tk.LEFT, padx=4, pady=4)

    def _save_as():
        if preview is None:
            messagebox.showinfo("No image", "No snapshot available to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".jpg",
                                            filetypes=[("JPEG", "*.jpg"), ("PNG","*.png")],
                                            initialfile=f"{name.replace(' ','_')}_{int(time.time())}.jpg")
        if not path:
            return
        ok = cv2.imwrite(path, preview)
        if ok:
            messagebox.showinfo("Saved", f"Saved to:\n{path}")

    def _open_folder():
        if not snap_path or not os.path.exists(snap_path):
            messagebox.showinfo("Not found", "No saved snapshot file on disk for this person.")
            return
        try:
            folder = os.path.dirname(snap_path)
            os.startfile(folder)  # Windows
        except Exception:
            pass

    tk.Button(btns, text="Save Snapshot As…", command=_save_as).pack(side=tk.LEFT, padx=4)
    tk.Button(btns, text="Open Containing Folder", command=_open_folder).pack(side=tk.LEFT, padx=4)

    panel = tk.Frame(win); panel.pack(fill=tk.BOTH, expand=True)
    if preview is not None:
        rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(pil)
        lbl = tk.Label(panel, image=imgtk, bg="black"); lbl.pack(fill=tk.BOTH, expand=True)
        lbl.image = imgtk
        lbl.bind('<Double-1>', lambda e: _display_bgr_in_canvas(f"{name} — Full", preview))
    else:
        tk.Label(panel, text="(No snapshot available)").pack(pady=20)
    apply_branding(win)

############################
# Row 3 Column 1: LIVE LOGS (moved under captured image; snug)
############################
live_logs_frame = tk.LabelFrame(root, text="Per-Camera Live Logs")
live_logs_frame.grid(row=3, column=1, padx=12, pady=(0, 12), sticky="nsew")  # snug to box above
live_logs_frame.rowconfigure(1, weight=1)
live_logs_frame.columnconfigure(0, weight=1)

live_log_cam_var = StringVar(root)
live_log_cam_var.set("All")

top_logs = tk.Frame(live_logs_frame)
top_logs.grid(row=0, column=0, sticky="ew")
tk.Label(top_logs, text="Camera:").pack(side=tk.LEFT, padx=4)
live_log_dropdown = tk.OptionMenu(top_logs, live_log_cam_var, "All")
live_log_dropdown.pack(side=tk.LEFT)
tk.Button(top_logs, text="Refresh", command=lambda: refresh_live_logs_ui()).pack(side=tk.LEFT, padx=6)
tk.Button(top_logs, text="Clear", command=lambda: clear_live_logs()).pack(side=tk.LEFT, padx=6)

log_area = tk.Frame(live_logs_frame)
log_area.grid(row=1, column=0, sticky="nsew")

live_log_listbox = tk.Listbox(log_area)
live_log_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
live_log_scrollbar = tk.Scrollbar(log_area, orient=tk.VERTICAL, command=live_log_listbox.yview)
live_log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
live_log_listbox.config(yscrollcommand=live_log_scrollbar.set)

def _refresh_live_log_dropdown():
    names = sorted([tpl[1] for tpl in camera_windows.values()])
    menu = live_log_dropdown["menu"]
    menu.delete(0, "end")
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
# Bottom toolbar (Refined; Recall wired to new popups)
############################
bottom_bar = tk.Frame(
    root,
    bd=0,
    bg=BRAND_SURFACE,
    highlightbackground=BRAND_BORDER,
    highlightcolor=BRAND_BORDER,
    highlightthickness=1,
)
bottom_bar.grid(row=5, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 16))
for c in range(12):
    bottom_bar.columnconfigure(c, weight=0)

tk.Label(bottom_bar, text="Object:").grid(row=0, column=0, sticky="w", padx=(8,4), pady=6)
bottom_obj_dropdown = OptionMenu(bottom_bar, object_var, "No objects logged")
bottom_obj_dropdown.grid(row=0, column=1, sticky="ew", padx=4, pady=6)
object_dropdowns.append(bottom_obj_dropdown)
tk.Button(bottom_bar, text="Recall", command=lambda: open_object_recall_window(object_var.get())).grid(row=0, column=2, padx=4, pady=6, sticky="ew")
tk.Button(bottom_bar, text="History", command=lambda: open_object_history_window(object_var.get())).grid(row=0, column=3, padx=4, pady=6, sticky="ew")

tk.Label(bottom_bar, text="Person:").grid(row=0, column=4, sticky="w", padx=(24,4), pady=6)
bottom_person_dropdown = OptionMenu(bottom_bar, person_var, "No persons logged")
bottom_person_dropdown.grid(row=0, column=5, sticky="ew", padx=4, pady=6)
person_dropdowns.append(bottom_person_dropdown)
tk.Button(bottom_bar, text="Recall", command=lambda: open_person_recall_window(person_var.get())).grid(row=0, column=6, padx=4, pady=6, sticky="ew")
tk.Button(bottom_bar, text="History", command=lambda: open_person_history_window(person_var.get())).grid(row=0, column=7, padx=4, pady=6, sticky="ew")

############################
# Top-right overlay Controls (hidden by default to avoid overlap)
############################
def create_top_right_controls():
    def show_overlay():
        overlay.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)
        overlay.lift(); overlay.tkraise()
        handle.place_forget()

    def hide_overlay():
        overlay.place_forget()
        handle.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

    overlay = tk.LabelFrame(video_feed_frame, text="Settings")
    # Not placed initially (prevents overlap); user opens via handle

    hdr = tk.Frame(overlay); hdr.pack(fill="x", padx=6, pady=(6,2))
    tk.Label(hdr, text="Quick Settings").pack(side=tk.LEFT)
    tk.Button(hdr, text="Close", command=hide_overlay).pack(side=tk.RIGHT)

    toggles = tk.Frame(overlay); toggles.pack(fill="x", padx=6, pady=2)
    tk.Checkbutton(toggles, textvariable=display_feeds_text, variable=DISPLAY_FEEDS_VAR,
                   indicatoron=False, command=lambda: (on_display_feeds_toggle(), _update_display_text())
                   ).pack(side=tk.LEFT, padx=2)
    tk.Checkbutton(toggles, textvariable=veh_snap_text, variable=ENABLE_VEHICLE_SNAPSHOTS_VAR,
                   indicatoron=False, command=_update_snap_text).pack(side=tk.LEFT, padx=6)
    tk.Checkbutton(toggles, textvariable=unk_snap_text, variable=ENABLE_UNKNOWN_PERSON_SNAPSHOTS_VAR,
                   indicatoron=False, command=_update_snap_text).pack(side=tk.LEFT, padx=6)

    cams = tk.LabelFrame(overlay, text="Cameras"); cams.pack(fill="x", padx=6, pady=6)
    row1 = tk.Frame(cams); row1.pack(fill="x")
    row2 = tk.Frame(cams); row2.pack(fill="x")
    for i in range(MAX_CAMERAS):
        parent = row1 if i < (MAX_CAMERAS//2 + MAX_CAMERAS%2) else row2
        tk.Checkbutton(parent, textvariable=cam_toggle_text[i], variable=camera_vars[i],
                       indicatoron=False, command=lambda ii=i: on_toggle(ii)
                       ).pack(side=tk.LEFT, padx=2)

    obj_blk = tk.LabelFrame(overlay, text="Object"); obj_blk.pack(fill="x", padx=6, pady=4)
    obj_row = tk.Frame(obj_blk); obj_row.pack(fill="x", padx=4, pady=2)
    dd_obj = OptionMenu(obj_row, object_var, object_var.get())
    dd_obj.pack(side=tk.LEFT, fill="x", expand=True)
    object_dropdowns.append(dd_obj)
    tk.Button(obj_row, text="Recall", command=lambda: open_object_recall_window(object_var.get())).pack(side=tk.LEFT, padx=3)
    tk.Button(obj_row, text="History", command=lambda: open_object_history_window(object_var.get())).pack(side=tk.LEFT, padx=3)

    per_blk = tk.LabelFrame(overlay, text="Person"); per_blk.pack(fill="x", padx=6, pady=4)
    per_row = tk.Frame(per_blk); per_row.pack(fill="x", padx=4, pady=2)
    dd_per = OptionMenu(per_row, person_var, person_var.get())
    dd_per.pack(side=tk.LEFT, fill="x", expand=True)
    person_dropdowns.append(dd_per)
    tk.Button(per_row, text="Recall", command=lambda: open_person_recall_window(person_var.get())).pack(side=tk.LEFT, padx=3)
    tk.Button(per_row, text="History", command=lambda: open_person_history_window(person_var.get())).pack(side=tk.LEFT, padx=3)

    misc = tk.Frame(overlay); misc.pack(fill="x", padx=6, pady=6)
    tk.Button(misc, text="Tuning Popup…", command=open_tuning_popup).pack(side=tk.LEFT, padx=3)
    tk.Button(misc, text="Refresh Logs", command=refresh_live_logs_ui).pack(side=tk.LEFT, padx=12)
    tk.Button(misc, text="Clear Logs", command=clear_live_logs).pack(side=tk.LEFT, padx=3)

    # Compact handle (always visible; does not cover icons/feeds)
    handle = tk.Button(video_feed_frame, text="⚙ Settings", command=show_overlay)
    handle.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

create_top_right_controls()

############################
# Dropdown updaters
############################
def update_object_dropdown():
    keys = sorted(object_memory.keys())
    for dd in object_dropdowns:
        menu = dd["menu"]
        menu.delete(0, "end")
        if keys:
            for obj in keys:
                menu.add_command(label=obj, command=lambda value=obj: object_var.set(value))
        else:
            menu.add_command(label="No objects logged", command=lambda: None)
    if keys and object_var.get() not in object_memory:
        object_var.set(keys[0])
    _refresh_sub_lists()

def update_person_dropdown():
    keys = sorted(person_memory.keys())
    for dd in person_dropdowns:
        menu = dd["menu"]
        menu.delete(0, "end")
        if keys:
            for person in keys:
                menu.add_command(label=person, command=lambda value=person: person_var.set(value))
        else:
            menu.add_command(label="No persons logged", command=lambda: None)
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

    logger.info(f"Enabled {camera_name(idx)}.")
    _update_video_strip_scrollregion()
    _refresh_live_log_dropdown()

def disable_camera(idx):
    worker = camera_workers.get(idx)
    if worker:
        try:
            worker.stop()
        except Exception:
            pass
    camera_workers[idx] = None

    if idx in camera_cells:
        cell, lbl = camera_cells[idx]
        try:
            lbl.config(image='', text='')
            cell.pack_forget()
        except Exception:
            pass

    if idx in camera_windows:
        try:
            del camera_windows[idx]
        except Exception:
            pass

    logger.info(f"Disabled {camera_name(idx)}.")
    _update_video_strip_scrollregion()
    _refresh_live_log_dropdown()

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
    current_detections.clear()
    _loop_counter += 1

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
                disp = cv2.resize(processed, (FEED_W, FEED_H), interpolation=cv2.INTER_AREA)
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

    root.after(max(1, int(FPS_CAP)), update_cameras)

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

############################
# Cleanup
############################
def on_closing():
    for idx, worker in list(camera_workers.items()):
        if worker:
            try:
                worker.stop()
            except Exception:
                pass
    time.sleep(0.2)
    cv2.destroyAllWindows()
    save_person_memory()
    save_notify_settings()
    save_vehicle_db()
    logger.info("Clean exit.")
    try:
        root.destroy()
    except Exception:
        pass

# Start the app
def _start_app():
    update_cameras()
    root.after(200, _push_once)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    apply_branding(root)
    root.mainloop()

if __name__ == "__main__":
    _start_app()
