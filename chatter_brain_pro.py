from __future__ import annotations
import json
import os
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional

DATA_DIR = os.environ.get("CHATTER_BRAIN_DATA", ".")
TEMPLATES_FILE = os.path.join(DATA_DIR, "brain_templates.json")
TUNER_FILE = os.path.join(DATA_DIR, "brain_tuner.json")
MEMORY_FILE = os.path.join(DATA_DIR, "brain_memory.json")


def _load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _save_json(path: str, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


_STOP = set(
    """
    a an and the is it this that those these to for with on in of as by from at into over under up down out be been are was were am
    will would can could should might maybe very really just your our their his her its not don't can't won't isn't wasn't weren't
    couldn't shouldn't they've we're i'm you're i've it'll we'll you'll
    """.split()
)


_MACRO = re.compile(r"\{([^{}]+)\}")


_DEFAULT_TEMPLATES = {
    "version": 1,
    "comment": "Editable chatter packs. The UI can safely overwrite these files.",
    "templates": {
        "core.object_seen": [
            "{choose:Heads up|FYI|Logged}: spotted {obj} on {camera}.",
            "Tracking {obj} via {camera}.",
        ],
        "core.person_seen": [
            "{choose:Noted|Logging|Tagging}: {person} on {camera}.",
            "Eyes on {person} at {camera}.",
        ],
        "core.vehicle_seen": [
            "Vehicle {vehicle} rolling by {camera}.",
            "{choose:Visual|Telemetry} shows {vehicle} on {camera}.",
        ],
        "core.chat.reply": [
            "{choose:Sure|Alright|Got it}. {clip:user,140}",
            "{choose:Keeping us on track|Recapping what matters}: {clip:context,200}",
            "{choose:I'm on it|Logging this|Got context}. {clip:user,120} {memory_hint}",
            "{choose:Noted|Understood|Captured}. Mood feels {mood}. {memory_hint}",
        ],
        "core.chat.fallback": [
            "I'm here and listening. Can you rephrase?",
            "I didn't catch a target in that request, but I'm ready to help.",
        ],
    },
}

_DEFAULT_TUNER = {
    "verbosity": 1.0,
    "humor": 0.15,
    "followup_rate": 0.35,
    "memory_recall_weight": 0.55,
}


class BrainPro:
    def __init__(
        self,
        display_fn: Optional[Callable[[str], None]] = None,
        speak_fn: Optional[Callable[[str], None]] = None,
        listen_fn: Optional[Callable[[Optional[int]], str]] = None,
        history_ref: Optional[List[Dict[str, Any]]] = None,
    ):
        self.display_fn = display_fn or (lambda text: None)
        self.speak_fn = speak_fn or (lambda text: None)
        self.listen_fn = listen_fn or (lambda *_: "")
        self.templates = _load_json(TEMPLATES_FILE, _DEFAULT_TEMPLATES)
        self.tuner = _load_json(TUNER_FILE, _DEFAULT_TUNER)
        self.memory = _load_json(MEMORY_FILE, {"events": [], "chat": []})
        self.dataset_answerer: Optional[Callable[[str], Optional[str]]] = None
        if history_ref:
            self.bootstrap_chat_history(history_ref)

    # ------------------------------------------------------------------
    # Public configuration helpers
    # ------------------------------------------------------------------
    def set_dataset_answerer(self, fn: Callable[[str], Optional[str]]):
        self.dataset_answerer = fn

    def update_tuner(self, **kwargs):
        self.tuner.update({k: v for k, v in kwargs.items() if k in _DEFAULT_TUNER})
        _save_json(TUNER_FILE, self.tuner)

    def bootstrap_chat_history(self, history: List[Dict[str, Any]], limit: int = 400):
        for entry in history[-limit:]:
            self._remember_chat(entry.get("sender", ""), entry.get("text", ""))
        self._persist_memory()

    # ------------------------------------------------------------------
    # Core rendering
    # ------------------------------------------------------------------
    def _tokens(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9']+", (text or "").lower())

    def _extract_keywords(self, text: str, k: int = 6) -> List[str]:
        toks = self._tokens(text)
        scored: Dict[str, float] = {}
        for i, w in enumerate(toks):
            if w in _STOP or len(w) < 3:
                continue
            scored[w] = scored.get(w, 0.0) + 1.0 + (2.0 / (1.0 + i))
        return [w for w, _ in sorted(scored.items(), key=lambda x: -x[1])[:k]]

    def _macro_clip(self, val: str, n: str) -> str:
        try:
            nn = int(n)
        except Exception:
            nn = 120
        s = str(val or "")
        return s[:nn]

    def _macro_choose(self, arg: str) -> str:
        parts = [p.strip() for p in arg.split("|") if p.strip()]
        return random.choice(parts) if parts else ""

    def _context_window(self, limit: int = 6) -> str:
        """Return a short recap of recent chat to improve flow."""
        recent = self.memory.get("chat", [])[-limit:]
        rows = []
        for item in recent:
            sender = item.get("sender", "")[:10]
            text = item.get("text", "")
            rows.append(f"{sender}: {self._macro_clip(text, 120)}")
        return " | ".join(rows)

    def _memory_hint(self, keywords: List[str], limit: int = 2) -> str:
        """Surface related memories (events or chat) that match keywords."""
        hints: List[str] = []

        def match_words(blob: str) -> bool:
            blob_l = blob.lower()
            return any(k.lower() in blob_l for k in keywords if k)

        for entry in reversed(self.memory.get("chat", [])):
            if match_words(entry.get("text", "")):
                hints.append(self._macro_clip(entry.get("text", ""), 80))
            if len(hints) >= limit:
                break

        if len(hints) < limit:
            for evt in reversed(self.memory.get("events", [])):
                blob = " ".join(str(v) for v in evt.values())
                if match_words(blob):
                    hints.append(self._macro_clip(blob, 80))
                if len(hints) >= limit:
                    break

        if not hints:
            return ""
        return "Related: " + " | ".join(hints)

    def _sentiment(self, text: str) -> str:
        good = {"great", "love", "nice", "cool", "amazing", "awesome", "thanks"}
        bad = {"bad", "hate", "annoy", "angry", "upset", "broken"}
        toks = set(self._tokens(text))
        if toks & good:
            return "positive"
        if toks & bad:
            return "concerned"
        return "neutral"

    def render_template(self, text: str, ctx: Dict[str, Any]) -> str:
        def repl(m):
            expr = m.group(1).strip()
            if expr.startswith("choose:"):
                return self._macro_choose(expr.split("choose:", 1)[1])
            if expr.startswith("clip:"):
                arg = expr.split("clip:", 1)[1]
                if "," in arg:
                    k, n = [x.strip() for x in arg.split(",", 1)]
                    return self._macro_clip(str(ctx.get(k, "")), n)
                return str(ctx.get(arg.strip(), ""))
            if expr.startswith("upper:"):
                key = expr.split("upper:", 1)[1].strip()
                return str(ctx.get(key, "")).upper()
            if expr.startswith("lower:"):
                key = expr.split("lower:", 1)[1].strip()
                return str(ctx.get(key, "")).lower()
            if expr.startswith("title:"):
                key = expr.split("title:", 1)[1].strip()
                return str(ctx.get(key, "")).title()
            if expr.startswith("randint:"):
                try:
                    a_s, b_s = [x.strip() for x in expr.split("randint:", 1)[1].split(",", 1)]
                    return str(random.randint(int(a_s), int(b_s)))
                except Exception:
                    return str(random.randint(0, 5))
            return str(ctx.get(expr, ""))

        out = _MACRO.sub(repl, text or "")
        out = re.sub(r"\s+", " ", out).strip()
        return out

    def _render_from_key(self, key: str, ctx: Dict[str, Any], fallback: str) -> str:
        tpl = self.templates.get("templates", {}).get(key) or []
        choice = random.choice(tpl) if tpl else fallback
        return self.render_template(choice, ctx)

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------
    def _persist_memory(self):
        _save_json(MEMORY_FILE, self.memory)

    def _remember_chat(self, sender: str, text: str):
        if not text:
            return
        entry = {"time": time.time(), "sender": sender, "text": text}
        self.memory.setdefault("chat", []).append(entry)
        self.memory["chat"] = self.memory["chat"][-600:]

    def remember_event(self, kind: str, payload: Dict[str, Any]):
        evt = {"time": time.time(), "kind": kind, **payload}
        self.memory.setdefault("events", []).append(evt)
        self.memory["events"] = self.memory["events"][-400:]
        self._persist_memory()

    # ------------------------------------------------------------------
    # Conversational interface
    # ------------------------------------------------------------------
    def reply(self, user_text: str, dataset_answerer: Optional[Callable[[str], Optional[str]]] = None) -> str:
        dataset = dataset_answerer or self.dataset_answerer
        self._remember_chat("User", user_text)
        if dataset:
            ds = dataset(user_text)
            if ds:
                self._remember_chat("AI", ds)
                self._persist_memory()
                return ds

        ctx = {
            "user": user_text,
            "keywords": self._extract_keywords(user_text, 4),
            "context": self._context_window(),
            "memory_hint": "",
            "answer": "",
            "mood": self._sentiment(user_text),
        }
        ctx["memory_hint"] = self._memory_hint(ctx["keywords"], limit=2)
        response = self._render_from_key(
            "core.chat.reply",
            ctx,
            "Okay. I have the thread in mind and will keep us moving.",
        )
        self._remember_chat("AI", response)
        self._persist_memory()
        return response

    def on_object(self, obj: str, camera: str, confidence: Optional[float] = None, color: Optional[str] = None) -> str:
        ctx = {
            "obj": obj,
            "camera": camera,
            "conf": f"{confidence:.2f}" if confidence is not None else "",
            "color": color or "",
        }
        msg = self._render_from_key("core.object_seen", ctx, f"{obj} on {camera}.")
        self.remember_event("object", ctx)
        return msg

    def on_person(self, name: str, camera: str) -> str:
        ctx = {"person": name, "camera": camera}
        msg = self._render_from_key("core.person_seen", ctx, f"I see {name} on {camera}.")
        self.remember_event("person", ctx)
        return msg

    def on_vehicle(self, label: str, camera: str) -> str:
        ctx = {"vehicle": label, "camera": camera}
        msg = self._render_from_key("core.vehicle_seen", ctx, f"Vehicle {label} on {camera}.")
        self.remember_event("vehicle", ctx)
        return msg

    def chat(self, prompt: str) -> str:
        reply = self.reply(prompt)
        if self.display_fn:
            try:
                self.display_fn(reply)
            except Exception:
                pass
        if self.speak_fn:
            try:
                self.speak_fn(reply)
            except Exception:
                pass
        return reply


__all__ = ["BrainPro"]
