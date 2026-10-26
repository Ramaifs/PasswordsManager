# Менеджер паролей

Настольная реализация 0.35 на Python/PySide6 для Windows x64 и отдельная первая [веб-версия](docs/web.md). В Windows есть локальное зашифрованное хранилище, русский GUI, импорт/экспорт, резервные состояния, восстановление и код синхронизации с Google Drive: причинные версии, очередь, конфликты, OAuth/DPAPI. Самостоятельный EXE собран и проверен в offscreen-режиме. OAuth-клиент настроен; реальный вход Google ещё не проверен. Веб-версия начинает с создания хранилища в стиле Obsidian и совместима по файлам PMVAULT. До внешней/ручной приёмки используйте вымышленные данные.

Готовые версии 0.35: [PasswordsManager.exe](https://github.com/Ramaifs/PasswordsManager/releases/download/v0.35/PasswordsManager.exe) и [portable ZIP](https://github.com/Ramaifs/PasswordsManager/releases/download/v0.35/PasswordManager-0.35-portable.zip). [Изменения и проверки](docs/release-0.35.md).

**Лицензия собственного кода: All Rights Reserved (ARR).** Публичный доступ к репозиторию не предоставляет разрешение изменять или распространять собственный код проекта. [Условия](LICENSE.txt); [сторонние компоненты](THIRD_PARTY_NOTICES.md).

Репозиторий: [Ramaifs/PasswordsManager](https://github.com/Ramaifs/PasswordsManager). В приложении есть проверка новых стабильных релизов; установка обновления выполняется пользователем.

## Запуск

Готовая переносимая сборка: распакуйте ZIP из `releases` и запустите `PasswordManager.exe` рядом с `_internal`. Python не требуется. [Инструкция пользователя](USER_GUIDE.md), [текущий протокол](docs/implementation-v0.2.md), [настройка Google](docs/google-setup.md).

После подготовки Python-окружения ниже запуск из исходников:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

Новое окружение (Python 3.14 x64):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\password-manager.exe
```

Данные находятся в `%LOCALAPPDATA%\PersonalPasswordManager`, отдельно от программы. При создании подтвердите мастер-пароль и сохранение отдельно показанного ключа восстановления. Пароль и ключ автоматически на диск не записываются. Один каталог одновременно открывает один экземпляр.

Импорт: «Импорт JSON» → предпросмотр → подтверждение. В [examples/legacy-demo.json](examples/legacy-demo.json) только вымышленные данные. Неизвестные поля и неверные типы отклоняются целиком; источник не изменяется.

Экспорт — зашифрованный `.pmvault`. На новом компьютере его можно открыть при первоначальной настройке кнопкой «Открыть зашифрованный экспорт», введя соответствующий мастер-пароль. Объединение экспорта с существующим хранилищем пока отсутствует. Смена секретов не меняет ранее экспортированные файлы.

«Резервные копии» показывает количество добавленных, удалённых и изменённых записей перед восстановлением. При повреждении актуального файла доступно восстановление читающейся копии на экране блокировки; исходные зашифрованные файлы сохраняются в `damaged-*`. Эти исходники не входят в восемь управляемых состояний и автоматически не обновляются при смене секретов.

## Проверки

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/tests.xml
.\.venv\Scripts\python.exe -m pip check
```

GUI проверяется через Qt offscreen; буфер обмена подменён фикстурой. Собранный EXE проверен отдельно с очищенным PATH и зависимостями внутри поставки, без прав администратора. Это не чистая VM, реальный буфер Windows, блокировка сеанса, сон или настоящий Drive. Подробности: [текущий протокол](docs/implementation-v0.2.md), [историческая 0.1](docs/implementation.md), [формат](docs/vault-format.md), [синхронизация](docs/sync-protocol.md).

Повторяемая проверка и хеши: `.\.venv\Scripts\python.exe scripts\verify.py`. Сборка: `scripts/build.py`, проверочный запуск сборки: `scripts/check_bundle.py`, лицензии/исходники библиотек: `scripts/collect_licenses.py`, архив: `scripts/package_release.py`. Последние два сценария не публикуют и не устанавливают программу; сбор исходников LGPL-библиотек читает официальные серверы Qt.

## Документы

- [Согласованный план](PLAN.md).
- [История согласования](docs/design-session.md).
- [Словарь](GLOSSARY.md).
- [Проверка исходного репозитория](docs/baseline.md).
- [Матрица приёмки](docs/verification.md).
- [Архитектурные решения](docs/adr/0004-pyside6-arr.md).
- [История изменений](CHANGELOG.md).

Исходный проект: [Ramaifs/Passwords-Manager](https://github.com/Ramaifs/Passwords-Manager), проверенный commit `eab2103453ddca4e3dadf2998130bddca544eb76`. Новый код написан самостоятельно; файлы исходного проекта не копировались. [Условия собственного кода](LICENSE.txt), [сторонние уведомления](THIRD_PARTY_NOTICES.md), [отчёт](docs/project-report.md), [сценарий презентации](docs/presentation.md). PPTX пока не экспортирован из-за недоступности требуемого presentation runtime.
