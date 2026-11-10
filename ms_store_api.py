"""
ms_store_api.py
───────────────
Module kết nối trực tiếp đến Microsoft FE3 SOAP API (Windows Update Protocol)
để lấy link tải gói cài đặt Microsoft Store (.appx, .msix, .msixbundle, ...).

Không phụ thuộc vào bất kỳ dịch vụ bên thứ 3 nào (RG-AdGuard hay web proxy).
"""

import base64
import hashlib
import html
import os
import re
import shutil
import time
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Tắt cảnh báo SSL cho máy chủ nội bộ Windows Update
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from soap_templates import (
    RELEASE_TYPE_RETAIL,
    RING_MAP,
    build_get_cookie_soap,
    build_get_file_url_soap,
    build_sync_updates_soap,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════
FE3_URL = "https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx"
FE3_SECURED_URL = FE3_URL + "/secured"
DISPLAY_CATALOG_URL = (
    "https://displaycatalog.mp.microsoft.com/v7.0/products/{product_id}"
    "?market=US&languages=en-us"
)

SOAP_HEADERS = {
    "Content-Type": "application/soap+xml; charset=utf-8",
    "Cache-Control": "no-cache, no-store",
    "Pragma": "no-cache",
}
REST_HEADERS = {
    "Cache-Control": "no-cache, no-store",
    "Pragma": "no-cache",
}
NS_CWS = "http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService"
CDN_WORKERS = 8          # số luồng song song khi phân giải link CDN


# ═══════════════════════════════════════════════════════════════════════════════
# Errors
# ═══════════════════════════════════════════════════════════════════════════════
class StoreError(Exception):
    """Lỗi mang khoá i18n + tham số, để giao diện dịch theo ngôn ngữ đang chọn."""

    def __init__(self, key: str, **params):
        super().__init__(key)
        self.key = key
        self.params = params


# ═══════════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class PackageFile:
    """Đại diện cho một gói/file có thể tải được."""
    name: str                   # Tên file đầy đủ (vd: Microsoft.WindowsStore_...msixbundle)
    size: int = 0               # Kích thước (bytes)
    digest: str = ""            # SHA-1 digest (Base64)
    digest_sha256: str = ""     # SHA-256 digest (Base64)
    update_id: str = ""         # UpdateID (GUID)
    revision: str = "1"         # RevisionNumber
    download_url: str = ""      # URL tải trực tiếp từ CDN Microsoft
    file_guid: str = ""         # GUID định danh file gốc

    @property
    def extension(self) -> str:
        parts = self.name.rsplit(".", 1)
        return parts[-1].lower() if len(parts) > 1 else ""

    @property
    def size_str(self) -> str:
        if self.size == 0:
            return "N/A"
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size / (1024 * 1024 * 1024):.2f} GB"


@dataclass
class ProductInfo:
    """Thông tin sản phẩm từ DisplayCatalog."""
    product_id: str
    title: str = "Unknown"
    publisher: str = ""
    wu_category_id: str = ""


class DownloadCancelledError(Exception):
    """Raised when a download is cancelled by the user."""


# ═══════════════════════════════════════════════════════════════════════════════
# API Client
# ═══════════════════════════════════════════════════════════════════════════════
class MSStoreAPI:
    """Client gọi trực tiếp Microsoft FE3 Windows Update SOAP API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False  # Bỏ qua xác thực chứng chỉ FE3
        retry_strategy = Retry(
            total=3,
            connect=3,
            read=2,
            status=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            pool_connections=CDN_WORKERS,
            pool_maxsize=CDN_WORKERS * 2,
            max_retries=retry_strategy,
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # ───────────────────────────────────────────────────────────────────────
    # Bước 0: Tra cứu thông tin sản phẩm qua DisplayCatalog
    # ───────────────────────────────────────────────────────────────────────
    def get_product_info(self, product_id: str) -> ProductInfo:
        """Truy vấn Microsoft DisplayCatalog API để lấy WuCategoryId."""
        url = DISPLAY_CATALOG_URL.format(product_id=product_id)
        resp = self.session.get(url, headers=REST_HEADERS, timeout=(10, 15))
        if resp.status_code == 404:
            raise StoreError("err_app_not_found", id=product_id)
        resp.raise_for_status()

        data = resp.json()
        product = data.get("Product", {})

        localized = product.get("LocalizedProperties", [{}])
        title = localized[0].get("ProductTitle", "Unknown") if localized else "Unknown"
        publisher = localized[0].get("PublisherName", "") if localized else ""

        # WuCategoryId
        wu_cat_id = ""
        m = re.search(r'"WuCategoryId"\s*:\s*"([0-9a-fA-F-]{36})"', resp.text)
        if m:
            wu_cat_id = m.group(1)

        if not wu_cat_id:
            raise StoreError("err_no_wucat", title=title)

        return ProductInfo(
            product_id=product_id,
            title=title,
            publisher=publisher,
            wu_category_id=wu_cat_id,
        )

    # ───────────────────────────────────────────────────────────────────────
    # Bước 1: Lấy session cookie (luôn lấy mới mỗi lần tra cứu)
    # ───────────────────────────────────────────────────────────────────────
    def _get_cookie(self) -> str:
        """Gửi GetCookie SOAP request → nhận EncryptedData token mới nhất."""
        body = build_get_cookie_soap()
        resp = self.session.post(
            FE3_URL, data=body, headers=SOAP_HEADERS, timeout=(10, 15)
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        el = root.find(f".//{{{NS_CWS}}}EncryptedData")
        if el is None or not el.text:
            raise StoreError("err_cookie")
        return el.text

    # ───────────────────────────────────────────────────────────────────────
    # Bước 2: SyncUpdates — lấy danh sách packages
    # ───────────────────────────────────────────────────────────────────────
    def _sync_updates(
        self, cookie: str, wu_cat_id: str, ring: str
    ) -> list[PackageFile]:
        """Đồng bộ metadata các gói qua SyncUpdates."""
        flight_ring = RING_MAP.get(ring, "Retail")
        body = build_sync_updates_soap(
            cookie=cookie,
            wu_cat_id=wu_cat_id,
            release_type=RELEASE_TYPE_RETAIL,
            flight_ring=flight_ring,
        )

        resp = self.session.post(
            FE3_URL, data=body, headers=SOAP_HEADERS, timeout=(10, 30)
        )
        resp.raise_for_status()

        raw_xml = resp.text

        # 1. Parse UpdateIdentity (UpdateID, Revision) từ <UpdateInfo> theo ID
        info_blocks = re.findall(r'<UpdateInfo>(.*?)</UpdateInfo>', raw_xml, re.DOTALL)
        id_to_identity = {}
        for b in info_blocks:
            id_m = re.search(r'<ID>(\d+)</ID>', b)
            uid_m = re.search(r'UpdateID="([0-9a-fA-F-]{36})"', b)
            rev_m = re.search(r'RevisionNumber="(\d+)"', b)
            if id_m and uid_m:
                id_to_identity[id_m.group(1)] = (uid_m.group(1), rev_m.group(1) if rev_m else "1")

        # 2. Parse File details từ <Update> theo cùng ID
        update_blocks = re.findall(r'<Update>(.*?)</Update>', raw_xml, re.DOTALL)
        packages: list[PackageFile] = []

        for b in update_blocks:
            id_m = re.search(r'<ID>(\d+)</ID>', b)
            if not id_m:
                continue
            int_id = id_m.group(1)
            if int_id not in id_to_identity:
                continue

            update_id, revision = id_to_identity[int_id]
            inner = html.unescape(b)

            for f_m in re.finditer(r'<File\s+([^>]*?)>(.*?)</File>|<File\s+([^>]*?)/>', inner, re.DOTALL):
                if f_m.group(1) is not None:
                    attrs = f_m.group(1)
                    body = f_m.group(2) or ""
                else:
                    attrs = f_m.group(3) or ""
                    body = ""

                fname_m = re.search(r'FileName="([^"]+)"', attrs)
                installer_m = re.search(r'InstallerSpecificIdentifier="([^"]+)"', attrs)
                size_m = re.search(r'Size="(\d+)"', attrs)
                digest_m = re.search(r'Digest="([^"]+)"', attrs)
                sha256_m = re.search(r'<AdditionalDigest[^>]*>([^<]+)</AdditionalDigest>', body)

                fn = fname_m.group(1) if fname_m else ""
                ins = installer_m.group(1) if installer_m else ""
                sz = int(size_m.group(1)) if size_m else 0
                dg = digest_m.group(1) if digest_m else ""
                dg256 = sha256_m.group(1).strip() if sha256_m else ""

                ext = fn.split(".")[-1] if "." in fn else ""
                if ins:
                    real_name = f"{ins}.{ext}" if ext and not ins.endswith(f".{ext}") else ins
                else:
                    real_name = fn

                # file_guid để map với URL download
                file_guid = fn.split(".")[0] if "." in fn else fn

                packages.append(PackageFile(
                    name=real_name,
                    size=sz,
                    digest=dg,
                    digest_sha256=dg256,
                    update_id=update_id,
                    revision=revision,
                    file_guid=file_guid,
                ))

        return packages

    # ───────────────────────────────────────────────────────────────────────
    # Bước 3: GetExtendedUpdateInfo2 — lấy URL tải CDN kèm FileDigest
    # ───────────────────────────────────────────────────────────────────────
    def _get_download_locations_for_update(
        self, update_id: str, revision: str, ring: str
    ) -> tuple[dict[str, str], list[str]]:
        """
        Truy vấn danh sách vị trí tải CDN cho một UpdateID.
        Trả về: (digest_to_url, all_urls)
        Có cơ chế thử lại nếu gặp lỗi mạng hoặc phản hồi rỗng tạm thời.
        """
        flight_ring = RING_MAP.get(ring, "Retail")

        for attempt in range(2):
            body = build_get_file_url_soap(
                update_id=update_id,
                revision=revision,
                release_type=RELEASE_TYPE_RETAIL,
                flight_ring=flight_ring,
            )
            try:
                resp = self.session.post(
                    FE3_SECURED_URL,
                    data=body,
                    headers=SOAP_HEADERS,
                    timeout=(10, 20),
                )
                if resp.status_code != 200:
                    if attempt == 0:
                        time.sleep(0.4)
                    continue

                root = ET.fromstring(resp.text)
                digest_to_url: dict[str, str] = {}
                urls: list[str] = []

                for elem in root.iter():
                    tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag_name == "FileLocation":
                        f_digest = ""
                        f_url = ""
                        for child in elem:
                            c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if c_tag == "FileDigest" and child.text:
                                f_digest = child.text.strip()
                            elif c_tag == "Url" and child.text and child.text.strip().startswith("http"):
                                f_url = child.text.strip()
                        if f_url:
                            urls.append(f_url)
                            if f_digest:
                                digest_to_url[f_digest] = f_url

                # Fallback nếu XML trả về thẻ <Url> ngoài <FileLocation>
                if not urls:
                    for fl in root.iter():
                        tag_name = fl.tag.split("}")[-1] if "}" in fl.tag else fl.tag
                        if tag_name == "Url" and fl.text and fl.text.strip().startswith("http"):
                            urls.append(fl.text.strip())

                if urls:
                    return digest_to_url, urls
            except Exception:
                if attempt == 0:
                    time.sleep(0.4)

        return {}, []

    # ───────────────────────────────────────────────────────────────────────
    # Public: Search pipeline đầy đủ
    # ───────────────────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        ring: str = "Retail",
        on_status: Optional[callable] = None,
    ) -> tuple[ProductInfo, list[PackageFile]]:
        """
        Pipeline hoàn chỉnh:
        ProductID → DisplayCatalog → GetCookie → SyncUpdates → GetExtendedUpdateInfo2.
        """
        def status(key: str, **params):
            """Báo tiến trình dưới dạng (khoá i18n, tham số)."""
            if on_status:
                on_status(key, params)

        product_id = self._extract_product_id(query)
        status("prog_lookup", id=product_id)

        # 0. DisplayCatalog
        info = self.get_product_info(product_id)
        status("prog_found", title=info.title, publisher=info.publisher)

        # 1. Cookie
        status("prog_cookie")
        cookie = self._get_cookie()
        status("prog_cookie_ok")

        # 2. SyncUpdates
        status("prog_sync", ring=ring)
        packages = self._sync_updates(cookie, info.wu_category_id, ring)
        status("prog_sync_ok", n=len(packages))

        # 3. Lấy URL download nhóm theo unique update_id
        unique_updates: dict[str, str] = {}  # update_id -> revision
        for p in packages:
            if p.update_id:
                unique_updates[p.update_id] = p.revision

        status("prog_resolve", n=len(unique_updates))
        resolved_locations: dict[str, tuple[dict[str, str], list[str]]] = {}
        total = len(unique_updates)
        if total:
            with ThreadPoolExecutor(max_workers=min(CDN_WORKERS, total)) as pool:
                futures = {
                    pool.submit(self._get_download_locations_for_update, uid, rev, ring): uid
                    for uid, rev in unique_updates.items()
                }
                for done, fut in enumerate(as_completed(futures), start=1):
                    resolved_locations[futures[fut]] = fut.result()
                    if done % 5 == 0 or done == total:
                        status("prog_cdn", done=done, total=total)

        # Gán URL vào từng PackageFile:
        # Ưu tiên 1: Khớp chính xác mã băm SHA-1 (FileDigest == pkg.digest)
        # Ưu tiên 2: Khớp file_guid trong URL
        # Ưu tiên 3: Chỉ dùng urls[0] khi UpdateID đó có đúng 1 file duy nhất
        ready_packages = []
        for pkg in packages:
            digest_map, urls = resolved_locations.get(pkg.update_id, ({}, []))
            matched_url = ""

            if pkg.digest and pkg.digest in digest_map:
                matched_url = digest_map[pkg.digest]

            if not matched_url and pkg.file_guid:
                fg_lower = pkg.file_guid.lower()
                for u in urls:
                    if fg_lower in u.lower():
                        matched_url = u
                        break

            if not matched_url and len(urls) == 1:
                matched_url = urls[0]

            if matched_url:
                pkg.download_url = matched_url
                ready_packages.append(pkg)

        status("prog_done", n=len(ready_packages))
        return info, ready_packages

    # ───────────────────────────────────────────────────────────────────────
    # Download (HTTP Range Resume + Atomic .part + SHA-256 / SHA-1)
    # ───────────────────────────────────────────────────────────────────────
    @staticmethod
    def _verify_file_digest(
        file_path: str,
        expected_digest: str = "",
        expected_digest_sha256: str = "",
    ) -> bool:
        """Kiểm tra mã băm: ưu tiên SHA-256, tự động fallback sang SHA-1 (hỗ trợ Base64 và Hex)."""
        if not os.path.isfile(file_path):
            return False

        exp256 = expected_digest_sha256.strip() if expected_digest_sha256 else ""
        exp1 = expected_digest.strip() if expected_digest else ""

        if not exp256 and not exp1:
            return True

        use_sha256 = bool(exp256)
        hasher = hashlib.sha256() if use_sha256 else hashlib.sha1()

        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 64), b""):
                    hasher.update(chunk)
        except OSError:
            return False

        target_exp = exp256 if use_sha256 else exp1
        act_b64 = base64.b64encode(hasher.digest()).decode("ascii")
        act_hex = hasher.hexdigest()
        return target_exp == act_b64 or target_exp.lower() == act_hex.lower()

    def download_file(
        self,
        url: str,
        save_path: str,
        on_progress: Optional[callable] = None,
        cancel_check: Optional[callable] = None,
        expected_size: int = 0,
        expected_digest: str = "",
        expected_digest_sha256: str = "",
    ):
        """
        Tải file từ Microsoft CDN:
        - Hỗ trợ Resume tải nối qua HTTP Range nếu có file dở dang `<save_path>.part`.
        - Kiểm tra toàn vẹn (ưu tiên SHA-256, tự động fallback sang SHA-1, hỗ trợ Base64 hoặc Hex).
        - Giữ lại file .part khi ngắt kết nối hoặc Cancel để có thể tải tiếp.
        - Đổi tên nguyên tử sang `save_path` khi hoàn tất và xác thực thành công.
        """
        if cancel_check and cancel_check():
            raise DownloadCancelledError()

        temp_path = f"{save_path}.part"
        have = os.path.getsize(temp_path) if os.path.isfile(temp_path) else 0

        headers = {}
        if have > 0:
            headers["Range"] = f"bytes={have}-"

        try:
            r = self.session.get(url, headers=headers, stream=True, timeout=(10, 30))
        except requests.exceptions.RequestException as e:
            raise IOError(f"Network error: {e}") from e

        # Xử lý 416 Range Not Satisfiable (file dở dang đã đủ kích thước hoặc lỗi Range)
        if r.status_code == 416:
            r.close()
            if self._verify_file_digest(temp_path, expected_digest, expected_digest_sha256):
                os.replace(temp_path, save_path)
                if on_progress:
                    sz = os.path.getsize(save_path)
                    on_progress(sz, sz)
                return
            # File .part bị lỗi: xóa và bắt đầu lại từ đầu
            try:
                os.remove(temp_path)
            except OSError:
                pass
            have = 0
            headers.pop("Range", None)
            r = self.session.get(url, headers=headers, stream=True, timeout=(10, 30))

        try:
            r.raise_for_status()

            is_partial = (r.status_code == 206 and have > 0)
            if is_partial:
                mode = "ab"
                remaining = int(r.headers.get("content-length", 0))
                total = have + remaining if remaining > 0 else expected_size
            else:
                have = 0
                mode = "wb"
                header_total = int(r.headers.get("content-length", 0))
                total = header_total if header_total > 0 else expected_size

            use_sha256 = bool(expected_digest_sha256)
            hasher = (
                hashlib.sha256()
                if use_sha256
                else (hashlib.sha1() if expected_digest else None)
            )

            # Nếu resume: đọc các byte đã có sẵn trên đĩa vào hasher
            if is_partial and hasher is not None:
                with open(temp_path, "rb") as pf:
                    for chunk in iter(lambda: pf.read(1024 * 64), b""):
                        hasher.update(chunk)

            downloaded = have
            if on_progress:
                on_progress(downloaded, total)

            with open(temp_path, mode) as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if cancel_check and cancel_check():
                        raise DownloadCancelledError()
                    if chunk:
                        f.write(chunk)
                        if hasher:
                            hasher.update(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            on_progress(downloaded, total)
                f.flush()
        finally:
            r.close()

        if cancel_check and cancel_check():
            raise DownloadCancelledError()

        # 1. Kiểm tra đứt luồng (Truncated stream)
        if total > 0 and downloaded < total:
            raise IOError(
                f"Incomplete download: received {downloaded} of {total} bytes"
            )

        # 2. Kiểm tra toàn vẹn (ưu tiên SHA-256, tự động fallback sang SHA-1)
        if hasher is not None:
            target_exp = (
                expected_digest_sha256.strip()
                if use_sha256
                else expected_digest.strip()
            )
            act_b64 = base64.b64encode(hasher.digest()).decode("ascii")
            act_hex = hasher.hexdigest()
            algo = "SHA-256" if use_sha256 else "SHA-1"
            if target_exp != act_b64 and target_exp.lower() != act_hex.lower():
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                raise IOError(
                    f"{algo} integrity check failed (expected {target_exp}, got {act_b64})"
                )

        # 3. Đổi tên nguyên tử từ .part sang file đích
        os.replace(temp_path, save_path)

    # ───────────────────────────────────────────────────────────────────────
    # Helpers
    # ───────────────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_product_id(raw: str) -> str:
        """Trích xuất Product ID 12 ký tự an toàn (tránh bắt nhầm tên miền/từ dài trong URL)."""
        raw = raw.strip()
        if re.fullmatch(r'[A-Za-z0-9]{12}', raw):
            return raw.upper()

        m = re.search(r'/detail/([A-Za-z0-9]{12})(?:[/?#&]|$)', raw, re.IGNORECASE)
        if m:
            return m.group(1).upper()

        m = re.search(r'productId[=/]([A-Za-z0-9]{12})(?:[/?#&]|$)', raw, re.IGNORECASE)
        if m:
            return m.group(1).upper()

        m = re.search(r'/([A-Za-z0-9]{12})(?:[?#&]|$)', raw)
        if m:
            return m.group(1).upper()

        # Ưu tiên mã Product ID chuẩn của Store bắt đầu bằng số 9 (12 ký tự độc lập)
        m = re.search(r'\b(9[A-Za-z0-9]{11})\b', raw)
        if m:
            return m.group(1).upper()

        # Nếu là URL thì bỏ phần scheme + domain trước khi quét từ 12 ký tự
        search_target = re.sub(r'^[a-zA-Z]+://[^/]+', '', raw)
        m = re.search(r'\b([A-Za-z0-9]{12})\b', search_target)
        if m:
            return m.group(1).upper()

        return raw.upper()


# ═══════════════════════════════════════════════════════════════════════════════
# Package Extraction Helper
# ═══════════════════════════════════════════════════════════════════════════════
def extract_package(
    package_path: str,
    target_dir: Optional[str] = None,
    progress_callback: Optional[callable] = None,
    cancel_check: Optional[callable] = None,
) -> str:
    """
    Giải nén file gói cài đặt (.msix, .appx, .msixbundle, .appxbundle) ra thư mục con.
    Sử dụng zipfile chuẩn, kiểm tra dung lượng ổ đĩa trống và báo cáo tiến trình.
    """
    p = os.path.abspath(os.path.normpath(package_path))
    if not os.path.isfile(p):
        raise StoreError("err_extract", msg=f"File not found: {p}")

    if not zipfile.is_zipfile(p):
        raise StoreError("err_extract", msg=f"Not a valid zip/package archive: {os.path.basename(p)}")

    if not target_dir:
        base, _ = os.path.splitext(p)
        target_dir = base

    target_dir = os.path.abspath(os.path.normpath(target_dir))
    os.makedirs(target_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(p, "r") as zf:
            infolist = zf.infolist()
            total_uncompressed = sum(m.file_size for m in infolist)

            free_bytes = shutil.disk_usage(target_dir).free
            if free_bytes < total_uncompressed:
                needed_mb = total_uncompressed / (1024 * 1024)
                free_mb = free_bytes / (1024 * 1024)
                raise StoreError(
                    "err_extract",
                    msg=f"Not enough disk space: {needed_mb:.1f} MB needed, but only {free_mb:.1f} MB available."
                )

            done = 0
            for member in infolist:
                if cancel_check and cancel_check():
                    raise DownloadCancelledError()
                zf.extract(member, target_dir)
                done += member.file_size
                if progress_callback:
                    progress_callback(done, total_uncompressed)
    except Exception as e:
        if isinstance(e, (StoreError, DownloadCancelledError)):
            raise
        raise StoreError("err_extract", msg=str(e)) from e

    return target_dir
