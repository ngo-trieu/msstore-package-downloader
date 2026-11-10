"""
make_preview.py
───────────────
Generate a high-definition preview screenshot of the application (assets/preview.png)
for GitHub README.md presentation.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
OUT_PATH = ASSETS_DIR / "preview.png"

# Color Palette matching app.py exactly
C_SHADOW_BG = "#0f172a"      # Slate 900 background for GitHub contrast
C_WINDOW_BG = "#eef2f6"      # Soft Slate window bg
C_CARD_BG = "#ffffff"        # White cards
C_BORDER = "#b8c4d4"         # Slate border
C_BORDER_FOCUS = "#0ea5e9"   # Sky 500
C_TEXT_PRIMARY = "#0f172a"   # Slate 900
C_TEXT_SECONDARY = "#334155" # Slate 700
C_TEXT_MUTED = "#64748b"     # Slate 500
C_ACCENT = "#0284c7"         # Sky 600
C_ACCENT_HOVER = "#0369a1"   # Sky 700
C_HEADING_BG = "#e2e8f0"     # Slate 200
C_ROW_ALT = "#f8fafc"        # Row alt
C_ROW_SEL = "#e0f2fe"        # Row selected
C_STATUS_DONE = "#15803d"    # Green 700
C_STATUS_DL = "#0284c7"      # Sky 600
C_STATUS_WAIT = "#475569"    # Slate 600

# Canvas dimensions (Window with generous outer shadow margin)
CANVAS_W, CANVAS_H = 1200, 820
WIN_X, WIN_Y = 50, 40
WIN_W, WIN_H = 1100, 740
CORNER_R = 12

img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (15, 23, 42, 255))
draw = ImageDraw.Draw(img)

# Fonts
font_title = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)
font_bold_lg = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 18)
font_regular = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 14)
font_bold = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 14)
font_semibold = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 14)
font_small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 12)
font_small_bold = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 12)

# 1. Subtle Window Drop Shadow
for i in range(12, 0, -1):
    alpha = int(14 * (1 - i / 12))
    draw.rounded_rectangle(
        [WIN_X - i, WIN_Y - i + 4, WIN_X + WIN_W + i, WIN_Y + WIN_H + i + 4],
        radius=CORNER_R + i,
        fill=(0, 0, 0, alpha),
    )

# 2. Window Body
draw.rounded_rectangle(
    [WIN_X, WIN_Y, WIN_X + WIN_W, WIN_Y + WIN_H],
    radius=CORNER_R,
    fill=C_WINDOW_BG,
    outline=C_BORDER,
    width=1,
)

# 3. Windows Title Bar
TITLE_H = 38
draw.rounded_rectangle(
    [WIN_X, WIN_Y, WIN_X + WIN_W, WIN_Y + TITLE_H],
    radius=CORNER_R,
    fill="#f1f5f9",
)
draw.rectangle(
    [WIN_X, WIN_Y + CORNER_R, WIN_X + WIN_W, WIN_Y + TITLE_H],
    fill="#f1f5f9",
)
draw.line(
    [(WIN_X, WIN_Y + TITLE_H), (WIN_X + WIN_W, WIN_Y + TITLE_H)],
    fill=C_BORDER,
    width=1,
)

# App icon in titlebar
ico_path = ASSETS_DIR / "app.png"
if ico_path.exists():
    ico = Image.open(ico_path).convert("RGBA").resize((20, 20), Image.Resampling.LANCZOS)
    img.paste(ico, (WIN_X + 14, WIN_Y + 9), ico)

draw.text((WIN_X + 42, WIN_Y + 10), "Microsoft Store Package Downloader", font=font_title, fill=C_TEXT_PRIMARY)

# Windows 11 Titlebar Buttons (Right)
BTNS_X = WIN_X + WIN_W - 130
draw.text((BTNS_X + 15, WIN_Y + 7), "—", font=font_regular, fill=C_TEXT_SECONDARY)
draw.text((BTNS_X + 55, WIN_Y + 8), "▢", font=font_regular, fill=C_TEXT_SECONDARY)
draw.text((BTNS_X + 95, WIN_Y + 8), "✕", font=font_regular, fill=C_TEXT_SECONDARY)

# 4. Content Area
CONTENT_X = WIN_X + 18
CONTENT_W = WIN_W - 36
CUR_Y = WIN_Y + TITLE_H + 14

# --- Card 1: Search & Ring Selector Bar ---
CARD1_H = 58
draw.rounded_rectangle(
    [CONTENT_X, CUR_Y, CONTENT_X + CONTENT_W, CUR_Y + CARD1_H],
    radius=8,
    fill=C_CARD_BG,
    outline=C_BORDER,
    width=1,
)

# Search Input
INP_X = CONTENT_X + 14
INP_Y = CUR_Y + 10
INP_W = 540
INP_H = 38
draw.rounded_rectangle(
    [INP_X, INP_Y, INP_X + INP_W, INP_Y + INP_H],
    radius=6,
    fill="#ffffff",
    outline=C_BORDER_FOCUS,
    width=2,
)
draw.text((INP_X + 12, INP_Y + 9), "9N0DX20HK701", font=font_regular, fill=C_TEXT_PRIMARY)

# Ring Combo
RING_X = INP_X + INP_W + 14
RING_W = 160
RING_H = 38
draw.rounded_rectangle(
    [RING_X, INP_Y, RING_X + RING_W, INP_Y + RING_H],
    radius=6,
    fill="#f8fafc",
    outline=C_BORDER,
    width=1,
)
draw.text((RING_X + 14, INP_Y + 9), "Retail", font=font_regular, fill=C_TEXT_PRIMARY)
# Chevron
draw.text((RING_X + RING_W - 22, INP_Y + 10), "▼", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 9), fill=C_TEXT_SECONDARY)

# Search Button
BTN_SEARCH_X = RING_X + RING_W + 14
BTN_SEARCH_W = 130
draw.rounded_rectangle(
    [BTN_SEARCH_X, INP_Y, BTN_SEARCH_X + BTN_SEARCH_W, INP_Y + INP_H],
    radius=6,
    fill=C_ACCENT,
)
draw.text((BTN_SEARCH_X + 38, INP_Y + 9), "Search", font=font_semibold, fill="#ffffff")

# Clear Button
BTN_CLR_X = BTN_SEARCH_X + BTN_SEARCH_W + 10
BTN_CLR_W = 100
draw.rounded_rectangle(
    [BTN_CLR_X, INP_Y, BTN_CLR_X + BTN_CLR_W, INP_Y + INP_H],
    radius=6,
    fill="#ffffff",
    outline=C_BORDER,
    width=1,
)
draw.text((BTN_CLR_X + 22, INP_Y + 9), "Clear list", font=font_regular, fill=C_TEXT_SECONDARY)

CUR_Y += CARD1_H + 12

# --- Card 2: App Metadata & Live Status Notification ---
CARD2_H = 68
draw.rounded_rectangle(
    [CONTENT_X, CUR_Y, CONTENT_X + CONTENT_W, CUR_Y + CARD2_H],
    radius=8,
    fill=C_CARD_BG,
    outline=C_BORDER,
    width=1,
)
# Line 1: App title & Publisher
draw.text((CONTENT_X + 16, CUR_Y + 11), "Windows Terminal", font=font_bold, fill=C_TEXT_PRIMARY)
draw.text((CONTENT_X + 155, CUR_Y + 11), "•   ID: 9N0DX20HK701   •   Microsoft Corporation", font=font_regular, fill=C_TEXT_MUTED)

# Line 2: Live Download Progress
draw.text(
    (CONTENT_X + 16, CUR_Y + 37),
    "Downloading (2/5): Microsoft.WindowsTerminal_1.19.10573.0_x64.msix — 68% (15.9 MB / 23.4 MB)",
    font=font_semibold,
    fill=C_ACCENT_HOVER,
)

CUR_Y += CARD2_H + 12

# --- Card 3: Packages Table ---
TABLE_H = 430
draw.rounded_rectangle(
    [CONTENT_X, CUR_Y, CONTENT_X + CONTENT_W, CUR_Y + TABLE_H],
    radius=8,
    fill=C_CARD_BG,
    outline=C_BORDER,
    width=1,
)

# Table Toolbar (Arch filter & Batch buttons)
BAR_Y = CUR_Y + 10
draw.text((CONTENT_X + 16, BAR_Y + 6), "Architecture:", font=font_regular, fill=C_TEXT_SECONDARY)

# Arch combo
ARCH_X = CONTENT_X + 110
ARCH_W = 110
draw.rounded_rectangle([ARCH_X, BAR_Y, ARCH_X + ARCH_W, BAR_Y + 30], radius=5, fill="#f8fafc", outline=C_BORDER, width=1)
draw.text((ARCH_X + 12, BAR_Y + 6), "All", font=font_regular, fill=C_TEXT_PRIMARY)
draw.text((ARCH_X + ARCH_W - 18, BAR_Y + 9), "▼", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 8), fill=C_TEXT_SECONDARY)

# Select all / Deselect buttons
BTN_ALL_X = ARCH_X + ARCH_W + 12
draw.rounded_rectangle([BTN_ALL_X, BAR_Y, BTN_ALL_X + 90, BAR_Y + 30], radius=5, fill="#ffffff", outline=C_BORDER, width=1)
draw.text((BTN_ALL_X + 16, BAR_Y + 6), "Select all", font=font_regular, fill=C_TEXT_SECONDARY)

BTN_NONE_X = BTN_ALL_X + 98
draw.rounded_rectangle([BTN_NONE_X, BAR_Y, BTN_NONE_X + 80, BAR_Y + 30], radius=5, fill="#ffffff", outline=C_BORDER, width=1)
draw.text((BTN_NONE_X + 16, BAR_Y + 6), "Deselect", font=font_regular, fill=C_TEXT_SECONDARY)

# Merged Summary
SUMMARY_TXT = "Selected: 2/5 files (68.2 MB)"
draw.text((CONTENT_X + CONTENT_W - 220, BAR_Y + 6), SUMMARY_TXT, font=font_semibold, fill=C_TEXT_PRIMARY)

# Table Header
HDR_Y = BAR_Y + 40
HDR_H = 34
draw.rectangle([CONTENT_X + 1, HDR_Y, CONTENT_X + CONTENT_W - 1, HDR_Y + HDR_H], fill=C_HEADING_BG)

COLS = [
    (CONTENT_X + 16, 30, ""),
    (CONTENT_X + 50, 520, "Package name"),
    (CONTENT_X + 580, 110, "Format"),
    (CONTENT_X + 700, 110, "Architecture"),
    (CONTENT_X + 820, 100, "Size"),
    (CONTENT_X + 930, 120, "Status"),
]
for cx, cw, cname in COLS[1:]:
    draw.text((cx, HDR_Y + 8), cname, font=font_semibold, fill=C_TEXT_PRIMARY)

# Header Checkbox
draw.rounded_rectangle([CONTENT_X + 18, HDR_Y + 9, CONTENT_X + 34, HDR_Y + 25], radius=3, fill="#ffffff", outline=C_BORDER, width=1)
draw.line([(CONTENT_X + 21, HDR_Y + 17), (CONTENT_X + 31, HDR_Y + 17)], fill=C_ACCENT, width=2) # Tri-state dash

# Table Rows
ROWS = [
    (True, "Microsoft.WindowsTerminal_1.19.10573.0_8wekyb3d8bbwe.msixbundle", "msixbundle", "Neutral", "44.8 MB", "Done", C_STATUS_DONE),
    (True, "Microsoft.WindowsTerminal_1.19.10573.0_x64.msix", "msix", "x64", "23.4 MB", "68%", C_STATUS_DL),
    (False, "Microsoft.WindowsTerminal_1.19.10573.0_arm64.msix", "msix", "arm64", "22.1 MB", "Waiting", C_STATUS_WAIT),
    (False, "Microsoft.UI.Xaml.2.8_8.2310.30001.0_x64.appx", "appx", "x64", "6.1 MB", "Waiting", C_STATUS_WAIT),
    (False, "Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_x64.appx", "appx", "x64", "17.9 MB", "Waiting", C_STATUS_WAIT),
    (False, "Microsoft.VCLibs.140.00.UWPDesktop_14.0.33728.0_arm64.appx", "appx", "arm64", "16.8 MB", "Ready", C_TEXT_MUTED),
    (False, "Microsoft.WindowsTerminal_1.19.10573.0_x86.msix", "msix", "x86", "20.5 MB", "Ready", C_TEXT_MUTED),
]

ROW_Y = HDR_Y + HDR_H
ROW_H = 38

for idx, (checked, name, fmt, arch, size, status, status_color) in enumerate(ROWS):
    bg_color = C_ROW_SEL if checked else (C_ROW_ALT if idx % 2 == 1 else "#ffffff")
    draw.rectangle([CONTENT_X + 1, ROW_Y, CONTENT_X + CONTENT_W - 1, ROW_Y + ROW_H], fill=bg_color)
    draw.line([(CONTENT_X + 1, ROW_Y + ROW_H), (CONTENT_X + CONTENT_W - 1, ROW_Y + ROW_H)], fill="#edf2f7", width=1)

    # Checkbox
    CB_X = CONTENT_X + 18
    CB_Y = ROW_Y + 11
    draw.rounded_rectangle([CB_X, CB_Y, CB_X + 16, CB_Y + 16], radius=3, fill=C_ACCENT if checked else "#ffffff", outline=C_ACCENT if checked else C_BORDER, width=1)
    if checked:
        # Checkmark
        draw.line([(CB_X + 4, CB_Y + 8), (CB_X + 7, CB_Y + 12), (CB_X + 13, CB_Y + 4)], fill="#ffffff", width=2)

    # Texts
    draw.text((COLS[1][0], ROW_Y + 10), name, font=font_regular, fill=C_TEXT_PRIMARY)
    draw.text((COLS[2][0], ROW_Y + 10), fmt, font=font_small, fill=C_TEXT_SECONDARY)
    draw.text((COLS[3][0], ROW_Y + 10), arch, font=font_small, fill=C_TEXT_SECONDARY)
    draw.text((COLS[4][0], ROW_Y + 10), size, font=font_regular, fill=C_TEXT_PRIMARY)

    # Status Pill Badge
    STATUS_X = COLS[5][0]
    STATUS_Y = ROW_Y + 8
    draw.rounded_rectangle([STATUS_X, STATUS_Y, STATUS_X + 90, STATUS_Y + 22], radius=11, fill="#ffffff" if checked else "#f1f5f9", outline=status_color, width=1)
    draw.text((STATUS_X + 18, STATUS_Y + 3), status, font=font_small_bold, fill=status_color)

    ROW_Y += ROW_H

CUR_Y += TABLE_H + 12

# --- Card 4: Bottom Save Folder & Download Action ---
CARD4_H = 54
draw.rounded_rectangle(
    [CONTENT_X, CUR_Y, CONTENT_X + CONTENT_W, CUR_Y + CARD4_H],
    radius=8,
    fill=C_CARD_BG,
    outline=C_BORDER,
    width=1,
)

DIR_Y = CUR_Y + 10
draw.text((CONTENT_X + 16, DIR_Y + 7), "Save folder:  C:\\Users\\Trieu Ngo\\Downloads\\MSStore", font=font_regular, fill=C_TEXT_PRIMARY)

BTN_CHG_X = CONTENT_X + 440
draw.rounded_rectangle([BTN_CHG_X, DIR_Y, BTN_CHG_X + 95, DIR_Y + 32], radius=5, fill="#ffffff", outline=C_BORDER, width=1)
draw.text((BTN_CHG_X + 16, DIR_Y + 7), "Change...", font=font_regular, fill=C_TEXT_SECONDARY)

BTN_OPN_X = BTN_CHG_X + 105
draw.rounded_rectangle([BTN_OPN_X, DIR_Y, BTN_OPN_X + 140, DIR_Y + 32], radius=5, fill="#ffffff", outline=C_BORDER, width=1)
draw.text((BTN_OPN_X + 16, DIR_Y + 7), "Open save folder", font=font_regular, fill=C_TEXT_SECONDARY)

BTN_DL_X = CONTENT_X + CONTENT_W - 170
draw.rounded_rectangle([BTN_DL_X, DIR_Y, BTN_DL_X + 155, DIR_Y + 34], radius=6, fill=C_ACCENT)
draw.text((BTN_DL_X + 18, DIR_Y + 8), "Download selected", font=font_semibold, fill="#ffffff")

# Save PNG
img.save(OUT_PATH, "PNG", optimize=True)
print(f"Preview image created successfully at {OUT_PATH} ({CANVAS_W}x{CANVAS_H})")
