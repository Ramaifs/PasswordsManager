"""The same lock mark used by the website and the Windows executable."""
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtSvg import QSvgRenderer


PATHS = {
    "asterisk": '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/>',
    "key": '<circle cx="8" cy="15" r="5"/><path d="m12 11 8-8m-3 3 3 3m-6 0 3 3"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3z"/>',
    "subfolder": '<path d="M4 10V5h6l3 3h7v2M2 12h20l-2 8H4z"/>',
    "settings": '<path fill="currentColor" fill-rule="evenodd" stroke="none" d="M9 2h6l.6 3.3 2.1 1.2 3.2-1.1 3 5.2-2.6 2.2v2.4l2.6 2.2-3 5.2-3.2-1.1-2.1 1.2-.6 3.3H9l-.6-3.3-2.1-1.2-3.2 1.1-3-5.2 2.6-2.2v-2.4L.1 10.6l3-5.2 3.2 1.1 2.1-1.2ZM12 10a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" transform="translate(2 0) scale(.83)"/>',
    "generator": '<path d="M4 7H2v10h2m16-10h2v10h-2M7 10v4m-1.7-3 3.4 2m-3.4 0 3.4-2m3.3-1v4m-1.7-3 3.4 2m-3.4 0 3.4-2m3.3-1v4m-1.7-3 3.4 2m-3.4 0 3.4-2"/>',
    "trash": '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    "moon": '<path d="M20 14a8 8 0 0 1-10-10 8 8 0 1 0 10 10z"/>',
}


def navigation_icon(name, color="#a09cb0", depth=0):
    dots = "".join(f'<circle cx="{i * 4 + 2}" cy="12" r="1.2" fill="{color}" stroke="none"/>' for i in range(depth))
    width = 24 + depth * 4
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 24" color="{color}" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{dots}<g transform="translate({depth * 4} 0)">{PATHS[name]}</g></svg>'
    pixmap = QPixmap(width * 2, 48)
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
