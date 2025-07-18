# Documentação das Rotas da API

> Para autenticação, utilize o token JWT retornado em `/auth/login` no header `Authorization: Bearer <token>`.

---

## 🟢 Autenticação

### POST /auth/login

- **Descrição:** Autentica usuário e retorna JWT.
- **Payload:**
  ```json
  {
    "username": "email@exemplo.com",
    "password": "suaSenha"
  }
  ```
- **Resposta:**
  ```json
  { "access_token": "...", "token_type": "bearer" }
  ```

### POST /auth/cadastro-convencional

- **Descrição:** Cadastra usuário convencional.
- **Payload:**
  ```json
  {
    "nome_completo": "João da Silva",
    "email": "joao@email.com",
    "senha": "SenhaForte123",
    "cpf": "12345678901",
    "crm": "12345"
  }
  ```
- **Resposta:** JWT do novo usuário.

### POST /auth/cadastro-administrador

- **Descrição:** Cadastra usuário administrador.
- **Payload:**
  ```json
  {
    "nome_completo": "Maria Admin",
    "email": "maria@email.com",
    "senha": "SenhaForte123"
  }
  ```
- **Resposta:** JWT do novo admin.

---

## 👤 Usuários

### GET /usuarios

- **Descrição:** Lista todos os usuários (admin only).
- **Resposta:** Lista de usuários com dados básicos, tipo, status, CPF/CRM.

### DELETE /usuarios/{id_usu}

- **Descrição:** Exclusão lógica de usuário (admin only).

### PATCH /usuarios/{id_usu}/reativar

- **Descrição:** Reativa usuário desativado (admin only).

---

## 📧 Whitelist (E-mails Permitidos)

### POST /whitelist

- **Descrição:** Adiciona e-mail à whitelist (admin only).
- **Payload:**
  ```json
  {
    "email": "novo@email.com",
    "id_tipo": 1
  }
  ```

### GET /whitelist

- **Descrição:** Lista todos os e-mails permitidos (admin only).

### DELETE /whitelist/{id_cad}

- **Descrição:** Exclusão lógica de e-mail permitido (admin only).

### PATCH /whitelist/{id_cad}/reativar

- **Descrição:** Reativa e-mail permitido (admin only).

---

## 🏢 Ambientes

### POST /ambientes

- **Descrição:** Cria novo ambiente (admin only).
- **Payload:**
  ```json
  {
    "titulo_amb": "Ambiente de Teste",
    "descricao": "Ambiente para testes."
  }
  ```

### GET /ambientes

- **Descrição:** Lista todos os ambientes (admin only).

### DELETE /ambientes/{id_amb}

- **Descrição:** Exclusão lógica de ambiente (admin only).

### PATCH /ambientes/{id_amb}/reativar

- **Descrição:** Reativa ambiente (admin only).

---

## 🔗 Usuarios-Ambientes (Vínculos)

### POST /usuarios-ambientes/{id_amb}/associar-todos

- **Descrição:** Vincula todos os usuários convencionais ativos ao ambiente (admin only).

### POST /usuarios-ambientes/{id_amb}/associar

- **Descrição:** Vincula 1 a N usuários convencionais ao ambiente (admin only).
- **Payload:**
  ```json
  {
    "ids_usuarios": ["id_con1", "id_con2"]
  }
  ```

### DELETE /usuarios-ambientes/{id_amb}/usuario/{id_con}

- **Descrição:** Exclusão lógica do vínculo (admin only).

### PATCH /usuarios-ambientes/{id_amb}/usuario/{id_con}/reativar

- **Descrição:** Reativa vínculo (admin only).

### GET /usuarios-ambientes

- **Descrição:** Lista todos os ambientes e usuários vinculados (admin only).

### GET /usuarios-ambientes/meus-ambientes

- **Descrição:** Usuário convencional vê seus próprios ambientes.

### POST /usuarios-ambientes/usuarios-ambientes

- **Descrição:** Admin consulta ambientes de 1 a N usuários.
- **Payload:**
  ```json
  {
    "ids_usuarios": ["id_con1", "id_con2"]
  }
  ```

---

## 🕵️ Auditoria

### GET /auditoria/logs

- **Descrição:** Lista logs de auditoria (admin only), ordenados do mais recente para o mais antigo.
- **Parâmetros opcionais:**
  - `page` (padrão: 1)
  - `page_size` (padrão: 50, máximo: 200)
  - `id_usuario` (filtra por usuário)
  - `id_evento` (filtra por tipo de evento)
  - `data_inicio`, `data_fim` (filtra por período, formato ISO)
- **Resposta:**
  ```json
  {
    "logs": [ ... ],
    "page": 1,
    "page_size": 50,
    "total": 120,
    "is_last_page": false
  }
  ```

### GET /auditoria/eventos

- **Descrição:** Lista todos os tipos de eventos de auditoria (admin only).

---

> Para exemplos completos de payloads e respostas, consulte o Swagger em `/docs`.
