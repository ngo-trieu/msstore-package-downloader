"""
_test.py
────────
Automated test suite for the Minimal Clean Tkinter MS Store Downloader.
"""

import base64
import hashlib
import os
import shutil
import time
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

# Use a test config file in TEMP
import i18n
i18n.CONFIG_PATH = Path(os.environ.get("TEMP", ".")) / "msstore_test_cfg.json"
if i18n.CONFIG_PATH.exists():
    i18n.CONFIG_PATH.unlink()

import app
from ms_store_api import PackageFile, ProductInfo, StoreError, extract_package
from soap_templates import (
    build_get_cookie_soap,
    build_get_file_url_soap,
    build_sync_updates_soap,
)

# Initialize MainWindow in hidden mode (withdraw)
w = app.MainWindow()
w.withdraw()

print("[1] Verifying window icon...")
assert w.iconbitmap is not None
print("    Window icon: OK")

print("[2] Verifying buttons (text-only, no icons, clean disabled state)...")
btns = [
    w.btn_search,
    w.btn_all,
    w.btn_none,
    w.btn_download,
    w.btn_change_dir,
    w.btn_open,
    w.btn_clear,
]
for b in btns:
    text = b.cget("text")
    image = b.cget("image")
    assert not image, f"Button {text} has an icon!"
for b in (w.btn_search, w.btn_download):
    assert b.cget("disabledforeground") == app.C_ACCENT_DISABLED_FG
    orig_text = b.cget("text")
    w._set_accent_btn_state(b, False, "Running...")
    assert b.cget("state") == "disabled" and b.cget("bg") == app.C_ACCENT_DISABLED_BG
    w._set_accent_btn_state(b, True, orig_text)
    assert b.cget("state") == "normal" and b.cget("bg") == app.C_ACCENT
print(f"    {len(btns)} buttons verified: clean text-only & faded disabled style")

print("[3] Verifying table rendering and empty default selection...")
pk = [
    PackageFile(name="App_1.0_x64__abc.msixbundle", size=50_000_000),
    PackageFile(name="Microsoft.VCLibs.140_14.0_x86__abc.appx", size=1_000_000),
    PackageFile(name="Microsoft.VCLibs.140_14.0_x64__abc.appx", size=1_200_000),
    PackageFile(name="Abm_xxx.cab", size=70_000),
]
for p in pk:
    p.download_url = "http://example.com/download"

w.product_info = ProductInfo(
    product_id="TESTID", title="Demo App", publisher="Test Publisher", wu_category_id="guid"
)
w._on_search_ok(w.product_info, pk)

# Verify default: nothing ticked -> lbl_summary in table_header_bar shows total files ("4 files ready")
assert len(w.checked_rows) == 0
assert w.lbl_summary.cget("text") == "4 files ready"
assert len(w.tree.get_children()) == 4
print("    Default selection is empty (0/4) & merged summary shows '4 files ready': OK")

# Verify Table Header Bar has the 3 pieces of information: Name, ID, Publisher
info_line1 = w.lbl_app_name.cget("text")
assert "Demo App" in info_line1
assert "TESTID" in info_line1
assert "Test Publisher" in info_line1

# Verify 1-line status label does NOT duplicate '4 files ready'
assert w.lbl_app_meta.cget("text") == i18n.tr("status_ready_select")
assert "4 files ready" not in w.lbl_app_meta.cget("text")

# Verify selectable text capability & Option A layout (borderless status + integrated table header bar)
assert isinstance(w.lbl_app_name, app.SelectableLabel)
assert isinstance(w.lbl_app_meta, app.SelectableLabel)
assert w.lbl_app_meta.cget("bg") == app.C_BG_WINDOW
assert w.lbl_app_name.master == w.table_header_bar
assert w.lbl_summary.master == w.table_header_bar
for card in (w.search_input_card, w.table_frame):
    assert int(card.cget("bd")) == 0 and card.cget("relief") == "flat"
    assert int(card.cget("highlightthickness")) == 1
    assert card.cget("highlightbackground") == app.C_BORDER
assert not hasattr(w, "progress_frame") and not hasattr(w, "progress")
assert w.search_input_card.cget("highlightcolor") == app.C_BORDER_FOCUS
print("    Table Header Bar (Name, ID, Publisher + Merged Summary) & Non-duplicated Status: OK")

print("[4] Verifying CPU architecture filter...")
x64_idx = 1 + app.ARCH_FILTERS.index("x64")
w.combo_arch.current(x64_idx)
w._apply_arch_filter()
vis = list(w.tree.get_children())
assert vis == ["0", "1"], f"Expected visible rows ['0', '1'], got {vis}"
assert "2 of 4 files ready (Filtered by x64)" in w.lbl_summary.cget("text")
print("    Filter x64 shows 2 packages & updates merged summary count: OK")

# Test auto-clearing 'warn_nosel' when user selects rows
w._notify("warning", i18n.tr("warn_nosel_content"), reason="warn_nosel")
assert "select at least one" in w.lbl_app_meta.cget("text").lower()

# Select all visible -> should auto-clear warn_nosel and switch merged summary to 'Selected: 2/2...'
w._select_all()
assert len(w._get_visible_checked_iids()) == 2
assert "2/2" in w.lbl_summary.cget("text")
assert w._notice is None and w.lbl_app_meta.cget("text") == i18n.tr("status_ready_select")
print("    Select all visible rows & auto-clear stale warning: OK")

# Deselect -> merged summary returns to '2 of 4 files ready (Filtered by x64)'
w._deselect_all()
assert len(w._get_visible_checked_iids()) == 0
assert "2 of 4 files ready (Filtered by x64)" in w.lbl_summary.cget("text")
print("    Deselect all rows restores total count: OK")

# Reset filter
w.combo_arch.current(0)
w._apply_arch_filter()
assert len(w.tree.get_children()) == 4

print("[5] Verifying download progress and row states...")
w._on_row_state(0, "waiting")
assert w.tree.set("0", "status") == "Waiting"
assert w._get_row_status_color(0) == app.C_STATUS_WAITING
w._on_progress(
    0,
    50,
    dl=25 * 1024 * 1024,
    total=50 * 1024 * 1024,
    file_idx=1,
    total_tasks=2,
    pkg_name="App_1.0_x64__abc.msixbundle",
)
assert "50%" in w.tree.set("0", "status")
assert w._get_row_status_color(0) == app.C_STATUS_DOWNLOADING
meta_txt = w.lbl_app_meta.cget("text")
assert "Downloading (1/2): App_1.0_x64__abc.msixbundle" in meta_txt
assert "50%" in meta_txt and "(25.0 MB / 50.0 MB)" in meta_txt
assert w.lbl_app_meta.cget("fg") == app.C_SUMMARY
w._on_row_state(0, "done")
assert w.tree.set("0", "status") == "Done"
assert w._get_row_status_color(0) == app.C_STATUS_DONE
w._on_row_state(0, "error")
assert w.tree.set("0", "status") == "Error"
assert w._get_row_status_color(0) == app.C_STATUS_ERROR
w._on_row_state(0, "cancelled")
assert w.tree.set("0", "status") == "Cancelled"
assert w._get_row_status_color(0) == app.C_STATUS_CANCELLED
w._on_row_state(0, "done")
w._on_download_done(0, 2, cancelled=False)
assert w.lbl_app_meta.cget("fg") == app.C_NOTICE_ERROR
w._on_download_done(1, 1, cancelled=False)
assert w.lbl_app_meta.cget("fg") == app.C_NOTICE_WARNING
w._on_download_done(2, 0, cancelled=False)
assert w.lbl_app_meta.cget("fg") == app.C_NOTICE_SUCCESS
print("    Progress, live Line 2 download status & done states (Error/Warning/Success): OK")

print("[6] Verifying fixed 2-line notice card...")
w._notify("warning", "Please select at least one file.")
assert w.lbl_app_meta.cget("text") == "Please select at least one file."
w._notify("success", "Download complete!")
assert w.lbl_app_meta.cget("text") == "Download complete!"
print("    Fixed notice card: OK")

print("[7] Verifying bottom save folder change & persistence...")
test_dir = str(Path(os.environ.get("TEMP", ".")) / "CustomSaveDir")
w.download_dir = test_dir
w.cfg["download_dir"] = test_dir
i18n.save_config(w.cfg)
loaded_cfg = i18n.load_config()
assert loaded_cfg.get("download_dir") == test_dir
print("    Bottom folder persistence: OK")

print("[8] Verifying resize & minsize layout anchoring...")
w.update()
init_foot_h = w.footer.winfo_height()
mw, mh = w.minsize()
w.geometry(f"{mw}x{mh}")
w.update()
assert w.footer.winfo_height() == init_foot_h and init_foot_h > 0
assert w.tree.winfo_height() >= 160
for st in [("readonly",), ("focus", "readonly"), ("pressed", "focus", "readonly")]:
    fg = w.tk.call("ttk::style", "lookup", "TCombobox", "-foreground", st)
    bg = w.tk.call("ttk::style", "lookup", "TCombobox", "-fieldbackground", st)
    assert fg != bg, f"Combobox text invisible in state {st}: fg={fg}, bg={bg}"
combo_layout_str = str(app.ttk.Style(w).layout("TCombobox"))
assert "FlatCombo.border" in combo_layout_str and "FlatCombo.downarrow" in combo_layout_str
# Pixel-level check: 4-sided border + visible chevron in combo_ring
import ctypes
w.deiconify(); w.update()
for cb in (w.combo_ring, w.combo_arch):
    dc = ctypes.windll.user32.GetDC(cb.winfo_id())
    cw, ch = cb.winfo_width(), cb.winfo_height()
    def _px(x, y):
        c = ctypes.windll.gdi32.GetPixel(dc, x, y)
        return f"#{c & 0xff:02x}{(c >> 8) & 0xff:02x}{(c >> 16) & 0xff:02x}"
    for edge in (_px(0, ch // 2), _px(cw - 1, ch // 2), _px(cw // 2, 0), _px(cw // 2, ch - 1)):
        assert edge in (app.C_BORDER, "#94a3b8", app.C_BORDER_FOCUS), f"Missing border pixel: {edge}"
    right_colors = {_px(x, y) for y in range(ch) for x in range(cw - 28, cw)}
    assert right_colors & {"#475569", "#1e293b", app.C_ACCENT}, f"Chevron not visible: {right_colors}"
    ctypes.windll.user32.ReleaseDC(cb.winfo_id(), dc)

# Focus & background unfocus behavior (while window is mapped)
w.entry_query.focus_set(); w.update()
assert w.focus_get() == w.entry_query
assert w.search_input_card.cget("highlightbackground") == app.C_BORDER_FOCUS
# Outside background click releases focus and restores slate border
w.root_frame.event_generate("<Button-1>"); w.update()
assert w.focus_get() == w
assert w.search_input_card.cget("highlightbackground") == app.C_BORDER
# Re-clicking search card restores focus and blue border ring
w.search_input_card.event_generate("<Button-1>"); w.update()
assert w.focus_get() == w.entry_query
assert w.search_input_card.cget("highlightbackground") == app.C_BORDER_FOCUS

# Explicit state model: opening popup sets 'pressed' (accent), selecting retains focus
w.dropdown_menu.popup_for_combobox(w.combo_ring); w.update()
assert "pressed" in w.combo_ring.state()
item_lbl = w.dropdown_menu._items[1][1]
item_lbl.event_generate("<Button-1>"); item_lbl.event_generate("<ButtonRelease-1>")
w.update()
import time; time.sleep(0.02); w.update()
assert not w.dropdown_menu.winfo_ismapped()
assert "focus" in w.combo_ring.state()
assert w.focus_get() == w.combo_ring

w.withdraw()

w.dropdown_menu.popup_for_combobox(w.combo_arch)
assert "pressed" in w.combo_arch.state()
w.dropdown_menu.close()
assert "pressed" not in w.combo_arch.state()
print("    Resize & minsize anchoring + Combobox 4-sided border & focus contrast: OK")

print("[9] Verifying right-click context menu actions, waiting queue & open file location...")
assert isinstance(w.context_menu, app.FlatContextMenu)
assert isinstance(w.dropdown_menu, app.FlatContextMenu)
for menu in (w.context_menu, w.dropdown_menu):
    assert menu.cget("highlightbackground") == app.C_BORDER
    assert int(menu.cget("highlightthickness")) == 1
    assert int(menu.cget("bd")) == 0
w.dropdown_menu.popup_for_combobox(w.combo_ring)
assert w.dropdown_menu.index("end") == len(app.RING_OPTIONS) - 1
w.dropdown_menu.close()
w.dropdown_menu.popup_for_combobox(w.combo_arch)
assert w.dropdown_menu.index("end") == len(app.ARCH_FILTERS)
w.dropdown_menu.close()
w.context_menu.delete(0, "end")
w.context_menu.add_command(label="Download", state="normal")
w.context_menu.add_separator()
w.context_menu.add_command(label="Open file location", state="disabled")
assert w.context_menu.index("end") == 2
w.context_menu.close()
# Verify clicking on row body only focuses row without toggling tick, whereas clicking #0 toggles tick
assert str(w.tree.column("#0", "anchor")) == "center"
assert w._img_unchecked.width() == 17 and w._img_checked.width() == 17
w._deselect_all()
assert len(w.checked_rows) == 0
row0_bbox = w.tree.bbox("0", "name")
assert row0_bbox, "Expected row 0 bbox to be visible"
ry = row0_bbox[1] + row0_bbox[3] // 2
# Click on 'name' column (x = row0_bbox[0] + 10) -> should NOT check row 0
ev_body = type("Ev", (), {"x": row0_bbox[0] + 10, "y": ry, "state": 0})()
w._on_tree_left_click(ev_body)
assert 0 not in w.checked_rows and w.tree.selection() == ("0",)
# Click on '#0' checkbox column (x = 15) -> SHOULD check row 0
ev_chk = type("Ev", (), {"x": 15, "y": ry, "state": 0})()
w._on_tree_left_click(ev_chk)
assert 0 in w.checked_rows
# Click on 'name' column again -> row 0 remains checked!
w._on_tree_left_click(ev_body)
assert 0 in w.checked_rows

# Verify decoupled Tick Box + Right-Click context row behavior:
# Even when multiple rows are ticked (0 & 1), right-clicking row 2 copies row 2's URL/name without losing ticked rows!
w._set_row_checked(0, True)
w._set_row_checked(1, True)
assert w.checked_rows == {0, 1}
w._context_row = 2
w._copy_selected_urls()
assert w.clipboard_get() == "http://example.com/download"
w._copy_selected_names()
assert w.clipboard_get() == "Microsoft.VCLibs.140_14.0_x86__abc.appx"
assert w.checked_rows == {0, 1}  # Ticked rows preserved!

w._context_row = 0
w._copy_selected_names()
assert w.clipboard_get() == "App_1.0_x64__abc.msixbundle"
w._on_row_state(0, "waiting")
assert w.tree.set("0", "status") == "Waiting"
assert not w._can_open_row_file(0)
w._on_row_state(0, "cancelled")
assert w.tree.set("0", "status") == "Cancelled"

# Test Open file location enable/disable logic
os.makedirs(w.download_dir, exist_ok=True)
dummy_file = w._get_package_save_path(0)
Path(dummy_file).write_bytes(b"test")
w._on_row_state(0, "done")
assert w._can_open_row_file(0) is True
assert w._can_open_row_file(None) is False
assert w._can_open_row_file(1) is False
try:
    os.remove(dummy_file)
except OSError:
    pass

w._downloading = True
w._cancel_download()
assert w._cancel_event.is_set()
w._on_download_done(1, 0, cancelled=True)
assert not w._downloading and "cancelled" in w.lbl_app_meta.cget("text").lower()

w._clear_list()
assert len(w.tree.get_children()) == 0
assert len(w.packages) == 0
assert w.lbl_summary.cget("text") == ""
assert w._info_state == "idle" and w._notice is None
assert i18n.tr("info_idle_title") in w.lbl_app_name.cget("text")
print("    Context menu copy, waiting queue, open file location, cancel & clear list: OK")

print("[10] Verifying API retry adapters, dynamic SOAP builders, safe ProductID regex & atomic download...")

# 10a. HTTP & HTTPS retry adapters
api = w.api
https_adapter = api.session.get_adapter("https://fe3.delivery.mp.microsoft.com")
http_adapter = api.session.get_adapter("http://tlu.dl.delivery.mp.microsoft.com")
assert https_adapter.max_retries.total == 3
assert http_adapter.max_retries.total == 3
assert 503 in http_adapter.max_retries.status_forcelist

# 10b. Dynamic SOAP envelopes
s1 = build_get_cookie_soap()
s2 = build_get_cookie_soap()
assert "{msg_id}" not in s1 and "{created}" not in s1 and "{expires}" not in s1
assert s1 != s2  # Unique UUID per call
su = build_sync_updates_soap("COOKIE_TOKEN", "00000000-0000-0000-0000-000000000000", "<User />", "Retail")
assert "COOKIE_TOKEN" in su and "{cookie_expires}" not in su
fu = build_get_file_url_soap("11111111-1111-1111-1111-111111111111", "1", "<User />", "Retail")
assert "11111111-1111-1111-1111-111111111111" in fu and "{msg_id}" not in fu

# 10c. Safe _extract_product_id regex (must not match 12-char words like 'applications')
assert api._extract_product_id("https://apps.microsoft.com/applications/9WZDNCRFJBMP") == "9WZDNCRFJBMP"
assert api._extract_product_id("https://apps.microsoft.com/store/detail/9NCBCSZSJRSB?hl=en-us") == "9NCBCSZSJRSB"
assert api._extract_product_id("  9wzdncrfjbmp ") == "9WZDNCRFJBMP"

# 10d. Atomic .part download + SHA-1 digest verification + truncation check
payload = b"MSStoreDownloader_Atomic_Integrity_Test_Payload" * 100
valid_b64_sha1 = base64.b64encode(hashlib.sha1(payload).digest()).decode("ascii")
dl_target = os.path.join(w.download_dir, "atomic_test.msix")
if os.path.exists(dl_target):
    os.remove(dl_target)

class _MockResp:
    def __init__(self, data: bytes, content_length: int, status_code: int = 200):
        self._data = data
        self.headers = {"content-length": str(content_length)}
        self.status_code = status_code
        self.text = data.decode("utf-8", errors="replace")
        self.content = data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")
    def iter_content(self, chunk_size=65536):
        yield self._data
    def close(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

orig_get = api.session.get
try:
    # Valid download -> writes .part then atomically replaces dl_target
    api.session.get = MagicMock(return_value=_MockResp(payload, len(payload)))
    api.download_file(
        "http://example.com/file.msix",
        dl_target,
        expected_size=len(payload),
        expected_digest=valid_b64_sha1,
    )
    assert os.path.isfile(dl_target)
    assert not os.path.exists(dl_target + ".part")
    assert Path(dl_target).read_bytes() == payload

    # Corrupted SHA-1 -> raises IOError, cleans up .part, keeps existing valid dl_target intact!
    api.session.get = MagicMock(return_value=_MockResp(payload, len(payload)))
    corrupted_caught = False
    try:
        api.download_file(
            "http://example.com/file.msix",
            dl_target,
            expected_size=len(payload),
            expected_digest="AAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        )
    except IOError:
        corrupted_caught = True
    assert corrupted_caught, "Expected IOError on SHA-1 mismatch"
    assert not os.path.exists(dl_target + ".part")
    assert os.path.isfile(dl_target) and Path(dl_target).read_bytes() == payload

    # Truncated stream -> raises IOError, preserves .part for resume!
    api.session.get = MagicMock(return_value=_MockResp(payload[:50], len(payload)))
    truncated_caught = False
    try:
        api.download_file(
            "http://example.com/file.msix",
            dl_target,
            expected_size=len(payload),
            expected_digest=valid_b64_sha1,
        )
    except IOError:
        truncated_caught = True
    assert truncated_caught, "Expected IOError on truncated stream"
    assert os.path.exists(dl_target + ".part") and os.path.getsize(dl_target + ".part") == 50
    os.remove(dl_target + ".part")
finally:
    api.session.get = orig_get
    if os.path.exists(dl_target):
        os.remove(dl_target)

print("    API retry adapters, dynamic SOAP, ProductID regex & atomic SHA-1 download: OK")

# ═══════════════════════════════════════════════════════════════════════════════
# [11] Verifying HTTP Range Resume download & cancellation preservation...
# ═══════════════════════════════════════════════════════════════════════════════
print("[11] Verifying HTTP Range Resume download & cancellation preservation...")
full_payload = b"MSStore_Range_Resume_Feature_Payload_Chunk_" * 200
total_len = len(full_payload)
valid_sha1 = base64.b64encode(hashlib.sha1(full_payload).digest()).decode("ascii")
valid_sha256 = base64.b64encode(hashlib.sha256(full_payload).digest()).decode("ascii")

resume_target = os.path.join(w.download_dir, "resume_test.msix")
part_file = resume_target + ".part"
for f in (resume_target, part_file):
    if os.path.exists(f):
        os.remove(f)

# Step A: Simulate partial download interrupted after 3000 bytes
split_point = 3000
with open(part_file, "wb") as pf:
    pf.write(full_payload[:split_point])
assert os.path.getsize(part_file) == split_point

# Step B: Call download_file with Range resume
range_received = []

def mock_range_get(url, headers=None, stream=True, timeout=None):
    assert headers is not None, "Headers missing from request"
    req_range = headers.get("Range", "")
    range_received.append(req_range)
    assert req_range == f"bytes={split_point}-", f"Unexpected Range header: {req_range}"
    remaining_data = full_payload[split_point:]
    return _MockResp(remaining_data, len(remaining_data), status_code=206)

orig_get = api.session.get
try:
    api.session.get = mock_range_get
    progress_records = []
    def on_prog(dl, tot):
        progress_records.append((dl, tot))

    api.download_file(
        "http://example.com/package.msix",
        resume_target,
        on_progress=on_prog,
        expected_size=total_len,
        expected_digest=valid_sha1,
        expected_digest_sha256=valid_sha256,
    )

    assert len(range_received) == 1
    # Verify .part file was atomically renamed to resume_target
    assert not os.path.exists(part_file)
    assert os.path.isfile(resume_target)
    assert Path(resume_target).read_bytes() == full_payload
    # Verify on_progress received initial bytes and final total
    assert progress_records[0][0] == split_point
    assert progress_records[-1][0] == total_len

    # Step C: Verify cancellation keeps .part intact
    if os.path.exists(resume_target):
        os.remove(resume_target)
    with open(part_file, "wb") as pf:
        pf.write(full_payload[:1000])

    cancel_caught = False
    try:
        api.download_file(
            "http://example.com/package.msix",
            resume_target,
            cancel_check=lambda: True,
            expected_size=total_len,
        )
    except app.DownloadCancelledError:
        cancel_caught = True
    assert cancel_caught, "Expected DownloadCancelledError"
    # .part file MUST be kept intact for future resume!
    assert os.path.exists(part_file) and os.path.getsize(part_file) == 1000

    # Step D: Test 416 Range Not Satisfiable (when .part is already full size)
    with open(part_file, "wb") as pf:
        pf.write(full_payload)
    def mock_416_get(url, headers=None, stream=True, timeout=None):
        return _MockResp(b"", 0, status_code=416)
    api.session.get = mock_416_get
    api.download_file(
        "http://example.com/package.msix",
        resume_target,
        expected_size=total_len,
        expected_digest=valid_sha1,
    )
    assert not os.path.exists(part_file)
    assert os.path.isfile(resume_target)
    assert Path(resume_target).read_bytes() == full_payload

finally:
    api.session.get = orig_get
    for f in (resume_target, part_file):
        if os.path.exists(f):
            os.remove(f)

print("    HTTP Range resume, 206 Partial, 416 completion & cancellation preservation: OK")

# ═══════════════════════════════════════════════════════════════════════════════
# [12] Verifying Dual SHA-256 and SHA-1 verification & XML parser...
# ═══════════════════════════════════════════════════════════════════════════════
print("[12] Verifying Dual SHA-256 and SHA-1 verification & XML parser...")
test_bytes = b"MicrosoftStorePackage_Dual_Digest_Verification_Payload" * 50
sha1_b64 = base64.b64encode(hashlib.sha1(test_bytes).digest()).decode("ascii")
sha1_hex = hashlib.sha1(test_bytes).hexdigest()
sha256_b64 = base64.b64encode(hashlib.sha256(test_bytes).digest()).decode("ascii")
sha256_hex = hashlib.sha256(test_bytes).hexdigest()

test_file = os.path.join(w.download_dir, "digest_test.bin")
Path(test_file).write_bytes(test_bytes)
try:
    # 1. SHA-256 (Base64) matches
    assert api._verify_file_digest(test_file, expected_digest="", expected_digest_sha256=sha256_b64)
    # 2. SHA-256 (Hex) matches
    assert api._verify_file_digest(test_file, expected_digest="", expected_digest_sha256=sha256_hex)
    # 3. Both match
    assert api._verify_file_digest(test_file, expected_digest=sha1_b64, expected_digest_sha256=sha256_b64)
    # 4. SHA-256 takes precedence: wrong SHA-1 is ignored if SHA-256 is valid
    assert api._verify_file_digest(test_file, expected_digest="WRONG_SHA1", expected_digest_sha256=sha256_b64)
    # 5. Wrong SHA-256 fails even if SHA-1 is correct
    assert not api._verify_file_digest(test_file, expected_digest=sha1_b64, expected_digest_sha256="WRONG_SHA256")
    # 6. Fallback to SHA-1 if SHA-256 is absent
    assert api._verify_file_digest(test_file, expected_digest=sha1_b64, expected_digest_sha256="")
    assert api._verify_file_digest(test_file, expected_digest=sha1_hex, expected_digest_sha256="")
    # 7. Wrong SHA-1 fails when SHA-256 is absent
    assert not api._verify_file_digest(test_file, expected_digest="WRONG_SHA1", expected_digest_sha256="")
    # 8. Both empty passes
    assert api._verify_file_digest(test_file, expected_digest="", expected_digest_sha256="")

    # 9. Verify XML parsing of <AdditionalDigest> in _sync_updates
    sample_xml = f"""<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">
      <Body>
        <SyncUpdatesResponse xmlns="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService">
          <SyncUpdatesResult>
            <NewUpdates>
              <UpdateInfo>
                <ID>10001</ID>
                <Xml>&lt;UpdateIdentity UpdateID="11111111-2222-3333-4444-555555555555" RevisionNumber="1"/&gt;</Xml>
              </UpdateInfo>
            </NewUpdates>
            <Updates>
              <Update>
                <ID>10001</ID>
                <Files>
                  <File Digest="{sha1_b64}" FileName="TestApp_1.0.0.0_x64.msix" Size="54321">
                    <AdditionalDigest Algorithm="SHA256">{sha256_b64}</AdditionalDigest>
                  </File>
                </Files>
              </Update>
            </Updates>
          </SyncUpdatesResult>
        </SyncUpdatesResponse>
      </Body>
    </Envelope>"""
    mock_soap_resp = _MockResp(sample_xml.encode("utf-8"), len(sample_xml))
    orig_post = api.session.post
    try:
        api.session.post = MagicMock(return_value=mock_soap_resp)
        pkgs = api._sync_updates("TEST_COOKIE", "00000000-0000-0000-0000-000000000000", "Retail")
        assert len(pkgs) == 1
        pkg = pkgs[0]
        assert pkg.name == "TestApp_1.0.0.0_x64.msix"
        assert pkg.digest == sha1_b64
        assert pkg.digest_sha256 == sha256_b64
        assert pkg.size == 54321
    finally:
        api.session.post = orig_post
finally:
    if os.path.exists(test_file):
        os.remove(test_file)

print("    Dual SHA-256 & SHA-1 verification + XML <AdditionalDigest> parser: OK")

# ═══════════════════════════════════════════════════════════════════════════════
# [13] Verifying Package Extraction (extract_package) & UI Context Menu...
# ═══════════════════════════════════════════════════════════════════════════════
print("[13] Verifying Package Extraction (extract_package) & UI Context Menu...")

msix_name = "MockPackage_1.0.0_x64.msix"
msix_path = os.path.join(w.download_dir, msix_name)
out_dir = os.path.join(w.download_dir, "MockPackage_1.0.0_x64")
for f in (msix_path,):
    if os.path.exists(f):
        os.remove(f)
if os.path.isdir(out_dir):
    shutil.rmtree(out_dir, ignore_errors=True)

manifest_data = b"<Package><Identity Name='TestPkg'/></Package>"
asset_data = b"PNG_FAKE_IMAGE_DATA_12345"
with zipfile.ZipFile(msix_path, "w") as zf:
    zf.writestr("AppxManifest.xml", manifest_data)
    zf.writestr("Assets/Logo.png", asset_data)

# Test extract_package
progress_history = []
def extract_prog(done, total):
    progress_history.append((done, total))

extracted_path = extract_package(msix_path, target_dir=out_dir, progress_callback=extract_prog)
assert os.path.isdir(extracted_path)
assert (Path(extracted_path) / "AppxManifest.xml").read_bytes() == manifest_data
assert (Path(extracted_path) / "Assets" / "Logo.png").read_bytes() == asset_data
assert len(progress_history) == 2
assert progress_history[-1][0] == progress_history[-1][1]  # 100% extraction completed

# Test invalid archive error handling
bad_file = os.path.join(w.download_dir, "bad.msix")
Path(bad_file).write_text("NOT A ZIP ARCHIVE")
err_caught = False
try:
    extract_package(bad_file)
except StoreError:
    err_caught = True
assert err_caught, "Expected StoreError for non-zip archive"
if os.path.exists(bad_file):
    os.remove(bad_file)

# Test UI context menu integration (_can_extract_row_file)
w.packages = [
    PackageFile(
        name=msix_name,
        size=os.path.getsize(msix_path),
        download_url="http://example.com/test.msix",
        update_id="111",
        revision="1",
        file_guid="1",
    )
]
w.row_states = [("downloading", 50)]
assert not w._can_extract_row_file(0), "Cannot extract while downloading"

w.row_states = [("done",)]
assert w._can_extract_row_file(0), "Should allow extract when row is done and file is .msix"

# Test full UI extraction flow through _extract_selected_package
w._context_row = 0
orig_startfile = getattr(os, "startfile", None)
startfile_called = []
os.startfile = lambda p: startfile_called.append(p)
try:
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    with zipfile.ZipFile(msix_path, "w") as zf:
        zf.writestr("AppxManifest.xml", b"<Package/>")
    w._extract_selected_package()
    # Pump tkinter loop until worker thread notifies success
    start_time = time.monotonic()
    while time.monotonic() - start_time < 3.0:
        w._process_ui_queue()
        w.update()
        if w._notice and w._notice[0] == "success":
            break
        time.sleep(0.05)
    assert w._notice is not None and w._notice[0] == "success"
    assert "Extracted package successfully" in w._notice[1]
    assert len(startfile_called) == 1 and os.path.normpath(startfile_called[0]) == os.path.normpath(out_dir)
    assert os.path.isdir(out_dir)

    # Test UI extraction failure notification (e.g. invalid/corrupted zip)
    with open(msix_path, "wb") as f:
        f.write(b"CORRUPTED_NOT_A_ZIP")
    w._extract_selected_package()
    start_time = time.monotonic()
    while time.monotonic() - start_time < 3.0:
        w._process_ui_queue()
        w.update()
        if w._notice and w._notice[0] == "error":
            break
        time.sleep(0.05)
    assert w._notice is not None and w._notice[0] == "error"
    assert "Extraction failed" in w._notice[1]
finally:
    if orig_startfile:
        os.startfile = orig_startfile
    else:
        delattr(os, "startfile")

# Test non-extractable file (.txt)
w.packages = [
    PackageFile(
        name="Readme.txt",
        size=10,
        download_url="http://example.com/readme.txt",
        update_id="112",
        revision="1",
        file_guid="2",
    )
]
txt_path = os.path.join(w.download_dir, "Readme.txt")
Path(txt_path).write_text("Hello")
assert not w._can_extract_row_file(0), "Cannot extract .txt file"
if os.path.exists(txt_path):
    os.remove(txt_path)

# Test _format_dl_start_msg for resuming status text
part_path = msix_path + ".part"
with open(part_path, "wb") as pf:
    pf.write(b"PARTIAL_BYTES" * 1000)
resume_msg = w._format_dl_start_msg(1, 1, w.packages[0], msix_path)
assert "Resuming" in resume_msg
if os.path.exists(part_path):
    os.remove(part_path)

# Clean up
w._clear_list()
if os.path.exists(msix_path):
    os.remove(msix_path)
if os.path.isdir(out_dir):
    shutil.rmtree(out_dir, ignore_errors=True)

print("    Package extraction (zip inspect, disk check, progress) & context menu rules: OK")

w.destroy()
print("\n=== ALL OK: All automated test suites passed successfully! ===")
