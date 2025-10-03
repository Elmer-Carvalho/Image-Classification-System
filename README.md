# Sistema de Classificação de Imagens

Este projeto é uma API robusta para cadastro, autenticação, gestão de usuários, ambientes, auditoria e classificação de imagens, pronta para integração com frontends modernos.

## 🚀 Como rodar o sistema

### 1. Pré-requisitos

- Docker e Docker Compose instalados
- (Opcional) Python 3.11+ para rodar scripts utilitários

### 2. Configuração do ambiente

1. Copie o arquivo `.env.example` para `.env` e preencha os valores necessários:
   ```bash
   cp env.example .env
   # Edite o .env com seus dados
   ```
2. (Opcional) Ajuste as portas no `.env` se necessário.

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

Para detalhes completos de payloads, exemplos e respostas de cada rota, consulte o arquivo [`ROTAS.md`](ROTAS.md).

## 🛠️ Scripts úteis

- Gerar arquivo de exemplo de variáveis de ambiente:

  ```bash
  python scripts/gerar_env_example.py
  ```

- Testar conexão com o banco de dados:
  ```bash
  python scripts/test_db_connection.py
  ```

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

2. **Teste a conexão manualmente:**

   ```bash
   python scripts/test_db_connection.py
   ```

3. **Reinicie os serviços:**

   ```bash
   docker-compose down
   docker-compose up --build
   ```

4. **Verifique os logs:**
   ```bash
   docker-compose logs postgres
   docker-compose logs app
   ```

### Problema: Tabelas não são criadas

Se as tabelas não forem criadas automaticamente:

1. **Verifique se o banco está acessível**
2. **Execute o script de teste de conexão**
3. **Verifique as permissões do usuário do banco**

---

Para dúvidas ou sugestões, abra uma issue ou entre em contato com o mantenedor.
