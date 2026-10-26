# Сторонние компоненты

Состав Windows x64 0.2.1 определяется фактическим каталогом `dist/PasswordManager` и [аудитом Qt](artifacts/bundle-audit.json). Собственный код использует условия [LICENSE.txt](LICENSE.txt). Эти условия не ограничивают права на библиотеки.

| Компонент | Версия | Условия |
| --- | --- | --- |
| CPython | 3.14.6 | PSF и включённые уведомления Python |
| PySide6, Shiboken6 | 6.12.0 | LGPLv3, выбранная из доступных альтернатив |
| Qt Core, GUI, Widgets, Network | 6.12.0 | LGPLv3 и сторонние уведомления исходного Qt Base |
| cryptography | 50.0.2 | Apache-2.0 или BSD, собственные уведомления зависимости |
| argon2-cffi | 25.1.0 | MIT |
| argon2-cffi-bindings / Argon2 | 26.1.0 | MIT, Apache-2.0/CC0 для соответствующих частей |
| cffi | 2.1.1 | MIT и уведомления libffi |
| PyInstaller bootloader | 6.22.3 | GPLv2 с исключением для собранных приложений |

Полные фактически поставленные уведомления и метаданные копируются в `release-materials/licenses` и в каталог `licenses` архива. Исходные архивы Qt Base, Qt Translations и PySide Setup (включая Shiboken) точной версии 6.12.0 включаются в `library-sources`, вместе с адресами и SHA256. Библиотеки не модифицировались. Архивы исходников не извлекаются и не исполняются при запуске приложения.

Qt подключается динамически: DLL и Qt-плагины находятся отдельно от EXE в `_internal/PySide6`. Пользователь может заменить их совместимыми сборками той же ABI; подпись/хеш приложения не блокируют такую замену. Для отладки изменённой библиотеки разрешена необходимая обратная разработка. Для пересборки библиотек используйте инструкции в исходных архивах соответствующей версии и сохраните имена/размещение DLL и плагинов; зависимости Microsoft runtime должны оставаться совместимыми.

PyInstaller по умолчанию включал дополнительные Qt-плагины. Скрипт сборки оставляет только используемые Core/GUI/Widgets/Network и ограниченный набор плагинов; Qt Virtual Keyboard, Qt PDF, QML/Quick и их плагины исключены. Тестовый `qoffscreen` сохранён для воспроизводимой проверки, `qwindows` — для обычного запуска. Русский перевод `qtbase_ru.qm` сохранён.

Уведомления OpenSSL и сторонних частей Qt/CPython входят в скопированные лицензии и исходные архивы. Microsoft runtime DLL предоставлены как компоненты официальных колёс Python/Qt; права принадлежат Microsoft. Служебные зависимости pytest/pefile/python-pptx и остальные инструменты разработки в программу не импортируются и в поставку намеренно не включаются.

Источники условий: [Qt LGPL](https://www.qt.io/development/open-source-lgpl-obligations), [Virtual Keyboard](https://doc.qt.io/qt-6/qtvirtualkeyboard-index.html), [исключение PyInstaller](https://pyinstaller.org/en/stable/license.html), [исходники PySide6](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/). Это описание состава подготовленной поставки, а не заключение независимого юриста.
