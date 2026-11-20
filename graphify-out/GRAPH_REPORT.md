# Graph Report - Password Manager  (2026-11-20)

## Corpus Check
- 172 files · ~107,310 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 4, .xml 2, .css 2)

## Summary
- 1799 nodes · 4615 edges · 123 communities (75 shown, 48 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 474 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- core.js
- session.test.mjs
- SyncUI
- MainActivity
- VaultError
- test_gui.py
- InvalidVault
- .refresh_entries
- Window
- Setup
- InvalidVault
- session.mjs
- app.py
- pytest
- app.js
- SyncError
- .build_editor
- README.md
- pathlib
- showModal
- hash-wasm.js
- deleteVault
- UpdateChecker
- История изменений
- browser_qa.py
- sync.test.mjs
- .toast
- google.js
- CategoryList
- esc
- cloudflare-pages/README.md
- stylesheet
- doUnlock
- Подготовка Google Drive для Windows и сайта
- benchmark-drive.mjs
- __awaiter
- Настольный менеджер паролей — сценарий презентации
- package.json
- Требования к менеджеру паролей
- ref_node_test
- Менеджер паролей 0.41 — инструкция
- WindowsEvents
- Разработка настольного менеджера паролей
- Проверка 0.38
- 0007-drive-versions.md
- Проверка 0.39
- test_search.py
- test_clipboard_timer_preserves_new_content
- Реализация 0.2.0 и обновление 0.2.1
- 0.35: подкатегории, настройки приложения и обновления
- Проверка 0.40
- Web 0.36: именованные хранилища, файл и Google Drive
- .lock
- Transport
- Google-сессии на Cloudflare Worker
- Проверка исходного репозитория
- Доступ к Google Drive через разрешение пользователя
- BundleFinder
- lockedCreate
- Версия 0.3.4
- WASMInterface
- Протокол синхронизации v1
- Менеджер паролей
- category-navigation-verification.md
- release-0.40.md
- oauth.py
- personal-password-manager
- model.py
- listCloud
- NumberInput
- syncDrive
- pbkdf2
- android/package.json
- createBLAKE2b
- blake2s
- crc64
- createXXHash128
- createXXHash3
- createXXHash64
- Mutex
- Checks
- verification-0.43.1.md
- createKeccak
- decodeBase64
- scrypt
- cloudflare-worker/README.md
- Протокол первой реализации
- records
- verification-0.43.2.md
- package-permissions.test.mjs
- SyncSchedule
- verification-0.42.5.md
- verification-0.43.0.md
- crypto.py
- updates.py

## God Nodes (most connected - your core abstractions)
1. `Window` - 100 edges
2. `VaultError` - 94 edges
3. `InvalidVault` - 44 edges
4. `Store` - 41 edges
5. `canonical()` - 38 edges
6. `SyncEngine` - 36 edges
7. `WASMInterface()` - 33 edges
8. `unlock()` - 31 edges
9. `SyncUI` - 29 edges
10. `SyncError` - 27 edges

## Surprising Connections (you probably didn't know these)
- `Содержимое и сохранение` --references--> `additional_fields()`  [INFERRED]
  docs/vault-format.md → src/password_manager/model.py
- `Синхронизация: общая логика двух клиентов` --references--> `IOThread`  [INFERRED]
  ARCHITECTURE.md → src/password_manager/sync_ui.py
- `Windows: интерфейс и управление состоянием` --references--> `Store`  [INFERRED]
  ARCHITECTURE.md → src/password_manager/storage.py
- `window()` --uses--> `Window`  [INFERRED]
  tests/test_gui.py → src/password_manager/app.py
- `test_switch_archives_every_old_snapshot_before_changing_access()` --uses--> `InvalidVault`  [INFERRED]
  tests/test_cloud_backups.py → src/password_manager/errors.py

## Import Cycles
- None detected.

## Communities (123 total, 48 thin omitted)

### Community 1 - "core.js"
Cohesion: 0.07
Nodes (75): normalizeParents(), validateParents(), aes(), b64(), baseHeader(), canonical(), serialize(), changePassword() (+67 more)

### Community 3 - "SyncUI"
Cohesion: 0.07
Nodes (18): backup_time(), copy_times(), display_time(), group_copies(), ordered_copies(), CloudCopiesDialog, CloudPreviewDialog, _dpapi() (+10 more)

### Community 4 - "MainActivity"
Cohesion: 0.06
Nodes (5): AuthFailure, Bridge, MainActivity, WebChromeClient, WebViewClient

### Community 5 - "VaultError"
Cohesion: 0.19
Nodes (10): VaultError, Preferences, github_asset(), redirect_request(), test_last_opened_preference_survives_other_preferences(), test_close_preference_survives_restart_and_can_return_to_ask(), test_damaged_or_oversized_preferences_default_to_question(), test_entry_sort_survives_other_preference_changes() (+2 more)

### Community 6 - "test_gui.py"
Cohesion: 0.06
Nodes (22): app(), seed(), test_close_choice_dialog_and_full_exit_saved(), test_close_dialog_enter_defaults_to_tray(), test_close_to_tray_remembers_choice_locks_and_restores(), test_default_color_is_only_inside_color_picker(), choose(), test_empty_trash_is_one_commit_ignores_search_and_preserves_active() (+14 more)

### Community 7 - "InvalidVault"
Cohesion: 0.06
Nodes (41): Google OAuth и Cloudflare, Windows: интерфейс и управление состоянием, Архитектура проекта Password Manager, Где что находится, Общая схема, Просмотр резервных копий и последнее открытое хранилище, С чего начинать изменение, Сборка, поставка и проверки (+33 more)

### Community 8 - ".refresh_entries"
Cohesion: 0.12
Nodes (10): save_settings(), category_path(), category_rows(), test_all_entries_category_color_caption_and_named_export(), test_category_arrow_click_drag_drop_and_root_move(), test_category_move_menu_excludes_descendants_and_keeps_subtree(), test_category_sort_groups_paths_and_keeps_unsaved_editor(), test_ctrl_shift_selection_bulk_actions_and_delete_only_selected() (+2 more)

### Community 9 - "Window"
Cohesion: 0.08
Nodes (15): configure_app(), main(), Window, application_icon(), new_document(), run(), test_autocomplete_uses_vault_values_and_clears_when_locked(), test_bulk_clipboard_and_additional_draft_reopen() (+7 more)

### Community 10 - "Setup"
Cohesion: 0.11
Nodes (3): LocalPython, Setup, Version

### Community 11 - "InvalidVault"
Cohesion: 0.07
Nodes (45): normalize_category_parents(), validate(), AccessConflict, digest(), conflicts(), empty(), state_id(), identifier() (+37 more)

### Community 12 - "session.mjs"
Cohesion: 0.21
Nodes (25): b64(), codeBody(), configured(), cookie(), decoder, encoder, fetch(), flowCookie() (+17 more)

### Community 13 - "app.py"
Cohesion: 0.06
Nodes (15): save_key(), run(), validate_password(), generate(), GeneratorOptions, entry_icon(), preview_legacy(), data_root() (+7 more)

### Community 14 - "pytest"
Cohesion: 0.12
Nodes (13): Session, backup_name(), validate_name(), test_bulk_passwords_keep_spaces_and_stay_out_of_uncategorized(), test_hierarchy_validation_and_parent_rename(), test_move_category_keeps_subtree_entries_and_rejects_cycles_without_mutation(), test_nested_filter_deletion_and_legacy_migration(), test_parent_register_sync_and_concurrent_cycle_is_deterministic() (+5 more)

### Community 15 - "app.js"
Cohesion: 0.06
Nodes (48): additionalFields(), EXTRA_FIELDS, FIELD_LABELS, migrateOldPasswords(), nextPasswordNumber(), splitPasswords(), acceptsCredentialInput(), actions (+40 more)

### Community 16 - "SyncError"
Cohesion: 0.16
Nodes (11): DriveTransport, file_id(), FolderMissing, SyncError, test_drive_lists_all_vaults_and_checks_ciphertext_before_open(), Connection, FakeAPI, test_cancel_prevents_api_calls() (+3 more)

### Community 18 - ".build_editor"
Cohesion: 0.12
Nodes (7): button(), field(), run(), action(), test_customization_saves_theme_and_accent(), test_general_settings_changes_remembered_close_action(), test_generator_does_not_write_vault_or_request_sync()

### Community 19 - "README.md"
Cohesion: 0.13
Nodes (9): Основной интерфейс — настольное приложение на PyQt, PySide6 и All Rights Reserved для собственного кода, Argon2id и AES-256-GCM через cryptography, Проверка 0.42, Матрица приёмки, Первые программные проверки — 2026-10-25, версия 0.1.0, Менеджер паролей, Термины (+1 more)

### Community 20 - "pathlib"
Cohesion: 0.06
Nodes (6): command(), certificate(), _dpapi(), run(), check_asset(), test_inputs()

### Community 21 - "showModal"
Cohesion: 0.15
Nodes (16): bulkDialog(), categoryDialog(), generator(), help(), settings(), showModal(), syncSettingsFields(), validCategoryDrop() (+8 more)

### Community 22 - "hash-wasm.js"
Cohesion: 0.05
Nodes (43): base64Lookup, bcryptVerify(), crc32(), createCRC32(), createXXHash32(), digit, encodeBase64(), encodeResult() (+35 more)

### Community 23 - "deleteVault"
Cohesion: 0.18
Nodes (16): checkIdle(), clearClipboard(), closeModal(), copy(), deleteVault(), error(), importFile(), lock() (+8 more)

### Community 24 - "UpdateChecker"
Cohesion: 0.14
Nodes (8): Синхронизация: общая логика двух клиентов, IOThread, DownloadThread, UpdateChecker, finished(), changed(), start(), finished()

### Community 25 - "История изменений"
Cohesion: 0.08
Nodes (24): 0.42.5, 2026-10-25 — Web 0.1, 2026-10-25 — Web 0.2.1, 2026-10-25 — Web 0.2.2, 2026-10-25 — Web 0.2 / Windows 0.3.0, 2026-10-25 — Windows 0.1.0, 2026-10-25 — Windows 0.2.0, 2026-10-25 — Windows 0.2.1 (+16 more)

### Community 26 - "browser_qa.py"
Cohesion: 0.17
Nodes (10): click(), fill(), js(), Page, process(), Results, screenshot(), submit() (+2 more)

### Community 30 - ".toast"
Cohesion: 0.24
Nodes (6): activate(), guard(), hide_suggestion(), suggestion_sources(), suggestions(), test_deletion_category_opens_actions_and_keeps_updates_below()

### Community 31 - "google.js"
Cohesion: 0.13
Nodes (22): checkUpdates(), driveDialog(), startVaultChecks(), stopDrive(), accept(), authorize(), authorizeRedirect, call() (+14 more)

### Community 34 - "esc"
Cohesion: 0.16
Nodes (29): applyAppearance(), applyEntryColors(), brand(), categoryDots(), entryInView(), esc(), home(), icon() (+21 more)

### Community 35 - "cloudflare-pages/README.md"
Cohesion: 0.18
Nodes (6): Перенос сайта на Cloudflare, Cloudflare Worker, Ограничение доступа, Мобильное дополнение 0.41 · 2026-11-01, Версия 0.41, Проверка версии 0.41

### Community 36 - "stylesheet"
Cohesion: 0.25
Nodes (4): navigation_icon(), stylesheet(), test_long_category_has_no_horizontal_scrollbar_or_corner(), test_checked_indicator_has_contrasting_tick_and_accent_background()

### Community 37 - "doUnlock"
Cohesion: 0.17
Nodes (26): ask(), checkEntrySpaces(), clone(), confirmLeave(), deleteCloudVault(), deleteSelectedRecords(), doUnlock(), download() (+18 more)

### Community 38 - "Подготовка Google Drive для Windows и сайта"
Cohesion: 0.40
Nodes (5): Веб-клиент, Доступ через разрешение без платёжной карты, Настройка разработчиком, Подготовка Google Drive для Windows и сайта, Сохранение веб-сессии

### Community 39 - "benchmark-drive.mjs"
Cohesion: 0.18
Nodes (5): ../dist/cloud-backups.js?reload, fixture(), measure(), previous, report

### Community 40 - "__awaiter"
Cohesion: 0.17
Nodes (20): argon2d(), argon2i(), argon2Internal(), argon2Verify(), __awaiter(), adopt(), fulfilled(), rejected() (+12 more)

### Community 41 - "Настольный менеджер паролей — сценарий презентации"
Cohesion: 0.17
Nodes (11): Настольный менеджер паролей — сценарий презентации, Слайд 10. Текущее состояние, Слайд 1. Менеджер паролей для Windows, Слайд 2. Требования, Слайд 3. Настольный интерфейс, Слайд 4. Шифрование и восстановление, Слайд 5. Сохранение при сбое, Слайд 6. Независимые изменения (+3 more)

### Community 42 - "package.json"
Cohesion: 0.18
Nodes (11): hash-wasm, dependencies, hash-wasm@4.12.0, name, private, scripts, dev, test (+3 more)

### Community 43 - "Требования к менеджеру паролей"
Cohesion: 0.18
Nodes (11): 10. Документы и оставшаяся инженерная работа, 1. Цель и границы версии, 2. Записи и интерфейс, 3. Генератор, 4. Защита и восстановление доступа, 5. Локальное хранение, удаление и импорт, 6. Google Drive, 7. Поставка и условия (+3 more)

### Community 45 - "Менеджер паролей 0.41 — инструкция"
Cohesion: 0.18
Nodes (11): Google Drive, Возможности 0.41, Записи, генератор и корзина, Запуск и данные, Импорт, экспорт и резервные состояния, Интерфейс, Категории и трей в версии 0.39, Копии Google Drive (+3 more)

### Community 48 - "Разработка настольного менеджера паролей"
Cohesion: 0.22
Nodes (9): Архитектура, Введение, Вывод по текущему состоянию, Защита данных, Надёжность локального сохранения, Проверки и поставка, Разработка настольного менеджера паролей, Синхронизация и конфликты (+1 more)

### Community 49 - "Проверка 0.38"
Cohesion: 0.22
Nodes (7): Версия 0.38, Google OAuth, Windows, Проверка 0.38, Результаты, Сайт, Цвета категорий

### Community 50 - "0007-drive-versions.md"
Cohesion: 0.29
Nodes (4): Локальная рабочая копия и прямое подключение к Google Drive, Конфликты записей требуют выбора пользователя, Аварийная замена ключа восстановления меняет ключ данных, Отдельные зашифрованные версии в Google Drive

### Community 51 - "Проверка 0.39"
Cohesion: 0.25
Nodes (6): Версия 0.39, Итоговые результаты, Облачные копии, Последнее открытие, Проверка 0.39, Просмотр и переключение

### Community 52 - "test_search.py"
Cohesion: 0.47
Nodes (3): test_search_finds_number_in_note_without_phone_field(), test_search_finds_text_in_every_record_field_without_modifying_document(), test_search_matches_phone_with_different_formatting()

### Community 54 - "Реализация 0.2.0 и обновление 0.2.1"
Cohesion: 0.33
Nodes (6): Проверки, Реализация 0.2.0 и обновление 0.2.1, Реализованный результат, Сборка и поставка, Сохраняющиеся ограничения, Что ещё не принято

### Community 55 - "0.35: подкатегории, настройки приложения и обновления"
Cohesion: 0.33
Nodes (5): 0.35: подкатегории, настройки приложения и обновления, Обновления и публичный код, Проверки и границы, Сборка, Совместимость и синхронизация

### Community 56 - "Проверка 0.40"
Cohesion: 0.33
Nodes (5): Итоговые результаты, Облачные копии, Последнее открытие, Проверка 0.40, Просмотр и переключение

### Community 57 - "Web 0.36: именованные хранилища, файл и Google Drive"
Cohesion: 0.33
Nodes (6): Drive, Web 0.36: именованные хранилища, файл и Google Drive, Проверка, Старые браузерные хранилища, Удаление, Файл на ПК

### Community 58 - ".lock"
Cohesion: 0.50
Nodes (3): Конверт и ключи, Локальный формат PMVAULT v1, Содержимое и сохранение

### Community 60 - "Google-сессии на Cloudflare Worker"
Cohesion: 0.40
Nodes (5): Google-сессии на Cloudflare Worker, Диагностика подключения, Настройка, Пошагово в Windows, Проверка после размещения

### Community 61 - "Проверка исходного репозитория"
Cohesion: 0.40
Nodes (4): README и ограничения проверки, Генератор, Менеджер, Проверка исходного репозитория

### Community 62 - "Доступ к Google Drive через разрешение пользователя"
Cohesion: 0.40
Nodes (4): Вывод, Доступ к Google Drive через разрешение пользователя, Карта и billing, Подход для этого проекта

### Community 64 - "lockedCreate"
Cohesion: 0.11
Nodes (18): adler32(), blake3(), createBLAKE3(), createSHA3(), lockedCreate(), md4(), md5(), ripemd160() (+10 more)

### Community 65 - "Версия 0.3.4"
Cohesion: 0.40
Nodes (4): Версия 0.3.4, Поведение, Повторение, Сборка и проверки

### Community 66 - "WASMInterface"
Cohesion: 0.14
Nodes (16): createAdler32(), createMD4(), createMD5(), createRIPEMD160(), createSHA1(), createSHA224(), createSHA256(), createSHA384() (+8 more)

### Community 67 - "Протокол синхронизации v1"
Cohesion: 0.50
Nodes (4): Очистка и транспорт, Причинные состояния, Протокол синхронизации v1, Публикация и доступ

### Community 68 - "Менеджер паролей"
Cohesion: 0.50
Nodes (4): Документация, Менеджер паролей, Разработка, Установка

### Community 71 - "oauth.py"
Cohesion: 0.15
Nodes (12): recovery_secret(), authorize(), get_request(), bearer(), config(), exchange_code(), validate_token(), verifier_pair() (+4 more)

### Community 75 - "model.py"
Cohesion: 0.08
Nodes (31): remove(), operation(), show(), operation(), additional_fields(), bulk_edit(), category(), category_descendants() (+23 more)

### Community 76 - "listCloud"
Cohesion: 0.24
Nodes (13): connectDrive(), driveTransport(), listCloud(), backupTime(), copyTimes(), displayTime(), groupCopies(), lastOpenedVault() (+5 more)

### Community 79 - "syncDrive"
Cohesion: 0.24
Nodes (13): changeList(), checkAutoSync(), checkRemoteChanges(), commitSyncStage(), requireSyncVault(), rpc(), savedStatus(), startDriveJob() (+5 more)

### Community 80 - "pbkdf2"
Cohesion: 0.40
Nodes (5): calculateHmac(), calculateKeyBuffer(), createHMAC(), pbkdf2(), validateOptions$2()

### Community 81 - "android/package.json"
Cohesion: 0.40
Nodes (4): name, private, type, version

### Community 82 - "createBLAKE2b"
Cohesion: 0.67
Nodes (4): blake2b(), createBLAKE2b(), getInitParam$1(), validateBits$4()

### Community 83 - "blake2s"
Cohesion: 0.67
Nodes (4): blake2s(), createBLAKE2s(), getInitParam(), validateBits$3()

### Community 84 - "crc64"
Cohesion: 0.67
Nodes (4): crc64(), createCRC64(), parsePoly(), writePoly()

### Community 85 - "createXXHash128"
Cohesion: 0.67
Nodes (4): createXXHash128(), validateSeed(), writeSeed(), xxhash128()

### Community 86 - "createXXHash3"
Cohesion: 0.67
Nodes (4): createXXHash3(), validateSeed$1(), writeSeed$1(), xxhash3()

### Community 87 - "createXXHash64"
Cohesion: 0.67
Nodes (4): createXXHash64(), validateSeed$2(), writeSeed$2(), xxhash64()

### Community 91 - "createKeccak"
Cohesion: 0.67
Nodes (3): createKeccak(), keccak(), validateBits()

### Community 92 - "decodeBase64"
Cohesion: 1.00
Nodes (3): decodeBase64(), getDecodeBase64Length(), getHashParameters()

### Community 93 - "scrypt"
Cohesion: 0.67
Nodes (3): isPowerOfTwo(), scrypt(), validateOptions$1()

### Community 94 - "cloudflare-worker/README.md"
Cohesion: 0.14
Nodes (10): Password Manager Android 0.42, Загрузка и проверка, Подготовка, Размещение на Cloudflare, Версия 0.36, Поставка и проверки, Версия 0.37, Веб-версия (+2 more)

### Community 105 - "Протокол первой реализации"
Cohesion: 0.40
Nodes (5): Проверки, Продолжение и ограничения, Протокол первой реализации, Реализация, Среда

### Community 112 - "package-permissions.test.mjs"
Cohesion: 0.16
Nodes (5): root, port, root, types, sourceRoot

### Community 123 - "crypto.py"
Cohesion: 0.14
Nodes (25): Access, b64(), canonical(), checked_envelope(), derive(), _pairs(), recovery_bytes(), seal() (+17 more)

### Community 127 - "updates.py"
Cohesion: 0.13
Nodes (17): parse(), HttpError, json_request(), request(), download_release(), _latest_manifest(), latest_release(), release_versions() (+9 more)

## Knowledge Gaps
- **5 isolated node(s):** `personal-password-manager`, `Version`, `records`, `../dist/storage.js?fresh-session`, `../dist/cloud-backups.js?reload`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 579 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **48 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Архитектура проекта Password Manager` connect `InvalidVault` to `UpdateChecker`, `README.md`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Window` (e.g. with `test_create_with_eight_character_master()` and `test_open_export_in_empty_profile()`) actually correct?**
  _`Window` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `personal-password-manager`, `Version`, `records` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `core.js` be split into smaller, more focused modules?**
  _Cohesion score 0.06794783802333562 - nodes in this community are weakly interconnected._
- **Why does `Store` connect `InvalidVault` to `Window`, `crypto.py`, `app.py`, `test_gui.py`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `VaultError` (e.g. with `Access` and `Preferences`) actually correct?**
  _`VaultError` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Should `SyncUI` be split into smaller, more focused modules?**
  _Cohesion score 0.06746031746031746 - nodes in this community are weakly interconnected._