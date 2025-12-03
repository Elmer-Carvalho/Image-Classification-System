from pydantic import BaseModel, EmailStr, constr, Field
import uuid
from typing import Optional
from datetime import datetime

# Schema para a resposta do token
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: int  # 1 = convencional, 2 = admin

# Remover LoginResponse e TokenData

class CadastroPermitidoCreate(BaseModel):
    """
    Schema de entrada para cadastro de e-mail na Whitelist.
    Utilizado em: POST /whitelist
    """
    email: EmailStr
    id_tipo: int

    class Config:
        json_schema_extra = {
            "example": {
                "email": "novo.usuario@email.com",
                "id_tipo": 1
            }
        }

class CadastroPermitidoOut(BaseModel):
    """
    Schema de saída para informações de e-mail cadastrado na Whitelist.
    Utilizado em: GET /whitelist
    """
    id_cad: str
    email: EmailStr
    id_tipo: int
    id_adm: str
    nome_administrador: str
    data_criado: datetime
    usado: bool
    data_expiracao: Optional[datetime] = None
    ativo: bool  # Indica se o e-mail está ativo (permitido) ou foi excluído logicamente

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id_cad": "b1e2c3d4-5678-1234-9abc-1234567890ab",
                "email": "novo.usuario@email.com",
                "id_tipo": 1,
                "id_adm": "a1b2c3d4-5678-1234-9abc-1234567890ab",
                "nome_administrador": "Maria Admin",
                "data_criado": "2024-06-01T12:34:56.789Z",
                "usado": False,
                "data_expiracao": "2024-07-01T00:00:00.000Z",
                "ativo": True
            }
        }

class UsuarioCreate(BaseModel):
    """Schema unificado para criação de usuários (convencionais e administradores)"""
    nome_completo: constr(strip_whitespace=True, min_length=5)
    email: EmailStr
    senha: constr(min_length=8)
    cpf: constr(min_length=11, max_length=14)

    class Config:
        json_schema_extra = {
            "example": {
                "nome_completo": "João da Silva",
                "email": "joao.silva@email.com",
                "senha": "SenhaForte123",
                "cpf": "12345678901"
            }
        }

class UsuarioOut(BaseModel):
    id_usu: str
    nome_completo: str
    email: EmailStr
    tipo: str
    cpf: str | None = None
    is_admin: bool
    ativo: bool

    class Config:
        from_attributes = True 

class AmbienteCreate(BaseModel):
    """
    Schema de entrada para criação de ambiente.
    Utilizado em: POST /ambientes
    """
    titulo_amb: constr(strip_whitespace=True, min_length=3, max_length=255)
    descricao: constr(strip_whitespace=True, min_length=3)
    ids_conjuntos: list[str] = Field(..., min_length=1, description="Lista de IDs de ConjuntoImagens (mínimo 1)")

    class Config:
        json_schema_extra = {
            "example": {
                "titulo_amb": "Ambiente de Teste",
                "descricao": "Ambiente para testes e validações.",
                "ids_conjuntos": [
                    "a1b2c3d4-5678-1234-9abc-1234567890ab",
                    "b2c3d4e5-6789-2345-0bcd-2345678901bc"
                ]
            }
        }

class AmbienteOut(BaseModel):
    """
    Schema de saída para informações de ambiente.
    Utilizado em: GET /ambientes
    """
    id_amb: str
    titulo_amb: str
    descricao: str
    data_criado: datetime
    id_adm: str
    nome_administrador: str
    ativo: bool
    ids_conjuntos: Optional[list[str]] = None  # Lista de IDs de conjuntos associados (opcional na resposta)

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id_amb": "a1b2c3d4-5678-1234-9abc-1234567890ab",
                "titulo_amb": "Ambiente de Teste",
                "descricao": "Ambiente para testes e validações.",
                "data_criado": "2024-06-01T12:34:56.789Z",
                "id_adm": "b1e2c3d4-5678-1234-9abc-1234567890ab",
                "nome_administrador": "Maria Admin",
                "ativo": True,
                "ids_conjuntos": [
                    "a1b2c3d4-5678-1234-9abc-1234567890ab",
                    "b2c3d4e5-6789-2345-0bcd-2345678901bc"
                ]
            }
        } 

# Schemas para Usuario-Ambiente (novos)
class UsuarioAmbienteAssociarIn(BaseModel):
    """
    Schema de entrada para associar usuários convencionais a um ambiente.
    Utilizado em: POST /usuarios-ambientes/associar
    """
    ids_usuarios: list[str] = Field(..., min_length=1, description="Lista de IDs de usuários convencionais (mínimo 1)")

    class Config:
        json_schema_extra = {
            "example": {
                "ids_usuarios": [
                    "c1d2e3f4-5678-1234-9abc-1234567890ab",
                    "d2e3f4c5-6789-2345-0bcd-2345678901bc"
                ]
            }
        }

class AmbienteInfoOut(BaseModel):
    """Informações básicas de um ambiente."""
    id_amb: str
    titulo_amb: str
    descricao: str
    ativo: bool

    class Config:
        from_attributes = True

class UsuarioAmbientesOut(BaseModel):
    """
    Schema de saída para listagem dos ambientes de um usuário.
    Utilizado em: GET /usuarios-ambientes/meus-ambientes ou GET /usuarios-ambientes/usuario/{id_con}
    """
    id_con: str
    nome_completo: str
    email: str
    ambientes: list[AmbienteInfoOut]

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id_con": "c1d2e3f4-5678-1234-9abc-1234567890ab",
                "nome_completo": "João da Silva",
                "email": "joao@email.com",
                "ambientes": [
                    {
                        "id_amb": "a1b2c3d4-5678-1234-9abc-1234567890ab",
                        "titulo_amb": "Ambiente de Teste",
                        "descricao": "Ambiente para testes",
                        "ativo": True
                    }
                ]
            }
        }

class UsuarioAmbienteAssociacaoOut(BaseModel):
    """Schema de saída para uma associação usuário-ambiente."""
    id_con: str
    id_amb: str
    data_associado: datetime
    ativo: bool
    nome_usuario: str
    email_usuario: str
    titulo_ambiente: str

    class Config:
        from_attributes = True

class UsuarioInfoOut(BaseModel):
    """Informações básicas de um usuário convencional."""
    id_con: str
    nome_completo: str
    email: str
    ativo: bool
    data_associado: datetime

    class Config:
        from_attributes = True

class AmbienteUsuariosOut(BaseModel):
    """
    Schema de saída para listagem de usuários associados a um ambiente.
    Utilizado em: GET /usuarios-ambientes/ambiente/{id_amb}/usuarios
    """
    id_amb: str
    titulo_amb: str
    descricao: str
    ativo: bool
    usuarios: list[UsuarioInfoOut]
    total: int

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id_amb": "a1b2c3d4-5678-1234-9abc-1234567890ab",
                "titulo_amb": "Ambiente de Teste",
                "descricao": "Ambiente para testes e validações.",
                "ativo": True,
                "usuarios": [
                    {
                        "id_con": "c1d2e3f4-5678-1234-9abc-1234567890ab",
                        "nome_completo": "João da Silva",
                        "email": "joao@email.com",
                        "ativo": True,
                        "data_associado": "2024-06-01T12:34:56.789Z"
                    }
                ],
                "total": 1
            }
        }

class LogAuditoriaOut(BaseModel):
    """
    Schema de saída para um log de auditoria.
    Utilizado em: GET /auditoria/logs
    """
    id_log: str
    id_usu: str
    nome_usuario: str
    id_evento: int
    nome_evento: str
    data_evento: datetime
    detalhes: dict

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id_log": "a1b2c3d4-5678-1234-9abc-1234567890ab",
                "id_usu": "b1c2d3e4-6789-2345-0bcd-2345678901bc",
                "nome_usuario": "Maria Admin",
                "id_evento": 1,
                "nome_evento": "criar_ambiente",
                "data_evento": "2024-06-01T12:34:56.789Z",
                "detalhes": {"id_amb": "...", "titulo_amb": "..."}
            }
        }

class EventoAuditoriaOut(BaseModel):
    """
    Schema de saída para um evento de auditoria.
    Utilizado em: GET /auditoria/eventos
    """
    id_evento: int
    nome: str
    descricao: str

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id_evento": 1,
                "nome": "criar_ambiente",
                "descricao": "Criação de ambiente"
            }
        }

class LogAuditoriaPage(BaseModel):
    """
    Schema de resposta paginada para logs de auditoria.
    Inclui metadados de paginação.
    """
    logs: list[LogAuditoriaOut]
    page: int
    page_size: int
    total: int
    is_last_page: bool

    class Config:
        json_schema_extra = {
            "example": {
                "logs": [
                    {
                        "id_log": "a1b2c3d4-5678-1234-9abc-1234567890ab",
                        "id_usu": "b1c2d3e4-6789-2345-0bcd-2345678901bc",
                        "nome_usuario": "Maria Admin",
                        "id_evento": 1,
                        "nome_evento": "criar_ambiente",
                        "data_evento": "2024-06-01T12:34:56.789Z",
                        "detalhes": {"id_amb": "...", "titulo_amb": "..."}
                    }
                ],
                "page": 1,
                "page_size": 50,
                "total": 120,
                "is_last_page": False
            }
        }
