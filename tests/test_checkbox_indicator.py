import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QStyle, QStyleOptionButton
from password_manager.theme import stylesheet


@pytest.mark.parametrize('accent,light_mark', [('#663399', True), ('#ccffcc', False)])
def test_checked_indicator_has_contrasting_tick_and_accent_background(accent, light_mark):
    app = QApplication.instance() or QApplication([])
    control = QCheckBox()
    control.setStyleSheet(stylesheet(True, accent))
    control.setChecked(True)
    control.resize(30, 30)
    try:
        control.show()
        app.processEvents()
        option = QStyleOptionButton()
        option.initFrom(control)
        rect = control.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, control)
        image = control.grab().toImage()
        colors = [image.pixelColor(x, y) for x in range(rect.left() + 3, rect.right() - 2) for y in range(rect.top() + 3, rect.bottom() - 2)]
        mark = sum(all(channel > 220 for channel in (c.red(), c.green(), c.blue())) if light_mark else all(channel < 55 for channel in (c.red(), c.green(), c.blue())) for c in colors)
        background = sum(c.name() == accent for c in colors)
        assert mark >= 3, 'Checked indicator lost its tick and became a solid color block'
        assert background >= 3, 'Accent must color the background behind the tick'
    finally:
        control.close()
        control.deleteLater()
