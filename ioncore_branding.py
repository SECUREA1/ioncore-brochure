"""Ioncore visual branding helpers for Tkinter applications.

Branding sync: Ioncore brochure index.html & webpage.html (2024-06-05).
This module centralizes the brochure styling primitives so every
desktop Bluetooth utility mirrors the public Ioncore experience.
It focuses on lightweight Tk widgets and keeps optional Pillow usage
guarded so the tools remain portable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import tkinter as tk
from tkinter import font as tkfont
try:  # Optional dependency; guarded so CLI tools still launch.
    from PIL import Image, ImageDraw, ImageTk  # type: ignore
except Exception:  # pragma: no cover - Pillow is optional at runtime
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageTk = None  # type: ignore


BRANDING_STAMP = "Ioncore Index • webpage.html sync • 2024-06-05"


IONCORE_THEME_PALETTES: Dict[str, Dict[str, str]] = {
    "dark": {
        "bg": "#030712",
        "surface": "#0D182E",
        "surface_alt": "#11203D",
        "border": "#1C2A41",
        "border_soft": "#152033",
        "accent": "#6AFF3B",
        "accent_hover": "#53E02D",
        "accent_active": "#3CBF2A",
        "accent_alt": "#38F0D1",
        "accent_fg": "#02110B",
        "text": "#F5F8FF",
        "muted_text": "#B7C7E4",
        "muted": "#7F8BA4",
        "list_bg": "#09101D",
        "list_fg": "#F5F8FF",
        "list_select": "#6AFF3B",
        "list_select_fg": "#030712",
        "entry_bg": "#0B1424",
        "entry_fg": "#F5F8FF",
        "log_bg": "#0B1424",
        "log_fg": "#AEE8B4",
    },
    "light": {
        "bg": "#F5F8FF",
        "surface": "#FFFFFF",
        "surface_alt": "#EDF4FF",
        "border": "#CAD7EF",
        "border_soft": "#D9E4F8",
        "accent": "#4CD067",
        "accent_hover": "#3BBC58",
        "accent_active": "#2EA14A",
        "accent_alt": "#32B5F0",
        "accent_fg": "#082015",
        "text": "#13233C",
        "muted_text": "#506080",
        "muted": "#7786A0",
        "list_bg": "#FFFFFF",
        "list_fg": "#13233C",
        "list_select": "#4CD067",
        "list_select_fg": "#FFFFFF",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#13233C",
        "log_bg": "#FFFFFF",
        "log_fg": "#24502F",
    },
}

FONT_CANDIDATES = (
    "Montserrat",
    "Inter",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
    "Helvetica",
)


@dataclass
class BrandingContext:
    """Runtime description of the active Ioncore styling."""

    root: tk.Misc
    mode: str
    colors: Dict[str, str]
    fonts: Dict[str, tkfont.Font]
    logo: Optional["ImageTk.PhotoImage"] = None

    def protect(self, widget: tk.Misc) -> None:
        """Mark a widget so automatic styling skips it."""

        setattr(widget, "_ioncore_preserve_style", True)


def _detect_font_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for name in FONT_CANDIDATES:
        if name in available:
            return name
    return tkfont.nametofont("TkDefaultFont").actual().get("family", "TkDefaultFont")


def _configure_global_fonts(root: tk.Misc, family: str) -> Dict[str, tkfont.Font]:
    fonts: Dict[str, tkfont.Font] = {}
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont"):
        try:
            font = tkfont.nametofont(name)
        except tk.TclError:
            continue
        size = 11 if name != "TkHeadingFont" else 18
        weight = "bold" if name == "TkHeadingFont" else font.actual().get("weight", "normal")
        font.configure(family=family, size=size, weight=weight)
        fonts[name] = font

    fonts["base"] = tkfont.Font(root=root, family=family, size=11)
    fonts["small"] = tkfont.Font(root=root, family=family, size=10)
    fonts["button"] = tkfont.Font(root=root, family=family, size=11, weight="bold")
    fonts["title"] = tkfont.Font(root=root, family=family, size=22, weight="bold")
    fonts["subtitle"] = tkfont.Font(root=root, family=family, size=12)
    return fonts


def brand_subtitle(*lines: str | Iterable[str]) -> str:
    """Return a subtitle with the global Ioncore branding stamp.

    Each Bluetooth utility can pass one or more human-friendly lines that
    precede the shared branding statement sourced from the brochure UI.
    """

    if not lines:
        return f"Branding sync: {BRANDING_STAMP}"

    normalized: list[str] = []
    for block in lines:
        if isinstance(block, str):
            normalized.append(block)
        else:
            normalized.extend(str(part) for part in block)
    normalized.append(f"Branding sync: {BRANDING_STAMP}")
    return "\n".join(normalized)


def _maybe_create_logo(size: int = 96) -> Optional["ImageTk.PhotoImage"]:
    if Image is None or ImageDraw is None or ImageTk is None:  # Pillow optional
        return None

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    center = size / 2
    outer_radius = size // 2 - 2

    start_rgb = (0x38, 0xF0, 0xD1)
    end_rgb = (0x6A, 0xFF, 0x3B)
    for i, radius in enumerate(range(outer_radius, 0, -1)):
        t = i / max(1, outer_radius)
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t)
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t)
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t)
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            fill=(r, g, b, 255),
        )

    inner_radius = int(outer_radius * 0.62)
    draw.ellipse(
        [center - inner_radius, center - inner_radius, center + inner_radius, center + inner_radius],
        fill=(6, 11, 26, 235),
    )

    orbit_radius = outer_radius - size * 0.14
    orbit_width = max(2, size // 26)
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

    core_radius = int(inner_radius * 0.45)
    draw.ellipse(
        [center - core_radius, center - core_radius, center + core_radius, center + core_radius],
        fill=(244, 249, 255, 235),
    )

    bar_width = max(4, size // 16)
    draw.rounded_rectangle(
        [center - bar_width * 1.4, center - bar_width * 0.24, center + bar_width * 1.4, center + bar_width * 0.24],
        radius=bar_width // 2,
        fill="#38F0D1",
    )
    draw.rounded_rectangle(
        [center - bar_width * 0.88, center - bar_width * 0.92, center + bar_width * 0.88, center - bar_width * 0.34],
        radius=bar_width // 2,
        fill="#6AFF3B",
    )

    return ImageTk.PhotoImage(canvas)


def apply_ioncore_branding(root: tk.Misc, *, mode: str = "dark") -> BrandingContext:
    mode = mode if mode in IONCORE_THEME_PALETTES else "dark"
    colors = IONCORE_THEME_PALETTES[mode]

    font_family = _detect_font_family(root)
    fonts = _configure_global_fonts(root, font_family)

    root.configure(bg=colors["bg"])
    base_spec = f"{fonts['base'].actual()['family']} {fonts['base'].actual()['size']}"
    button_spec = f"{fonts['button'].actual()['family']} {fonts['button'].actual()['size']} bold"
    root.option_add("*Font", base_spec)
    root.option_add("*Label.font", base_spec)
    root.option_add("*Label.background", colors["bg"])
    root.option_add("*Label.foreground", colors["text"])
    root.option_add("*Button.font", button_spec)
    root.option_add("*Button.background", colors["surface_alt"])
    root.option_add("*Button.foreground", colors["text"])
    root.option_add("*Button.activeBackground", colors["accent"])
    root.option_add("*Button.activeForeground", colors["accent_fg"])
    root.option_add("*Entry.background", colors["entry_bg"])
    root.option_add("*Entry.foreground", colors["entry_fg"])
    root.option_add("*Entry.insertBackground", colors["accent"])
    root.option_add("*Listbox.background", colors["list_bg"])
    root.option_add("*Listbox.foreground", colors["list_fg"])
    root.option_add("*Listbox.selectBackground", colors["list_select"])
    root.option_add("*Listbox.selectForeground", colors["list_select_fg"])
    root.option_add("*HighlightThickness", 0)

    branding = BrandingContext(root=root, mode=mode, colors=colors, fonts=fonts, logo=_maybe_create_logo())
    return branding


def build_branding_header(
    parent: tk.Misc,
    branding: BrandingContext,
    *,
    title: str,
    subtitle: Optional[str] = None,
) -> tk.Frame:
    colors = branding.colors
    frame = tk.Frame(parent, bg=colors["surface_alt"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
    branding.protect(frame)

    frame.configure(padx=18, pady=16)

    if branding.logo is not None:
        logo_label = tk.Label(frame, image=branding.logo, bg=colors["surface_alt"], bd=0)
        logo_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 18))
        branding.protect(logo_label)

    title_label = tk.Label(
        frame,
        text=title,
        bg=colors["surface_alt"],
        fg=colors["text"],
        font=branding.fonts["title"],
        anchor="w",
    )
    title_label.grid(row=0, column=1, sticky="w")
    branding.protect(title_label)

    if subtitle:
        subtitle_label = tk.Label(
            frame,
            text=subtitle,
            bg=colors["surface_alt"],
            fg=colors["muted_text"],
            font=branding.fonts["subtitle"],
            anchor="w",
            justify="left",
            wraplength=720,
        )
        subtitle_label.grid(row=1, column=1, sticky="w", pady=(6, 0))
        branding.protect(subtitle_label)

    frame.grid_columnconfigure(1, weight=1)
    return frame


def style_card(frame: tk.Frame, branding: BrandingContext) -> None:
    if getattr(frame, "_ioncore_preserve_style", False):
        return
    colors = branding.colors
    frame.configure(
        bg=colors["surface"],
        highlightbackground=colors["border"],
        highlightthickness=1,
        bd=0,
        padx=16,
        pady=14,
    )
    style_children(frame, branding)


def style_label_frame(labelframe: tk.LabelFrame, branding: BrandingContext) -> None:
    if getattr(labelframe, "_ioncore_preserve_style", False):
        return
    colors = branding.colors
    labelframe.configure(
        bg=colors["surface"],
        fg=colors["accent"],
        labelanchor="nw",
        highlightbackground=colors["border"],
        highlightthickness=1,
        bd=0,
        padx=16,
        pady=12,
    )
    style_children(labelframe, branding)


def style_text(widget: tk.Text, branding: BrandingContext) -> None:
    colors = branding.colors
    widget.configure(
        bg=colors["log_bg"],
        fg=colors["log_fg"],
        insertbackground=colors["accent"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=colors["border"],
    )


def style_children(parent: tk.Misc, branding: BrandingContext) -> None:
    for child in parent.winfo_children():
        style_widget(child, branding)

"""
Ioncore visual branding helpers for Tkinter applications.

This module centralizes the Ioncore Index palette and reusable
helpers so our desktop utilities can present a consistent visual
identity. It focuses on lightweight Tk widgets and keeps optional
Pillow usage guarded so the tools remain portable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import io
import math
import tkinter as tk
from tkinter import font as tkfont

try:  # Optional dependency; guarded so CLI tools still launch.
    from PIL import Image, ImageDraw, ImageTk  # type: ignore
except Exception:  # pragma: no cover - Pillow is optional at runtime
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageTk = None  # type: ignore

# ---------------------------------------------------------------------------
# Core brand constants
# ---------------------------------------------------------------------------

BRAND_NAME = "Ioncore"
BRAND_SUITE = "Ioncore Index"

# Short “stamp” you can safely use in window titles, about boxes, status bars, etc.
BRANDING_STAMP = f"{BRAND_SUITE} • Cohesive desktop controls"

# Longer tagline reused by helpers below
_BRANDING_TAGLINE = "Ioncore Index utilities · Cohesive desktop controls"


IONCORE_THEME_PALETTES: Dict[str, Dict[str, str]] = {
    "dark": {
        "bg": "#030712",
        "surface": "#0D182E",
        "surface_alt": "#11203D",
        "border": "#1C2A41",
        "border_soft": "#152033",
        "accent": "#6AFF3B",
        "accent_hover": "#53E02D",
        "accent_active": "#3CBF2A",
        "accent_alt": "#38F0D1",
        "accent_fg": "#02110B",
        "text": "#F5F8FF",
        "muted_text": "#B7C7E4",
        "muted": "#7F8BA4",
        "list_bg": "#09101D",
        "list_fg": "#F5F8FF",
        "list_select": "#6AFF3B",
        "list_select_fg": "#030712",
        "entry_bg": "#0B1424",
        "entry_fg": "#F5F8FF",
        "log_bg": "#0B1424",
        "log_fg": "#AEE8B4",
    },
    "light": {
        "bg": "#F5F8FF",
        "surface": "#FFFFFF",
        "surface_alt": "#EDF4FF",
        "border": "#CAD7EF",
        "border_soft": "#D9E4F8",
        "accent": "#4CD067",
        "accent_hover": "#3BBC58",
        "accent_active": "#2EA14A",
        "accent_alt": "#32B5F0",
        "accent_fg": "#082015",
        "text": "#13233C",
        "muted_text": "#506080",
        "muted": "#7786A0",
        "list_bg": "#FFFFFF",
        "list_fg": "#13233C",
        "list_select": "#4CD067",
        "list_select_fg": "#FFFFFF",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#13233C",
        "log_bg": "#FFFFFF",
        "log_fg": "#24502F",
    },
}

FONT_CANDIDATES = (
    "Montserrat",
    "Inter",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
    "Helvetica",
)


@dataclass
class BrandingContext:
    """Runtime description of the active Ioncore styling."""

    root: tk.Misc
    mode: str
    colors: Dict[str, str]
    fonts: Dict[str, tkfont.Font]
    logo: Optional["ImageTk.PhotoImage"] = None

    def protect(self, widget: tk.Misc) -> None:
        """Mark a widget so automatic styling skips it."""
        setattr(widget, "_ioncore_preserve_style", True)


# ---------------------------------------------------------------------------
# Brand text helpers
# ---------------------------------------------------------------------------

def brand_title(app_name: str) -> str:
    """Return a standard Ioncore window title."""
    return f"{BRAND_NAME} • {app_name}"


def brand_subtitle(*lines: str) -> str:
    """
    Compose a standard multi-line subtitle/tagline string.

    If lines are provided, they are joined and the shared tagline is
    appended as the final line. If no lines are given, just return the
    default tagline.
    """
    if not lines:
        return _BRANDING_TAGLINE
    return "\n".join([*lines, _BRANDING_TAGLINE])


# ---------------------------------------------------------------------------
# Font detection / configuration
# ---------------------------------------------------------------------------

def _detect_font_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for name in FONT_CANDIDATES:
        if name in available:
            return name
    return tkfont.nametofont("TkDefaultFont").actual().get("family", "TkDefaultFont")


def _configure_global_fonts(root: tk.Misc, family: str) -> Dict[str, tkfont.Font]:
    fonts: Dict[str, tkfont.Font] = {}
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont"):
        try:
            font = tkfont.nametofont(name)
        except tk.TclError:
            continue
        size = 11 if name != "TkHeadingFont" else 18
        weight = "bold" if name == "TkHeadingFont" else font.actual().get("weight", "normal")
        font.configure(family=family, size=size, weight=weight)
        fonts[name] = font

    fonts["base"] = tkfont.Font(root=root, family=family, size=11)
    fonts["small"] = tkfont.Font(root=root, family=family, size=10)
    fonts["button"] = tkfont.Font(root=root, family=family, size=11, weight="bold")
    fonts["title"] = tkfont.Font(root=root, family=family, size=22, weight="bold")
    fonts["subtitle"] = tkfont.Font(root=root, family=family, size=12)
    return fonts


def _font_to_option_string(font: tkfont.Font, *, include_weight: bool = False) -> str:
    """
    Convert a tkfont.Font into a Tk font string suitable for option_add.

    Ensures that font families with spaces (e.g. 'Segoe UI') are wrapped in
    braces so Tk doesn't mis-read 'UI' as the size.
    """
    actual = font.actual()
    family = actual.get("family", "TkDefaultFont")
    size = actual.get("size", 11)
    weight = actual.get("weight", "normal")

    # Wrap family in braces if it contains spaces
    if " " in family:
        family_token = f"{{{family}}}"
    else:
        family_token = family

    if include_weight and weight not in ("", "normal"):
        return f"{family_token} {size} {weight}"
    else:
        return f"{family_token} {size}"


# ---------------------------------------------------------------------------
# SVG-based Ioncore crest logo
# ---------------------------------------------------------------------------

BATTERY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" aria-labelledby="title desc">
  <title id="title">Ioncore Energy emblem</title>
  <desc id="desc">Ioncore crest featuring a neon-green lightning bolt encircled by an eight-point energy ring.</desc>
  <defs>
    <path id="spike" d="M60 6 72 24H48Z" />
  </defs>
  <g fill="#6aff3b">
    <use href="#spike" />
    <use href="#spike" transform="rotate(45 60 60)" />
    <use href="#spike" transform="rotate(90 60 60)" />
    <use href="#spike" transform="rotate(135 60 60)" />
    <use href="#spike" transform="rotate(180 60 60)" />
    <use href="#spike" transform="rotate(225 60 60)" />
    <use href="#spike" transform="rotate(270 60 60)" />
    <use href="#spike" transform="rotate(315 60 60)" />
  </g>
  <circle cx="60" cy="60" r="36" fill="none" stroke="#6aff3b" stroke-width="12" />
  <path fill="#6aff3b" d="M72 10 36 74h20l-8 36 44-70H68Z" />
</svg>"""


def _rotate_point(x: float, y: float, cx: float, cy: float, theta: float) -> tuple[float, float]:
    """Rotate (x, y) around center (cx, cy) by theta radians."""
    tx, ty = x - cx, y - cy
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    rx = tx * cos_t - ty * sin_t
    ry = tx * sin_t + ty * cos_t
    return (rx + cx, ry + cy)


def _create_logo_from_svg(svg_content: str, size: int = 96) -> Optional["ImageTk.PhotoImage"]:
    """
    Try to rasterize the Ioncore SVG crest using cairosvg → Pillow.
    Fallback: approximate the crest procedurally with Pillow only.
    """
    # 1) Preferred path: cairosvg (if available) + Pillow
    try:
        import cairosvg  # type: ignore

        if Image is not None and ImageTk is not None:
            png_bytes = cairosvg.svg2png(
                bytestring=svg_content.encode("utf-8"),
                output_width=size,
                output_height=size,
            )
            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            return ImageTk.PhotoImage(img)
    except Exception:
        # If cairosvg is missing or fails, fall back below
        pass

    # 2) Fallback: procedural Pillow drawing that approximates the SVG
    if Image is None or ImageDraw is None or ImageTk is None:
        return None

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    view = 120.0
    scale = size / view

    # Spikes (triangles) rotated around center
    base_tri = [(60.0, 6.0), (72.0, 24.0), (48.0, 24.0)]
    for i in range(8):
        angle = math.radians(45 * i)
        rotated = [_rotate_point(px, py, 60.0, 60.0, angle) for (px, py) in base_tri]
        scaled = [(int(round(x * scale)), int(round(y * scale))) for (x, y) in rotated]
        draw.polygon(scaled, fill="#6aff3b")

    # Ring
    cx, cy, r = 60.0, 60.0, 36.0
    bbox = (
        int(round((cx - r) * scale)),
        int(round((cy - r) * scale)),
        int(round((cx + r) * scale)),
        int(round((cy + r) * scale)),
    )
    stroke_w = max(1, int(round(12.0 * scale)))
    try:
        draw.ellipse(bbox, outline="#6aff3b", width=stroke_w)
    except TypeError:
        # Older Pillow versions without 'width' support
        outer = bbox
        inner_r = r - 12.0 / 2.0
        inner_bbox = (
            int(round((cx - inner_r) * scale)),
            int(round((cy - inner_r) * scale)),
            int(round((cx + inner_r) * scale)),
            int(round((cy + inner_r) * scale)),
        )
        draw.ellipse(outer, fill="#6aff3b")
        draw.ellipse(inner_bbox, fill=(0, 0, 0, 0))

    # Lightning bolt approximation
    bolt_pts = [
        (72.0, 10.0),
        (36.0, 74.0),
        (56.0, 74.0),
        (48.0, 110.0),
        (92.0, 40.0),
        (68.0, 40.0),
    ]
    bolt_scaled = [(int(round(x * scale)), int(round(y * scale))) for (x, y) in bolt_pts]
    draw.polygon(bolt_scaled, fill="#6aff3b")

    return ImageTk.PhotoImage(img)


def _maybe_create_logo(size: int = 96) -> Optional["ImageTk.PhotoImage"]:
    """
    Create the Ioncore crest logo image, if the required imaging stack is
    available. Returns None if Pillow (and/or cairosvg) aren't present.
    """
    return _create_logo_from_svg(BATTERY_SVG, size=size)


# ---------------------------------------------------------------------------
# Tk theming & header widgets
# ---------------------------------------------------------------------------

def apply_ioncore_branding(root: tk.Misc, *, mode: str = "dark") -> BrandingContext:
    """Apply the Ioncore theme to a Tk root / Toplevel and return a BrandingContext."""
    mode = mode if mode in IONCORE_THEME_PALETTES else "dark"
    colors = IONCORE_THEME_PALETTES[mode]

    font_family = _detect_font_family(root)
    fonts = _configure_global_fonts(root, font_family)

    root.configure(bg=colors["bg"])

    # Use safe font strings for option_add so families with spaces work (e.g. 'Segoe UI')
    base_spec = _font_to_option_string(fonts["base"])
    button_spec = _font_to_option_string(fonts["button"], include_weight=True)

    root.option_add("*Font", base_spec)
    root.option_add("*Label.font", base_spec)
    root.option_add("*Label.background", colors["bg"])
    root.option_add("*Label.foreground", colors["text"])
    root.option_add("*Button.font", button_spec)
    root.option_add("*Button.background", colors["surface_alt"])
    root.option_add("*Button.foreground", colors["text"])
    root.option_add("*Button.activeBackground", colors["accent"])
    root.option_add("*Button.activeForeground", colors["accent_fg"])
    root.option_add("*Entry.background", colors["entry_bg"])
    root.option_add("*Entry.foreground", colors["entry_fg"])
    root.option_add("*Entry.insertBackground", colors["accent"])
    root.option_add("*Listbox.background", colors["list_bg"])
    root.option_add("*Listbox.foreground", colors["list_fg"])
    root.option_add("*Listbox.selectBackground", colors["list_select"])
    root.option_add("*Listbox.selectForeground", colors["list_select_fg"])
    root.option_add("*HighlightThickness", 0)

    branding = BrandingContext(
        root=root,
        mode=mode,
        colors=colors,
        fonts=fonts,
        logo=_maybe_create_logo(),
    )
    return branding


def build_branding_header(
    parent: tk.Misc,
    branding: BrandingContext,
    *,
    title: str,
    subtitle: Optional[str] = None,
) -> tk.Frame:
    """Create a standard header with logo, title, and optional subtitle."""
    colors = branding.colors
    frame = tk.Frame(
        parent,
        bg=colors["surface_alt"],
        highlightbackground=colors["border"],
        highlightthickness=1,
        bd=0,
    )
    branding.protect(frame)

    frame.configure(padx=18, pady=16)

    if branding.logo is not None:
        logo_label = tk.Label(frame, image=branding.logo, bg=colors["surface_alt"], bd=0)
        logo_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 18))
        branding.protect(logo_label)
        # keep a reference to avoid GC
        logo_label.image = branding.logo

    title_label = tk.Label(
        frame,
        text=title,
        bg=colors["surface_alt"],
        fg=colors["text"],
        font=branding.fonts["title"],
        anchor="w",
    )
    title_label.grid(row=0, column=1, sticky="w")
    branding.protect(title_label)

    if subtitle:
        subtitle_label = tk.Label(
            frame,
            text=subtitle,
            bg=colors["surface_alt"],
            fg=colors["muted_text"],
            font=branding.fonts["subtitle"],
            anchor="w",
            justify="left",
            wraplength=720,
        )
        subtitle_label.grid(row=1, column=1, sticky="w", pady=(6, 0))
        branding.protect(subtitle_label)

    frame.grid_columnconfigure(1, weight=1)
    return frame


# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------

def style_card(frame: tk.Frame, branding: BrandingContext) -> None:
    if getattr(frame, "_ioncore_preserve_style", False):
        return
    colors = branding.colors
    frame.configure(
        bg=colors["surface"],
        highlightbackground=colors["border"],
        highlightthickness=1,
        bd=0,
        padx=16,
        pady=14,
    )
    style_children(frame, branding)


def style_label_frame(labelframe: tk.LabelFrame, branding: BrandingContext) -> None:
    if getattr(labelframe, "_ioncore_preserve_style", False):
        return
    colors = branding.colors
    labelframe.configure(
        bg=colors["surface"],
        fg=colors["accent"],
        labelanchor="nw",
        highlightbackground=colors["border"],
        highlightthickness=1,
        bd=0,
        padx=16,
        pady=12,
    )
    style_children(labelframe, branding)


def style_text(widget: tk.Text, branding: BrandingContext) -> None:
    colors = branding.colors
    widget.configure(
        bg=colors["log_bg"],
        fg=colors["log_fg"],
        insertbackground=colors["accent"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=colors["border"],
    )


def style_children(parent: tk.Misc, branding: BrandingContext) -> None:
    for child in parent.winfo_children():
        style_widget(child, branding)


def style_widget(widget: tk.Misc, branding: BrandingContext) -> None:
    if getattr(widget, "_ioncore_preserve_style", False):
        return

    colors = branding.colors
    widget_class = widget.winfo_class()

    if widget_class in {"Frame"}:
        widget.configure(bg=colors["surface"])
        style_children(widget, branding)
    elif widget_class in {"Labelframe"}:
        style_label_frame(widget, branding)
    elif widget_class in {"Label"}:
        bg = widget.master.cget("bg") if hasattr(widget.master, "cget") else colors["surface"]
        widget.configure(bg=bg, fg=colors["text"], font=branding.fonts["base"])
    elif widget_class in {"Button"}:
        widget.configure(
            bg=colors["accent"],
            fg=colors["bg"],
            activebackground=colors["accent_hover"],
            activeforeground=colors["bg"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=16,
            pady=8,
            font=branding.fonts["button"],
            cursor="hand2",
        )
    elif widget_class in {"Checkbutton"}:
        bg = widget.master.cget("bg") if hasattr(widget.master, "cget") else colors["surface"]
        widget.configure(
            bg=bg,
            fg=colors["muted_text"],
            activebackground=bg,
            activeforeground=colors["accent"],
            selectcolor=colors["bg"],
            highlightthickness=0,
            font=branding.fonts["base"],
        )
    elif widget_class in {"Entry"}:
        widget.configure(
            bg=colors["entry_bg"],
            fg=colors["entry_fg"],
            insertbackground=colors["accent"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
        )
    elif widget_class in {"Listbox"}:
        widget.configure(
            bg=colors["list_bg"],
            fg=colors["list_fg"],
            selectbackground=colors["list_select"],
            selectforeground=colors["list_select_fg"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
            activestyle="dotbox",
        )
    elif widget_class in {"Text"}:
        style_text(widget, branding)
    elif widget_class in {"Scrollbar"}:
        widget.configure(
            bg=colors["surface"],
            activebackground=colors["accent"],
            troughcolor=colors["surface_alt"],
            relief="flat",
            bd=0,
            highlightthickness=0,
        )

    # Recurse for children except where already handled
    if widget_class not in {"Frame", "Labelframe"}:
        for child in widget.winfo_children():
            style_widget(child, branding)
