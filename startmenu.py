# startup.py
from __future__ import annotations

import os
import sys
import threading
import subprocess
import queue
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

import ioncore_branding


# --------------------------- Model ---------------------------------

@dataclass
class MenuEntry:
    label: str
    path: Path

    @property
    def exists(self) -> bool:
        try:
            return self.path.exists()
        except Exception:
            return False


EXPLICIT_ENTRIES = [
    ("Bulk Access 22-23", Path("22-23.py")),
    ("Bulk Access 2234", Path("2234.py")),
    ("Bulk Access 2235", Path("2235.py")),
    ("Experiment Spot", Path("experiment spot.py")),
    ("A2S2", Path("a2s2.py")),
]


def app_base_dir() -> Path:
    """Folder that should contain the runnable scripts."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def build_menu() -> List[MenuEntry]:
    base = app_base_dir()
    entries: List[MenuEntry] = []

    # Add explicit known entries
    for label, rel in EXPLICIT_ENTRIES:
        entries.append(MenuEntry(label=label, path=(base / rel)))

    # Add dynamic mace*.py scripts
    for s in sorted(base.glob("mace*.py")):
        label = s.stem.replace("_", " ").title()
        entries.append(MenuEntry(label=label, path=s))

    # De-dup by path (keep first)
    seen = set()
    unique: List[MenuEntry] = []
    for e in entries:
        if e.path not in seen:
            unique.append(e)
            seen.add(e.path)
    return unique


def resolve_cli_target(arg: str, entries: List[MenuEntry]) -> Optional[MenuEntry]:
    # 1) Index (1-based)
    if arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(entries):
            return entries[idx]

    # 2) Exact filename
    for e in entries:
        if e.path.name.lower() == arg.lower():
            return e

    # 3) Label prefix
    for e in entries:
        if e.label.lower().startswith(arg.lower()):
            return e

    # 4) Direct path
    p = Path(arg)
    if p.suffix == ".py" and p.exists():
        return MenuEntry(label=p.stem, path=p.resolve())

    return None


# --------------------------- GUI ------------------------------------

class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.branding = ioncore_branding.apply_ioncore_branding(self)
        self.title("Ioncore Launch Hub")
        self.geometry("980x600")
        self.minsize(880, 520)

        self.branding_header = ioncore_branding.build_branding_header(
            self,
            self.branding,
            title="Ioncore Launch Hub",
            subtitle="Launch Ioncore bulk access suites and supporting tools.",
        )
        self.branding_header.pack(fill="x", padx=18, pady=(18, 12))

        # State
        self.entries: List[MenuEntry] = build_menu()
        self.proc: Optional[subprocess.Popen] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.output_q: queue.Queue[str] = queue.Queue()
        self.stop_reader = threading.Event()
        self.new_console_var = tk.BooleanVar(value=False)

        # UI
        self._build_ui()

        # If user passed a quick-run arg, run it
        if len(sys.argv) > 1:
            target = resolve_cli_target(sys.argv[1], self.entries)
            if target and target.exists:
                self._select_entry_by_path(target.path)
                self.run_selected()
            else:
                self._log_line(f"Could not resolve target from CLI: {sys.argv[1]!r}")

        # Start polling for output
        self.after(60, self._drain_output_queue)

    # ---- UI Layout ----

    def _build_ui(self):
        toolbar = tk.Frame(self, bd=0)
        toolbar.pack(fill=tk.X, padx=18, pady=(0, 16))

        tk.Button(toolbar, text="Refresh", command=self.refresh_menu).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(toolbar, text="Run Selected", command=self.run_selected).pack(side=tk.LEFT, padx=6)
        tk.Button(toolbar, text="Stop", command=self.stop_running).pack(side=tk.LEFT, padx=6)
        tk.Button(toolbar, text="Add Script…", command=self.add_script).pack(side=tk.LEFT, padx=12)
        tk.Button(toolbar, text="Open Folder", command=self.open_selected_folder).pack(side=tk.LEFT, padx=6)

        tk.Checkbutton(
            toolbar,
            text="Run in new console (Windows)",
            variable=self.new_console_var,
        ).pack(side=tk.RIGHT, padx=(12, 0))

        paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            relief=tk.FLAT,
            bd=0,
            bg=self.branding.colors["bg"],
            handlepad=2,
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))

        left_card = tk.Frame(paned, bd=0)
        paned.add(left_card, minsize=280)

        tk.Label(left_card, text="Scripts", font=("Montserrat", 12, "bold")).pack(anchor="w", pady=(0, 8))
        self.listbox = tk.Listbox(left_card, height=16, activestyle="dotbox")
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self.run_selected())

        right_container = tk.Frame(paned, bd=0, bg=self.branding.colors["bg"])
        paned.add(right_container, minsize=420)

        self.sel_name = tk.StringVar(value="-")
        self.sel_path = tk.StringVar(value="-")
        self.sel_status = tk.StringVar(value="-")
        self.run_status = tk.StringVar(value="Idle")

        details_card = tk.Frame(right_container, bd=0)
        details_card.pack(fill=tk.X, pady=(0, 16))

        tk.Label(details_card, text="Details", font=("Montserrat", 12, "bold")).pack(anchor="w", pady=(0, 8))

        def add_detail(label_text: str, var: tk.StringVar) -> None:
            row = tk.Frame(details_card, bd=0)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label_text, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, textvariable=var, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        add_detail("Selected:", self.sel_name)
        add_detail("Path:", self.sel_path)
        add_detail("Exists:", self.sel_status)
        add_detail("Runner:", self.run_status)

        output_card = tk.Frame(right_container, bd=0)
        output_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(output_card, text="Output", font=("Montserrat", 12, "bold")).pack(anchor="w", pady=(0, 8))
        self.txt = scrolledtext.ScrolledText(output_card, wrap="word", height=18)
        self.txt.pack(fill=tk.BOTH, expand=True)
        self.txt.configure(state=tk.DISABLED)

        ioncore_branding.style_card(toolbar, self.branding)
        ioncore_branding.style_card(left_card, self.branding)
        ioncore_branding.style_card(details_card, self.branding)
        ioncore_branding.style_card(output_card, self.branding)
        ioncore_branding.style_widget(self.txt, self.branding)

        # Keep selection labels updated
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._update_selection_labels())

        # Finally load items (now safe to call; StringVars exist)
        self._reload_listbox()

    # ---- Helpers ----

    def _reload_listbox(self):
        self.listbox.delete(0, tk.END)
        for e in self.entries:
            status = "✓" if e.exists else "✗ missing"
            self.listbox.insert(tk.END, f"{e.label}  ({e.path.name})  [{status}]")
        if self.entries:
            self.listbox.selection_set(0)
        self._update_selection_labels()

    def _current_entry(self) -> Optional[MenuEntry]:
        sel = self.listbox.curselection()
        if not sel:
            return None
        return self.entries[sel[0]]

    def _select_entry_by_path(self, p: Path):
        for i, e in enumerate(self.entries):
            try:
                if e.path.resolve() == p.resolve():
                    self.listbox.selection_clear(0, tk.END)
                    self.listbox.selection_set(i)
                    self.listbox.see(i)
                    self._update_selection_labels()
                    return
            except Exception:
                pass

    def _update_selection_labels(self):
        e = self._current_entry()
        if e is None:
            self.sel_name.set("-")
            self.sel_path.set("-")
            self.sel_status.set("-")
            return
        self.sel_name.set(e.label)
        self.sel_path.set(str(e.path))
        self.sel_status.set("Yes" if e.exists else "No")

    def _log_line(self, s: str):
        self.txt.configure(state=tk.NORMAL)
        self.txt.insert(tk.END, s + "\n")
        self.txt.see(tk.END)
        self.txt.configure(state=tk.DISABLED)

    def _drain_output_queue(self):
        try:
            while True:
                line = self.output_q.get_nowait()
                self._log_line(line.rstrip("\n"))
        except queue.Empty:
            pass
        # Poll again
        self.after(80, self._drain_output_queue)

    def refresh_menu(self):
        self.entries = build_menu()
        self._reload_listbox()

    def add_script(self):
        path = filedialog.askopenfilename(
            title="Add Python Script",
            filetypes=[("Python files", "*.py")],
            initialdir=str(app_base_dir()),
        )
        if not path:
            return
        p = Path(path)
        label = p.stem.replace("_", " ").title()
        self.entries.append(MenuEntry(label=label, path=p))
        self._reload_listbox()
        self._select_entry_by_path(p)

    def open_selected_folder(self):
        e = self._current_entry()
        if not e:
            return
        try:
            folder = e.path.parent
            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)
        except Exception as ex:
            messagebox.showerror("Open Folder", f"Failed to open folder:\n{ex}")

    # ---- Running / Stopping ----

    def run_selected(self):
        e = self._current_entry()
        if not e:
            messagebox.showwarning("Run", "Please select a script.")
            return
        if not e.exists:
            messagebox.showerror("Run", f"File not found:\n{e.path}")
            return

        # If a script is already running, ask to stop it first
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno("Script Running", "A script is running. Stop it and start the new one?"):
                return
            self.stop_running()

        # Prepare environment
        env = os.environ.copy()
        base = str(app_base_dir())
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{base}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = base

        cmd = [sys.executable, str(e.path)]
        cwd = str(e.path.resolve().parent)

        creationflags = 0
        start_new_session = True  # cross-platform process group
        stdout = subprocess.PIPE
        stderr = subprocess.STDOUT

        if sys.platform.startswith("win") and self.new_console_var.get():
            # Open a new console window on Windows
            creationflags = 0x00000010  # CREATE_NEW_CONSOLE
            stdout = None
            stderr = None

        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                creationflags=creationflags,
                stdout=stdout,
                stderr=stderr,
                text=True,
                bufsize=1,
                universal_newlines=True,
                start_new_session=start_new_session,
            )
        except Exception as ex:
            messagebox.showerror("Run", f"Failed to start script:\n{ex}")
            self.proc = None
            return

        self.run_status.set(f"Running {e.path.name} (PID {self.proc.pid})")
        self._log_line(f"--- Running {e.path.name} ---")
        self._log_line(f"cwd: {cwd}")
        self._log_line(f"python: {sys.executable}")

        # Start reader thread if we capture output
        if self.proc.stdout is not None:
            self.stop_reader.clear()
            self.reader_thread = threading.Thread(target=self._read_stdout_loop, daemon=True)
            self.reader_thread.start()
        else:
            self._log_line("(Output directed to a new console window.)")

        # Monitor process done
        threading.Thread(target=self._wait_for_exit, daemon=True).start()

    def _read_stdout_loop(self):
        try:
            assert self.proc is not None and self.proc.stdout is not None
            for line in self.proc.stdout:
                if self.stop_reader.is_set():
                    break
                self.output_q.put(line.rstrip("\r\n"))
        except Exception as ex:
            self.output_q.put(f"[reader error] {ex}")

    def _wait_for_exit(self):
        if not self.proc:
            return
        code = self.proc.wait()
        self.output_q.put(f"--- Script exited with code {code} ---")
        self.run_status.set("Idle")
        self.proc = None
        self.stop_reader.set()

    def stop_running(self):
        if not self.proc:
            return
        try:
            pid = self.proc.pid
            if sys.platform.startswith("win"):
                # Terminate the process tree on Windows
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            else:
                # Send SIGTERM to the whole process group
                os.killpg(self.proc.pid, signal.SIGTERM)
        except Exception:
            try:
                self.proc.terminate()
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        finally:
            self.run_status.set("Idle")
            self.stop_reader.set()
            self.proc = None
            self._log_line("--- Stopped ---")


# --------------------------- Main -----------------------------------

def main():
    app = LauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()

