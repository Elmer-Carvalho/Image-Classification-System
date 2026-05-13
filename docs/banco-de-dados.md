# Banco de Dados

O sistema usa **MySQL 8.0** e define o schema conforme o ambiente (`ENV`).

## Comportamento por ambiente

| Ambiente | Comportamento |
|----------|----------------|
| **Produção** (`ENV=production`) | Na subida da aplicação, o sistema verifica/cria as tabelas (`create_all` com `checkfirst=True`) e executa as **migrações Alembic** automaticamente. O startup só prossegue após as migrações concluírem. Nenhum dado é apagado. |
| **Desenvolvimento** (`ENV=development`) | A cada início todas as tabelas são removidas (com `FOREIGN_KEY_CHECKS` desabilitado temporariamente) e recriadas a partir dos modelos atuais. O Alembic marca o banco como atualizado (stamp). **Todos os dados são perdidos a cada reinício.** |

## Configuração

- **`DATABASE_URL`**: URL de conexão (ex.: `mysql+pymysql://user:password@host:3306/dbname?charset=utf8mb4`).
- Defina `ENV=production` no `.env` em deploy; use `ENV=development` apenas em ambiente local/desenvolvimento.

## Migrações (Alembic)

As migrações ficam em `alembic/` e são aplicadas dentro do **lifespan** da aplicação em produção, sem necessidade de rodar comandos manuais. Para detalhes sobre como funcionam e como criar novas migrações, veja [Migrações](migracoes.md).

## Troubleshooting

- **Conexão recusada**: verifique se o MySQL está rodando e se `DATABASE_URL` está correto. Em Docker: `docker-compose ps` e logs do serviço da API.
- **Tabelas não criadas ou schema desatualizado em produção**: confirme `ENV=production` no `.env` e verifique os logs da aplicação (ex.: "Migrações Alembic concluídas com sucesso!" ou mensagens de erro de migração). Garanta que o usuário do banco tem permissão para criar/alterar tabelas.
