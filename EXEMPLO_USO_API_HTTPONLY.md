# Exemplo de Uso da API com Cookies HttpOnly - React/JavaScript

Este arquivo demonstra como um projeto JavaScript/React deve interagir com a API, utilizando corretamente os cookies HttpOnly para autenticação.

## 📋 Índice

1. [Configuração Base](#configuração-base)
2. [Login e Autenticação](#login-e-autenticação)
3. [Requisições Autenticadas](#requisições-autenticadas)
4. [Exemplo: Listar Ambientes](#exemplo-listar-ambientes)
5. [Logout](#logout)
6. [Hook React Customizado](#hook-react-customizado)
7. [Tratamento de Erros](#tratamento-de-erros)

---

## 🔧 Configuração Base

### Variáveis de Ambiente

```javascript
// .env ou config.js
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
```

### Configuração do Axios/Fetch

**IMPORTANTE:** Para que os cookies HttpOnly funcionem corretamente, você DEVE configurar `credentials: 'include'` em todas as requisições.

```javascript
// api.js - Configuração base do cliente HTTP
import axios from 'axios';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // CRÍTICO: Permite envio de cookies HttpOnly
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para tratamento de erros
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expirado ou inválido
      // Redirecionar para login ou renovar token
      console.error('Sessão expirada. Faça login novamente.');
    }
    return Promise.reject(error);
  }
);

export default api;
```

**OU usando Fetch nativo:**

```javascript
// api.js - Usando Fetch nativo
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const config = {
    ...options,
    credentials: 'include', // CRÍTICO: Permite envio de cookies HttpOnly
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  const response = await fetch(url, config);
  
  if (!response.ok) {
    if (response.status === 401) {
      console.error('Sessão expirada. Faça login novamente.');
    }
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
}

export default apiRequest;
```

---

## 🔐 Login e Autenticação

### Login com FormData (OAuth2PasswordRequestForm)

O endpoint `/auth/login` espera um `FormData` com os campos `username` (email) e `password`.

```javascript
// authService.js
import api from './api';

/**
 * Realiza login do usuário
 * @param {string} email - Email do usuário
 * @param {string} password - Senha do usuário
 * @returns {Promise<Object>} Dados do token e informações do usuário
 */
export async function login(email, password) {
  // IMPORTANTE: OAuth2PasswordRequestForm requer FormData, não JSON
  const formData = new FormData();
  formData.append('username', email); // Campo deve ser 'username', não 'email'
  formData.append('password', password);

  try {
    const response = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data', // FormData requer este header
      },
    });

    // O cookie HttpOnly é definido automaticamente pelo servidor
    // Não é necessário armazenar manualmente o token
    
    // A resposta contém o token (para compatibilidade), mas o cookie já foi definido
    const { access_token, token_type, user_type } = response.data;
    
    console.log('Login realizado com sucesso!');
    console.log('Cookie HttpOnly definido automaticamente pelo servidor.');
    
    return {
      access_token, // Disponível apenas para referência (não usar manualmente)
      token_type,
      user_type,
    };
  } catch (error) {
    if (error.response?.status === 401) {
      throw new Error('Email ou senha incorretos');
    } else if (error.response?.status === 403) {
      throw new Error('Conta desativada. Entre em contato com o administrador.');
    }
    throw new Error('Erro ao realizar login. Tente novamente.');
  }
}
```

**Usando Fetch nativo:**

```javascript
// authService.js - Usando Fetch
export async function login(email, password) {
  const formData = new FormData();
  formData.append('username', email);
  formData.append('password', password);

  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      credentials: 'include', // CRÍTICO: Permite receber cookies HttpOnly
      body: formData,
      // NÃO definir Content-Type manualmente para FormData
      // O navegador define automaticamente com boundary
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Email ou senha incorretos');
      } else if (response.status === 403) {
        throw new Error('Conta desativada. Entre em contato com o administrador.');
      }
      throw new Error('Erro ao realizar login.');
    }

    const data = await response.json();
    // Cookie HttpOnly já foi definido automaticamente
    
    return data;
  } catch (error) {
    throw error;
  }
}
```

---

## 📡 Requisições Autenticadas

Após o login, todas as requisições subsequentes **automaticamente** incluem o cookie HttpOnly. Você **NÃO precisa** enviar o token manualmente no header `Authorization`.

### Exemplo Genérico

```javascript
// apiService.js
import api from './api';

/**
 * Exemplo de requisição autenticada
 * O cookie HttpOnly é enviado automaticamente
 */
export async function getDadosProtegidos() {
  try {
    // NÃO é necessário passar o token manualmente
    // O cookie HttpOnly é enviado automaticamente pelo navegador
    const response = await api.get('/alguma-rota-protegida');
    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      throw new Error('Não autenticado. Faça login novamente.');
    } else if (error.response?.status === 403) {
      throw new Error('Acesso negado. Você não tem permissão para esta ação.');
    }
    throw error;
  }
}
```

---

## 🏢 Exemplo: Listar Ambientes

A rota `GET /ambientes` exige autenticação de administrador e funciona automaticamente com cookies HttpOnly.

```javascript
// ambienteService.js
import api from './api';

/**
 * Lista todos os ambientes
 * Requer: Autenticação de administrador
 * O cookie HttpOnly é enviado automaticamente
 * 
 * @returns {Promise<Array>} Lista de ambientes
 */
export async function listarAmbientes() {
  try {
    // O cookie HttpOnly é enviado automaticamente
    // NÃO é necessário passar Authorization header
    const response = await api.get('/ambientes');
    
    return response.data;
  } catch (error) {
    if (error.response?.status === 401) {
      throw new Error('Não autenticado. Faça login como administrador.');
    } else if (error.response?.status === 403) {
      throw new Error('Acesso negado. Apenas administradores podem listar ambientes.');
    }
    throw new Error('Erro ao listar ambientes.');
  }
}
```

**Usando Fetch nativo:**

```javascript
// ambienteService.js - Usando Fetch
export async function listarAmbientes() {
  try {
    const response = await fetch(`${API_BASE_URL}/ambientes`, {
      method: 'GET',
      credentials: 'include', // CRÍTICO: Envia cookie HttpOnly automaticamente
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Não autenticado. Faça login como administrador.');
      } else if (response.status === 403) {
        throw new Error('Acesso negado. Apenas administradores podem listar ambientes.');
      }
      throw new Error('Erro ao listar ambientes.');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    throw error;
  }
}
```

### Exemplo de Uso em Componente React

```javascript
// AmbientesList.jsx
import React, { useState, useEffect } from 'react';
import { listarAmbientes } from './services/ambienteService';

function AmbientesList() {
  const [ambientes, setAmbientes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function carregarAmbientes() {
      try {
        setLoading(true);
        const dados = await listarAmbientes();
        setAmbientes(dados);
        setError(null);
      } catch (err) {
        setError(err.message);
        console.error('Erro ao carregar ambientes:', err);
      } finally {
        setLoading(false);
      }
    }

    carregarAmbientes();
  }, []);

  if (loading) return <div>Carregando ambientes...</div>;
  if (error) return <div>Erro: {error}</div>;

  return (
    <div>
      <h2>Lista de Ambientes</h2>
      <ul>
        {ambientes.map((ambiente) => (
          <li key={ambiente.id_amb}>
            <strong>{ambiente.titulo_amb}</strong>
            <p>{ambiente.descricao_questionario}</p>
            <small>Criado em: {new Date(ambiente.data_criado).toLocaleDateString()}</small>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default AmbientesList;
```

---

## 🚪 Logout

```javascript
// authService.js
import api from './api';

/**
 * Realiza logout do usuário
 * Remove o cookie HttpOnly do navegador
 */
export async function logout() {
  try {
    // O cookie HttpOnly é enviado automaticamente
    // O servidor remove o cookie na resposta
    await api.post('/auth/logout');
    
    console.log('Logout realizado com sucesso!');
    console.log('Cookie HttpOnly removido pelo servidor.');
  } catch (error) {
    // Mesmo em caso de erro, o cookie pode ter sido removido
    console.error('Erro ao realizar logout:', error);
    throw error;
  }
}
```

**Usando Fetch nativo:**

```javascript
// authService.js - Usando Fetch
export async function logout() {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include', // Envia cookie para o servidor removê-lo
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Erro ao realizar logout');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    throw error;
  }
}
```

---

## 🎣 Hook React Customizado

Aqui está um exemplo completo de hook customizado para gerenciar autenticação:

```javascript
// useAuth.js
import { useState, useEffect, createContext, useContext } from 'react';
import { login as loginService, logout as logoutService } from './services/authService';
import api from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Verifica se o usuário está autenticado ao carregar
  useEffect(() => {
    async function verificarAutenticacao() {
      try {
        // Tenta fazer uma requisição autenticada
        // Se o cookie HttpOnly for válido, a requisição terá sucesso
        const response = await api.get('/auth/me'); // Assumindo que existe esta rota
        setUser(response.data);
      } catch (error) {
        // Se falhar, o usuário não está autenticado
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    verificarAutenticacao();
  }, []);

  const login = async (email, password) => {
    try {
      const data = await loginService(email, password);
      // Após login bem-sucedido, buscar dados do usuário
      const userResponse = await api.get('/auth/me');
      setUser(userResponse.data);
      return data;
    } catch (error) {
      throw error;
    }
  };

  const logout = async () => {
    try {
      await logoutService();
      setUser(null);
    } catch (error) {
      // Mesmo em caso de erro, limpar estado local
      setUser(null);
      throw error;
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth deve ser usado dentro de AuthProvider');
  }
  return context;
}
```

**Uso do Hook:**

```javascript
// App.jsx
import { AuthProvider, useAuth } from './hooks/useAuth';
import LoginForm from './components/LoginForm';
import AmbientesList from './components/AmbientesList';

function AppContent() {
  const { user, loading, login, logout } = useAuth();

  if (loading) {
    return <div>Carregando...</div>;
  }

  if (!user) {
    return <LoginForm onLogin={login} />;
  }

  return (
    <div>
      <header>
        <p>Bem-vindo, {user.nome_completo}!</p>
        <button onClick={logout}>Sair</button>
      </header>
      <main>
        {user.is_admin && <AmbientesList />}
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
```

---

## ⚠️ Tratamento de Erros

### Códigos de Status Comuns

```javascript
// errorHandler.js
export function handleApiError(error) {
  if (!error.response) {
    // Erro de rede ou servidor não respondeu
    return 'Erro de conexão. Verifique sua internet.';
  }

  const status = error.response.status;
  const message = error.response.data?.detail || 'Erro desconhecido';

  switch (status) {
    case 401:
      return 'Não autenticado. Faça login novamente.';
    case 403:
      return 'Acesso negado. Você não tem permissão para esta ação.';
    case 404:
      return 'Recurso não encontrado.';
    case 409:
      return 'Conflito: ' + message;
    case 422:
      return 'Dados inválidos: ' + message;
    case 500:
      return 'Erro interno do servidor. Tente novamente mais tarde.';
    default:
      return message || 'Erro desconhecido';
  }
}
```

### Interceptor Global de Erros (Axios)

```javascript
// api.js
import axios from 'axios';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// Interceptor de resposta para tratamento global de erros
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    
    if (status === 401) {
      // Token expirado ou inválido
      // Redirecionar para login
      window.location.href = '/login';
    } else if (status === 403) {
      // Acesso negado
      console.error('Acesso negado:', error.response.data?.detail);
    }
    
    return Promise.reject(error);
  }
);

export default api;
```

---

## ✅ Checklist de Implementação

- [ ] Configurar `credentials: 'include'` (Fetch) ou `withCredentials: true` (Axios)
- [ ] Usar `FormData` para login (não JSON)
- [ ] Campo de login deve ser `username` (não `email`)
- [ ] **NÃO** armazenar token manualmente (cookie HttpOnly é gerenciado pelo navegador)
- [ ] **NÃO** enviar `Authorization: Bearer <token>` manualmente
- [ ] Tratar erros 401 (não autenticado) e 403 (acesso negado)
- [ ] Implementar logout para remover cookie
- [ ] Verificar CORS no backend (deve permitir credenciais)

---

## 🔒 Segurança

### Por que usar Cookies HttpOnly?

1. **Proteção contra XSS**: Cookies HttpOnly não podem ser acessados via JavaScript, protegendo contra ataques de script injection
2. **Gerenciamento automático**: O navegador gerencia o cookie automaticamente
3. **SameSite protection**: Proteção adicional contra CSRF quando configurado como `SameSite=Lax` ou `SameSite=Strict`

### Configuração CORS no Backend

Certifique-se de que o backend está configurado para aceitar credenciais:

```python
# main.py (FastAPI)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # URL do frontend
    allow_credentials=True,  # CRÍTICO: Permite cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📚 Recursos Adicionais

- [MDN: Using Fetch with credentials](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch#sending_a_request_with_credentials_included)
- [Axios: Request Config - withCredentials](https://axios-http.com/docs/config)
- [OWASP: HttpOnly Cookie](https://owasp.org/www-community/HttpOnly)

---

**Última atualização:** 2024


