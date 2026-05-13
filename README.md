# Sistema de Classificação de Imagens

API para cadastro, autenticação, gestão de usuários, ambientes, auditoria e classificação de imagens, com integração a NextCloud e pronta para frontends modernos.

## 🚀 Início rápido

1. **Pré-requisitos:** Docker e Docker Compose.
2. **Configuração:** Copie `env.example` para `.env` e preencha os valores. Em produção, defina `ENV=production`.
3. **Subir:** `docker-compose up --build`
4. **API:** [http://localhost:8000](http://localhost:8000) · **Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)

Para testar rotas protegidas, faça login em `/auth/login` e use o token no botão "Authorize" do Swagger ou consuma a API com cookies HttpOnly (veja documentação abaixo).

---

## 📚 Documentação

Toda a documentação está na pasta **[docs/](docs/)**. Use os links abaixo para abrir cada tópico (no GitHub ou em qualquer visualizador de Markdown, os links abrem os arquivos correspondentes).

| Tópico | Descrição |
|--------|------------|
| [**Banco de dados**](docs/banco-de-dados.md) | MySQL, comportamento por ambiente (`ENV`), configuração e troubleshooting. |
| [**Migrações**](docs/migracoes.md) | Alembic: onde ficam, como rodam no startup, como criar novas migrações. |
| [**Sincronização NextCloud**](docs/sincronizacao-nextcloud.md) | Activity API, WebDAV, variáveis de ambiente e comportamento em falhas. |
| [**Variáveis de ambiente**](docs/variaveis-ambiente.md) | Referência de todas as variáveis (ENV, JWT, cookie, banco, API, NextCloud, timezone). |
| [**Rotas da API**](docs/rotas.md) | Referência de endpoints (auth, usuários, whitelist, ambientes, classificações, auditoria, etc.). |
| [**Autenticação**](docs/autenticacao.md) | Login, cookies HttpOnly, Bearer token, JWT e uso no frontend (FormData, credenciais, CORS). |

---

## 📝 Observações

- Auditoria completa de ações administrativas; exclusões são lógicas.
- Rotas sensíveis exigem permissão de administrador.
- A pasta `scripts/` não é versionada; use `env.example` como base para o `.env`.

## 🔧 Troubleshooting

- **Banco não conecta:** verifique se o MySQL está rodando (`docker-compose ps`) e os logs (`docker-compose logs mysql`, `docker-compose logs app`). Reinicie com `docker-compose down` e `docker-compose up --build`.
- **Tabelas não criadas / schema desatualizado:** em produção, confirme `ENV=production` no `.env` e veja os logs da aplicação (mensagens de migração Alembic). Detalhes em [Banco de dados](docs/banco-de-dados.md).

---

Para dúvidas ou sugestões, abra uma issue ou entre em contato com o mantenedor.
