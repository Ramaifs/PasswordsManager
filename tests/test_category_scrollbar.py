import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem
from password_manager.category_list import CategoryList, HAS_CHILDREN
from password_manager.theme import stylesheet


def test_long_category_has_no_horizontal_scrollbar_or_corner(tmp_path):
    app = QApplication.instance() or QApplication([])
    widget = CategoryList()
    widget.setStyleSheet(stylesheet())
    widget.resize(210, 380)
    try:
        for index in range(30):
            item = QListWidgetItem('    ' * (index % 4) + 'Long category name ' * 6)
            item.setData(HAS_CHILDREN, index % 2 == 0)
            widget.addItem(item)
        widget.show()
        app.processEvents()
        widget.scrollToBottom()
        app.processEvents()
        widget.grab().save(str(tmp_path / 'category-scrollbar.png'))
        assert widget.verticalScrollBar().isVisible()
        assert not widget.horizontalScrollBar().isVisible(), 'Horizontal track and dark end block appear below category list'
        assert widget.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert widget.visualItemRect(widget.item(29)).width() <= widget.viewport().width()
    finally:
        widget.close()
        widget.deleteLater()
