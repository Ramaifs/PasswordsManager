# Cloudflare Worker

Адрес проекта: https://password-manager-vault.masaoyhs.workers.dev.

На 2026-10-25 по HTTPS была доступна заглушка с HTTP 200. Публикация актуальной версии приложения на этом адресе не подтверждена. Подготовленный локально ZIP сам по себе не означает обновления сайта.

Пакет для загрузки: `artifacts/cloudflare-workers-upload.zip`. Файл `artifacts/cloudflare-pages-upload.zip` содержит ту же сборку под совместимым именем. Порядок подготовки и проверки — в [инструкции размещения](../deployment/cloudflare-pages/README.md).

## Ограничение доступа

Cloudflare Access настраивается при необходимости:

1. Workers & Pages → password-manager-vault → Access.
2. Protect this Worker behind Access → All traffic.
3. В политике разрешите нужные email без Everyone/Bypass.
4. После применения проверьте production и preview в приватном окне: перед загрузкой приложения должен требоваться вход.

[Документация Cloudflare Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/).
