# Cloudflare Worker

Адрес проекта: https://password-manager-vault.masaoyhs.workers.dev.

2026-10-27 опубликована пересборка 0.40 с поиском по содержимому записей и телефону, разделом «Прочие пароли», автоподстановкой контактных данных, сортировкой и дополнительными полями паролей. Worker version ID: `fb034907-f439-417c-a077-526268dc6fa0`. Все 22 публичных файла проверены по SHA-256 на совпадение с текущим `web/password-manager/dist`. Серверный маршрут `/api/google/config` ответил HTTP 200, `enabled: true`, Client ID совпадает с конфигурацией сайта. Живой вход в Google этой проверкой не выполнялся.

Публикация выполнена через существующую конфигурацию `deployment/cloudflare-worker/wrangler.jsonc`, с сохранением KV binding и секретов. Локальный архив актуальных файлов: `releases/0.40/PasswordManager-web-0.40.zip`. Результаты: `artifacts/cloudflare-public-check.json`, `artifacts/cloudflare-google-config-check.json` и [протокол пересборки](category-navigation-verification.md).

## Ограничение доступа

Cloudflare Access настраивается при необходимости:

1. Workers & Pages → password-manager-vault → Access.
2. Protect this Worker behind Access → All traffic.
3. В политике разрешите нужные email без Everyone/Bypass.
4. После применения проверьте production и preview в приватном окне: перед загрузкой приложения должен требоваться вход.

[Документация Cloudflare Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/).
