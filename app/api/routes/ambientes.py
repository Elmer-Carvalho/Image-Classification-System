from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin
from app.schemas.auth_schema import AmbienteCreate, AmbienteOut
from app.crud import ambiente_crud
from app.db import models
from datetime import datetime, timezone
from app.db.models import EventoAuditoria, LogAuditoria

router = APIRouter(prefix="/ambientes", tags=["Ambientes"])

@router.post("/", response_model=AmbienteOut, status_code=201)
def criar_ambiente(
    ambiente: AmbienteCreate = Body(...),
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Cria um novo ambiente.
    - **Acesso:** Apenas administradores autenticados.
    - **Regras:** Título único, título e descrição obrigatórios.
    - **Respostas:**
      - 201: Ambiente criado
      - 400/409/422: Erros de validação ou negócio
    """
    if ambiente_crud.buscar_ambiente_por_titulo(db, ambiente.titulo_amb):
        exc = HTTPException(status_code=409, detail="Já existe um ambiente com este título.")
        exc.code = "ambiente_title_exists"
        raise exc
    novo = ambiente_crud.criar_ambiente(db, ambiente.titulo_amb, ambiente.descricao, admin.administrador.id_adm)
    if not novo:
        exc = HTTPException(status_code=500, detail="Erro interno: não foi possível criar o ambiente. Tente novamente ou contate o suporte.")
        exc.code = "internal_error"
        raise exc
    nome_adm = admin.nome_completo
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="criar_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": str(novo.id_amb), "titulo_amb": novo.titulo_amb}
        )
        db.add(log)
        db.commit()
    return AmbienteOut(
        id_amb=str(novo.id_amb),
        titulo_amb=novo.titulo_amb,
        descricao=novo.descricao,
        data_criado=novo.data_criado,
        id_adm=str(novo.id_adm),
        nome_administrador=nome_adm,
        ativo=novo.ativo
    )

@router.get("/", response_model=list[AmbienteOut])
def listar_ambientes(
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lista todos os ambientes.
    - **Acesso:** Apenas administradores autenticados.
    - **Resposta:** Lista de ambientes com informações completas.
    """
    ambientes = ambiente_crud.listar_ambientes(db)
    result = []
    for a in ambientes:
        nome_adm = a.administrador.usuario.nome_completo if a.administrador and a.administrador.usuario else "(desconhecido)"
        result.append(
            AmbienteOut(
                id_amb=str(a.id_amb),
                titulo_amb=a.titulo_amb,
                descricao=a.descricao,
                data_criado=a.data_criado,
                id_adm=str(a.id_adm),
                nome_administrador=nome_adm,
                ativo=a.ativo
            )
        )
    return result

@router.delete("/{id_amb}", status_code=204)
def excluir_ambiente_route(id_amb: str, admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Realiza a exclusão lógica (desativação) de um ambiente pelo ID.
    - **Acesso:** Apenas administradores autenticados.
    - **Respostas:**
      - 204: Ambiente desativado com sucesso
      - 404: Ambiente não encontrado ou já inativo
    """
    ambiente = ambiente_crud.excluir_ambiente(db, id_amb)
    if not ambiente:
        exc = HTTPException(status_code=404, detail="Ambiente não encontrado ou já inativo.")
        exc.code = "ambiente_not_found"
        raise exc
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="excluir_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb}
        )
        db.add(log)
        db.commit()
    return

@router.patch("/{id_amb}/reativar", status_code=200)
def reativar_ambiente_route(id_amb: str, admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Reativa um ambiente desativado pelo ID.
    - **Acesso:** Apenas administradores autenticados.
    - **Respostas:**
      - 200: Ambiente reativado com sucesso
      - 404: Ambiente não encontrado ou já ativo
    """
    ambiente = ambiente_crud.reativar_ambiente(db, id_amb)
    if not ambiente:
        exc = HTTPException(status_code=404, detail="Ambiente não encontrado ou já ativo.")
        exc.code = "ambiente_not_found"
        raise exc
    nome_adm = ambiente.administrador.usuario.nome_completo if ambiente.administrador and ambiente.administrador.usuario else "(desconhecido)"
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="reativar_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb}
        )
        db.add(log)
        db.commit()
    return {
        "message": "Ambiente reativado com sucesso.",
        "ambiente": AmbienteOut(
            id_amb=str(ambiente.id_amb),
            titulo_amb=ambiente.titulo_amb,
            descricao=ambiente.descricao,
            data_criado=ambiente.data_criado,
            id_adm=str(ambiente.id_adm),
            nome_administrador=nome_adm,
            ativo=ambiente.ativo
        )
    } 