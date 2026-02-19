# Variáveis de ambiente

O sistema é configurado via variáveis de ambiente. Use o arquivo **`env.example`** na raiz do projeto como modelo: copie para `.env` e preencha os valores. O `.env` não é versionado.

## Grupos de configuração

### Ambiente da aplicação

| Variável | Descrição |
|----------|-----------|
| `ENV` | `development` (banco recriado a cada início) ou `production` (tabelas e migrações aplicadas sem apagar dados). **Em deploy use `production`.** |

### Admin inicial

Criado automaticamente no primeiro startup se não existir usuário administrador.

| Variável | Descrição |
|----------|-----------|
| `ADMIN_NOME_COMPLETO` | Nome do administrador inicial |
| `ADMIN_EMAIL` | E-mail do admin |
| `ADMIN_SENHA` | Senha do admin |
| `ADMIN_CPF` | CPF do admin |

### JWT

| Variável | Descrição |
|----------|-----------|
| `JWT_SECRET_KEY` | Chave secreta para assinatura dos tokens (obrigatória) |
| `JWT_ALGORITHM` | Algoritmo (padrão: HS256) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Tempo de expiração do token em minutos |

### Cookies (HttpOnly)

| Variável | Descrição |
|----------|-----------|
| `COOKIE_NAME` | Nome do cookie (padrão: access_token) |
| `COOKIE_HTTPONLY` | HttpOnly (padrão: true) |
| `COOKIE_SAMESITE` | SameSite (padrão: lax) |
| `COOKIE_SECURE` | true em produção com HTTPS |
| `COOKIE_DOMAIN` | Domínio do cookie (None para localhost) |

### Banco de dados

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | URL de conexão PostgreSQL (ex.: `postgresql://user:password@host:5432/dbname`). Usada pela aplicação e pelo Alembic. |
| `POSTGRES_*` | Variáveis auxiliares para o serviço PostgreSQL no Docker (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT). O `docker-compose` pode montar `DATABASE_URL` a partir delas. |

### API

| Variável | Descrição |
|----------|-----------|
| `API_HOST` | Host do servidor (ex.: 0.0.0.0) |
| `API_PORT` | Porta (ex.: 8000) |

### NextCloud e sincronização

Ver [Sincronização NextCloud](sincronizacao-nextcloud.md) para detalhes. Resumo:

- **Conexão:** `NEXTCLOUD_BASE_URL`, `NEXTCLOUD_USERNAME`, `NEXTCLOUD_PASSWORD`, `NEXTCLOUD_WEBDAV_PATH`, `NEXTCLOUD_USER_PATH`, `NEXTCLOUD_MAX_PAGE_SIZE`, `NEXTCLOUD_VERIFY_SSL`.
- **Sincronização:** `NEXTCLOUD_SYNC_ACTIVITY_API_INTERVAL`, `NEXTCLOUD_SYNC_WEBDAV_INTERVAL`, `NEXTCLOUD_SYNC_INITIAL_ON_STARTUP`, `NEXTCLOUD_SYNC_MAX_RETRIES`, `NEXTCLOUD_SYNC_RETRY_DELAY`, `NEXTCLOUD_SYNC_BATCH_SIZE`.

### Timezone

| Variável | Descrição |
|----------|-----------|
| `TIMEZONE` | Fuso horário (padrão: America/Sao_Paulo). Usado em datas e logs. |

## Segurança

- Nunca commite o arquivo `.env` nem valores reais de `JWT_SECRET_KEY`, senhas ou `DATABASE_URL` no repositório.
- Em produção, use segredos do ambiente de execução (variáveis de ambiente do sistema ou do provedor de deploy) em vez de arquivo `.env` no servidor, quando aplicável.
