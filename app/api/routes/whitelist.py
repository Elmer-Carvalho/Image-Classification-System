from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin
from app.schemas.auth_schema import CadastroPermitidoCreate, CadastroPermitidoOut
from app.crud import cadastro_permitido_crud
from app.db import models
from datetime import datetime, timezone
from app.db.models import EventoAuditoria, LogAuditoria

router = APIRouter(prefix="/whitelist", tags=["Whitelist"])

@router.post("/", status_code=201)
def cadastrar_email_permitido(
    cadastro: CadastroPermitidoCreate = Body(...),
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Adiciona um novo e-mail à Whitelist (lista de e-mails permitidos para cadastro de usuário).

    - **Acesso:** Apenas administradores autenticados.
    - **Payload de exemplo:**
      {
        "email": "novo.usuario@email.com",
        "id_tipo": 1
      }
    - **Respostas:**
      - 201: Cadastro permitido criado
      - 400/409/422/500: Erros de validação ou negócio
    """
    if db.query(models.Usuario).filter(models.Usuario.email == cadastro.email).first():
        exc = HTTPException(status_code=400, detail="Este email já está cadastrado como usuário. Não é possível permitir novo cadastro.")
        exc.code = "email_already_registered"
        raise exc
    if cadastro_permitido_crud.get_cadastro_permitido_by_email(db, cadastro.email):
        exc = HTTPException(status_code=409, detail="Este email já está na whitelist. Não é possível cadastrar novamente.")
        exc.code = "email_already_permitted"
        raise exc
    tipo = db.query(models.TipoUsuario).filter(models.TipoUsuario.id_tipo == cadastro.id_tipo).first()
    if not tipo:
        exc = HTTPException(status_code=422, detail="Tipo de usuário informado é inválido. Verifique o id_tipo enviado.")
        exc.code = "invalid_user_type"
        raise exc
    novo = cadastro_permitido_crud.create_cadastro_permitido(db, cadastro.email, cadastro.id_tipo, admin.administrador.id_adm)
    if not novo:
        exc = HTTPException(status_code=500, detail="Erro interno: não foi possível cadastrar o email. Tente novamente ou contate o suporte.")
        exc.code = "internal_error"
        raise exc
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="cadastrar_email_permitido").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_cad": str(novo.id_cad), "email": novo.email}
        )
        db.add(log)
        db.commit()
    return {"id_cad": str(novo.id_cad), "email": novo.email, "id_tipo": novo.id_tipo, "id_adm": str(novo.id_adm), "data_criado": novo.data_criado}

@router.get("/", response_model=list[CadastroPermitidoOut])
def listar_cadastros_permitidos(
    admin: models.Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lista todos os e-mails permitidos (Whitelist) para cadastro de usuário.

    - **Acesso:** Apenas administradores autenticados.
    - **Resposta:** Lista de e-mails permitidos com informações completas.
    """
    cadastros = cadastro_permitido_crud.list_cadastros_permitidos(db)
    result = []
    for c in cadastros:
        nome_adm = c.administrador.usuario.nome_completo if c.administrador and c.administrador.usuario else "(desconhecido)"
        result.append(
            CadastroPermitidoOut(
                id_cad=str(c.id_cad),
                email=c.email,
                id_tipo=c.id_tipo,
                id_adm=str(c.id_adm),
                nome_administrador=nome_adm,
                data_criado=c.data_criado,
                usado=c.usado,
                data_expiracao=c.data_expiracao,
                ativo=c.ativo
            )
        )
    return result

@router.delete("/{id_cad}", status_code=204)
def excluir_cadastro_permitido_route(id_cad: str, admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Realiza a exclusão lógica (desativação) de um e-mail da Whitelist pelo ID.

    - **Acesso:** Apenas administradores autenticados.
    - **Respostas:**
      - 204: E-mail desativado com sucesso
      - 404: E-mail não encontrado ou já inativo
    """
    cadastro = cadastro_permitido_crud.excluir_cadastro_permitido(db, id_cad)
    if not cadastro:
        exc = HTTPException(status_code=404, detail="Cadastro permitido não encontrado ou já inativo.")
        exc.code = "cadastro_not_found"
        raise exc
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="excluir_cadastro_permitido").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_cad": id_cad}
        )
        db.add(log)
        db.commit()
    return

@router.patch("/{id_cad}/reativar", status_code=200)
def reativar_cadastro_permitido_route(id_cad: str, admin: models.Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Reativa um e-mail desativado na Whitelist pelo ID.

    - **Acesso:** Apenas administradores autenticados.
    - **Respostas:**
      - 200: E-mail reativado com sucesso
      - 404: E-mail não encontrado ou já ativo
    """
    cadastro = cadastro_permitido_crud.reativar_cadastro_permitido(db, id_cad)
    if not cadastro:
        exc = HTTPException(status_code=404, detail="Cadastro permitido não encontrado ou já ativo.")
        exc.code = "cadastro_not_found"
        raise exc
    # Auditoria
    evento = db.query(EventoAuditoria).filter_by(nome="reativar_cadastro_permitido").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_cad": id_cad}
        )
        db.add(log)
        db.commit()
    return {"message": "Cadastro permitido reativado com sucesso."} 