"""The same lock mark used by the website and the Windows executable."""
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtSvg import QSvgRenderer


PATHS = {
    "asterisk": '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/>',
    "key": '<circle cx="8" cy="15" r="5"/><path d="m12 11 8-8m-3 3 3 3m-6 0 3 3"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3z"/>',
    "trash": '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    "moon": '<path d="M20 14a8 8 0 0 1-10-10 8 8 0 1 0 10 10z"/>',
}


def navigation_icon(name, color="#a09cb0"):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)


def entry_icon(title, accent="#8864cb"):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    color = QColor(accent)
    painter.setBrush(color.darker(240))
    painter.drawRoundedRect(QRectF(1, 1, 62, 62), 14, 14)
    painter.setPen(color.lighter(165))
    font = QFont("Segoe UI")
    font.setPixelSize(30)
    font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, (title.strip()[:1] or "?").upper())
    painter.end()
    return QIcon(pixmap)


def application_icon():
    return QIcon(str(Path(__file__).with_name("assets") / "app.ico"))
