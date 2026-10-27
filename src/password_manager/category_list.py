"""Category navigation with explicit move targets and fold controls."""
from PySide6.QtCore import Qt, QMimeData, QPointF, Signal, QSize
from PySide6.QtGui import QDrag, QPen, QPolygonF
from PySide6.QtWidgets import QListWidget, QStyledItemDelegate, QAbstractItemView

MIME = "application/x-password-manager-category"
HAS_CHILDREN = int(Qt.ItemDataRole.UserRole) + 1
COLLAPSED = int(Qt.ItemDataRole.UserRole) + 2


class CategoryDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        # Category labels fit the sidebar; long names must not widen its content.
        return QSize(0, super().sizeHint(option, index).height())

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if index.data(HAS_CHILDREN) and option.rect.width() > 0:
            option.text = option.fontMetrics.elidedText(option.text, Qt.TextElideMode.ElideRight, max(0, option.rect.width() - 62))

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if not index.data(HAS_CHILDREN):
            return
        x, y = option.rect.right() - 18, option.rect.center().y()
        points = [(x - 2, y - 4), (x + 2, y), (x - 2, y + 4)] if index.data(COLLAPSED) else [(x - 4, y - 2), (x, y + 2), (x + 4, y - 2)]
        painter.save()
        painter.setPen(QPen(option.palette.text().color(), 1.5))
        painter.drawPolyline(QPolygonF([QPointF(*p) for p in points]))
        painter.restore()


class CategoryList(QListWidget):
    toggleRequested = Signal(str)
    moveRequested = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_ids = set()
        self.setItemDelegate(CategoryDelegate(self))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAccessibleName("Категории: перетаскивание и сворачивание подкатегорий")

    def arrow_at(self, point):
        item = self.itemAt(point)
        return item if item and item.data(HAS_CHILDREN) and point.x() >= self.visualItemRect(item).right() - 34 else None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.arrow_at(event.position().toPoint()):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        item = self.arrow_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and item:
            self.toggleRequested.emit(item.data(Qt.ItemDataRole.UserRole))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        item = self.currentItem()
        if item and item.data(HAS_CHILDREN) and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            collapse = event.key() == Qt.Key.Key_Left
            if collapse != bool(item.data(COLLAPSED)):
                self.toggleRequested.emit(item.data(Qt.ItemDataRole.UserRole))
            event.accept()
            return
        super().keyPressEvent(event)

    def startDrag(self, actions):
        item = self.currentItem()
        if not item or item.data(Qt.ItemDataRole.UserRole) not in self.category_ids:
            return
        mime = QMimeData()
        mime.setData(MIME, item.data(Qt.ItemDataRole.UserRole).encode("ascii"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def drop_target(self, event):
        if event.source() is not self or not event.mimeData().hasFormat(MIME):
            return None
        try:
            source = bytes(event.mimeData().data(MIME)).decode("ascii")
        except UnicodeError:
            return None
        item = self.itemAt(event.position().toPoint())
        target = item.data(Qt.ItemDataRole.UserRole) if item else None
        if source not in self.category_ids or target == source or (target != "all" and target not in self.category_ids):
            return None
        return source, None if target == "all" else target

    def dragEnterEvent(self, event):
        if event.source() is self and event.mimeData().hasFormat(MIME):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self.drop_target(event):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        target = self.drop_target(event)
        if target:
            # The model owns hierarchy changes. Qt never reorders stored rows itself.
            self.moveRequested.emit(*target)
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()
