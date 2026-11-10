"""
app.py
──────
Microsoft Store Package Downloader — Ultra Clean & Minimal Native Tkinter (~10MB).
English UI, high-contrast light theme, multi-row selection, direct bottom folder controls,
and razor-sharp Windows High-DPI display.
"""

import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Optional

from i18n import load_config, save_config, tr
from ms_store_api import (
    DownloadCancelledError,
    MSStoreAPI,
    PackageFile,
    ProductInfo,
    StoreError,
    extract_package,
)

BASE_DIR = Path(__file__).resolve().parent
ICON_ICO = BASE_DIR / "assets" / "app.ico"

# ═══════════════════════════════════════════════════════════════════════════════
# Clean High-Contrast Light Theme Palette (Calibrated WCAG Contrast)
# ═══════════════════════════════════════════════════════════════════════════════
C_BG_WINDOW = "#eef2f6"        # Soft Slate background (clear separation from white cards)
C_BG_CARD = "#ffffff"          # Pure white card
C_TEXT_PRIMARY = "#0f172a"     # Slate 900 (17.8:1 AAA contrast on white)
C_TEXT_SECONDARY = "#334155"   # Slate 700 (9.3:1 AAA contrast on white)
C_BORDER = "#b8c4d4"           # Crisp Slate outline (1.77:1 vs white, 1.57:1 vs window)
C_BORDER_FOCUS = "#0ea5e9"     # Clear Sky 500 focus outline (2.77:1 vs white)
C_TABLE_BG = "#ffffff"
C_TABLE_ROW_ALT = "#f3f6fa"    # Distinct yet gentle alternating row background
C_TABLE_FG = "#0f172a"
C_TABLE_HEADING_BG = "#e2e8f0" # Slate 200 header (clear separation from table rows)
C_TABLE_HEADING_FG = "#1e293b" # Slate 800 header text (11.5:1 AAA contrast)
C_TABLE_SEL_BG = "#cbeafe"     # Rich Sky selection highlight (clearly visible on white)
C_TABLE_SEL_FG = "#0c4a6e"     # Deep Sky 900 selection text (8.0:1 AAA contrast)
C_BTN_NORMAL_BG = "#d8e2ee"    # Tactile secondary button background
C_BTN_NORMAL_FG = "#0f172a"
C_BTN_NORMAL_ACTIVE = "#c3d0e0"
C_SUMMARY = "#0369a1"
C_ACCENT = "#0284c7"           # Sky 600 primary button accent
C_ACCENT_HOVER = "#0369a1"     # Sky 700 hover
C_ACCENT_DISABLED_BG = "#6dbbe3"  # Faded sky blue when disabled
C_ACCENT_DISABLED_FG = "#ffffff"  # Keep white text when disabled
C_NOTICE_SUCCESS = "#15803d"   # Green 700 (5.0:1 AA contrast on white)
C_NOTICE_WARNING = "#b45309"   # Amber 700 (5.0:1 AA contrast on white)
C_NOTICE_ERROR = "#b91c1c"     # Red 700 (6.4:1 AA contrast on white)

# Per-state text colors for the table Status column
C_STATUS_WAITING = "#475569"      # Slate 600 (queued / waiting)
C_STATUS_DOWNLOADING = C_SUMMARY  # Sky 700 (active download)
C_STATUS_DONE = C_NOTICE_SUCCESS  # Green 700 (completed)
C_STATUS_ERROR = C_NOTICE_ERROR   # Red 700 (failed)
C_STATUS_CANCELLED = C_NOTICE_WARNING  # Amber 700 (cancelled)

STATUS_COLOR_MAP = {
    "ready": C_TABLE_FG,
    "waiting": C_STATUS_WAITING,
    "downloading": C_STATUS_DOWNLOADING,
    "done": C_STATUS_DONE,
    "error": C_STATUS_ERROR,
    "cancelled": C_STATUS_CANCELLED,
}

RING_OPTIONS = [
    "Retail (Stable)",
    "Release Preview",
    "Insider Slow (Beta)",
    "Insider Fast (Dev/Canary)",
]
ARCH_FILTERS = ["x64", "x86", "ARM64", "ARM", "Neutral"]


class SelectableLabel(tk.Entry):
    """A borderless, readonly Entry styled as a Label that allows mouse selection & copy."""

    def __init__(self, master, font=None, fg=None, bg=None, **kwargs):
        super().__init__(
            master,
            font=font,
            fg=fg,
            bg=bg,
            readonlybackground=bg,
            selectbackground=C_ACCENT,
            selectforeground="#ffffff",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="xterm",
            **kwargs,
        )
        self.config(state="readonly")

    def set_text(self, text: str, fg: Optional[str] = None):
        self.config(state="normal")
        self.delete(0, "end")
        self.insert(0, text)
        self.xview_moveto(0)
        if fg:
            super().config(fg=fg)
        self.config(state="readonly")

    def cget(self, key):
        if key == "text":
            return self.get()
        return super().cget(key)

    def config(self, **kwargs):
        if "text" in kwargs:
            self.set_text(kwargs.pop("text"), fg=kwargs.get("fg"))
        if kwargs:
            super().config(**kwargs)

    configure = config


class FlatContextMenu(tk.Toplevel):
    """
    Modern flat context menu matching the application's Slate & Sky-Blue light palette.
    Replaces native Win32 tk.Menu (which ignores custom colors/borders on Windows).
    """

    def __init__(self, master):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.configure(
            bg=C_BG_CARD,
            bd=0,
            relief="flat",
            highlightbackground=C_BORDER,
            highlightcolor=C_BORDER,
            highlightthickness=1,
        )
        self.container = tk.Frame(self, bg=C_BG_CARD, padx=4, pady=4)
        self.container.pack(fill="both", expand=True)
        self._items: list = []
        self._active_combo: Optional[ttk.Combobox] = None

        def _on_escape(e):
            combo = self._active_combo
            self.close()
            if combo is not None:
                try:
                    combo.focus_set()
                except tk.TclError:
                    pass

        self.bind("<Escape>", _on_escape)
        self.bind("<FocusOut>", self._on_focus_out)
        master.bind("<Button-1>", self._on_master_click, add="+")
        master.bind("<Configure>", lambda e: self.close(), add="+")

    def _on_focus_out(self, event):
        self.after(10, self._check_focus)

    def _pointer_over_active_combo(self) -> bool:
        if self._active_combo is None:
            return False
        try:
            px, py = self.winfo_pointerxy()
            return self.winfo_containing(px, py) is self._active_combo
        except (tk.TclError, KeyError):
            return False

    def _check_focus(self):
        if not self.winfo_ismapped():
            return
        # Clicking the owning combobox again is handled as a toggle by its own handler.
        if self._pointer_over_active_combo():
            return
        focused = self.focus_get()
        if focused is None or (
            focused is not self
            and focused is not self._active_combo
            and not str(focused).startswith(str(self))
        ):
            self.close()

    def _on_master_click(self, event):
        if not self.winfo_ismapped():
            return
        w = event.widget
        if (
            w is not self
            and w is not self._active_combo
            and not str(w).startswith(str(self))
        ):
            self.close()

    def close(self):
        if self._active_combo is not None:
            try:
                self._active_combo.state(["!pressed"])
            except tk.TclError:
                pass
        self._active_combo = None
        if self.winfo_ismapped():
            self.withdraw()

    def delete(self, start, end=None):
        for child in self.container.winfo_children():
            child.destroy()
        self._items.clear()

    def index(self, idx):
        if idx == "end":
            return len(self._items) - 1 if self._items else None
        return idx

    def add_separator(self):
        sep = tk.Frame(self.container, bg=C_BORDER, height=1, bd=0)
        sep.pack(fill="x", padx=8, pady=4)
        self._items.append(("separator", sep))

    def add_command(
        self,
        label: str = "",
        command=None,
        state: str = "normal",
        selected: bool = False,
    ):
        enabled = state == "normal"
        base_bg = "#eef6ff" if (enabled and selected) else C_BG_CARD
        base_fg = (
            C_TABLE_SEL_FG
            if (enabled and selected)
            else (C_TEXT_PRIMARY if enabled else "#94a3b8")
        )
        font_spec = ("Segoe UI", 10, "bold") if (enabled and selected) else ("Segoe UI", 10)
        lbl = tk.Label(
            self.container,
            text=label,
            font=font_spec,
            bg=base_bg,
            fg=base_fg,
            anchor="w",
            padx=12,
            pady=6,
            cursor="hand2" if enabled else "arrow",
        )
        lbl.pack(fill="x")

        if enabled:
            def on_enter(e, w=lbl):
                w.config(bg=C_TABLE_SEL_BG, fg=C_TABLE_SEL_FG)

            def on_leave(e, w=lbl, bg=base_bg, fg=base_fg):
                w.config(bg=bg, fg=fg)

            def on_click(e, cmd=command):
                self.close()
                if cmd:
                    self.master.after(1, cmd)
                return "break"

            lbl.bind("<Enter>", on_enter)
            lbl.bind("<Leave>", on_leave)
            lbl.bind("<ButtonRelease-1>", on_click)

        self._items.append(("command", lbl))

    def popup_for_combobox(self, combo: ttk.Combobox):
        if self.winfo_ismapped() and self._active_combo is combo:
            self.close()
            try:
                combo.focus_set()
            except tk.TclError:
                pass
            return
        self.close()
        self._active_combo = combo
        combo.state(["pressed"])
        self.delete(0, "end")
        values = list(combo["values"])
        cur_idx = combo.current()

        def _select_idx(idx: int):
            combo.current(idx)
            combo.event_generate("<<ComboboxSelected>>")
            try:
                combo.focus_set()
            except tk.TclError:
                pass

        for i, val in enumerate(values):
            self.add_command(
                label=str(val),
                command=lambda idx=i: _select_idx(idx),
                state="normal",
                selected=(i == cur_idx),
            )

        combo.update_idletasks()
        x = combo.winfo_rootx()
        y = combo.winfo_rooty() + combo.winfo_height() + 2
        self.tk_popup(x, y, min_width=combo.winfo_width(), match_width=True)

    def tk_popup(
        self,
        x: int,
        y: int,
        min_width: int = 210,
        match_width: bool = False,
    ):
        self.update_idletasks()
        content_w = self.container.winfo_reqwidth() + 2
        req_w = max(min_width, content_w) if not match_width else max(min_width, content_w)
        req_h = self.container.winfo_reqheight() + 2
        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        if x + req_w > scr_w - 8:
            x = max(8, scr_w - req_w - 8)
        if y + req_h > scr_h - 40:
            y = max(8, y - req_h)
        self.geometry(f"{req_w}x{req_h}+{x}+{y}")
        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except Exception:
            pass


def get_architecture(name: str) -> str:
    """Identify CPU architecture from filename."""
    nl = name.lower()
    if "_x64" in nl:
        return "x64"
    if "_arm64" in nl:
        return "ARM64"
    if "_x86" in nl:
        return "x86"
    if "_arm" in nl:
        return "ARM"
    if "neutral" in nl:
        return "Neutral"
    return ""


def format_size(n: int) -> str:
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024**3:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / 1024**3:.2f} GB"


# ═══════════════════════════════════════════════════════════════════════════════
# Main Window
# ═══════════════════════════════════════════════════════════════════════════════
class MainWindow(tk.Tk):
    def __init__(self, start_maximized: bool = False):
        super().__init__()
        # Hide window during widget construction & layout calculation to prevent
        # the default 200x200 Tk window from flashing on screen at startup.
        self.withdraw()
        self.title(tr("app_title"))
        self.configure(bg=C_BG_WINDOW)

        cfg = load_config()
        self.cfg = cfg
        self.download_dir = cfg.get("download_dir") or str(
            Path.home() / "Downloads" / "MSStore"
        )

        self.api = MSStoreAPI()
        self.packages: list[PackageFile] = []
        self.product_info: Optional[ProductInfo] = None
        self.row_states: list[tuple] = []   # ("ready",) | ("downloading", pct) | ("done",) | ("error",)
        self.checked_rows: set[int] = set()
        self._last_clicked_row: Optional[int] = None
        self._context_row: Optional[int] = None
        self._status_cells: dict[str, tk.Label] = {}

        self._create_checkbox_images()

        self._info_state = "idle"           # idle | connecting | error | result
        self._info_text = ""
        self._progress_text = ""
        self._notice: Optional[tuple] = None  # (kind, text)
        self._notice_reason = ""              # "warn_missing" | "warn_nosel" | "copied" | ...
        self._worker_active = False
        self._downloading = False
        self._cancel_event = threading.Event()
        self._ui_queue = queue.Queue()
        self._process_ui_queue()

        self._init_styles()
        self._build_ui()
        self._render_info()

        # Lock dynamic minsize so top & bottom stay fixed and only table resizes
        # down to its minimum height (4 rows) before stopping.
        self.update_idletasks()
        min_w = max(960, self.winfo_reqwidth())
        min_h = self.winfo_reqheight()
        self.minsize(min_w, min_h)
        init_w = max(1100, min_w)
        init_h = max(720, min_h + 140)
        self.geometry(f"{init_w}x{init_h}")

        if start_maximized:
            self.state("zoomed")
        else:
            self.deiconify()
        self._set_app_icon()
        self.entry_query.focus_set()
        self.after(50, self.entry_query.focus_set)

    def _process_ui_queue(self):
        """Thread-safe UI queue processor executing on the Tkinter main thread."""
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        except Exception:
            pass
        finally:
            try:
                self.after(30, self._process_ui_queue)
            except Exception:
                pass

    def _run_on_ui(self, fn, *args, **kwargs):
        """Dispatch a function call to execute safely on the main GUI thread."""
        self._ui_queue.put(lambda: fn(*args, **kwargs))
        try:
            self.after(0, self._process_ui_queue)
        except Exception:
            pass

    def _set_app_icon(self):
        """Set native multi-resolution Windows icon directly from .ico via Win32 API."""
        if not ICON_ICO.exists():
            return
        ico_str = str(ICON_ICO)
        try:
            self.iconbitmap(default=ico_str)
        except Exception:
            try:
                self.iconbitmap(ico_str)
            except Exception:
                pass
        try:
            import ctypes
            from ctypes import wintypes

            u32 = ctypes.windll.user32
            u32.LoadImageW.restype = ctypes.c_void_p
            u32.LoadImageW.argtypes = [
                wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            u32.SendMessageW.restype = ctypes.c_void_p
            u32.SendMessageW.argtypes = [
                wintypes.HWND, wintypes.UINT, wintypes.WPARAM, ctypes.c_void_p,
            ]
            u32.SetClassLongPtrW.restype = ctypes.c_void_p
            u32.SetClassLongPtrW.argtypes = [
                wintypes.HWND, ctypes.c_int, ctypes.c_void_p,
            ]

            self.update_idletasks()
            hwnd = u32.GetParent(self.winfo_id()) or self.winfo_id()
            cx_big, cy_big = u32.GetSystemMetrics(11), u32.GetSystemMetrics(12)
            cx_sm, cy_sm = u32.GetSystemMetrics(49), u32.GetSystemMetrics(50)

            self._hicon_big = u32.LoadImageW(None, ico_str, 1, cx_big, cy_big, 0x0010)
            self._hicon_sm = u32.LoadImageW(None, ico_str, 1, cx_sm, cy_sm, 0x0010)
            if self._hicon_big:
                u32.SendMessageW(hwnd, 0x0080, 1, self._hicon_big)
                u32.SetClassLongPtrW(hwnd, -14, self._hicon_big)
            if self._hicon_sm:
                u32.SendMessageW(hwnd, 0x0080, 0, self._hicon_sm)
                u32.SetClassLongPtrW(hwnd, -34, self._hicon_sm)
        except Exception:
            pass

    def _create_checkbox_images(self):
        """Build symmetric 17x17 flat checkbox PhotoImages (15x15 box centered at 1..16)."""
        # Unchecked: #94a3b8 1px rounded-corner outline, #ffffff interior
        unchk = tk.PhotoImage(width=17, height=17)
        unchk.put("#94a3b8", to=(1, 1, 16, 16))
        unchk.put("#cbd5e1", to=(1, 1, 2, 2))
        unchk.put("#cbd5e1", to=(15, 1, 16, 2))
        unchk.put("#cbd5e1", to=(1, 15, 2, 16))
        unchk.put("#cbd5e1", to=(15, 15, 16, 16))
        unchk.put("#ffffff", to=(2, 2, 15, 15))
        self._img_unchecked = unchk

        # Checked: C_ACCENT (#0284c7) fill + crisp 2px white checkmark
        chk = tk.PhotoImage(width=17, height=17)
        chk.put(C_ACCENT, to=(1, 1, 16, 16))
        chk.put("#7dd3fc", to=(1, 1, 2, 2))
        chk.put("#7dd3fc", to=(15, 1, 16, 2))
        chk.put("#7dd3fc", to=(1, 15, 2, 16))
        chk.put("#7dd3fc", to=(15, 15, 16, 16))
        # 2px thick white checkmark strokes (centered inside 2..15)
        for x, y in (
            (4, 8), (5, 9), (6, 10), (7, 11),
            (8, 10), (9, 9), (10, 8), (11, 7), (12, 6), (13, 5),
        ):
            chk.put("#ffffff", to=(x, y, x + 1, y + 2))
        self._img_checked = chk

        # 9-slice 1px flat border images for TCombobox (normal / hover-focus)
        def _make_border(border_hex: str) -> tk.PhotoImage:
            img = tk.PhotoImage(width=8, height=8)
            img.put(border_hex, to=(0, 0, 8, 8))
            img.put(C_BG_CARD, to=(1, 1, 7, 7))
            return img

        self._img_combo_border = _make_border(C_BORDER)
        self._img_combo_border_hover = _make_border("#94a3b8")
        self._img_combo_border_focus = _make_border(C_BORDER_FOCUS)

        # Modern flat Chevron (⌄) icons for TCombobox (normal: Slate 600, active/focus: Sky 600)
        def _make_chevron(stroke_hex: str, aa_hex: str) -> tk.PhotoImage:
            img = tk.PhotoImage(width=18, height=16)
            img.put(C_BG_CARD, to=(0, 0, 18, 16))
            pts = (
                (3, 5), (4, 6), (5, 7), (6, 8), (7, 9), (8, 10),
                (9, 9), (10, 8), (11, 7), (12, 6), (13, 5),
            )
            for x, y in pts:
                img.put(aa_hex, to=(x, y - 1, x + 1, y))
                img.put(aa_hex, to=(x, y + 2, x + 1, y + 3))
            for x, y in pts:
                img.put(stroke_hex, to=(x, y, x + 1, y + 2))
            return img

        self._img_chevron_normal = _make_chevron("#475569", "#94a3b8")
        self._img_chevron_hover = _make_chevron("#1e293b", "#64748b")
        self._img_chevron_active = _make_chevron("#0369a1", C_ACCENT)

    def _init_styles(self):
        """Configure standard modern ttk widget styles."""
        style = ttk.Style(self)
        style.theme_use("clam")

        # Remove clam's dark 3D inner Treeview.field border so table_frame's 1px C_BORDER shines cleanly
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        # Center Treeitem.image horizontally & vertically inside column #0
        style.layout(
            "Treeview.Item",
            [
                (
                    "Treeitem.padding",
                    {
                        "sticky": "nswe",
                        "children": [
                            ("Treeitem.image", {"sticky": ""}),
                        ],
                    },
                )
            ],
        )
        style.configure("Treeview.Item", padding=(0, 0, 0, 0))
        style.configure(
            "Treeview",
            background=C_TABLE_BG,
            foreground=C_TABLE_FG,
            fieldbackground=C_TABLE_BG,
            bordercolor=C_TABLE_BG,
            lightcolor=C_TABLE_BG,
            darkcolor=C_TABLE_BG,
            rowheight=36,
            font=("Segoe UI", 11),
            indent=0,
            padding=0,
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", C_TABLE_SEL_BG)],
            foreground=[("selected", C_TABLE_SEL_FG)],
        )
        # Center Treeheading.image so the #0 header checkbox aligns directly above row checkboxes
        style.layout(
            "Treeview.Heading",
            [
                ("Treeheading.cell", {"sticky": "nswe"}),
                (
                    "Treeheading.border",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Treeheading.padding",
                                {
                                    "sticky": "nswe",
                                    "children": [
                                        ("Treeheading.image", {"sticky": ""}),
                                        ("Treeheading.text", {"sticky": "we"}),
                                    ],
                                },
                            )
                        ],
                    },
                ),
            ],
        )
        style.configure(
            "Treeview.Heading",
            background=C_TABLE_HEADING_BG,
            foreground=C_TABLE_HEADING_FG,
            bordercolor=C_BORDER,
            lightcolor=C_TABLE_HEADING_BG,
            darkcolor=C_BORDER,
            font=("Segoe UI", 10, "bold"),
            padding=(10, 7),
            relief="flat",
            borderwidth=1,
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#d3dce8")],
        )

        # Flat, harmonious vertical scrollbar inside table_frame
        style.configure(
            "Vertical.TScrollbar",
            troughcolor=C_TABLE_BG,
            background="#b8c4d4",
            bordercolor=C_TABLE_BG,
            lightcolor=C_TABLE_BG,
            darkcolor=C_TABLE_BG,
            arrowcolor="#475569",
            arrowsize=12,
            gripcount=0,
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", "#94a3b8"), ("pressed", "#64748b")],
        )

        # Custom image elements: clam's Combobox.field omits the right border without its
        # native downarrow, and Entry.field does not render image children. A 9-slice
        # border image draws all 4 sides and hosts the chevron reliably.
        #
        # Explicit visual state model (first match wins, so priority is top-down):
        #   pressed (popup open)  -> Sky accent border + Sky chevron
        #   focus   (keyboard Tab)-> Sky accent border + Slate chevron
        #   hover   (mouse over)  -> darker Slate border + darker chevron
        #   normal                -> Slate border + Slate chevron
        # Mouse clicks never move keyboard focus onto the combobox, so the accent border
        # no longer jumps between focus/unfocus while the popup opens or closes.
        try:
            style.element_create(
                "FlatCombo.border",
                "image",
                self._img_combo_border,
                ("pressed", self._img_combo_border_focus),
                ("focus", self._img_combo_border_focus),
                ("hover", self._img_combo_border_hover),
                border=(1, 1, 1, 1),
                sticky="nswe",
            )
            style.element_create(
                "FlatCombo.downarrow",
                "image",
                self._img_chevron_normal,
                ("pressed", self._img_chevron_active),
                ("focus", self._img_chevron_active),
                ("hover", self._img_chevron_hover),
                sticky="e",
                padding=(4, 0, 6, 0),
            )
        except tk.TclError:
            pass
        style.layout(
            "TCombobox",
            [
                (
                    "FlatCombo.border",
                    {
                        "sticky": "nswe",
                        "children": [
                            ("FlatCombo.downarrow", {"side": "right", "sticky": "ns"}),
                            (
                                "Combobox.padding",
                                {
                                    "sticky": "nswe",
                                    "children": [
                                        ("Combobox.textarea", {"sticky": "nswe"}),
                                    ],
                                },
                            ),
                        ],
                    },
                )
            ],
        )
        style.configure(
            "TCombobox",
            fieldbackground=C_BG_CARD,
            background=C_BG_CARD,
            foreground=C_TEXT_PRIMARY,
            padding=(10, 4, 4, 4),
        )
        style.map(
            "TCombobox",
            foreground=[
                ("readonly", "focus", C_TEXT_PRIMARY),
                ("readonly", C_TEXT_PRIMARY),
            ],
            fieldbackground=[
                ("readonly", "focus", C_BG_CARD),
                ("readonly", C_BG_CARD),
            ],
            selectbackground=[
                ("readonly", "focus", C_BG_CARD),
                ("readonly", C_BG_CARD),
            ],
            selectforeground=[
                ("readonly", "focus", C_TEXT_PRIMARY),
                ("readonly", C_TEXT_PRIMARY),
            ],
        )

        style.configure(
            "ComboboxPopdownFrame",
            background=C_BORDER,
            bordercolor=C_BORDER,
            lightcolor=C_BORDER,
            darkcolor=C_BORDER,
            relief="flat",
            borderwidth=1,
        )

        # Configure the dropdown popup Listbox font & palette (Tk default is 9pt)
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 11))
        self.option_add("*TCombobox*Listbox.background", C_BG_CARD)
        self.option_add("*TCombobox*Listbox.foreground", C_TEXT_PRIMARY)
        self.option_add("*TCombobox*Listbox.selectBackground", C_TABLE_SEL_BG)
        self.option_add("*TCombobox*Listbox.selectForeground", C_TABLE_SEL_FG)
        self.option_add("*TCombobox*Listbox.relief", "flat")
        self.option_add("*TCombobox*Listbox.borderWidth", 0)
        self.option_add("*TCombobox*Listbox.highlightThickness", 1)
        self.option_add("*TCombobox*Listbox.highlightBackground", C_BORDER)
        self.option_add("*TCombobox*Listbox.highlightColor", C_BORDER)
        self.option_add("*TCombobox*Listbox.activestyle", "none")

    # ───────────────────────────────────────────────────────────────
    # UI Layout Construction
    # ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.root_frame = tk.Frame(self, bg=C_BG_WINDOW, padx=24, pady=16)
        self.root_frame.pack(fill="both", expand=True)

        # ── 1. Clean Header (Title + Subtitle only) ──
        self.header_frame = tk.Frame(self.root_frame, bg=C_BG_WINDOW)
        self.header_frame.pack(fill="x", pady=(0, 12))

        self.lbl_title = tk.Label(
            self.header_frame,
            text=tr("app_title"),
            font=("Segoe UI", 18, "bold"),
            bg=C_BG_WINDOW,
            fg=C_TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_subtitle = tk.Label(
            self.header_frame,
            text=tr("app_subtitle"),
            font=("Segoe UI", 10),
            bg=C_BG_WINDOW,
            fg=C_TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_subtitle.pack(anchor="w", pady=(2, 0))

        # ── 2. Search Row: Input Card + Ring Dropdown + Search Button ──
        self.search_row = tk.Frame(self.root_frame, bg=C_BG_WINDOW)
        self.search_row.pack(fill="x", pady=(0, 6))

        # Input Card (soft 1px outline, subtle sky-blue focus ring)
        self.search_input_card = tk.Frame(
            self.search_row,
            bg=C_BG_CARD,
            bd=0,
            relief="flat",
            highlightbackground=C_BORDER,
            highlightcolor=C_BORDER_FOCUS,
            highlightthickness=1,
            padx=10,
            pady=3,
        )
        self.search_input_card.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.entry_query = tk.Entry(
            self.search_input_card,
            font=("Segoe UI", 11),
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            insertbackground=C_TEXT_PRIMARY,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        self.entry_query.pack(fill="both", expand=True, ipady=4)
        self.entry_query.bind("<Return>", lambda e: self._start_search())
        self.entry_query.bind("<KeyRelease>", self._on_query_key_release)
        self.entry_query.bind(
            "<FocusIn>",
            lambda e: self.search_input_card.config(highlightbackground=C_BORDER_FOCUS),
            add="+",
        )
        self.entry_query.bind(
            "<FocusOut>",
            lambda e: self.search_input_card.config(highlightbackground=C_BORDER),
            add="+",
        )
        self.search_input_card.bind("<Button-1>", lambda e: self.entry_query.focus_set())

        # Ring Selector Dropdown
        self.ring_var = tk.StringVar(value=RING_OPTIONS[0])
        self.combo_ring = ttk.Combobox(
            self.search_row,
            textvariable=self.ring_var,
            values=RING_OPTIONS,
            state="readonly",
            width=23,
            font=("Segoe UI", 11),
        )
        self.combo_ring.current(0)
        self.combo_ring.pack(side="left", padx=(0, 10), ipady=4)

        # Search Action Button
        self.btn_search = tk.Button(
            self.search_row,
            text=tr("search"),
            font=("Segoe UI", 10, "bold"),
            bg=C_ACCENT,
            fg="#ffffff",
            activebackground=C_ACCENT_HOVER,
            activeforeground="#ffffff",
            disabledforeground=C_ACCENT_DISABLED_FG,
            relief="flat",
            bd=0,
            padx=20,
            pady=7,
            cursor="hand2",
            command=self._start_search,
        )
        self.btn_search.pack(side="left")

        # ── 3. Unified Single-Line Status Label (Borderless, right below Search Row) ──
        self.lbl_app_meta = SelectableLabel(
            self.root_frame,
            font=("Segoe UI", 10),
            bg=C_BG_WINDOW,
            fg=C_TEXT_SECONDARY,
        )
        self.lbl_app_meta.pack(fill="x", padx=2, pady=(0, 10))

        # ── 4. Toolbar ──
        self.toolbar = tk.Frame(self.root_frame, bg=C_BG_WINDOW)
        self.toolbar.pack(fill="x", pady=(0, 8))

        self.btn_all = tk.Button(
            self.toolbar,
            text=tr("select_all"),
            font=("Segoe UI", 10, "bold"),
            bg=C_BTN_NORMAL_BG,
            fg=C_BTN_NORMAL_FG,
            activebackground=C_BTN_NORMAL_ACTIVE,
            disabledforeground="#94a3b8",
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._select_all,
        )
        self.btn_all.pack(side="left", padx=(0, 6))

        self.btn_none = tk.Button(
            self.toolbar,
            text=tr("deselect_all"),
            font=("Segoe UI", 10, "bold"),
            bg=C_BTN_NORMAL_BG,
            fg=C_BTN_NORMAL_FG,
            activebackground=C_BTN_NORMAL_ACTIVE,
            disabledforeground="#94a3b8",
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._deselect_all,
        )
        self.btn_none.pack(side="left", padx=(0, 14))

        self.lbl_arch = tk.Label(
            self.toolbar,
            text=tr("arch_label"),
            font=("Segoe UI", 11),
            bg=C_BG_WINDOW,
            fg=C_TEXT_SECONDARY,
        )
        self.lbl_arch.pack(side="left", padx=(0, 6))

        self.arch_var = tk.StringVar(value="")
        self.combo_arch = ttk.Combobox(
            self.toolbar,
            textvariable=self.arch_var,
            values=[tr("arch_all")] + ARCH_FILTERS,
            state="readonly",
            width=11,
            font=("Segoe UI", 11),
        )
        self.combo_arch.current(0)
        self.combo_arch.pack(side="left", ipady=3)
        self.combo_arch.bind("<<ComboboxSelected>>", lambda e: self._apply_arch_filter())

        self.btn_download = tk.Button(
            self.toolbar,
            text=tr("download"),
            font=("Segoe UI", 10, "bold"),
            bg=C_ACCENT,
            fg="#ffffff",
            activebackground=C_ACCENT_HOVER,
            activeforeground="#ffffff",
            disabledforeground=C_ACCENT_DISABLED_FG,
            relief="flat",
            bd=0,
            padx=20,
            pady=7,
            cursor="hand2",
            command=self._start_download,
        )
        self.btn_download.pack(side="right")

        # ── 5. Footer (Anchored to bottom FIRST so it never gets clipped on resize) ──
        self.footer = tk.Frame(self.root_frame, bg=C_BG_WINDOW)
        self.footer.pack(side="bottom", fill="x")

        # Right side: Clear list button (packed first to anchor right edge)
        self.btn_clear = tk.Button(
            self.footer,
            text=tr("clear_list"),
            font=("Segoe UI", 9, "bold"),
            bg=C_BTN_NORMAL_BG,
            fg=C_BTN_NORMAL_FG,
            activebackground=C_BTN_NORMAL_ACTIVE,
            disabledforeground="#94a3b8",
            relief="flat",
            bd=0,
            padx=16,
            pady=5,
            cursor="hand2",
            command=self._clear_list,
        )
        self.btn_clear.pack(side="right", padx=(10, 0))

        # Left side: Save folder path + Change... + Open save folder
        self.lbl_save_dir = tk.Label(
            self.footer,
            text=tr("save_dir", path=self.download_dir),
            font=("Segoe UI", 9),
            bg=C_BG_WINDOW,
            fg=C_TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_save_dir.pack(side="left")

        self.btn_change_dir = tk.Button(
            self.footer,
            text=tr("change_folder"),
            font=("Segoe UI", 9, "bold"),
            bg=C_BTN_NORMAL_BG,
            fg=C_BTN_NORMAL_FG,
            activebackground=C_BTN_NORMAL_ACTIVE,
            disabledforeground="#94a3b8",
            relief="flat",
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self._change_dir,
        )
        self.btn_change_dir.pack(side="left", padx=(10, 6))

        self.btn_open = tk.Button(
            self.footer,
            text=tr("open_folder"),
            font=("Segoe UI", 9, "bold"),
            bg=C_BTN_NORMAL_BG,
            fg=C_BTN_NORMAL_FG,
            activebackground=C_BTN_NORMAL_ACTIVE,
            disabledforeground="#94a3b8",
            relief="flat",
            bd=0,
            padx=14,
            pady=5,
            cursor="hand2",
            command=self._open_directory,
        )
        self.btn_open.pack(side="left")

        # ── 6. Table (ttk.Treeview — expands/shrinks vertically between top & bottom) ──
        self.table_frame = tk.Frame(
            self.root_frame,
            bg=C_BG_CARD,
            bd=0,
            relief="flat",
            highlightbackground=C_BORDER,
            highlightcolor=C_BORDER,
            highlightthickness=1,
        )
        self.table_frame.pack(side="top", fill="both", expand=True, pady=(0, 10))

        # Integrated Table Header Bar (Left: App Name • ID • Publisher | Right: Total / Selected Summary)
        self.table_header_bar = tk.Frame(
            self.table_frame,
            bg=C_BG_CARD,
            padx=12,
            pady=8,
        )
        self.table_header_bar.pack(side="top", fill="x")

        self.lbl_summary = tk.Label(
            self.table_header_bar,
            text="",
            font=("Segoe UI", 10, "bold"),
            bg=C_BG_CARD,
            fg=C_TEXT_SECONDARY,
            anchor="e",
        )
        self.lbl_summary.pack(side="right", padx=(12, 0))

        self.lbl_app_name = SelectableLabel(
            self.table_header_bar,
            font=("Segoe UI", 11, "bold"),
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
        )
        self.lbl_app_name.pack(side="left", fill="x", expand=True)

        self.table_header_sep = tk.Frame(
            self.table_frame,
            bg=C_BORDER,
            height=1,
            bd=0,
        )
        self.table_header_sep.pack(side="top", fill="x")

        columns = ("name", "ext", "arch", "size", "status")
        self.tree = ttk.Treeview(
            self.table_frame,
            columns=columns,
            show="tree headings",
            selectmode="browse",
            height=4,
        )
        self.tree.heading(
            "#0",
            image=self._img_unchecked,
            anchor="center",
            command=self._toggle_all_checked,
        )
        self.tree.heading("name", text=tr("col_name"), anchor="w")
        self.tree.heading("ext", text=tr("col_format"), anchor="center")
        self.tree.heading("arch", text=tr("col_arch"), anchor="center")
        self.tree.heading("size", text=tr("col_size"), anchor="e")
        self.tree.heading("status", text=tr("col_status"), anchor="center")

        self.tree.column("#0", width=42, minwidth=42, stretch=False, anchor="center")
        self.tree.column("name", width=430, minwidth=240, stretch=True, anchor="w")
        self.tree.column("ext", width=100, minwidth=80, stretch=False, anchor="center")
        self.tree.column("arch", width=100, minwidth=80, stretch=False, anchor="center")
        self.tree.column("size", width=110, minwidth=90, stretch=False, anchor="e")
        self.tree.column("status", width=140, minwidth=100, stretch=False, anchor="center")

        self.tree.tag_configure("even", background=C_TABLE_BG)
        self.tree.tag_configure("odd", background=C_TABLE_ROW_ALT)

        self.scrollbar = ttk.Scrollbar(
            self.table_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=self._on_tree_yscroll)

        self.tree.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", lambda e: self._sync_status_cells())
        self.tree.bind("<Configure>", lambda e: self.after_idle(self._sync_status_cells))
        self.tree.bind("<Button-1>", self._on_tree_left_click)
        self.tree.bind("<ButtonRelease-1>", lambda e: self.after_idle(self._sync_status_cells))
        self.tree.bind("<space>", self._on_tree_space_toggle)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        self.context_menu = FlatContextMenu(self)
        self.dropdown_menu = FlatContextMenu(self)
        self._bind_flat_combobox(self.combo_ring)
        self._bind_flat_combobox(self.combo_arch)
        self.bind("<Button-1>", self._on_window_click, add="+")

    def _on_window_click(self, event):
        w = event.widget
        if w is self.search_input_card or w is self.entry_query:
            return
        if isinstance(w, (tk.Entry, ttk.Entry)):
            return
        self.focus_set()

    def _bind_flat_combobox(self, combo: ttk.Combobox):
        """Attach the custom FlatContextMenu popup to a readonly ttk.Combobox."""
        combo.configure(cursor="hand2")
        def _on_click(event, cb=combo):
            if str(cb.cget("state")) == "disabled":
                return "break"
            self.context_menu.close()
            self.dropdown_menu.popup_for_combobox(cb)
            return "break"

        def _on_step(delta: int, cb=combo):
            if str(cb.cget("state")) == "disabled":
                return "break"
            vals = list(cb["values"])
            if vals:
                nxt = max(0, min(len(vals) - 1, cb.current() + delta))
                if nxt != cb.current():
                    cb.current(nxt)
                    cb.event_generate("<<ComboboxSelected>>")
            return "break"

        combo.bind("<Button-1>", _on_click)
        combo.bind("<space>", _on_click)
        combo.bind("<Down>", lambda e: _on_step(1))
        combo.bind("<Up>", lambda e: _on_step(-1))

    def _set_accent_btn_state(self, btn: tk.Button, enabled: bool, text: str):
        if enabled:
            btn.config(state="normal", bg=C_ACCENT, cursor="hand2", text=text)
        else:
            btn.config(
                state="disabled",
                bg=C_ACCENT_DISABLED_BG,
                cursor="arrow",
                text=text,
            )

    def _set_secondary_btn_state(self, btn: tk.Button, enabled: bool):
        if enabled:
            btn.config(state="normal", cursor="hand2")
        else:
            btn.config(state="disabled", cursor="arrow")

    # ───────────────────────────────────────────────────────────────
    # Info & Status Notifications
    # ───────────────────────────────────────────────────────────────
    def _render_info(self):
        # 1. Fixed Application Identity in Table Header Bar (self.lbl_app_name)
        if self.product_info:
            info = self.product_info
            parts = [info.title, f"ID: {info.product_id}"]
            if info.publisher:
                parts.append(info.publisher)
            app_header_text = "   •   ".join(parts)
            app_header_fg = C_TEXT_PRIMARY
        elif self._info_state == "connecting":
            app_header_text = tr("info_connecting", query=self._info_text)
            app_header_fg = C_TEXT_SECONDARY
        else:
            app_header_text = tr("info_idle_title")
            app_header_fg = "#64748b"

        self.lbl_app_name.config(text=app_header_text, fg=app_header_fg)

        # 2. Single-line Unified Status Label below Search Row (self.lbl_app_meta)
        if self._info_state == "idle":
            status_line = tr("info_idle_meta")
        elif self._info_state == "connecting":
            status_line = self._progress_text or tr("info_init")
        elif self._info_state == "error":
            status_line = ""
        elif self._info_state == "result" and self.product_info:
            status_line = tr("status_ready_select")
        else:
            status_line = ""

        self.lbl_app_meta.config(text=status_line)
        self._style_meta()
        self._update_summary()

    def _style_meta(self):
        if self._notice:
            kind, text = self._notice
            self.lbl_app_meta.config(text=text)
            color = {
                "info": C_SUMMARY,
                "success": C_NOTICE_SUCCESS,
                "warning": C_NOTICE_WARNING,
                "error": C_NOTICE_ERROR,
            }.get(kind, C_TEXT_PRIMARY)
            self.lbl_app_meta.config(fg=color, font=("Segoe UI", 10, "bold"))
        elif self._info_state == "connecting":
            self.lbl_app_meta.config(fg=C_SUMMARY, font=("Segoe UI", 10, "bold"))
        else:
            self.lbl_app_meta.config(fg=C_TEXT_SECONDARY, font=("Segoe UI", 10))

    def _notify(self, kind: str, text: str, reason: str = ""):
        self._notice = (kind, text)
        self._notice_reason = reason
        self._style_meta()

    def _on_query_key_release(self, event=None):
        if self._notice_reason == "warn_missing" and self.entry_query.get().strip():
            self._notice = None
            self._notice_reason = ""
            self._render_info()

    # ───────────────────────────────────────────────────────────────
    # Search Operation
    # ───────────────────────────────────────────────────────────────
    def _start_search(self):
        query = self.entry_query.get().strip()
        if not query:
            self._notify("warning", tr("warn_missing_content"), reason="warn_missing")
            return
        if self._worker_active:
            return

        ring_idx = max(0, self.combo_ring.current())
        ring = ["Retail", "Release Preview", "Insider Slow", "Insider Fast"][ring_idx]

        self._worker_active = True
        self._set_accent_btn_state(self.btn_search, False, tr("searching"))
        self._set_accent_btn_state(self.btn_download, False, tr("download"))
        self._set_secondary_btn_state(self.btn_clear, False)
        self._set_secondary_btn_state(self.btn_all, False)
        self._set_secondary_btn_state(self.btn_none, False)
        self._notice = None
        self._notice_reason = ""
        self._progress_text = ""
        self.product_info = None
        self._info_state, self._info_text = "connecting", query
        self._render_info()

        self._reset_table_data()

        def worker():
            try:
                def on_status(key, params):
                    msg = tr(key, **params)
                    self._run_on_ui(lambda k=key, p=params, m=msg: self._on_search_step(k, p, m))

                info, packages = self.api.search(query, ring=ring, on_status=on_status)
                self._run_on_ui(lambda: self._on_search_ok(info, packages))
            except StoreError as e:
                err_msg = tr(e.key, **e.params)
                self._run_on_ui(lambda: self._on_search_error(err_msg))
            except Exception as e:
                err_msg = tr("err_network", msg=str(e))
                self._run_on_ui(lambda: self._on_search_error(err_msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_step(self, key: str, params: dict, text: str):
        if self._info_state != "connecting":
            return
        if key == "prog_found":
            pid = self.api._extract_product_id(self._info_text)
            self.product_info = ProductInfo(
                product_id=pid,
                title=params.get("title", "Unknown"),
                publisher=params.get("publisher", ""),
            )
        self._on_progress_text(text)

    def _on_progress_text(self, text: str):
        if self._info_state == "connecting":
            self._progress_text = text
            self._render_info()

    def _on_search_ok(self, info: ProductInfo, packages: list):
        self._worker_active = False
        self._set_accent_btn_state(self.btn_search, True, tr("search"))
        self._set_accent_btn_state(self.btn_download, True, tr("download"))
        self._set_secondary_btn_state(self.btn_clear, True)
        self._set_secondary_btn_state(self.btn_all, True)
        self._set_secondary_btn_state(self.btn_none, True)
        self.product_info = info

        def sort_key(p: PackageFile):
            ext = p.extension
            if ext in ("msixbundle", "appxbundle"):
                return (0, -p.size, p.name)
            if ext in ("msix", "appx"):
                return (1, -p.size, p.name)
            if ext in ("blockmap", "xml", "cab"):
                return (3, 0, p.name)
            return (2, -p.size, p.name)

        self.packages = sorted(packages, key=sort_key)
        self.row_states = [("ready",)] * len(self.packages)
        self.checked_rows.clear()
        self._last_clicked_row = None
        self._context_row = None
        self._info_state = "result"
        self._notice = None
        self._notice_reason = ""
        if not self.packages:
            self._notice = ("warning", tr("no_files_found"))
            self._notice_reason = "no_files"
        self._apply_arch_filter()
        self._render_info()

    def _on_search_error(self, message: str):
        self._worker_active = False
        self._set_accent_btn_state(self.btn_search, True, tr("search"))
        self._set_accent_btn_state(self.btn_download, True, tr("download"))
        self._set_secondary_btn_state(self.btn_clear, True)
        self._set_secondary_btn_state(self.btn_all, True)
        self._set_secondary_btn_state(self.btn_none, True)
        self._info_state, self._info_text = "error", message
        self._notice = ("error", message)
        self._notice_reason = "search_error"
        self._render_info()

    # ───────────────────────────────────────────────────────────────
    # Table & Multi-row Selection
    # ───────────────────────────────────────────────────────────────
    def _on_tree_yscroll(self, first, last):
        self.scrollbar.set(first, last)
        self.after_idle(self._sync_status_cells)

    def _clear_status_cells(self):
        for lbl in self._status_cells.values():
            try:
                lbl.destroy()
            except Exception:
                pass
        self._status_cells.clear()

    def _reset_table_data(self):
        self._clear_status_cells()
        self.tree.delete(*self.tree.get_children())
        self.packages = []
        self.row_states = []
        self.checked_rows.clear()
        self._last_clicked_row = None
        self._context_row = None
        self.tree.heading("#0", image=self._img_unchecked)
        self.lbl_summary.config(text="")

    def _get_row_status_color(self, row: int) -> str:
        if 0 <= row < len(self.row_states):
            st_key = self.row_states[row][0]
            return STATUS_COLOR_MAP.get(st_key, C_TABLE_FG)
        return C_TABLE_FG

    def _get_or_create_status_cell(self, iid: str) -> tk.Label:
        lbl = self._status_cells.get(iid)
        if lbl is not None and lbl.winfo_exists():
            return lbl
        lbl = tk.Label(
            self.tree,
            text="",
            font=("Segoe UI", 10, "bold"),
            anchor="center",
            bd=0,
            padx=0,
            pady=0,
        )

        def _on_click(event, item_id=iid):
            self.tree.focus_set()
            if item_id.isdigit():
                self._context_row = int(item_id)
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
            self._sync_status_cells()
            return "break"

        def _on_rclick(event, item_id=iid):
            event.x = event.x_root - self.tree.winfo_rootx()
            event.y = event.y_root - self.tree.winfo_rooty()
            self._on_tree_right_click(event)

        def _on_wheel(event):
            self.tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        lbl.bind("<Button-1>", _on_click)
        lbl.bind("<Button-3>", _on_rclick)
        lbl.bind("<MouseWheel>", _on_wheel)
        self._status_cells[iid] = lbl
        return lbl

    def _sync_status_cells(self):
        if not self.row_states:
            if self._status_cells:
                self._clear_status_cells()
            return

        selected_set = set(self.tree.selection())
        visible_children = set(self.tree.get_children())

        for iid, lbl in list(self._status_cells.items()):
            if iid not in visible_children:
                lbl.place_forget()

        for iid in visible_children:
            if not iid.isdigit():
                continue
            r = int(iid)
            if r >= len(self.row_states):
                continue
            state = self.row_states[r]
            st_key = state[0]
            text = self.tree.set(iid, "status")
            if st_key == "ready" or not text:
                if iid in self._status_cells:
                    self._status_cells[iid].place_forget()
                continue

            bbox = self.tree.bbox(iid, "status")
            if not bbox or len(bbox) != 4:
                if iid in self._status_cells:
                    self._status_cells[iid].place_forget()
                continue

            x, y, w, h = bbox
            if y < 20 or w <= 4 or h <= 4:
                if iid in self._status_cells:
                    self._status_cells[iid].place_forget()
                continue

            tags = self.tree.item(iid, "tags") or ()
            if iid in selected_set:
                bg = C_TABLE_SEL_BG
            elif "odd" in tags:
                bg = C_TABLE_ROW_ALT
            else:
                bg = C_TABLE_BG

            fg = STATUS_COLOR_MAP.get(st_key, C_TABLE_FG)
            lbl = self._get_or_create_status_cell(iid)
            lbl.config(text=text, fg=fg, bg=bg)
            lbl.place(x=x + 1, y=y + 1, width=w - 2, height=h - 2)

    def _render_row_status(self, row: int):
        if row >= len(self.row_states):
            return
        state = self.row_states[row]
        if state[0] == "downloading":
            text = (
                f"{tr('st_downloading')} {state[1]}%"
                if len(state) > 1
                else tr("st_downloading")
            )
        else:
            status_map = {
                "ready": "st_ready",
                "waiting": "st_waiting",
                "done": "st_done",
                "error": "st_error",
                "cancelled": "st_cancelled",
            }
            text = tr(status_map.get(state[0], "st_ready"))
        if self.tree.exists(str(row)):
            self.tree.set(str(row), "status", text)
            self._sync_status_cells()

    def _get_visible_checked_iids(self) -> list[str]:
        return [
            iid
            for iid in self.tree.get_children()
            if iid.isdigit() and int(iid) in self.checked_rows
        ]

    def _sync_header_checkbox(self):
        vis_iids = [iid for iid in self.tree.get_children() if iid.isdigit()]
        all_checked = bool(vis_iids) and all(int(iid) in self.checked_rows for iid in vis_iids)
        self.tree.heading(
            "#0",
            image=self._img_checked if all_checked else self._img_unchecked,
        )

    def _set_row_checked(self, row: int, checked: bool, update_ui: bool = True):
        if checked:
            self.checked_rows.add(row)
        else:
            self.checked_rows.discard(row)
        iid = str(row)
        if self.tree.exists(iid):
            self.tree.item(iid, image=self._img_checked if checked else self._img_unchecked)
        if update_ui:
            self._sync_header_checkbox()
            self._update_summary()

    def _toggle_row_checked(self, row: int):
        self._set_row_checked(row, row not in self.checked_rows)

    def _toggle_all_checked(self):
        vis_iids = [iid for iid in self.tree.get_children() if iid.isdigit()]
        if not vis_iids:
            return
        if all(int(iid) in self.checked_rows for iid in vis_iids):
            self._deselect_all()
        else:
            self._select_all()

    def _on_tree_left_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region not in ("tree", "cell"):
            return
        iid = self.tree.identify_row(event.y)
        if not iid or not iid.isdigit():
            return
        r = int(iid)
        col = self.tree.identify_column(event.x)

        # Only toggle the checkbox when clicking inside the Tick Box column (#0)
        if region == "tree" or col == "#0":
            new_state = r not in self.checked_rows
            if (event.state & 0x0001) and self._last_clicked_row is not None:
                vis_rows = [int(x) for x in self.tree.get_children() if x.isdigit()]
                if self._last_clicked_row in vis_rows and r in vis_rows:
                    i1 = vis_rows.index(self._last_clicked_row)
                    i2 = vis_rows.index(r)
                    lo, hi = min(i1, i2), max(i1, i2)
                    for vr in vis_rows[lo : hi + 1]:
                        self._set_row_checked(vr, new_state, update_ui=False)
                    self._sync_header_checkbox()
                    self._update_summary()
                else:
                    self._set_row_checked(r, new_state)
            else:
                self._set_row_checked(r, new_state)
            self._last_clicked_row = r

        self._context_row = r
        self.tree.focus_set()
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self._sync_status_cells()
        return "break"

    def _on_tree_space_toggle(self, event=None):
        sel = self.tree.selection()
        if sel and sel[0].isdigit():
            self._toggle_row_checked(int(sel[0]))
            return "break"

    def _update_summary(self):
        checked_vis_iids = self._get_visible_checked_iids()
        all_vis_iids = self.tree.get_children()
        if checked_vis_iids:
            if self._notice_reason == "warn_nosel":
                self._notice = None
                self._notice_reason = ""
                self._render_info()
                return
            total_size = sum(
                self.packages[int(iid)].size
                for iid in checked_vis_iids
                if iid.isdigit() and int(iid) < len(self.packages)
            )
            size_str = format_size(total_size)
            self.lbl_summary.config(
                text=tr(
                    "selected_summary",
                    sel=len(checked_vis_iids),
                    vis=len(all_vis_iids),
                    size=size_str,
                ),
                fg=C_SUMMARY,
            )
        elif self._info_state == "result" and self.packages:
            arch_idx = self.combo_arch.current()
            if arch_idx > 0:
                arch_name = ARCH_FILTERS[arch_idx - 1]
                text = tr(
                    "files_ready_filtered",
                    vis=len(all_vis_iids),
                    n=len(self.packages),
                    arch=arch_name,
                )
            else:
                text = tr("files_ready", n=len(self.packages))
            self.lbl_summary.config(text=text, fg=C_TEXT_SECONDARY)
        else:
            self.lbl_summary.config(text="", fg=C_TEXT_SECONDARY)

    def _select_all(self):
        all_items = self.tree.get_children()
        if all_items:
            for iid in all_items:
                if iid.isdigit():
                    self._set_row_checked(int(iid), True, update_ui=False)
            self._sync_header_checkbox()
            self._update_summary()
            self._sync_status_cells()

    def _deselect_all(self):
        all_items = self.tree.get_children()
        for iid in all_items:
            if iid.isdigit():
                self._set_row_checked(int(iid), False, update_ui=False)
        if self.combo_arch.current() <= 0:
            self.checked_rows.clear()
        self._sync_header_checkbox()
        self._update_summary()
        self._sync_status_cells()

    def _apply_arch_filter(self):
        arch_idx = self.combo_arch.current()
        wanted = None if arch_idx <= 0 else ARCH_FILTERS[arch_idx - 1]

        currently_focused = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        to_refocus = []
        vis_idx = 0

        for r, pkg in enumerate(self.packages):
            if wanted is not None and get_architecture(pkg.name) != wanted:
                continue
            iid = str(r)
            ext_d = f".{pkg.extension}" if pkg.extension else ""
            arch_d = get_architecture(pkg.name) or tr("arch_other")
            row_tag = "even" if vis_idx % 2 == 0 else "odd"
            vis_idx += 1
            chk_img = self._img_checked if r in self.checked_rows else self._img_unchecked
            self.tree.insert(
                "",
                "end",
                iid=iid,
                image=chk_img,
                values=(pkg.name, ext_d, arch_d, pkg.size_str, ""),
                tags=(row_tag,),
            )
            self._render_row_status(r)
            if iid in currently_focused:
                to_refocus.append(iid)

        if to_refocus:
            self.tree.selection_set(to_refocus[:1])
        self._sync_header_checkbox()
        if self._notice_reason in ("warn_nosel", "copied"):
            self._notice = None
            self._notice_reason = ""
        if self._info_state == "result" and not self._notice:
            self._render_info()
        self._update_summary()
        self._sync_status_cells()

    # ───────────────────────────────────────────────────────────────
    # Right-Click Context Menu
    # ───────────────────────────────────────────────────────────────
    def _get_package_save_path(self, row: int) -> str:
        pkg = self.packages[row]
        safe = "".join(c for c in pkg.name if c not in '<>:"/\\|?*')
        return os.path.join(self.download_dir, safe)

    def _can_open_row_file(self, row: Optional[int]) -> bool:
        if row is None or not (0 <= row < len(self.packages)):
            return False
        if row >= len(self.row_states) or self.row_states[row][0] != "done":
            return False
        return os.path.isfile(self._get_package_save_path(row))

    def _can_extract_row_file(self, row: Optional[int]) -> bool:
        if not self._can_open_row_file(row):
            return False
        save_path = self._get_package_save_path(row)
        ext = os.path.splitext(save_path)[1].lower()
        return ext in (".msix", ".appx", ".msixbundle", ".appxbundle", ".zip")

    def _resolve_target_row(self) -> Optional[int]:
        if self._context_row is not None and 0 <= self._context_row < len(self.packages):
            return self._context_row
        sel = self.tree.selection()
        if len(sel) == 1 and sel[0].isdigit() and int(sel[0]) < len(self.packages):
            return int(sel[0])
        return None

    def _download_single_row(self, row: int):
        if 0 <= row < len(self.packages):
            self._set_row_checked(row, True)
            self._start_download()

    def _on_tree_right_click(self, event):
        self.dropdown_menu.close()
        iid = self.tree.identify_row(event.y)
        if iid and iid.isdigit():
            self._context_row = int(iid)
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self._sync_status_cells()
        else:
            self._context_row = self._resolve_target_row()

        checked_vis_iids = self._get_visible_checked_iids()
        if self._context_row is None and not checked_vis_iids and not self._downloading:
            return

        self.context_menu.delete(0, "end")

        if self._downloading:
            self.context_menu.add_command(
                label=tr("ctx_cancel"),
                command=self._cancel_download,
            )
        elif checked_vis_iids:
            self.context_menu.add_command(
                label=tr("ctx_download", n=len(checked_vis_iids)),
                command=self._start_download,
                state="normal" if not self._worker_active else "disabled",
            )
        elif self._context_row is not None:
            r = self._context_row
            self.context_menu.add_command(
                label=tr("ctx_download_one"),
                command=lambda row=r: self._download_single_row(row),
                state="normal" if not self._worker_active else "disabled",
            )

        if self._context_row is not None:
            if self.context_menu.index("end") is not None:
                self.context_menu.add_separator()
            self.context_menu.add_command(
                label=tr("ctx_copy_url"),
                command=self._copy_selected_urls,
                state="normal",
            )
            self.context_menu.add_command(
                label=tr("ctx_copy_name"),
                command=self._copy_selected_names,
                state="normal",
            )

        self.context_menu.add_separator()
        self.context_menu.add_command(
            label=tr("ctx_open_location"),
            command=self._open_selected_file_location,
            state="normal" if self._can_open_row_file(self._context_row) else "disabled",
        )
        self.context_menu.add_command(
            label=tr("ctx_extract"),
            command=self._extract_selected_package,
            state="normal" if (self._can_extract_row_file(self._context_row) and not self._worker_active) else "disabled",
        )
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _extract_selected_package(self):
        row = self._resolve_target_row()
        if not self._can_extract_row_file(row):
            return
        pkg = self.packages[row]
        save_path = os.path.abspath(os.path.normpath(self._get_package_save_path(row)))
        base_name = os.path.splitext(os.path.basename(save_path))[0]
        out_dir = os.path.join(os.path.dirname(save_path), base_name)

        self._notify("info", tr("msg_extracting", name=pkg.name), reason="extracting")

        last_update = [0.0]

        def on_progress(done: int, total: int):
            now = time.monotonic()
            if now - last_update[0] >= 0.1 or done == total:
                last_update[0] = now
                pct = (done * 100 // total) if total > 0 else 0
                msg = f"{tr('msg_extracting', name=pkg.name)} ({pct}%)"
                self._run_on_ui(lambda m=msg: self._notify("info", m, reason="extracting") if self._notice_reason == "extracting" else None)

        def worker():
            try:
                dest = extract_package(save_path, out_dir, progress_callback=on_progress)
                def on_done():
                    folder_name = os.path.basename(dest)
                    success_msg = tr("ok_extract", folder=folder_name, dest=folder_name)
                    self._notify("success", success_msg, reason="extracted")
                    try:
                        os.startfile(dest)
                    except Exception:
                        pass
                self._run_on_ui(on_done)
            except Exception as exc:
                err_msg = str(exc)
                def on_err(m=err_msg):
                    fail_msg = tr("err_extract", msg=m, err=m)
                    self._notify("error", fail_msg, reason="extract_err")
                self._run_on_ui(on_err)

        threading.Thread(target=worker, daemon=True).start()

    def _open_selected_file_location(self):
        row = self._resolve_target_row()
        if not self._can_open_row_file(row):
            return
        file_path = os.path.abspath(
            os.path.normpath(self._get_package_save_path(row))
        )
        try:
            import ctypes
            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32
            ole32.CoInitialize(None)
            shell32.ILCreateFromPathW.argtypes = [ctypes.c_wchar_p]
            shell32.ILCreateFromPathW.restype = ctypes.c_void_p
            shell32.SHOpenFolderAndSelectItems.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.c_ulong,
            ]
            shell32.SHOpenFolderAndSelectItems.restype = ctypes.c_long
            shell32.ILFree.argtypes = [ctypes.c_void_p]

            pidl = shell32.ILCreateFromPathW(file_path)
            if pidl:
                try:
                    hr = shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0)
                    if hr == 0:
                        return
                finally:
                    shell32.ILFree(pidl)
        except Exception:
            pass

        try:
            # Pass raw command string so quotes wrap only the path after /select,
            subprocess.Popen(f'explorer.exe /select,"{file_path}"')
        except Exception:
            pass

    def _copy_selected_urls(self):
        row = self._resolve_target_row()
        if row is None:
            return
        url = self.packages[row].download_url
        if url:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update_idletasks()
            self._notify("success", tr("msg_copied_url"), reason="copied")

    def _copy_selected_names(self):
        row = self._resolve_target_row()
        if row is None:
            return
        name = self.packages[row].name
        if name:
            self.clipboard_clear()
            self.clipboard_append(name)
            self.update_idletasks()
            self._notify("success", tr("msg_copied_name"), reason="copied")

    def _cancel_download(self):
        if self._downloading:
            self._cancel_event.set()
            self._notify("warning", tr("msg_dl_cancelling"), reason="cancelling")

    # ───────────────────────────────────────────────────────────────
    # Download Operation
    # ───────────────────────────────────────────────────────────────
    @staticmethod
    def _format_dl_start_msg(idx: int, total: int, pkg: PackageFile, save_path: str = "") -> str:
        part_path = (save_path + ".part") if save_path else ""
        if part_path and os.path.isfile(part_path):
            try:
                have = os.path.getsize(part_path)
                if have > 0:
                    eff_total = pkg.size if pkg.size > 0 else have
                    pct = (have * 100 // eff_total) if eff_total > 0 else 0
                    return tr(
                        "msg_dl_resuming",
                        idx=idx,
                        total=total,
                        name=pkg.name,
                        pct=pct,
                        dl=format_size(have),
                        size=format_size(eff_total),
                    )
            except Exception:
                pass
        if pkg.size > 0:
            return tr(
                "msg_dl_progress",
                idx=idx,
                total=total,
                name=pkg.name,
                pct=0,
                dl=format_size(0),
                size=format_size(pkg.size),
            )
        return tr("msg_dl_starting", idx=idx, total=total, name=pkg.name)

    def _start_download(self):
        if self._worker_active:
            return
        checked_vis_iids = self._get_visible_checked_iids()
        tasks = []
        for iid in checked_vis_iids:
            if iid.isdigit() and int(iid) < len(self.packages):
                r = int(iid)
                pkg = self.packages[r]
                tasks.append((r, pkg, self._get_package_save_path(r)))

        if not tasks:
            self._notify("warning", tr("warn_nosel_content"), reason="warn_nosel")
            return

        self._worker_active = True
        self._downloading = True
        self._cancel_event.clear()
        self._set_accent_btn_state(self.btn_download, False, tr("downloading"))
        self._set_accent_btn_state(self.btn_search, False, tr("search"))
        self._set_secondary_btn_state(self.btn_clear, False)
        self._set_secondary_btn_state(self.btn_change_dir, False)
        self._set_secondary_btn_state(self.btn_all, False)
        self._set_secondary_btn_state(self.btn_none, False)

        # Immediately mark all selected files as Waiting in queue
        for r, _, _ in tasks:
            self._on_row_state(r, "waiting")

        total_tasks = len(tasks)
        self._notify(
            "info",
            self._format_dl_start_msg(1, total_tasks, tasks[0][1], tasks[0][2]),
            reason="downloading",
        )

        def worker():
            ok = fail = 0
            cancelled = False
            os.makedirs(self.download_dir, exist_ok=True)
            for idx, (row, pkg, save_path) in enumerate(tasks):
                if self._cancel_event.is_set():
                    cancelled = True
                    for rem_r, _, _ in tasks[idx:]:
                        self._run_on_ui(lambda r=rem_r: self._on_row_state(r, "cancelled"))
                    break
                file_idx = idx + 1
                start_msg = self._format_dl_start_msg(file_idx, total_tasks, pkg, save_path)
                self._run_on_ui(
                    lambda r=row, msg=start_msg: (
                        self._on_row_state(r, "downloading"),
                        self._notify("info", msg, reason="downloading")
                        if not self._cancel_event.is_set()
                        else None,
                    )
                )
                last = [-1, 0.0]

                def on_progress(
                    dl,
                    total,
                    r=row,
                    fi=file_idx,
                    p_name=pkg.name,
                    p_size=pkg.size,
                    last=last,
                ):
                    eff_total = total if total > 0 else p_size
                    pct = dl * 100 // eff_total if eff_total > 0 else -1
                    now = time.monotonic()
                    if pct != last[0] or (now - last[1] >= 0.15):
                        last[0] = pct
                        last[1] = now
                        self._run_on_ui(
                            lambda r=r, pc=pct, d=dl, t=eff_total, fi=fi, pn=p_name: self._on_progress(
                                r, pc, d, t, fi, total_tasks, pn
                            )
                        )

                try:
                    self.api.download_file(
                        pkg.download_url,
                        save_path,
                        on_progress=on_progress,
                        cancel_check=self._cancel_event.is_set,
                        expected_size=pkg.size,
                        expected_digest=pkg.digest,
                        expected_digest_sha256=getattr(pkg, "digest_sha256", ""),
                    )
                    self._run_on_ui(lambda r=row: self._on_row_state(r, "done"))
                    ok += 1
                except DownloadCancelledError:
                    cancelled = True
                    for rem_r, _, _ in tasks[idx:]:
                        self._run_on_ui(lambda r=rem_r: self._on_row_state(r, "cancelled"))
                    break
                except Exception:
                    self._run_on_ui(lambda r=row: self._on_row_state(r, "error"))
                    fail += 1

            self._run_on_ui(lambda: self._on_download_done(ok, fail, cancelled))

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(
        self,
        row: int,
        pct: int,
        dl: int = 0,
        total: int = 0,
        file_idx: int = 1,
        total_tasks: int = 1,
        pkg_name: str = "",
    ):
        self.row_states[row] = ("downloading", pct)
        self._render_row_status(row)
        if not self._cancel_event.is_set() and pkg_name:
            if total > 0 and pct >= 0:
                msg = tr(
                    "msg_dl_progress",
                    idx=file_idx,
                    total=total_tasks,
                    name=pkg_name,
                    pct=pct,
                    dl=format_size(dl),
                    size=format_size(total),
                )
            else:
                msg = tr(
                    "msg_dl_starting",
                    idx=file_idx,
                    total=total_tasks,
                    name=pkg_name,
                )
            self._notify("info", msg, reason="downloading")

    def _on_row_state(self, row: int, state: str):
        self.row_states[row] = (state,)
        self._render_row_status(row)

    def _on_download_done(self, ok: int, fail: int, cancelled: bool = False):
        self._worker_active = False
        self._downloading = False
        self._set_accent_btn_state(self.btn_download, True, tr("download"))
        self._set_accent_btn_state(self.btn_search, True, tr("search"))
        self._set_secondary_btn_state(self.btn_clear, True)
        self._set_secondary_btn_state(self.btn_change_dir, True)
        self._set_secondary_btn_state(self.btn_all, True)
        self._set_secondary_btn_state(self.btn_none, True)
        if cancelled:
            self._notify("warning", tr("msg_dl_cancelled", ok=ok), reason="dl_cancelled")
            return
        if fail and ok == 0:
            msg = tr("err_dl_all_failed", fail=fail)
            self._notify("error", msg, reason="dl_error")
        elif fail:
            msg = tr("err_dl_content", ok=ok, fail=fail, folder=self.download_dir).replace("\n", " ")
            self._notify("warning", msg, reason="dl_partial")
        else:
            msg = tr("ok_dl_content", ok=ok, folder=self.download_dir).replace("\n", " ")
            self._notify("success", msg, reason="dl_ok")

    # ───────────────────────────────────────────────────────────────
    # Folder Actions
    # ───────────────────────────────────────────────────────────────
    def _change_dir(self):
        d = filedialog.askdirectory(
            parent=self,
            title=tr("choose_folder_title"),
            initialdir=self.download_dir,
        )
        if d:
            norm_d = os.path.normpath(d)
            self.download_dir = norm_d
            self.cfg["download_dir"] = norm_d
            save_config(self.cfg)
            self.lbl_save_dir.config(text=tr("save_dir", path=norm_d))

    def _open_directory(self):
        folder_path = os.path.abspath(os.path.normpath(self.download_dir))
        os.makedirs(folder_path, exist_ok=True)
        try:
            os.startfile(folder_path)
        except Exception:
            pass

    def _clear_list(self):
        if self._worker_active:
            return
        self.product_info = None
        self._reset_table_data()
        self.combo_arch.current(0)
        self._info_state = "idle"
        self._info_text = ""
        self._progress_text = ""
        self._notice = None
        self._notice_reason = ""
        self._render_info()


# ═══════════════════════════════════════════════════════════════════════════════
def main():
    try:
        import ctypes
        # Windows Per-Monitor High DPI Awareness
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        # AppUserModelID for crisp taskbar icon grouping
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("msstore.downloader.app")
    except Exception:
        pass

    app = MainWindow(start_maximized=True)
    app.mainloop()


if __name__ == "__main__":
    main()
