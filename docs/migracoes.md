# Migrações (Alembic)

O projeto usa **Alembic** para evoluir o schema do banco de dados (novas colunas, tabelas, etc.) de forma versionada e reproduzível.

## Onde ficam

- **`alembic.ini`**: configuração geral (na raiz do projeto). A URL do banco é definida em `alembic/env.py` a partir de `settings.DATABASE_URL`.
- **`alembic/env.py`**: usa o engine e os modelos da aplicação (`app.db.models`, `Base.metadata`).
- **`alembic/versions/`**: cada arquivo é uma revisão (migração) com `upgrade()` e `downgrade()`.

## Como rodam em produção

No **lifespan** da aplicação, quando `ENV=production`:

1. Após o banco estar acessível, é executado `Base.metadata.create_all(bind=engine, checkfirst=True)`.
2. Em seguida é executado `alembic upgrade head` de forma **programática** (módulo `app.db.run_migrations`). O startup é **bloqueante**: a aplicação só continua depois que todas as migrações pendentes forem aplicadas.

Não é necessário rodar `alembic upgrade head` manualmente em produção; o próprio processo da API aplica as migrações ao subir.

## Desenvolvimento

Com `ENV=development`, o banco é recriado do zero a cada início. Depois do `create_all`, o sistema chama `alembic stamp head` para marcar o banco como estando na revisão mais recente, evitando que migrações sejam reaplicadas em cenários em que o mesmo banco fosse usado depois com `ENV=production`.

## Como criar uma nova migração

1. Instale as dependências e ative o ambiente (ou use o mesmo que a aplicação).
2. Na raiz do projeto, gere uma nova revisão:
   ```bash
   alembic revision -m "descricao_da_mudanca"
   ```
3. Edite o arquivo em `alembic/versions/` e implemente `upgrade()` e `downgrade()` usando `op` e `sa` (ex.: `op.add_column`, `op.drop_column`).
4. Teste localmente (por exemplo com `ENV=production` e um banco de teste):
   ```bash
   alembic upgrade head
   ```
5. Faça commit do novo arquivo de migração. No próximo deploy, a aplicação aplicará essa revisão automaticamente no startup.

## Boas práticas

- Use `IF NOT EXISTS` / `IF EXISTS` quando fizer sentido (ex.: adicionar colunas que podem já existir).
- Não remova ou altere migrações já aplicadas em produção; crie uma nova revisão para corrigir o schema.
- Mantenha o `downgrade()` consistente com o `upgrade()` para permitir rollback em desenvolvimento.
