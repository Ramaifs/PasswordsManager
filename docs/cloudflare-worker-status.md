# Cloudflare Worker

Адрес проекта: https://password-manager-vault.masaoyhs.workers.dev.

2026-11-01 опубликовано [мобильное дополнение 0.41](mobile-0.41-verification.md):
Android/iOS Google-вход через полный переход с PKCE/state, отдельная вкладка при
открытом хранилище, ссылка на подписанный Android APK. Worker:
`5cc2a8d2-83e4-4ecb-8094-a7b17e6bfa65`. Все 24 публичных файла сверены с исходниками
по SHA-256, живой start-маршрут и разрешённый Google redirect URI проверены.
Полный вход реального аккаунта на телефоне не проверялся. Детали:
`artifacts/mobile-0.41-public-check.json`. Ниже сохранён предыдущий протокол.

2026-10-27 опубликована версия 0.41: настройка темы и основного цвета со сбросом внутри выбора цвета, дополнительные нумерованные поля, единый показ паролей, перенос старых паролей, массовая вставка в «Прочие пароли» сортировка по категориям, Ctrl/Shift и ПКМ для массовых действий, продолжение номеров вставки и удаление дополнительных полей через «−». Worker version ID: `3a61b2d2-9175-4425-86e8-d7b31d00ce3f`. Все 24 публичных файла проверены по SHA-256 на совпадение с текущим `web/password-manager/dist`. Серверный маршрут `/api/google/config` ответил HTTP 200, `enabled: true`, Client ID совпадает с конфигурацией сайта. Живой вход в Google этой проверкой не выполнялся.

Публикация выполнена через существующую конфигурацию `deployment/cloudflare-worker/wrangler.jsonc`, с сохранением KV binding и секретов. Локальный архив актуальных файлов: `releases/0.41/PasswordManager-web-0.41.zip`. Результаты: `artifacts/cloudflare-public-check.json`, `artifacts/cloudflare-google-config-check.json` и [протокол 0.41](verification-0.41.md).

## Ограничение доступа

Cloudflare Access настраивается при необходимости:

1. Workers & Pages → password-manager-vault → Access.
2. Protect this Worker behind Access → All traffic.
3. В политике разрешите нужные email без Everyone/Bypass.
4. После применения проверьте production и preview в приватном окне: перед загрузкой приложения должен требоваться вход.

[Документация Cloudflare Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/).
