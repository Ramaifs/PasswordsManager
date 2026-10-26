# Google-сессии на Cloudflare Worker

Worker обслуживает статический сайт и четыре OAuth-маршрута. Содержимое хранилищ, мастер-пароли и ключи восстановления на сервер не передаются.

Сессия действует до 30 дней. Браузер получает случайный идентификатор в cookie `Secure; HttpOnly; SameSite=Strict`, а access token хранит только в памяти. Refresh token хранится в KV в конверте AES-256-GCM. После перезагрузки страницы и при истечении access token клиент обращается к Worker без нового окна Google. Отключение Google удаляет серверную сессию и cookie. Отзыв разрешений, истечение сессии или ограничения Google требуют нового подключения.

## Настройка

1. Для Web OAuth-клиента разрешите HTTPS origin сайта. Client ID в `wrangler.jsonc` и `web/password-manager/dist/oauth-config.js` должен совпадать.
2. Создайте KV namespace и замените `REPLACE_WITH_KV_NAMESPACE_ID` в `wrangler.jsonc` его ID. Binding — `GOOGLE_SESSIONS`.
3. Задайте `SITE_ORIGIN` точным origin сайта без завершающего `/`.
4. В секретах Worker задайте `GOOGLE_CLIENT_SECRET` этого Web OAuth-клиента и `SESSION_ENCRYPTION_KEY`: 32 случайных байта в base64/base64url. Секреты не входят в Git, статические assets или ZIP. Замена ключа шифрования завершает прежние сессии.
5. Разместите Worker из этого каталога с конфигурацией `wrangler.jsonc`. Assets берутся из `web/password-manager/dist`; отдельный веб-архив не требуется.

Один статический Direct Upload не включает серверные OAuth-маршруты. До настройки Worker сайт использует прежний браузерный вход с коротким сроком доступа и сообщает об этом в окне Google Drive.

## Проверка после размещения

Проверьте `/api/google/config`: `enabled: true`, ожидаемый Client ID. Подключите Google, перезагрузите сайт и убедитесь, что список облачных копий открывается без нового окна входа. После отключения Google перезагрузка не должна восстанавливать сессию. Проверьте истечение access token и повторное подключение после отзыва разрешений.

Локальные тесты: из `web/password-manager` выполните `npm test`. Они проверяют обмен кода, продление, cookie, шифрование KV, отключение, подмену origin, повреждённую сессию и ошибки провайдера. Запросы Google в тестах подменены; реальная авторизация и размещение проверяются отдельно.

Документация: [Google code model](https://developers.google.com/identity/oauth2/web/guides/use-code-model), [Cloudflare secrets](https://developers.cloudflare.com/workers/configuration/secrets/), [Workers KV](https://developers.cloudflare.com/kv/).
