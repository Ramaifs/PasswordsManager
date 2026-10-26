# Размещение на Cloudflare

Приложение состоит из статических файлов и может размещаться на Workers или Pages. Python и Node на сервере не нужны.

## Подготовка

Из корня репозитория:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_cloudflare.py
```

Скрипт проверяет состояние `web/password-manager/dist`, обязательные модули, соответствие CSP, целостность ZIP и SHA256 файлов. Результат — `artifacts/cloudflare-workers-upload.zip`; совместимое имя `artifacts/cloudflare-pages-upload.zip` содержит те же байты. Отчёт записывается в `artifacts/cloudflare-pages-preparation.json`.

В корне ZIP находится `index.html`; включены JavaScript, CSS, значок, локальная WASM-библиотека и лицензии. Файлы разработки и данные хранилищ в пакет не входят. `_headers` задаёт CSP, запрет iframe, кеширования и передачи referrer, а также nosniff и noindex. Noindex не ограничивает доступ к сайту.

## Загрузка и проверка

1. В Cloudflare Workers & Pages откройте существующий проект или создайте новый для статических файлов.
2. Загрузите подготовленный ZIP. Для Pages используйте Direct Upload; для текущего Worker см. [состояние переноса](../../docs/cloudflare-worker-status.md).
3. При необходимости ограничьте доступ через Cloudflare Access. Проверьте политику отдельно для production и preview.
4. Проверьте фактический HTTPS-адрес, загрузку JS/WASM, заголовки, открытие, сохранение и экспорт тестового хранилища.
5. Для переноса данных скачайте `.pmvault` со старого сайта и откройте его на новом. До проверки сохраните исходные копии.

Сборка ZIP не публикует приложение. Тестовые ключи, OAuth-токены и секреты аккаунта не должны попадать в архив или репозиторий.

Документация: [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/), [headers](https://developers.cloudflare.com/pages/configuration/headers/), [Cloudflare Access для Workers](https://developers.cloudflare.com/workers/configuration/cloudflare-access/).
