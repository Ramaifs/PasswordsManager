"""Native Qt styling shared by the vault, lock screen and owned dialogs."""


def stylesheet(dark=True, accent_color="#8864cb"):
    from PySide6.QtGui import QColor
    primary = QColor(accent_color)
    if not primary.isValid():
        primary = QColor("#8864cb")
    def mix(background, ratio):
        base = QColor(background)
        return QColor(*(round(a * ratio + b * (1 - ratio)) for a, b in zip(primary.getRgb()[:3], base.getRgb()[:3]))).name()
    if dark:
        bg, side, panel, field = "#1e1e24", "#19191f", "#24242c", "#202027"
        text, muted, line, hover = "#e5e3ed", "#a09cb0", "#35343f", "#302d40"
        accent, selected = "#b49af3", "#373047"
    else:
        bg, side, panel, field = "#faf9fc", "#f0eef5", "#ffffff", "#ffffff"
        text, muted, line, hover = "#282332", "#706a7c", "#ddd8e5", "#eae4f5"
        accent, selected = "#7050b8", "#e6dcf8"
    accent = mix(text, .65) if dark else primary.name()
    selected, hover = mix(bg, .26), mix(bg, .14)
    ink = "#ffffff" if primary.redF() * .299 + primary.greenF() * .587 + primary.blueF() * .114 < .6 else "#17171b"
    primary_hover = primary.lighter(112).name() if dark else primary.darker(110).name()
    return f"""
        QWidget {{ background: {bg}; color: {text}; font-family: 'Segoe UI'; font-size: 13px; }}
        QWidget#sidebar, QWidget#sidebar QLabel {{ background: {side}; }}
        QWidget#entryColumn, QWidget#entryColumn QLabel {{ background: {panel}; }}
        QWidget#lockCard {{ background: {panel}; border: 1px solid {line}; border-radius: 16px; }}
        QWidget#lockCard QLabel {{ background: transparent; }}
        QLabel[accentHeading="true"] {{ color: {accent}; font-weight:600; font-size:14px; }}
        QFrame#lastOpenedCopy {{ border:1px solid {accent}; border-radius:10px; background:{selected}; }}
        QFrame#lastOpenedCopy QLabel {{ background:transparent; border:none; }}
        QProgressBar::chunk {{ background: {primary.name()}; }}
        QLabel#brand {{ color: {accent}; font-size: 18px; font-weight: 600; }}
        QLabel#heading {{ font-size: 27px; font-weight: 600; }}
        QLabel#sectionHeading {{ font-size: 18px; font-weight: 600; }}
        QLabel#caption {{ color: {muted}; font-size: 11px; }}
        QLabel#status {{ color: {muted}; padding: 10px 18px; border-top: 1px solid {line}; }}
        QLabel#lockMark {{ color: {accent}; font-size: 36px; background: transparent; }}
        QLineEdit, QTextEdit, QComboBox, QSpinBox {{ background: {field}; border: 1px solid {line};
            border-radius: 7px; padding: 9px 11px; selection-background-color: {selected}; }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {accent}; }}
        QPushButton, QToolButton {{ background: transparent; border: 1px solid transparent;
            border-radius: 7px; padding: 9px 12px; }}
        QPushButton:hover, QToolButton:hover {{ background: {hover}; border-color: {line}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {selected}; }}
        QPushButton:disabled {{ color: {muted}; }}
        QPushButton#primary {{ background: {primary.name()}; color: {ink}; font-weight: 600; }}
        QPushButton#primary:hover {{ background: {primary_hover}; }}
        QPushButton#advancedOptions:checked {{ background: {selected}; color: {accent}; border-color: {accent}; }}
        QCheckBox::indicator:checked {{ background: {primary.name()}; border: 1px solid {accent}; border-radius: 3px; }}
        QPushButton#primary:disabled {{ background: {line}; color: {muted}; }}
        QDialog#closeChoice QPushButton {{ background: transparent; border: 1px solid {line}; }}
        QDialog#closeChoice QPushButton:hover {{ background: {hover}; border-color: {accent}; }}
        QDialog#closeChoice QPushButton#primary {{ background: {primary.name()}; color: {ink}; border-color: {primary.name()}; }}
        QDialog#closeChoice QPushButton#primary:hover {{ background: {primary_hover}; border-color: {primary_hover}; }}
        QDialog#closeChoice QPushButton#primary:disabled {{ background: {line}; color: {muted}; border-color: {line}; }}
        QPushButton#danger {{ color: {"#ed9da8" if dark else "#ad354b"}; }}
        QListWidget {{ background: transparent; border: none; outline: none; padding: 4px; }}
        QListWidget::item {{ padding: 13px 11px; border-radius: 7px; margin: 2px 0; }}
        QListWidget#entryList::item {{ padding: 0; min-height: 42px; }}
        QListWidget::item:hover {{ background: {hover}; }}
        QListWidget::item:selected {{ background: {selected}; color: {text}; }}
        QSplitter::handle {{ background: {line}; width: 1px; }}
        QScrollArea {{ border: none; }}
        QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {line}; border-radius: 3px; min-height: 25px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QCheckBox {{ spacing: 9px; padding: 4px 0; }}
        QMenu {{ background: {panel}; border: 1px solid {line}; padding: 6px; }}
        QMenu::item {{ padding: 9px 25px 9px 14px; border-radius: 5px; }}
        QMenu::item:selected {{ background: {selected}; }}
        QToolButton::menu-indicator {{ width: 0; }}
        QPushButton#settingsAction {{ background: {field}; border: 1px solid {line}; border-radius: 7px; padding: 10px 12px; text-align: left; }}
        QPushButton#settingsAction:hover {{ background: {hover}; border-color: {accent}; }}
        QFrame#settingsSeparator {{ color: {line}; background: {line}; max-height: 1px; margin: 8px 0; }}
        QToolTip {{ background: {panel}; color: {text}; border: 1px solid {line}; padding: 6px; }}
        QTableWidget {{ background: {panel}; gridline-color: {line}; border: 1px solid {line}; }}
        QHeaderView::section {{ background: {side}; padding: 8px; border: none; }}
    """
