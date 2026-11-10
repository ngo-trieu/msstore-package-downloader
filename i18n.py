"""
i18n.py
───────
Application configuration and English string resources.
"""

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".msstore_downloader.json"

STRINGS = {
    "app_title": "Microsoft Store Package Downloader",
    "app_subtitle": "Direct Microsoft FE3 SOAP connection • Official .msix / .appx packages",
    "open_folder": "Open save folder",
    "change_folder": "Change...",
    "clear_list": "Clear list",
    "choose_folder_title": "Choose save folder",
    "search": "Search",
    "searching": "Searching...",
    "info_idle_title": "No application loaded",
    "info_idle_meta": "Enter a Product ID or Microsoft Store link above, then press Search.",
    "info_connecting": "Searching Microsoft Store: {query}...",
    "info_init": "Initializing Microsoft FE3 SOAP session...",
    "files_ready": "{n} files ready",
    "files_ready_filtered": "{vis} of {n} files ready (Filtered by {arch})",
    "status_ready_select": "Search complete • Select packages below to download.",
    "no_files_found": "No downloadable packages found for this ring.",
    "select_all": "Select all",
    "deselect_all": "Deselect",
    "arch_label": "Architecture:",
    "arch_all": "All",
    "arch_other": "Other",
    "selected_summary": "Selected: {sel}/{vis} files ({size})",
    "download": "Download selected",
    "downloading": "Downloading...",
    "col_name": "Package name",
    "col_format": "Format",
    "col_arch": "Architecture",
    "col_size": "Size",
    "col_status": "Status",
    "st_ready": "",
    "st_waiting": "Waiting",
    "st_downloading": "Downloading",
    "st_done": "Done",
    "st_error": "Error",
    "st_cancelled": "Cancelled",
    "ctx_download": "Download selected ({n})",
    "ctx_download_one": "Download this package",
    "ctx_cancel": "Cancel download",
    "ctx_copy_url": "Copy download link",
    "ctx_copy_name": "Copy package name",
    "ctx_open_location": "Open file location",
    "ctx_extract": "Extract package files",
    "msg_copied_url": "Copied download link to clipboard",
    "msg_copied_name": "Copied package name to clipboard",
    "msg_dl_starting": "Downloading ({idx}/{total}): {name}...",
    "msg_dl_resuming": "Resuming ({idx}/{total}): {name} from {dl} — {pct}% ({dl} / {size})",
    "msg_dl_progress": "Downloading ({idx}/{total}): {name} — {pct}% ({dl} / {size})",
    "msg_dl_cancelling": "Cancelling active download...",
    "msg_dl_cancelled": "Download cancelled ({ok} completed)",
    "msg_extracting": "Extracting: {name}...",
    "ok_extract": "Extracted package successfully to: {folder}",
    "err_extract": "Extraction failed: {msg}",
    "save_dir": "Save folder: {path}",
    "warn_missing_content": "Please enter a Product ID (e.g. 9WZDNCRFJBMP) or a Microsoft Store link.",
    "warn_nosel_content": "Please select at least one file in the table to download.",
    "ok_dl_content": "Download complete: Saved {ok} file(s) to {folder}",
    "err_dl_content": "Download finished: {ok} succeeded, {fail} failed (Folder: {folder})",
    "err_dl_all_failed": "Download failed: {fail} file(s) could not be downloaded.",
    "err_app_not_found": "No application found matching Product ID: {id}",
    "err_no_wucat": "'{title}' does not expose a WuCategoryId for offline package download.",
    "err_cookie": "Could not obtain a session token from Microsoft FE3 server.",
    "err_network": "Network / server error: {msg}",
    "prog_lookup": "Step 1/4 • Looking up product metadata ({id})...",
    "prog_found": "Step 1/4 • Found: {title} ({publisher})",
    "prog_cookie": "Step 2/4 • Requesting session token from Microsoft FE3...",
    "prog_cookie_ok": "Step 2/4 • Session token received",
    "prog_sync": "Step 3/4 • Syncing package catalog (Ring: {ring})...",
    "prog_sync_ok": "Step 3/4 • Synced {n} package entries",
    "prog_resolve": "Step 4/4 • Resolving CDN links for {n} package groups...",
    "prog_cdn": "Step 4/4 • Resolving Microsoft CDN links ({done}/{total})...",
    "prog_done": "Completed • {n} files ready to download.",
}


def tr(key: str, **kwargs) -> str:
    """Format an English string resource safely."""
    text = STRINGS.get(key, key)
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except KeyError as e:
        missing = e.args[0] if e.args else ""
        if missing in ("folder", "dest", "path"):
            val = kwargs.get("folder") or kwargs.get("dest") or kwargs.get("path")
            if val is not None:
                kwargs[missing] = val
                try:
                    return text.format(**kwargs)
                except Exception:
                    pass
        if missing in ("msg", "err", "error"):
            val = kwargs.get("msg") or kwargs.get("err") or kwargs.get("error")
            if val is not None:
                kwargs[missing] = val
                try:
                    return text.format(**kwargs)
                except Exception:
                    pass
        return text
    except Exception:
        return text


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
