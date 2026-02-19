# Sincronização com NextCloud

O sistema sincroniza imagens e metadados com um servidor **NextCloud** usando dois mecanismos: **Activity API** (mais frequente) e **WebDAV** (sincronização mais pesada e periódica).

## Visão geral

- **Activity API**: consulta atividades recentes no NextCloud para detectar arquivos novos/alterados e sincronizar com menor atraso. Executada em intervalo configurável (ex.: a cada 5 minutos).
- **WebDAV**: varredura mais completa dos arquivos do usuário, usada em intervalos maiores (ex.: a cada 5 horas) e na sincronização inicial ao subir a aplicação.

O estado da sincronização (última execução, falhas, servidor offline, etc.) é persistido na tabela `sync_status` e usado para decisões de quando e como sincronizar.

## Variáveis de ambiente

Configure no `.env` (baseado no `env.example`):

| Variável | Descrição |
|----------|-----------|
| `NEXTCLOUD_BASE_URL` | URL base do servidor (ex.: `https://cloud.example.com`) |
| `NEXTCLOUD_USERNAME` | Usuário para autenticação WebDAV |
| `NEXTCLOUD_PASSWORD` | Senha ou App Password |
| `NEXTCLOUD_WEBDAV_PATH` | Path base do WebDAV (padrão: `/remote.php/dav`) |
| `NEXTCLOUD_USER_PATH` | Path do usuário (ex.: `/files/username`) |
| `NEXTCLOUD_VERIFY_SSL` | Verificar certificado SSL (`true`/`false`; use `false` só em desenvolvimento) |
| `NEXTCLOUD_MAX_PAGE_SIZE` | Tamanho máximo de página para paginação (padrão: 100) |

### Sincronização

| Variável | Descrição |
|----------|-----------|
| `NEXTCLOUD_SYNC_ACTIVITY_API_INTERVAL` | Intervalo em **minutos** para a Activity API (padrão: 5) |
| `NEXTCLOUD_SYNC_WEBDAV_INTERVAL` | Intervalo em **minutos** para o WebDAV (padrão: 300 = 5 horas) |
| `NEXTCLOUD_SYNC_INITIAL_ON_STARTUP` | Executar sincronização completa ao iniciar (`true`/`false`, padrão: `true`) |
| `NEXTCLOUD_SYNC_MAX_RETRIES` | Número máximo de tentativas em caso de erro (padrão: 3) |
| `NEXTCLOUD_SYNC_RETRY_DELAY` | Delay em **segundos** entre tentativas (padrão: 30) |
| `NEXTCLOUD_SYNC_BATCH_SIZE` | Tamanho do lote de imagens por execução (padrão: 50) |

## Comportamento em caso de falha

- Se a Activity API ou o WebDAV retornarem erro (ex.: 503 em manutenção), o sistema registra o evento, incrementa contadores de falha e pode marcar o servidor como offline após falhas consecutivas.
- Os avisos aparecem nos logs (ex.: "Activity API não disponível"). A aplicação continua rodando; quando o NextCloud voltar, as próximas execuções do scheduler tentarão novamente.

## Documentação da API NextCloud

- [NextCloud Activity API](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/OCS/ocs-api-overview.html#activity-api)
- [WebDAV](https://docs.nextcloud.com/server/latest/user_manual/files/access_webdav.html) para acesso a arquivos.
