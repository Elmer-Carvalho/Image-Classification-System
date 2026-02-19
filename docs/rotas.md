# Documentação das Rotas da API

> Para autenticação, o sistema suporta duas formas:
>
> 1. **Cookies HttpOnly** (recomendado): Após login, o token é automaticamente armazenado em cookie seguro
> 2. **Bearer Token**: Utilize o token JWT retornado em `/auth/login` no header `Authorization: Bearer <token>`
>
> Detalhes e uso no frontend: [Autenticação](autenticacao.md).

---

## 🟢 Autenticação

### POST /auth/login

- **Descrição:** Autentica usuário e retorna JWT. Define automaticamente cookie HttpOnly com SameSite=Lax.
- **Payload:** Enviar como **FormData** (application/x-www-form-urlencoded ou multipart/form-data), não JSON. Campos: `username` (e-mail do usuário) e `password`.
- **Resposta:**
  ```json
  { 
    "access_token": "...", 
    "token_type": "bearer",
    "user_type": 2
  }
  ```
- **JWT Payload:** O token contém informações do usuário:
  ```json
  {
    "sub": "user-uuid",
    "user_type": "admin",           // "admin" ou "convencional"
    "user_type_id": 2,             // 1 = convencional, 2 = admin
    "name": "João da Silva",
    "email": "joao@email.com",
    "is_admin": true,              // boolean para facilitar verificações
    "exp": 1234567890
  }
  ```

### POST /auth/cadastro

- **Descrição:** Cadastra usuário (convencional ou administrador). O tipo é determinado automaticamente pelo cadastro permitido na whitelist. Define automaticamente cookie HttpOnly com SameSite=Lax.
- **Payload:**
  ```json
  {
    "nome_completo": "João da Silva",
    "email": "joao@email.com",
    "senha": "SenhaForte123",
    "cpf": "12345678901"
  }
  ```
- **Resposta:** JWT do novo usuário com informações do usuário no payload (mesma estrutura do login).

### POST /auth/logout

- **Descrição:** Realiza logout do usuário, removendo o cookie de autenticação.
- **Acesso:** Usuário autenticado (via cookie ou Bearer token)
- **Resposta:**
  ```json
  { "message": "Logout realizado com sucesso" }
  ```

---

## 🔐 Como Usar o JWT no Frontend

### Decodificando o Token

O frontend pode decodificar o JWT para obter informações do usuário sem fazer requisições adicionais:

```javascript
function decodeJWT(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    
    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('Erro ao decodificar JWT:', error);
    return null;
  }
}

// Uso
const token = localStorage.getItem('token');
const userData = decodeJWT(token);

if (userData) {
  console.log('Tipo:', userData.user_type);        // "admin" ou "convencional"
  console.log('Nome:', userData.name);             // "João da Silva"
  console.log('É admin:', userData.is_admin);      // true/false
}
```

### ⚠️ Importante

- **Sempre valide no backend** - o frontend pode ler, mas nunca deve ser a única fonte de verdade
- **O JWT é público** - qualquer um pode decodificar e ler essas informações
- **Não inclua dados sensíveis** - CPF, senhas, etc. não devem estar no JWT

---

## 👤 Usuários

### GET /usuarios

- **Descrição:** Lista todos os usuários (admin only).
- **Resposta:** Lista de usuários com dados básicos, tipo, status e CPF.

### GET /usuarios/me

- **Descrição:** Retorna os dados do usuário autenticado (qualquer usuário logado).
- **Resposta:** Objeto com id_usu, nome_completo, email, tipo, ativo, etc.

### PATCH /usuarios/me

- **Descrição:** Atualiza dados do usuário autenticado (nome, email, telefone).

### PATCH /usuarios/me/senha

- **Descrição:** Altera a senha do usuário autenticado (requer senha atual).

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

### POST /ambientes/importar

- **Descrição:** Cria novo ambiente associado a conjuntos de imagens e opções (admin only).
- **Payload:**
  ```json
  {
    "titulo_amb": "Título do ambiente",
    "titulo_questionario": "Título do questionário",
    "descricao_questionario": "Descrição exibida ao usuário",
    "ids_conjuntos": ["uuid-conjunto-1", "uuid-conjunto-2"],
    "opcoes": ["Opção A", "Opção B", "Opção C"]
  }
  ```
  - `ids_conjuntos`: pelo menos 1 ID de conjunto de imagens (ex.: retornados por `/test/conjuntos`).
  - `opcoes`: pelo menos 2 textos de opção de classificação.

### GET /ambientes

- **Descrição:** Lista todos os ambientes (admin only).

### DELETE /ambientes/{id_amb}

- **Descrição:** Exclusão lógica de ambiente (admin only).

### PATCH /ambientes/{id_amb}/reativar

- **Descrição:** Reativa ambiente (admin only).

### PATCH /ambientes/{id_amb}/titulo

- **Descrição:** Atualiza o título do ambiente (admin only).

### PATCH /ambientes/{id_amb}/descricao-questionario

- **Descrição:** Atualiza a descrição do questionário (admin only).

### PATCH /ambientes/{id_amb}/titulo-questionario

- **Descrição:** Atualiza o título do questionário (admin only).

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

### GET /usuarios-ambientes/meus-ambientes

- **Descrição:** Usuário convencional vê seus próprios ambientes associados.

### GET /usuarios-ambientes/usuario/{id_con}/ambientes

- **Descrição:** Lista ambientes associados a um usuário convencional (admin only).

### GET /usuarios-ambientes/ambiente/{id_amb}/usuarios

- **Descrição:** Lista usuários vinculados a um ambiente (admin only).

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

## Outras rotas

O sistema expõe ainda os prefixos abaixo. Para payloads, parâmetros e respostas completos, use o **Swagger** em `/docs`.

- **/classificacoes** – Inicializar ambiente, avançar/voltar imagem, classificar, contagem, histórico.
- **/opcoes** – CRUD de opções por ambiente (`POST /opcoes/ambiente/{id_amb}`, `GET /opcoes/ambiente/{id_amb}`).
- **/nextcloud** – Listagem e acesso a imagens sincronizadas do NextCloud (`GET /nextcloud/images`, `GET /nextcloud/images/{file_path}`).
- **/test** – Rotas de teste/sincronização: conjuntos de imagens e imagens por conjunto (`GET /test/conjuntos`, `GET /test/conjuntos/{id_cnj}/imagens`).
- **/images** – Busca por hash (`POST /images/buscar-por-hash`).

---

> Para exemplos completos de payloads e respostas, consulte o Swagger em `/docs`.
