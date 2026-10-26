# Менеджер паролей

Версия 0.38. Менеджер паролей для Windows x64 на Python и PySide6. Хранит записи в зашифрованном локальном хранилище и поддерживает синхронизацию через Google Drive. Отдельная [веб-версия](web/password-manager/README.md) работает с файлами того же формата PMVAULT.

Возможности:

- Записи с отдельными полями сайта, логина, почты, телефона, пароля и заметки.
- Вложенные категории с перетаскиванием и сворачиванием, цветные названия записей, поиск и темы.
- Генератор паролей, корзина, импорт JSON и зашифрованный экспорт.
- Мастер-пароль, ключ восстановления, автоматическая блокировка, закрытие в трей и восемь резервных состояний.
- Синхронизация с сохранением конфликтующих версий и работа без интернета.

## Установка

Версия 0.38: [установщик PasswordsManager.exe](https://github.com/Ramaifs/PasswordsManager/releases/download/v0.38/PasswordsManager.exe) или [portable ZIP](https://github.com/Ramaifs/PasswordsManager/releases/download/v0.38/PasswordManager-0.38-portable.zip). В переносимой версии запустите `PasswordManager.exe` рядом с каталогом `_internal`. Python для готовой сборки не нужен.

Данные хранятся отдельно от программы: `%LOCALAPPDATA%\PersonalPasswordManager`. При создании хранилища сохраните ключ восстановления отдельно. Подробности — в [инструкции пользователя](USER_GUIDE.md).

Локальная сборка 0.38: `releases/0.38/PasswordsManager.exe` и `releases/0.38/PasswordManager-0.38-portable.zip`. Для длительного входа Google на сайте нужна [настройка Worker](deployment/cloudflare-worker/README.md).

## Разработка

Требуется Python 3.14 x64:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\password-manager.exe
```

Проверки:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/tests.xml
.\.venv\Scripts\python.exe -m pip check
```

Сборка: `scripts/build.py`. Проверка собранного приложения: `scripts/check_bundle.py`. Подготовка лицензий и архива: `scripts/collect_licenses.py` и `scripts/package_release.py`. Полная локальная проверка: `scripts/verify.py`.

Автотесты используют Qt offscreen и имитацию Drive. Реальный вход Google, обмен между двумя компьютерами, сон и блокировка Windows требуют отдельной проверки. Независимый аудит безопасности не проводился; для испытаний используйте вымышленные данные. [Результаты и ограничения](docs/verification.md).

## Документация

- [Инструкция пользователя](USER_GUIDE.md).
- [Требования](PLAN.md) и [термины](GLOSSARY.md).
- [Формат хранилища](docs/vault-format.md) и [протокол синхронизации](docs/sync-protocol.md).
- [Настройка Google OAuth](docs/google-setup.md).
- [Веб-версия](docs/web.md) и [размещение на Cloudflare](deployment/cloudflare-pages/README.md).
- [Архитектурные решения](docs/adr/0004-pyside6-arr.md).
- [История изменений](CHANGELOG.md) и [изменения версии 0.38](docs/release-0.38.md).

Исходный консольный проект: [Ramaifs/Passwords-Manager](https://github.com/Ramaifs/Passwords-Manager). Его JSON-формат поддерживается при импорте; пример с вымышленными данными — [legacy-demo.json](examples/legacy-demo.json).

Собственный код распространяется на условиях [All Rights Reserved](LICENSE.txt). Установка и использование готовой программы бесплатны; публичный доступ к исходникам не разрешает их изменение и распространение. [Лицензии сторонних компонентов](THIRD_PARTY_NOTICES.md).
