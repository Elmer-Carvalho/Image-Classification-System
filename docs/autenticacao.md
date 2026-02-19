# Autenticação

A API suporta duas formas de autenticação para rotas protegidas:

1. **Cookies HttpOnly** (recomendado): após login ou cadastro, o servidor define um cookie HttpOnly com o token. O navegador envia o cookie automaticamente em requisições subsequentes (mesmo domínio ou conforme CORS). Mais seguro contra XSS.
2. **Bearer Token**: o cliente envia o JWT no header `Authorization: Bearer <token>`. Útil para testes (ex.: Swagger) ou clientes que não usam cookies.

## Endpoints de autenticação

- **POST /auth/login** – Login com `username` (e-mail) e `password` enviados como **FormData** (não JSON). Retorna JWT e define cookie HttpOnly.
- **POST /auth/cadastro** – Cadastro de usuário (convencional ou admin conforme whitelist). Corpo em JSON. Retorna JWT e define cookie HttpOnly.
- **POST /auth/logout** – Encerra a sessão e remove o cookie (requer autenticação).

Detalhes de payloads e respostas estão em [Rotas da API](rotas.md).

## Conteúdo do JWT

O token contém, entre outros campos: `sub` (ID do usuário, UUID), `user_type` (`"admin"` ou `"convencional"`), `user_type_id` (1 = convencional, 2 = admin), `name`, `email`, `is_admin`, `exp` (expiração). O frontend pode decodificar o JWT (base64) para exibir nome/tipo; **a validação de permissão é sempre feita no backend**.

## Uso no frontend (HttpOnly)

Para consumir a API com cookies HttpOnly a partir de um frontend (React/JavaScript):

1. **Credenciais**: em todas as requisições use `credentials: 'include'` (Fetch) ou `withCredentials: true` (Axios). Sem isso o navegador não envia o cookie.
2. **Login**: o endpoint `/auth/login` espera **FormData** com os campos `username` (e-mail) e `password` — não envie JSON.
3. **Não armazenar o token**: o cookie é gerenciado pelo navegador; não é necessário (nem recomendado) guardar o token no `localStorage` ao usar HttpOnly.

Exemplo mínimo de login com Fetch:

```javascript
const formData = new FormData();
formData.append('username', email);
formData.append('password', password);

const response = await fetch(`${API_BASE_URL}/auth/login`, {
  method: 'POST',
  credentials: 'include',
  body: formData,
});
```

Exemplo com Axios: use `withCredentials: true` na instância e envie o FormData no body do `post('/auth/login', formData)`.

4. **CORS**: o backend deve permitir credenciais (`allow_credentials=True`) e incluir a origem do frontend em `allow_origins` (por padrão o projeto usa `http://localhost:5173` e `http://127.0.0.1:5173`). Para outro domínio, ajuste em `app/main.py`.

**Checklist rápido:** usar credenciais em toda requisição; FormData no login com `username` e `password`; não enviar `Authorization: Bearer` manualmente ao usar cookie; tratar 401 (não autenticado) e 403 (acesso negado).

## Dados do usuário autenticado

A rota **GET /usuarios/me** retorna os dados do usuário logado (requer autenticação). Use essa rota após o login para obter nome, tipo, etc., em vez de depender apenas da decodificação do JWT. Ver [Rotas da API](rotas.md).

## Configuração no servidor

No `.env` podem ser ajustados: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `COOKIE_NAME`, `COOKIE_HTTPONLY`, `COOKIE_SAMESITE`, `COOKIE_SECURE`, `COOKIE_DOMAIN`. Em produção com HTTPS, use `COOKIE_SECURE=true`. Referência completa: [Variáveis de ambiente](variaveis-ambiente.md).
