"""
Rotas para gerenciamento de Opções de Ambientes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, Path
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin, get_current_user
from app.schemas.auth_schema import (
    OpcaoCreate,
    OpcaoOut,
    OpcoesListResponse
)
from app.crud import opcao_crud
from app.db.models import EventoAuditoria, LogAuditoria, Usuario
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opcoes", tags=["Opções"])


@router.post("/ambiente/{id_amb}", response_model=OpcaoOut, status_code=201)
def criar_opcao(
    id_amb: str = Path(..., description="ID do ambiente"),
    opcao: OpcaoCreate = Body(...),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Cria uma nova opção para um ambiente.
    
    - **Acesso:** Apenas administradores autenticados.
    - **Parâmetros:**
      - **id_amb**: ID do ambiente
    - **Payload:**
      - **texto**: Texto da opção (1 a 255 caracteres)
    - **Validações:**
      - Ambiente deve existir e estar ativo
      - Texto não pode ser vazio ou só espaços
      - Texto não pode exceder 255 caracteres
      - Não pode existir opção com mesmo texto no mesmo ambiente
    - **Respostas:**
      - 201: Opção criada com sucesso
      - 400: Texto inválido ou opção duplicada
      - 404: Ambiente não encontrado ou inativo
    """
    nova_opcao = opcao_crud.criar_opcao(db, id_amb, opcao.texto)
    
    if not nova_opcao:
        exc = HTTPException(
            status_code=400,
            detail="Não foi possível criar a opção. Verifique se o ambiente está ativo, se o texto é válido (1-255 caracteres) e se não há opção duplicada."
        )
        exc.code = "opcao_creation_failed"
        raise exc
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="criar_opcao").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={
                "id_opc": str(nova_opcao.id_opc),
                "id_amb": id_amb,
                "texto": nova_opcao.texto
            }
        )
        db.add(log)
        db.commit()
    
    return OpcaoOut(
        id_opc=str(nova_opcao.id_opc),
        texto=nova_opcao.texto,
        id_amb=str(nova_opcao.id_amb)
    )


@router.get("/ambiente/{id_amb}", response_model=OpcoesListResponse)
def listar_opcoes_ambiente(
    id_amb: str = Path(..., description="ID do ambiente"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista todas as opções de um ambiente.
    
    - **Acesso:** Usuários autenticados (convencionais ou administradores)
    - **Autenticação:** JWT (via cookie HttpOnly ou Bearer token)
    - **Parâmetros:**
      - **id_amb**: ID do ambiente
    - **Resposta:** Lista de opções do ambiente
    - **Respostas:**
      - 200: Lista de opções
      - 401: Não autenticado
      - 404: Ambiente não encontrado
    """
    ambiente, opcoes = opcao_crud.listar_opcoes_ambiente(db, id_amb)
    
    if not ambiente:
        exc = HTTPException(
            status_code=404,
            detail="Ambiente não encontrado."
        )
        exc.code = "ambiente_not_found"
        raise exc
    
    opcoes_out = [
        OpcaoOut(
            id_opc=str(opc.id_opc),
            texto=opc.texto,
            id_amb=str(opc.id_amb)
        )
        for opc in opcoes
    ]
    
    return OpcoesListResponse(
        id_amb=str(ambiente.id_amb),
        titulo_amb=ambiente.titulo_amb,
        opcoes=opcoes_out,
        total=len(opcoes_out)
    )

