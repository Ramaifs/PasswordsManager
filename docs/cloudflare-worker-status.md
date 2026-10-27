# Cloudflare Worker

Адрес проекта: https://password-manager-vault.masaoyhs.workers.dev.

2026-10-27 опубликована версия 0.41: настройка темы и основного цвета со сбросом внутри выбора цвета, дополнительные нумерованные поля, единый показ паролей, перенос старых паролей, массовая вставка в «Прочие пароли» и сортировка по категориям. Worker version ID: `e4fc07cb-ac10-4322-ac20-e36620c1f4e4`. Все 23 публичных файла проверены по SHA-256 на совпадение с текущим `web/password-manager/dist`. Серверный маршрут `/api/google/config` ответил HTTP 200, `enabled: true`, Client ID совпадает с конфигурацией сайта. Живой вход в Google этой проверкой не выполнялся.

Публикация выполнена через существующую конфигурацию `deployment/cloudflare-worker/wrangler.jsonc`, с сохранением KV binding и секретов. Локальный архив актуальных файлов: `releases/0.41/PasswordManager-web-0.41.zip`. Результаты: `artifacts/cloudflare-public-check.json`, `artifacts/cloudflare-google-config-check.json` и [протокол 0.41](verification-0.41.md).

## Ограничение доступа

Cloudflare Access настраивается при необходимости:

1. Workers & Pages → password-manager-vault → Access.
2. Protect this Worker behind Access → All traffic.
3. В политике разрешите нужные email без Everyone/Bypass.
4. После применения проверьте production и preview в приватном окне: перед загрузкой приложения должен требоваться вход.

[Документация Cloudflare Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/).
