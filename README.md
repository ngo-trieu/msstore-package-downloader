# Microsoft Store Package Downloader

Lightweight Windows app (Native Tkinter ~10MB) for directly downloading Microsoft Store installation packages (`.appx`, `.msix`, `.msixbundle`...) via Microsoft's official FE3 SOAP API without third-party intermediaries.

## Running

```bash
pip install -r requirements.txt
python app.py
```

Or run `run.bat`. Compile to standalone EXE: `build_exe.bat`.

## Features

- Paste a Product ID (e.g. `9WZDNCRFJBMP`) or Microsoft Store URL; select release ring (Retail / Release Preview / Insider).
- Multi-row selection table with blue highlight, architecture filter (x64, x86, ARM64, ARM, Neutral), queue status (`Waiting` / `Downloading` / `Done` / `Cancelled`), and dynamic selected size summary.
- HTTP Range resume download (`Range: bytes={have}-`) with automatic `.part` preservation on cancellation or connection drops.
- Dual cryptographic integrity verification: SHA-256 primary verification with SHA-1 fallback (Base64 / Hex).
- Right-click context menu: `Download selected` / `Cancel download`, `Copy download link`, `Copy package name`, `Open file location`, and `Extract package files` (extracts `.msix`, `.appx`, `.msixbundle` with real-time percentage and opens folder).
- Clean high-contrast light theme, English UI, fixed 2-line selectable/copyable status card (`App Name • ID • Publisher`) without popups.
- Direct save folder controls anchored at the bottom (`Change...` and `Open save folder`), configuration saved to `~/.msstore_downloader.json`.
- Text-only clean buttons, razor-sharp High-DPI Windows display and multi-size DIB/PNG taskbar icon.

## Structure

```
app.py            Minimal Native Tkinter UI
i18n.py           English strings & persistent configuration
ms_store_api.py   Direct Microsoft FE3 / DisplayCatalog client (multithreaded)
soap_templates.py SOAP XML envelope templates
make_icon.py      Multi-resolution sharp vector icon generator
assets/           Application icons (app.ico, app.png)
_test.py          Comprehensive automated test suite
```

## Disclaimer

This project is an independent open-source tool and is not affiliated with, endorsed by, or sponsored by Microsoft Corporation. Microsoft, Windows, Microsoft Store, and Windows Update are registered trademarks of Microsoft Corporation. All packages are retrieved directly from official Microsoft Content Delivery Network servers.

## License

This project is licensed under the [MIT License](LICENSE).
