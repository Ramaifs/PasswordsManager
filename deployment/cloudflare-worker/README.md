# Google-сессии на Cloudflare Worker

Worker обслуживает статический сайт и четыре OAuth-маршрута. Содержимое хранилищ, мастер-пароли и ключи восстановления на сервер не передаются.

Сессия действует до 30 дней. Браузер получает случайный идентификатор в cookie `Secure; HttpOnly; SameSite=Strict`, а access token хранит только в памяти. Refresh token хранится в KV в конверте AES-256-GCM. После перезагрузки страницы и при истечении access token клиент обращается к Worker без нового окна Google. Отключение Google удаляет серверную сессию и cookie. Отзыв разрешений, истечение сессии или ограничения Google требуют нового подключения.

## Настройка

1. Для Web OAuth-клиента разрешите HTTPS origin сайта. Client ID в `wrangler.jsonc` и `web/password-manager/dist/oauth-config.js` должен совпадать.
2. Создайте KV namespace и замените `REPLACE_WITH_KV_NAMESPACE_ID` в `wrangler.jsonc` его ID. Binding — `GOOGLE_SESSIONS`.
3. Задайте `SITE_ORIGIN` точным origin сайта без завершающего `/`.
4. В секретах Worker задайте `GOOGLE_CLIENT_SECRET` этого Web OAuth-клиента и `SESSION_ENCRYPTION_KEY`: 32 случайных байта в base64/base64url. Секреты не входят в Git, статические assets или ZIP. Замена ключа шифрования завершает прежние сессии.
5. Разместите Worker из этого каталога с конфигурацией `wrangler.jsonc`. Assets берутся из `web/password-manager/dist`; отдельный веб-архив не требуется.

## Пошагово в Windows

Worker — серверная часть сайта, которая запоминает подключение к Google и продлевает доступ. Настроить её нужно один раз. Пароли по-прежнему шифруются на устройстве.

**1. Откройте PowerShell в папке проекта.** Нужны установленный Node.js и вход в свой аккаунт Cloudflare:

```powershell
Set-Location 'D:\Programs\CodeProjects\Password Manager\deployment\cloudflare-worker'
npx wrangler login
```

Откроется браузер. Разрешите Wrangler доступ к вашему Cloudflare. Если `npx` предложит загрузить Wrangler, подтвердите. Это официальный инструмент Cloudflare; [инструкция установки](https://developers.cloudflare.com/workers/wrangler/install-and-update/).

**2. Создайте место для сохранённых сессий.** В том же PowerShell:

```powershell
npx wrangler kv namespace create GOOGLE_SESSIONS
```

Команда напечатает `id`. Откройте [wrangler.jsonc](wrangler.jsonc) и вставьте этот ID вместо `REPLACE_WITH_KV_NAMESPACE_ID`. Имя binding оставьте `GOOGLE_SESSIONS`. KV — небольшое серверное хранилище записей сессий. [Документация KV](https://developers.cloudflare.com/kv/get-started/).

**3. Проверьте адрес сайта.** В этом же файле `SITE_ORIGIN` должен быть адресом сайта без пути и завершающего `/`:

```text
https://password-manager-vault.masaoyhs.workers.dev
```

В Google Cloud откройте существующий OAuth-клиент типа **Web application**. Разрешите этот адрес как JavaScript origin. Используйте его Client ID и Client secret; Desktop-клиент предназначен для Windows-приложения. Client ID в настройках Worker и в `web/password-manager/dist/oauth-config.js` должен совпадать.

**4. Добавьте два секрета.** Сначала выполните:

```powershell
npx wrangler secret put GOOGLE_CLIENT_SECRET
```

В появившееся поле вставьте Client secret Web-клиента. Затем создайте случайный ключ:

```powershell
node -e "console.log(require('node:crypto').randomBytes(32).toString('base64url'))"
npx wrangler secret put SESSION_ENCRYPTION_KEY
```

Во второе поле вставьте строку, напечатанную командой `node`. Оба значения хранятся в секретах Cloudflare. Не вставляйте их в `wrangler.jsonc`, исходники или переписку. Команды `secret put` применяют секреты к Worker. [Документация секретов](https://developers.cloudflare.com/workers/configuration/secrets/).

**5. Загрузите сайт вместе с серверной частью:**

```powershell
npx wrangler deploy
```

Команда использует готовую конфигурацию и публикует `session.mjs` вместе с файлами сайта. Имя существующего Worker — `password-manager-vault`; менять адрес или покупать домен не требуется. [Статические файлы вместе с Worker](https://developers.cloudflare.com/workers/static-assets/binding/).

**6. Проверьте результат.** Откройте:

```text
https://password-manager-vault.masaoyhs.workers.dev/api/google/config
```

Должно быть `"enabled": true`. Затем откройте сайт, подключите Google и перезагрузите страницу. Облачные копии должны открываться без нового окна Google. Если `enabled` равен `false`, проверьте два секрета, `SITE_ORIGIN`, Client ID и binding `GOOGLE_SESSIONS`.

Один статический Direct Upload не включает серверные OAuth-маршруты. До настройки Worker сайт использует прежний браузерный вход с коротким сроком доступа и сообщает об этом в окне Google Drive.

## Проверка после размещения

Проверьте `/api/google/config`: `enabled: true`, ожидаемый Client ID. Подключите Google, перезагрузите сайт и убедитесь, что список облачных копий открывается без нового окна входа. После отключения Google перезагрузка не должна восстанавливать сессию. Проверьте истечение access token и повторное подключение после отзыва разрешений.

Локальные тесты: из `web/password-manager` выполните `npm test`. Они проверяют обмен кода, продление, cookie, шифрование KV, отключение, подмену origin, повреждённую сессию и ошибки провайдера. Запросы Google в тестах подменены; реальная авторизация и размещение проверяются отдельно.

Документация: [Google code model](https://developers.google.com/identity/oauth2/web/guides/use-code-model), [Cloudflare secrets](https://developers.cloudflare.com/workers/configuration/secrets/), [Workers KV](https://developers.cloudflare.com/kv/).
