# Версия 0.3.4

Готовые локальные поставки находятся в `releases/0.3.4`: PasswordsManager.exe и
PasswordManager-0.3.4-portable.zip. Контрольные суммы — в manifest.json.
Ничего не опубликовано и не установлено в пользовательский профиль.

## Поведение

Веб-источники этого проекта находятся непосредственно в
`web/password-manager/dist`; изменения применены там. Сайт снаружи ещё не обновлён.
Настройки показывают checkbox справа, ручной обмен под интервалом и сохранение
в самом низу. Записи открываются для просмотра. Категория имеет кнопку настройки,
удаление с подтверждением и выбор цвета; при удалении записи сохраняются.
Цвета остаются локальными зашифрованными настройками, включая экспорт PMVAULT.

Настольная версия поддерживает те же действия, вход через Google в настройках,
а на пустом профиле — открытие версии из Drive с мастер-паролем. OAuth остаётся
через системный браузер с PKCE, state и loopback callback согласно
[официальному протоколу Google](https://developers.google.com/identity/protocols/oauth2/native-app).
Комплектный Desktop client JSON идентифицирует публичный установленный клиент;
он не содержит пользовательских токенов. Google прямо определяет Desktop apps
как public clients, которые не могут хранить конфиденциальный client secret.
Файл не включается в веб-приложение. Локальные пользовательские токены — DPAPI.

## Сборка и проверки

Исходное `.venv` ссылается на недоступный Python из AppData. Для локальной
проверки использован CPython 3.14 из прежней проверенной поставки через
`scripts/local_python.cs` и `scripts/local_python_bootstrap.py`. Новые зависимости
не загружались. Полный pytest в таком ограниченном stdlib не запускался (нет bdb).

`scripts/rebuild_from_bundle.py` заменяет все модули password_manager в архиве
прежнего PyInstaller EXE, сохраняя bootloader и библиотеки, добавляет новый
модуль путей и OAuth JSON. `artifacts/build-034.json` фиксирует исходный EXE,
хеши модулей и результат. Обычный `scripts/build.py` также обновлён для включения
OAuth JSON и остаётся вариантом сборки с полноценным Python.

- Веб-ядро: 16 Node-тестов, включая обмен Python/JS и контроль шифрования.
- Новые настольные сценарии: `artifacts/verification-034.json`; реальные Qt workers,
  собственные вымышленные хранилища, имитация транспорта Drive, неверный пароль,
  просмотр, редактирование, категории, настройки и пути данных.
- Браузер: `web/password-manager/artifacts/browser/result.json`; QtWebEngine
  с отдельным временным профилем, localhost и имитированными Google/Drive.
  Chromium sandbox отключён только для этого изолированного тестового процесса.
- Собранный EXE: `artifacts/frozen-034/smoke-result.json`, offscreen smoke.
- PasswordsManager.exe `--verify <новая-папка>` распаковывает только payload без установки,
  сверяет число файлов и SHA-256. Проверка выполнена в рабочей папке проекта.

Установщик собран локальным .NET Framework csc, доступным в Windows. Он пишет
только в пользовательские Programs/Start Menu и HKCU Uninstall при явном запуске
установки пользователем. Проверяется отсутствие reparse points; удаление использует
список установленных файлов и сохраняет `%LOCALAPPDATA%\PersonalPasswordManager`.
Установка, обновление, поиск Windows, удаление и чистая VM ещё не проверены.
Реальное OAuth-согласие и обмен с настоящим Google Drive также не проверены.

## Повторение

Из корня: собрать `scripts/local_python.cs` в `build/local-python.exe` локальным
csc, затем выполнить `build/local-python.exe scripts/verify_034.py`,
`build/local-python.exe scripts/rebuild_from_bundle.py` и
`build/local-python.exe scripts/package_034.py`. Первая поставка
`dist/PasswordManager` служит базой и не перезаписывается.
Для Node-тестов из `web/password-manager` укажите `PM_TEST_PYTHON` равным
абсолютному пути `build/local-python.exe` и выполните `node --test tests/*.test.mjs`.
