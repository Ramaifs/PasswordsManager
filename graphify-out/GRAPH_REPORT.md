# Graph Report - Password Manager  (2026-11-17)

## Corpus Check
- 161 files · ~101,014 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 4, .xml 2, .css 2)

## Summary
- 1700 nodes · 4370 edges · 110 communities (73 shown, 37 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 476 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- core.js
- test_sync.py
- SyncUI
- MainActivity
- VaultError
- test_gui.py
- Store
- .refresh_entries
- Window
- Setup
- sync_ui.py
- session.mjs
- app.py
- pytest
- app.js
- crypto.py
- .build_editor
- README.md
- json
- SyncError
- hash-wasm.js
- .save
- test_search.py
- История изменений
- browser_qa.py
- sync.test.mjs
- os
- bulk-entries.test.mjs
- google.js
- CategoryList
- esc
- cloudflare-pages/README.md
- showModal
- doUnlock
- Подготовка Google Drive для Windows и сайта
- benchmark-drive.mjs
- __awaiter
- Настольный менеджер паролей — сценарий презентации
- package.json
- Требования к менеджеру паролей
- ref_node_test
- Менеджер паролей 0.41 — инструкция
- test_network_recovery.py
- Разработка настольного менеджера паролей
- Проверка 0.38
- 0007-drive-versions.md
- Проверка 0.39
- verify_034.py
- build_android.py
- Реализация 0.2.0 и обновление 0.2.1
- 0.35: подкатегории, настройки приложения и обновления
- Проверка 0.40
- Web 0.36: именованные хранилища, файл и Google Drive
- Google-сессии на Cloudflare Worker
- Проверка исходного репозитория
- Доступ к Google Drive через разрешение пользователя
- Протокол первой реализации
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
- SyncSchedule
- pbkdf2
- android/package.json
- createBLAKE2b
- blake2s
- crc64
- createXXHash128
- createXXHash3
- createXXHash64
- Mutex
- generate
- .choose_close_action
- createKeccak
- decodeBase64
- scrypt
- cloudflare-worker/README.md
- records

## God Nodes (most connected - your core abstractions)
1. `VaultError` - 94 edges
2. `Window` - 94 edges
3. `InvalidVault` - 46 edges
4. `Store` - 41 edges
5. `canonical()` - 38 edges
6. `SyncEngine` - 33 edges
7. `WASMInterface()` - 33 edges
8. `unlock()` - 31 edges
9. `SyncUI` - 29 edges
10. `SyncError` - 27 edges

## Surprising Connections (you probably didn't know these)
- `Синхронизация: общая логика двух клиентов` --references--> `IOThread`  [INFERRED]
  ARCHITECTURE.md → src/password_manager/sync_ui.py
- `Windows: интерфейс и управление состоянием` --references--> `Store`  [INFERRED]
  ARCHITECTURE.md → src/password_manager/storage.py
- `Содержимое и сохранение` --references--> `additional_fields()`  [INFERRED]
  docs/vault-format.md → src/password_manager/model.py
- `limited()` --calls--> `HttpError`  [INFERRED]
  tests/test_network_recovery.py → src/password_manager/http_client.py
- `fail()` --calls--> `StorageError`  [INFERRED]
  tests/test_gui.py → src/password_manager/errors.py

## Import Cycles
- None detected.

## Communities (110 total, 37 thin omitted)

### Community 1 - "core.js"
Cohesion: 0.07
Nodes (70): normalizeParents(), aes(), b64(), baseHeader(), canonical(), serialize(), changePassword(), charLength() (+62 more)

### Community 2 - "test_sync.py"
Cohesion: 0.17
Nodes (22): SyncEngine, align(), MemoryDrive, test_category_and_subcategory_colors_roundtrip_drive(), test_cleanup_does_not_remove_unresolved_contributors(), test_concurrent_cleanup_views_keep_eight_covering_states(), test_concurrent_color_changes_resolve_without_resurrection(), test_conflict_requires_explicit_choice() (+14 more)

### Community 3 - "SyncUI"
Cohesion: 0.10
Nodes (11): CloudPreviewDialog, _dpapi(), ProtectedConnection, SyncUI, connected(), fetch_copies(), received(), connected() (+3 more)

### Community 4 - "MainActivity"
Cohesion: 0.06
Nodes (4): Bridge, MainActivity, WebChromeClient, WebViewClient

### Community 5 - "VaultError"
Cohesion: 0.06
Nodes (39): Синхронизация: общая логика двух клиентов, _pairs(), parse(), VaultError, HttpError, json_request(), request(), preview_legacy() (+31 more)

### Community 6 - "test_gui.py"
Cohesion: 0.05
Nodes (21): test_autocomplete_uses_vault_values_and_clears_when_locked(), test_category_arrow_click_drag_drop_and_root_move(), test_category_sort_groups_paths_and_keeps_unsaved_editor(), seed(), test_close_choice_dialog_and_full_exit_saved(), test_customization_saves_theme_and_accent(), test_default_color_is_only_inside_color_picker(), choose() (+13 more)

### Community 7 - "Store"
Cohesion: 0.06
Nodes (51): Google OAuth и Cloudflare, Windows: интерфейс и управление состоянием, Архитектура проекта Password Manager, Где что находится, Общая схема, Просмотр резервных копий и последнее открытое хранилище, С чего начинать изменение, Сборка, поставка и проверки (+43 more)

### Community 8 - ".refresh_entries"
Cohesion: 0.17
Nodes (8): category(), category_descendants(), category_path(), category_rows(), move_category(), test_category_move_menu_excludes_descendants_and_keeps_subtree(), test_ctrl_shift_selection_bulk_actions_and_delete_only_selected(), test_sidebar_context_actions_and_nested_categories()

### Community 9 - "Window"
Cohesion: 0.13
Nodes (5): Window, save_settings(), test_all_entries_category_color_caption_and_named_export(), test_close_to_tray_remembers_choice_locks_and_restores(), test_window_mode_survives_minimize_tray_and_restart()

### Community 10 - "Setup"
Cohesion: 0.11
Nodes (3): LocalPython, Setup, Version

### Community 11 - "sync_ui.py"
Cohesion: 0.11
Nodes (23): checked_envelope(), unb64(), normalize_category_parents(), AccessConflict, digest(), header_id(), conflicts(), empty() (+15 more)

### Community 12 - "session.mjs"
Cohesion: 0.21
Nodes (25): b64(), codeBody(), configured(), cookie(), decoder, encoder, fetch(), flowCookie() (+17 more)

### Community 13 - "app.py"
Cohesion: 0.11
Nodes (10): configure_app(), main(), validate_password(), application_icon(), entry_icon(), navigation_icon(), run(), stylesheet() (+2 more)

### Community 14 - "pytest"
Cohesion: 0.12
Nodes (15): Blob, backup_name(), validate_name(), test_additional_fields_encryption_search_sync_and_validation(), test_bulk_passwords_keep_spaces_and_stay_out_of_uncategorized(), test_hierarchy_validation_and_parent_rename(), test_move_category_keeps_subtree_entries_and_rejects_cycles_without_mutation(), test_nested_filter_deletion_and_legacy_migration() (+7 more)

### Community 15 - "app.js"
Cohesion: 0.08
Nodes (30): additionalFields(), EXTRA_FIELDS, FIELD_LABELS, migrateOldPasswords(), nextPasswordNumber(), splitPasswords(), actions, app (+22 more)

### Community 16 - "crypto.py"
Cohesion: 0.17
Nodes (17): Access, b64(), canonical(), derive(), recovery_bytes(), recovery_secret(), seal(), unlock() (+9 more)

### Community 18 - ".build_editor"
Cohesion: 0.13
Nodes (6): button(), field(), save_key(), action(), backup_diff(), test_danger_actions_are_last_and_sync_success_is_green()

### Community 19 - "README.md"
Cohesion: 0.11
Nodes (12): Основной интерфейс — настольное приложение на PyQt, PySide6 и All Rights Reserved для собственного кода, Argon2id и AES-256-GCM через cryptography, Версия 0.42, Конверт и ключи, Локальный формат PMVAULT v1, Проверка 0.42, Матрица приёмки (+4 more)

### Community 20 - "json"
Cohesion: 0.10
Nodes (3): command(), check_asset(), test_inputs()

### Community 21 - "SyncError"
Cohesion: 0.15
Nodes (13): DriveTransport, file_id(), FolderMissing, SyncError, test_drive_lists_all_vaults_and_checks_ciphertext_before_open(), Connection, FakeAPI, test_cancel_prevents_api_calls() (+5 more)

### Community 22 - "hash-wasm.js"
Cohesion: 0.05
Nodes (43): base64Lookup, bcryptVerify(), crc32(), createCRC32(), createXXHash32(), digit, encodeBase64(), encodeResult() (+35 more)

### Community 23 - ".save"
Cohesion: 0.08
Nodes (14): Содержимое и сохранение, remove(), operation(), test_bulk_clipboard_and_additional_draft_reopen(), test_clipboard_timer_preserves_new_content(), test_crud_lock_draft_and_resume(), test_extra_only_password_remains_visible_and_revealable(), test_extra_password_fields_mask_copy_save_reopen_and_lock() (+6 more)

### Community 24 - "test_search.py"
Cohesion: 0.47
Nodes (3): test_search_finds_number_in_note_without_phone_field(), test_search_finds_text_in_every_record_field_without_modifying_document(), test_search_matches_phone_with_different_formatting()

### Community 25 - "История изменений"
Cohesion: 0.10
Nodes (21): 2026-10-25 — Web 0.1, 2026-10-25 — Web 0.2.1, 2026-10-25 — Web 0.2.2, 2026-10-25 — Web 0.2 / Windows 0.3.0, 2026-10-25 — Windows 0.1.0, 2026-10-25 — Windows 0.2.0, 2026-10-25 — Windows 0.2.1, 2026-10-25 — Windows 0.3.1 (+13 more)

### Community 26 - "browser_qa.py"
Cohesion: 0.17
Nodes (10): click(), fill(), js(), Page, process(), Results, screenshot(), submit() (+2 more)

### Community 30 - "bulk-entries.test.mjs"
Cohesion: 0.13
Nodes (4): port, root, types, sourceRoot

### Community 31 - "google.js"
Cohesion: 0.12
Nodes (26): checkAutoSync(), checkRemoteChanges(), connectDrive(), driveDialog(), driveTransport(), settings(), stopDrive(), syncDrive() (+18 more)

### Community 34 - "esc"
Cohesion: 0.16
Nodes (28): applyAppearance(), applyEntryColors(), brand(), esc(), home(), icon(), initials(), listActions() (+20 more)

### Community 35 - "cloudflare-pages/README.md"
Cohesion: 0.18
Nodes (6): Перенос сайта на Cloudflare, Cloudflare Worker, Ограничение доступа, Мобильное дополнение 0.41 · 2026-11-01, Версия 0.41, Проверка версии 0.41

### Community 36 - "showModal"
Cohesion: 0.16
Nodes (15): bulkDialog(), categoryDialog(), generator(), help(), showModal(), validCategoryDrop(), categoryRows(), descendants() (+7 more)

### Community 37 - "doUnlock"
Cohesion: 0.10
Nodes (41): ask(), checkIdle(), clearClipboard(), clone(), closeModal(), commitSyncStage(), confirmLeave(), copy() (+33 more)

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

### Community 46 - "test_network_recovery.py"
Cohesion: 0.22
Nodes (4): test_expired_google_grant_requires_reconnect_without_deleting_connection(), test_update_check_and_version_picker_survive_github_api_rate_limit(), limited(), test_update_fallback_rejects_invalid_installer_metadata()

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

### Community 52 - "verify_034.py"
Cohesion: 0.11
Nodes (3): Checks, Transport, test_wheel_requires_click_and_loses_permission_on_focus_out()

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

### Community 60 - "Google-сессии на Cloudflare Worker"
Cohesion: 0.40
Nodes (5): Google-сессии на Cloudflare Worker, Диагностика подключения, Настройка, Пошагово в Windows, Проверка после размещения

### Community 61 - "Проверка исходного репозитория"
Cohesion: 0.40
Nodes (4): README и ограничения проверки, Генератор, Менеджер, Проверка исходного репозитория

### Community 62 - "Доступ к Google Drive через разрешение пользователя"
Cohesion: 0.40
Nodes (4): Вывод, Доступ к Google Drive через разрешение пользователя, Карта и billing, Подход для этого проекта

### Community 63 - "Протокол первой реализации"
Cohesion: 0.40
Nodes (5): Проверки, Продолжение и ограничения, Протокол первой реализации, Реализация, Среда

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
Cohesion: 0.19
Nodes (7): authorize(), get_request(), bearer(), config(), exchange_code(), validate_token(), test_oauth_config_rejects_foreign_endpoint()

### Community 75 - "model.py"
Cohesion: 0.09
Nodes (27): operation(), show(), backup_time(), display_time(), group_copies(), ordered_copies(), CloudCopiesDialog, additional_fields() (+19 more)

### Community 76 - "listCloud"
Cohesion: 0.42
Nodes (8): listCloud(), backupTime(), displayTime(), groupCopies(), lastOpenedVault(), orderedCopies(), rememberOpenedVault(), uuid()

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

### Community 89 - "generate"
Cohesion: 0.18
Nodes (7): run(), WindowsEvents, generate(), GeneratorOptions, test_bad_generator(), test_generator(), test_similar_exclusion()

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

## Knowledge Gaps
- **5 isolated node(s):** `records`, `Version`, `../dist/storage.js?fresh-session`, `../dist/cloud-backups.js?reload`, `personal-password-manager`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 545 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **37 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Архитектура проекта Password Manager` connect `Store` to `README.md`, `VaultError`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `VaultError` (e.g. with `Access` and `validate()`) actually correct?**
  _`VaultError` has 20 INFERRED edges - model-reasoned connections that need verification._
- **What connects `records`, `Version`, `../dist/storage.js?fresh-session` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `core.js` be split into smaller, more focused modules?**
  _Cohesion score 0.07201225740551584 - nodes in this community are weakly interconnected._
- **Why does `Store` connect `Store` to `Window`, `app.py`, `pytest`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Window` (e.g. with `SyncUI` and `test_create_with_eight_character_master()`) actually correct?**
  _`Window` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `SyncUI` be split into smaller, more focused modules?**
  _Cohesion score 0.09663120567375887 - nodes in this community are weakly interconnected._