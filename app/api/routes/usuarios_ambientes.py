"""
Rotas para gerenciamento de associações entre Usuários Convencionais e Ambientes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin, get_current_user
from app.schemas.auth_schema import (
    UsuarioAmbienteAssociarIn,
    UsuarioAmbientesOut,
    AmbienteInfoOut,
    AmbienteUsuariosOut,
    UsuarioInfoOut
)
from app.crud import usuarios_ambientes_crud
from app.db.models import EventoAuditoria, LogAuditoria, Usuario
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usuarios-ambientes", tags=["Usuários-Ambientes"])


@router.get("/meus-ambientes", response_model=UsuarioAmbientesOut)
def meus_ambientes(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos os ambientes associados ao usuário autenticado.
    
    - **Acesso:** Usuários autenticados (convencionais ou administradores)
    - **Autenticação:** JWT (via cookie HttpOnly ou Bearer token)
    - **Resposta:** Lista de ambientes associados ao usuário
    - **Respostas:**
      - 200: Lista de ambientes
      - 401: Não autenticado
      - 403: Usuário não é convencional ou está inativo
      - 404: Usuário não encontrado
    """
    # Verificar se é usuário convencional
    if not usuario.convencional:
        exc = HTTPException(
            status_code=403,
            detail="Apenas usuários convencionais podem ter ambientes associados."
        )
        exc.code = "not_conventional_user"
        raise exc
    
    if not usuario.ativo:
        exc = HTTPException(
            status_code=403,
            detail="Usuário inativo não pode acessar ambientes."
        )
        exc.code = "inactive_user"
        raise exc
    
    usuario_conv, ambientes = usuarios_ambientes_crud.listar_ambientes_usuario(
        db, str(usuario.convencional.id_con)
    )
    
    if not usuario_conv:
        exc = HTTPException(
            status_code=404,
            detail="Usuário convencional não encontrado."
        )
        exc.code = "usuario_not_found"
        raise exc
    
    # Converter ambientes para o schema
    ambientes_out = [
        AmbienteInfoOut(
            id_amb=amb["id_amb"],
            titulo_amb=amb["titulo_amb"],
            descricao_questionario=amb["descricao_questionario"],
            ativo=amb["ativo"],
            total_imagens=amb.get("total_imagens", 0),
            total_classificadas=amb.get("total_classificadas", 0)
        )
        for amb in ambientes
    ]
    
    return UsuarioAmbientesOut(
        id_con=str(usuario_conv.id_con),
        nome_completo=usuario_conv.usuario.nome_completo,
        email=usuario_conv.usuario.email,
        ambientes=ambientes_out
    )


@router.get("/usuario/{id_con}/ambientes", response_model=UsuarioAmbientesOut)
def listar_ambientes_usuario(
    id_con: str = Path(..., description="ID do usuário convencional"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos os ambientes associados a um usuário convencional específico.
    
    - **Acesso:** Usuários autenticados (convencionais ou administradores)
    - **Autenticação:** JWT (via cookie HttpOnly ou Bearer token)
    - **Parâmetros:**
      - **id_con**: ID do usuário convencional
    - **Resposta:** Lista de ambientes associados ao usuário
    - **Respostas:**
      - 200: Lista de ambientes
      - 401: Não autenticado
      - 403: Tentando acessar ambientes de outro usuário (apenas para convencionais)
      - 404: Usuário não encontrado
    """
    # Se for usuário convencional, só pode ver seus próprios ambientes
    if usuario.convencional:
        if str(usuario.convencional.id_con) != id_con:
            exc = HTTPException(
                status_code=403,
                detail="Você só pode visualizar seus próprios ambientes."
            )
            exc.code = "forbidden"
            raise exc
    
    usuario_conv, ambientes = usuarios_ambientes_crud.listar_ambientes_usuario(db, id_con)
    
    if not usuario_conv:
        exc = HTTPException(
            status_code=404,
            detail="Usuário convencional não encontrado ou inativo."
        )
        exc.code = "usuario_not_found"
        raise exc
    
    # Converter ambientes para o schema
    ambientes_out = [
        AmbienteInfoOut(
            id_amb=amb["id_amb"],
            titulo_amb=amb["titulo_amb"],
            descricao_questionario=amb["descricao_questionario"],
            ativo=amb["ativo"],
            total_imagens=amb.get("total_imagens", 0),
            total_classificadas=amb.get("total_classificadas", 0)
        )
        for amb in ambientes
    ]
    
    return UsuarioAmbientesOut(
        id_con=str(usuario_conv.id_con),
        nome_completo=usuario_conv.usuario.nome_completo,
        email=usuario_conv.usuario.email,
        ambientes=ambientes_out
    )


@router.post("/{id_amb}/associar", status_code=200)
def criar_associacoes(
    id_amb: str = Path(..., description="ID do ambiente"),
    payload: UsuarioAmbienteAssociarIn = Body(...),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Cria associações entre um ambiente e uma lista de usuários convencionais.
    
    - **Acesso:** Apenas administradores autenticados
    - **Parâmetros:**
      - **id_amb**: ID do ambiente
    - **Payload:**
      - **ids_usuarios**: Lista de IDs de usuários convencionais (mínimo 1)
    - **Validações:**
      - Ambiente deve existir e estar ativo
      - Todos os IDs de usuários devem ser válidos e existir
      - Usuários devem ser convencionais e estar ativos
      - Não cria associações duplicadas
    - **Respostas:**
      - 200: Associações criadas com sucesso
      - 400: IDs inválidos ou lista vazia
      - 404: Ambiente não encontrado ou inativo
    """
    ambiente, associados = usuarios_ambientes_crud.criar_associacoes(
        db, id_amb, payload.ids_usuarios
    )
    
    if ambiente is None:
        exc = HTTPException(
            status_code=404,
            detail="Ambiente não encontrado, inativo, ou IDs de usuários inválidos."
        )
        exc.code = "ambiente_not_found_or_invalid_ids"
        raise exc
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="associar_usuarios_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={
                "id_amb": id_amb,
                "ids_usuarios": associados,
                "total_associados": len(associados)
            }
        )
        db.add(log)
        db.commit()
    
    return {
        "message": f"{len(associados)} usuário(s) associado(s) ao ambiente com sucesso.",
        "id_amb": id_amb,
        "ids_usuarios_associados": associados,
        "total": len(associados)
    }


@router.post("/{id_amb}/associar-todos", status_code=200)
def associar_todos_usuarios(
    id_amb: str = Path(..., description="ID do ambiente"),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Associa todos os usuários convencionais ativos a um ambiente.
    
    - **Acesso:** Apenas administradores autenticados
    - **Parâmetros:**
      - **id_amb**: ID do ambiente
    - **Validações:**
      - Ambiente deve existir e estar ativo
      - Apenas usuários convencionais ativos são associados
      - Não cria associações duplicadas
    - **Respostas:**
      - 200: Usuários associados com sucesso
      - 404: Ambiente não encontrado ou inativo
    """
    count = usuarios_ambientes_crud.associar_todos_usuarios_ao_ambiente(db, id_amb)
    
    if count is None:
        exc = HTTPException(
            status_code=404,
            detail="Ambiente não encontrado ou inativo."
        )
        exc.code = "ambiente_not_found"
        raise exc
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="associar_todos_usuarios_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb, "total_associados": count}
        )
        db.add(log)
        db.commit()
    
    return {
        "message": f"{count} usuário(s) convencional(is) associado(s) ao ambiente.",
        "id_amb": id_amb,
        "total_associados": count
    }


@router.delete("/{id_amb}/usuario/{id_con}", status_code=204)
def excluir_associacao(
    id_amb: str = Path(..., description="ID do ambiente"),
    id_con: str = Path(..., description="ID do usuário convencional"),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Exclui logicamente uma associação entre um usuário convencional e um ambiente.
    
    - **Acesso:** Apenas administradores autenticados
    - **Parâmetros:**
      - **id_amb**: ID do ambiente
      - **id_con**: ID do usuário convencional
    - **Validações:**
      - Associação deve existir e estar ativa
      - Não tenta excluir associação já excluída
    - **Respostas:**
      - 204: Associação excluída com sucesso
      - 404: Associação não encontrada ou já inativa
    """
    vinculo = usuarios_ambientes_crud.excluir_associacao(db, id_con, id_amb)
    
    if not vinculo:
        exc = HTTPException(
            status_code=404,
            detail="Associação não encontrada ou já inativa."
        )
        exc.code = "associacao_not_found"
        raise exc
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="excluir_associacao_usuario_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb, "id_con": id_con}
        )
        db.add(log)
        db.commit()
    
    return


@router.patch("/{id_amb}/usuario/{id_con}/reativar", status_code=200)
def reativar_associacao(
    id_amb: str = Path(..., description="ID do ambiente"),
    id_con: str = Path(..., description="ID do usuário convencional"),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reativa logicamente uma associação entre um usuário convencional e um ambiente.
    
    - **Acesso:** Apenas administradores autenticados
    - **Parâmetros:**
      - **id_amb**: ID do ambiente
      - **id_con**: ID do usuário convencional
    - **Validações:**
      - Associação deve existir e estar inativa
      - Ambiente deve estar ativo
      - Usuário deve estar ativo
      - Não tenta reativar associação já ativa
    - **Respostas:**
      - 200: Associação reativada com sucesso
      - 404: Associação não encontrada, já ativa, ou não pode ser reativada (ambiente/usuário inativo)
    """
    vinculo = usuarios_ambientes_crud.reativar_associacao(db, id_con, id_amb)
    
    if not vinculo:
        exc = HTTPException(
            status_code=404,
            detail="Associação não encontrada, já ativa, ou não pode ser reativada (ambiente ou usuário inativo)."
        )
        exc.code = "associacao_not_found_or_cannot_reactivate"
        raise exc
    
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="reativar_associacao_usuario_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb, "id_con": id_con}
        )
        db.add(log)
        db.commit()
    
    return {
        "message": "Associação reativada com sucesso.",
        "id_amb": id_amb,
        "id_con": id_con
    }


@router.get("/ambiente/{id_amb}/usuarios", response_model=AmbienteUsuariosOut)
def listar_usuarios_do_ambiente(
    id_amb: str = Path(..., description="ID do ambiente"),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lista todos os usuários convencionais associados a um ambiente específico.
    
    - **Acesso:** Apenas administradores autenticados
    - **Parâmetros:**
      - **id_amb**: ID do ambiente
    - **Resposta:** Lista de usuários convencionais associados ao ambiente (apenas associações ativas)
    - **Respostas:**
      - 200: Lista de usuários associados
      - 401: Não autenticado
      - 403: Acesso negado (não é administrador)
      - 404: Ambiente não encontrado
    """
    ambiente, usuarios = usuarios_ambientes_crud.listar_usuarios_do_ambiente(db, id_amb)
    
    if not ambiente:
        exc = HTTPException(
            status_code=404,
            detail="Ambiente não encontrado."
        )
        exc.code = "ambiente_not_found"
        raise exc
    
    # Converter usuários para o schema
    usuarios_out = [
        UsuarioInfoOut(
            id_con=usr["id_con"],
            nome_completo=usr["nome_completo"],
            email=usr["email"],
            ativo=usr["ativo"],
            data_associado=usr["data_associado"]
        )
        for usr in usuarios
    ]
    
    return AmbienteUsuariosOut(
        id_amb=str(ambiente.id_amb),
        titulo_amb=ambiente.titulo_amb,
        descricao_questionario=ambiente.descricao_questionario,
        ativo=ambiente.ativo,
        usuarios=usuarios_out,
        total=len(usuarios_out)
    )
