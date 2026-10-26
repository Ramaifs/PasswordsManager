# Перенос на Cloudflare Pages

Подготовка: 2026-10-25. Пользователь согласился заменить адрес `chatgpt.site`; выбран вариант Cloudflare Pages без покупки домена. Действующий приватный сайт сохранён.

## Готовый результат

Из проверенного commit сайта подготовлен `artifacts/cloudflare-pages-upload.zip`: `index.html` находится в корне, включены JS/CSS/значок/локальный WASM bundle и лицензии. Метаданные `.openai`, исходники тестов, тестовые хранилища, ключи восстановления, Git и `node_modules` исключены. Служебный `_headers` задаёт CSP, запрет iframe, отсутствие кеширования и referrer, nosniff и noindex. Noindex не является контролем доступа.

Сборка и проверка:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_cloudflare.py
```

Проверяется чистое состояние исходных assets, наличие модулей, соответствие CSP HTML/Cloudflare и каждый файл ZIP по SHA256. Отчёт: `artifacts/cloudflare-pages-preparation.json`. Ожидаемое имя проекта — `password-manager-vault`; конкретный адрес и доступность имени определит Cloudflare при создании, поэтому неподтверждённый hostname не выдаётся за готовый.

## Чего пока нет

В окружении нет подключённого провайдера Cloudflare, Wrangler или его сохранённого входа, а также указанных через окружение API token/account ID. Поиск подключения Cloudflare в доступном каталоге плагинов вернул пустой результат. Инструмент Browser также пока не может загрузить свой runtime, поэтому чужая браузерная авторизация не использовалась. Новый аккаунт не создавался, условия сервиса от имени пользователя не принимались, проект не публиковался. Доступные плагины могут меняться: [каталог](https://chatgpt.com/plugins).

Фактическое создание Pages-проекта требует входа в Cloudflare. Можно выполнить его самостоятельно на `https://dash.cloudflare.com/` или отдельно авторизовать официальный Wrangler командой `npx wrangler login` после установки CLI. Пароль, одноразовые коды и API-токен не следует отправлять в чат или включать в ZIP.

## Порядок размещения с сохранением приватности

1. Войти в свой Cloudflare и открыть Workers & Pages. Создать Pages-проект, желательно сначала с безличной заглушкой, чтобы получить подтверждённое имя/hostname без открытия приложения.
2. Настроить Cloudflare Access только на владельца. Защитить **оба** адреса: основной `<project>.pages.dev` и preview `*.<project>.pages.dev`. Обычная кнопка Enable access policy защищает preview, но не основной адрес; проверьте отдельную политику для него.
3. Проверить в отдельном неавторизованном сеансе, что основной и preview-адреса требуют входа и не отдают assets приложения.
4. В Pages загрузить подготовленный ZIP через Direct Upload. Для него не нужен Python, Node или build command на сервере. Подтвердить успешное размещение и фактически выданный URL, а не предполагаемое имя.
5. На старом сайте скачать `.pmvault` каждого нужного хранилища; открыть файл на новом адресе и разблокировать. IndexedDB привязан к origin и сам не переносится.
6. Проверить открытие/сохранение/экспорт, Worker/WASM, HTTPS и headers на новом адресе. Только после этого считать перенос завершённым. Старый сайт/локальные данные до этого не удалять.

Источники: [Direct Upload, вход и формат ZIP](https://developers.cloudflare.com/pages/get-started/direct-upload/), [headers](https://developers.cloudflare.com/pages/configuration/headers/), [различие production/preview Access](https://developers.cloudflare.com/pages/configuration/preview-deployments/), [защита основного pages.dev](https://developers.cloudflare.com/pages/platform/known-issues/#enable-access-on-your-pagesdev-domain).
