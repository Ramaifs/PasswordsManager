"""Render the existing website SVG into a Windows icon without external tools."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import struct
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

root = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
svg = (root / "web/password-manager/dist/icon.svg").read_bytes()
renderer = QSvgRenderer(svg)
if not renderer.isValid():
    raise SystemExit("Invalid source icon")
frames = []
for size in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
    bitmap = QImage(size, size, QImage.Format.Format_ARGB32)
    bitmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(bitmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert bitmap.save(buffer, "PNG")
    frames.append((size, bytes(buffer.data())))
header = struct.pack("<HHH", 0, 1, len(frames))
offset = 6 + 16 * len(frames)
entries = []
for size, data in frames:
    entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
    offset += len(data)
target = root / "src/password_manager/assets"
target.mkdir(exist_ok=True)
(target / "app.svg").write_bytes(svg)
(target / "app.ico").write_bytes(header + b"".join(entries) + b"".join(data for _, data in frames))
print("Created app.ico with", len(frames), "sizes from the website SVG")
