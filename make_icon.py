"""
make_icon.py
────────────
Vẽ icon ứng dụng (mũi tên tải xuống vào khay, nền xanh da trời) bằng Qt và đóng gói
thành assets/app.ico với các kích thước 256-16 px.
Các size < 256 được lưu ở định dạng chuẩn 32-bit BGRA DIB (BITMAPINFOHEADER) để
tương thích tuyệt đối với Tcl/Tk và Win32 API (không bị lấy nhầm frame 16x16 phóng đại).

Chạy: python make_icon.py
"""

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
    from PyQt5.QtGui import (QColor, QImage, QLinearGradient, QPainter, QPainterPath,
                             QPen)
    from PyQt5.QtWidgets import QApplication
    HAS_QT = True
except ImportError:
    HAS_QT = False

SIZES = [256, 128, 64, 48, 32, 24, 16]
OUT_DIR = Path(__file__).parent / "assets"


def draw(size: int) -> "QImage":
    """Vẽ icon ở kích thước size x size (toạ độ chuẩn hoá 0..1 nhân với size)."""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    s = float(size)

    # Nền bo góc, gradient xanh da trời
    m = s * 0.04
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), s * 0.22, s * 0.22)
    grad = QLinearGradient(0, 0, 0, s)
    grad.setColorAt(0.0, QColor("#38bdf8"))
    grad.setColorAt(1.0, QColor("#0369a1"))
    p.fillPath(bg, grad)

    white = QColor("#ffffff")
    # Nét vẽ dày hơn ở size nhỏ để không bị mờ
    w = s * (0.095 if size >= 48 else 0.12)
    pen = QPen(white, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    cx = s / 2
    # Mũi tên: thân + đầu
    top, tip = s * 0.20, s * 0.58
    p.drawLine(QPointF(cx, top), QPointF(cx, tip))
    head = s * 0.17
    p.drawLine(QPointF(cx - head, tip - head), QPointF(cx, tip))
    p.drawLine(QPointF(cx + head, tip - head), QPointF(cx, tip))

    # Khay: hình chữ U bên dưới
    tl, tr, tb = s * 0.24, s * 0.76, s * 0.78
    tray = QPainterPath()
    tray.moveTo(tl, s * 0.60)
    tray.lineTo(tl, tb)
    tray.lineTo(tr, tb)
    tray.lineTo(tr, s * 0.60)
    p.drawPath(tray)

    p.end()
    return img


def png_bytes(img: "QImage") -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def dib_bytes(img: "QImage") -> bytes:
    """Chuyển QImage sang cấu trúc 32-bit BGRA DIB chuẩn của file .ico (BITMAPINFOHEADER + XOR + AND mask)."""
    img = img.convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    bih = struct.pack("<IIIHHIIIIII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    ptr = img.bits()
    ptr.setsize(h * w * 4)
    raw = bytes(ptr)
    stride = w * 4
    xor_rows = b"".join(raw[(h - 1 - y) * stride : (h - y) * stride] for y in range(h))
    and_stride = ((w + 31) // 32) * 4
    and_rows = bytearray(and_stride * h)
    for y in range(h):
        src_y = h - 1 - y
        for x in range(w):
            if raw[(src_y * w + x) * 4 + 3] == 0:
                and_rows[y * and_stride + (x // 8)] |= 1 << (7 - (x % 8))
    return bih + xor_rows + bytes(and_rows)


def write_ico(path: Path, entries: list):
    """Ghi file .ico chứa các ảnh DIB/PNG (entries: [(size, bytes)])."""
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory, blobs = b"", b""
    for size, data in entries:
        dim = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    path.write_bytes(header + directory + blobs)


def main():
    if not HAS_QT:
        if (OUT_DIR / "app.ico").exists():
            print("INFO: assets/app.ico đã tồn tại sẵn, bỏ qua việc tạo lại.")
            return
        print("LƯU Ý: Cần PyQt5 nếu muốn vẽ lại icon từ đầu. Đang sử dụng file sẵn có.")
        return
    _ = QApplication(sys.argv)
    OUT_DIR.mkdir(exist_ok=True)
    entries = []
    png_256 = b""
    for sz in SIZES:
        im = draw(sz)
        if sz == 256:
            png_256 = png_bytes(im)
            entries.append((sz, png_256))
        else:
            entries.append((sz, dib_bytes(im)))
    write_ico(OUT_DIR / "app.ico", entries)
    if png_256:
        (OUT_DIR / "app.png").write_bytes(png_256)
    print("OK:", OUT_DIR / "app.ico", [sz for sz, _ in entries])


if __name__ == "__main__":
    main()
