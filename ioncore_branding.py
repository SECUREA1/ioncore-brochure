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
