# Sistema de Classificação de Imagens

Este projeto é uma API robusta para cadastro, autenticação, gestão de usuários, ambientes, auditoria e classificação de imagens, pronta para integração com frontends modernos.

## 🚀 Como rodar o sistema

### 1. Pré-requisitos

- Docker e Docker Compose instalados
- (Opcional) Python 3.11+ para rodar scripts utilitários

### 2. Configuração do ambiente

1. Copie o arquivo `env.example` para `.env` e preencha os valores necessários:
   ```bash
   cp env.example .env
   # Edite o .env com seus dados
   ```
2. Defina `ENV=production` no `.env` quando for usar em produção (deploy). Com `ENV=development` (padrão), o banco é recriado do zero a cada início (veja [Banco de dados e migrações](#-banco-de-dados-e-migrações)).
3. (Opcional) Ajuste as portas no `.env` se necessário.

### 3. Subindo o sistema

```bash
docker-compose up --build
```

A API estará disponível em: [http://localhost:8000](http://localhost:8000)

### 4. Acessando a documentação interativa (Swagger)

- [http://localhost:8000/docs](http://localhost:8000/docs)

## 🧪 Testando as rotas

- Use o Swagger para testar todas as rotas de forma interativa.
- Para rotas protegidas, faça login em `/auth/login` e use o token JWT retornado no botão "Authorize" do Swagger.

## 🔗 Integração com Frontend

- O frontend pode consumir a API via HTTP/HTTPS usando o token JWT para autenticação.
- Basta enviar o token no header `Authorization: Bearer <token>` em cada requisição protegida.
- As rotas seguem padrões REST e retornam JSON padronizado.

## 📚 Detalhes das rotas

Para detalhes completos de payloads, exemplos e respostas de cada rota, consulte o arquivo [`ROTAS.md`](ROTAS.md). Para uso da API com cookies HttpOnly no frontend, veja [`EXEMPLO_USO_API_HTTPONLY.md`](EXEMPLO_USO_API_HTTPONLY.md).

## 🗄️ Banco de dados e migrações

- **Produção (`ENV=production`)**: na subida da aplicação, o sistema verifica/cria as tabelas e executa as migrações **Alembic** automaticamente (incluindo novas colunas em tabelas existentes). O startup só prossegue após as migrações concluírem.
- **Desenvolvimento (`ENV=development`)**: a cada início o schema público é recriado (banco limpo) e as tabelas são criadas a partir dos modelos atuais; o Alembic marca o banco como atualizado (stamp) para manter consistência.
- As migrações ficam em `alembic/` e são aplicadas dentro do ciclo de vida da aplicação (lifespan), sem necessidade de rodar comandos manuais em produção.

## 🛠️ Scripts e utilitários

- A pasta `scripts/` não é versionada (`.gitignore`). Use `env.example` como base para o `.env`.
- Para testar conexão com o banco em ambiente Docker, use os logs do serviço da API ou conecte ao PostgreSQL exposto pelo `docker-compose`.

## 📝 Observações

- O sistema implementa auditoria completa de todas as ações administrativas.
- Exclusões são lógicas, mantendo histórico.
- Apenas administradores podem acessar rotas sensíveis.

## 🔧 Troubleshooting

### Problema: Erro de conexão com banco de dados

Se você encontrar erros como `connection refused` ou `database not ready`:

1. **Verifique se o PostgreSQL está rodando:**

   ```bash
   docker-compose ps
   ```

2. **Reinicie os serviços:**

   ```bash
   docker-compose down
   docker-compose up --build
   ```

3. **Verifique os logs:**
   ```bash
   docker-compose logs postgres
   docker-compose logs app
   ```

### Problema: Tabelas não são criadas ou schema desatualizado

- Em **produção**, as tabelas e migrações (Alembic) rodam automaticamente no startup. Confirme no `.env` que `ENV=production` está definido e verifique os logs da aplicação (ex.: "Migrações Alembic concluídas com sucesso!" ou mensagens de erro de migração).
- Garanta que o banco está acessível e que o usuário do banco tem permissão para criar/alterar tabelas.

---

Para dúvidas ou sugestões, abra uma issue ou entre em contato com o mantenedor.
