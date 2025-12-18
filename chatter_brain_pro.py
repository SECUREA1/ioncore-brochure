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
        "core.object_tagged": [
            "{tag} [{camera}{choose:| · conf {conf}| · seen {count}x}]",
            "{choose:And then|Suddenly|Popping in}: {tag} (camera {camera}).",
        ],
        "core.person_seen": [
            "{choose:Noted|Logging|Tagging}: {person} on {camera}.",
            "Eyes on {person} at {camera}.",
        ],
        "core.person_recall": [
            "Last time was {ago} on {camera_last}.",
            "Previously spotted {ago} via {camera_last}.",
        ],
        "core.vehicle_seen": [
            "Vehicle {vehicle} rolling by {camera}.",
            "{choose:Visual|Telemetry} shows {vehicle} on {camera}.",
        ],
        "core.chat.reply": [
            "{choose:Sure|Alright|Got it}. {clip:user,140}",
            "Processing. {choose:Working on it|Here's what I have}: {clip:answer,200}",
        ],
        "core.chat.casual": [
            "{choose:By the way|On the side}, I remember {memory_hint}.",
            "{choose:Fun fact|Quick recall}: {memory_hint} (keywords: {keywords}).",
            "You mentioned {clip:user,120}; pairing that with {memory_hint} if it helps.",
        ],
        "core.chat.fallback": [
            "I'm here and listening. Can you rephrase?",
            "I didn't catch a target in that request, but I'm ready to help.",
        ],
        "core.memory.recall": [
            "{choose:Last sighting|Recent memory}: {memory_hint}.",
            "Memory ping → {memory_hint}.",
            "Pulled from recall: {memory_hint}.",
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

        self.object_tags = {
            "bottle": ["Bottle spotted—hydration checkpoint!", "A bottle pops up—potion or seltzer?"],
            "remote": ["Remote in sight—ready to switch universes?", "Remote detected—want me to track where it gets left?"],
            "cellphone": ["Phone in frame—ping me if it moves?", "Cell phone sighted—log a quick note?"],
            "cell phone": ["Phone in frame—ping me if it moves?", "Cell phone sighted—log a quick note?"],
            "laptop": ["Laptop detected—should I keep an eye on it?", "Laptop’s up—project time?"],
            "tv": ["A TV appears—portal to drama unlocked.", "TV spotted—binge mode engaged?"],
            "chair": ["Chair ready—the throne of productivity awaits.", "Seat detected—permission to lounge?"],
            "cup": ["Cup spotted—brew checkpoint!", "Cup in frame—steeped in possibility."],
            "table": ["Table present—prime stage for plans.", "Table spotted—ready for sketches or snacks."],
            "couch": ["Couch check—perfect for a debrief.", "Couch in view—calling for a chill session."],
            "bed": ["Bed detected—nap ambitions rising.", "Bed in sight—dreams on standby."],
            "microwave": ["Microwave ready—reheating a plot twist?", "Microwave on deck—snack time soon."],
            "oven": ["Oven detected—preheating suspense.", "Oven in frame—recipes inbound."],
            "toaster": ["Toaster ready—popping up surprises.", "Toaster spotted—breakfast ally engaged."],
            "sink": ["Sink found—reset station online.", "Sink in view—rinse and reset?"],
            "refrigerator": ["Fridge keeps it cool—any midnight snacks to track?", "Refrigerator present—guardian of snacks."],
            "dog": ["Dog detected—tail-wagging happiness logged.", "Dog in sight—mood booster activated."],
            "cat": ["Cat spotted—plotting purrfectly.", "Cat in frame—stealth mode probable."],
            "car": ["Car in view—ready to roll?", "Car detected—should I log its plate?"],
        }

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

    def _format_ago(self, ts: float) -> str:
        delta = max(0, time.time() - ts)
        minutes = int(delta // 60)
        hours = int(minutes // 60)
        days = int(hours // 24)
        if delta < 60:
            return f"{int(delta)}s ago"
        if minutes < 60:
            return f"{minutes}m ago"
        if hours < 24:
            return f"{hours}h ago"
        return f"{days}d ago"

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

    def _tag_object(self, obj: str) -> str:
        bank = self.object_tags.get(obj.lower())
        if bank:
            return random.choice(bank)
        return f"{obj.capitalize()} in view—want me to note anything?"

    def _last_event(self, kind: str, field: str, value: str) -> Optional[Dict[str, Any]]:
        events = [e for e in reversed(self.memory.get("events", [])) if e.get("kind") == kind and e.get(field) == value]
        return events[0] if events else None

    def _count_events(self, kind: str, field: str, value: str) -> int:
        return sum(1 for e in self.memory.get("events", []) if e.get("kind") == kind and e.get(field) == value)

    def _build_memory_hint(self, topic: str) -> str:
        topic_l = topic.lower().strip()
        p = self._last_event("person", "person", topic)
        if p:
            return f"{topic} last seen {self._format_ago(p['time'])} on {p.get('camera','?')}"
        o = self._last_event("object", "obj", topic_l)
        if o:
            return f"{topic_l} last seen {self._format_ago(o['time'])} on {o.get('camera','?')}"
        return f"No recent memory for {topic}."

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
        self._remember_chat("user", user_text)
        self._persist_memory()
        dataset = dataset_answerer or self.dataset_answerer
        if dataset:
            ds = dataset(user_text)
            if ds:
                self._remember_chat("AI", ds)
                self._persist_memory()
                return ds

        ctx = {
            "user": user_text,
            "keywords": self._extract_keywords(user_text, 4),
            "answer": "",
            "memory_hint": self._build_memory_hint(user_text.split()[0]) if user_text.strip() else "",
        }
        response = self._render_from_key("core.chat.reply", ctx, "Okay.")
        # Blend in casual chit-chat that feels a bit more conversational (BERT-lite)
        if random.random() < max(0.1, float(self.tuner.get("humor", 0.15))):
            casual = self._render_from_key("core.chat.casual", ctx, "Keeping things noted.")
            response = f"{response} {casual}"
        self._remember_chat("AI", response)
        self._persist_memory()
        return response

    def on_object(self, obj: str, camera: str, confidence: Optional[float] = None, color: Optional[str] = None) -> str:
        ctx = {
            "obj": obj,
            "camera": camera,
            "conf": f"{confidence:.2f}" if confidence is not None else "",
            "color": color or "",
            "tag": self._tag_object(obj),
            "count": self._count_events("object", "obj", obj),
        }
        msg = self._render_from_key("core.object_tagged", ctx, f"{obj} on {camera}.")
        self.remember_event("object", ctx)
        return msg

    def on_person(self, name: str, camera: str) -> str:
        ctx = {"person": name, "camera": camera}
        last = self._last_event("person", "person", name)
        msg = self._render_from_key("core.person_seen", ctx, f"I see {name} on {camera}.")
        if last:
            ctx.update({
                "ago": self._format_ago(last["time"]),
                "camera_last": last.get("camera", ""),
            })
            recall = self._render_from_key("core.person_recall", ctx, "")
            if recall:
                msg = f"{msg} {recall}"
        self.remember_event("person", ctx)
        return msg

    def on_vehicle(self, label: str, camera: str) -> str:
        ctx = {"vehicle": label, "camera": camera}
        msg = self._render_from_key("core.vehicle_seen", ctx, f"Vehicle {label} on {camera}.")
        self.remember_event("vehicle", ctx)
        return msg

    def recall_topic(self, topic: str) -> str:
        hint = self._build_memory_hint(topic)
        ctx = {
            "memory_hint": hint,
            "keywords": ", ".join(self._extract_keywords(topic, 3)),
        }
        msg = self._render_from_key("core.memory.recall", ctx, hint)
        self._remember_chat("AI", msg)
        self._persist_memory()
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
