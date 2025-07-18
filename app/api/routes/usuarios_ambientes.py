from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin, get_current_user
from app.schemas.auth_schema import UsuarioAmbienteVinculoIn, UsuarioAmbienteVinculoOut, UsuarioAmbienteAmbientesOut
from app.crud import usuarios_ambientes_crud
from app.db.models import EventoAuditoria, LogAuditoria, Usuario
from datetime import datetime, timezone

router = APIRouter(prefix="/usuarios-ambientes", tags=["Usuarios-Ambientes"])

@router.post("/{id_amb}/associar-todos", status_code=200)
def associar_todos_usuarios(
    id_amb: str,
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    count = usuarios_ambientes_crud.associar_todos_usuarios_ao_ambiente(db, id_amb)
    if count is None:
        exc = HTTPException(status_code=404, detail="Ambiente não encontrado ou inativo.")
        exc.code = "ambiente_not_found"
        raise exc
    # Auditoria global
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
    return {"message": f"{count} usuários convencionais associados ao ambiente."}

@router.post("/{id_amb}/associar", status_code=200)
def associar_usuarios(
    id_amb: str,
    payload: UsuarioAmbienteVinculoIn = Body(...),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ambiente, associados = usuarios_ambientes_crud.associar_usuarios_ao_ambiente(db, id_amb, payload.ids_usuarios)
    if ambiente is None:
        exc = HTTPException(status_code=404, detail="Ambiente não encontrado ou inativo.")
        exc.code = "ambiente_not_found"
        raise exc
    # Auditoria individual
    evento = db.query(EventoAuditoria).filter_by(nome="associar_usuario_ambiente").first()
    for id_con in associados:
        if evento:
            log = LogAuditoria(
                id_usu=admin.id_usu,
                evento_id=evento.id_evento,
                data_evento=datetime.now(timezone.utc),
                detalhes={"id_amb": id_amb, "id_con": id_con}
            )
            db.add(log)
    db.commit()
    return {"message": f"{len(associados)} usuários associados ao ambiente."}

@router.delete("/{id_amb}/usuario/{id_con}", status_code=204)
def excluir_vinculo_route(id_amb: str, id_con: str, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    vinculo = usuarios_ambientes_crud.excluir_vinculo(db, id_amb, id_con)
    if not vinculo:
        exc = HTTPException(status_code=404, detail="Vínculo não encontrado ou já inativo.")
        exc.code = "vinculo_not_found"
        raise exc
    evento = db.query(EventoAuditoria).filter_by(nome="excluir_vinculo_usuario_ambiente").first()
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
def reativar_vinculo_route(id_amb: str, id_con: str, admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    vinculo = usuarios_ambientes_crud.reativar_vinculo(db, id_amb, id_con)
    if not vinculo:
        exc = HTTPException(status_code=404, detail="Vínculo não encontrado ou já ativo.")
        exc.code = "vinculo_not_found"
        raise exc
    evento = db.query(EventoAuditoria).filter_by(nome="reativar_vinculo_usuario_ambiente").first()
    if evento:
        log = LogAuditoria(
            id_usu=admin.id_usu,
            evento_id=evento.id_evento,
            data_evento=datetime.now(timezone.utc),
            detalhes={"id_amb": id_amb, "id_con": id_con}
        )
        db.add(log)
        db.commit()
    return {"message": "Vínculo reativado com sucesso."}

@router.get("/", response_model=list[UsuarioAmbienteVinculoOut])
def listar_vinculos_admin(admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    result = usuarios_ambientes_crud.listar_vinculos_admin(db)
    return result

@router.get("/meus-ambientes", response_model=UsuarioAmbienteAmbientesOut)
def meus_ambientes(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    # Só permite usuário convencional
    if not usuario.convencional or not usuario.ativo:
        exc = HTTPException(status_code=403, detail="Apenas usuários convencionais ativos podem acessar seus ambientes.")
        exc.code = "forbidden"
        raise exc
    usuario_conv, ambientes = usuarios_ambientes_crud.listar_ambientes_usuario(db, usuario.convencional.id_con)
    if not usuario_conv:
        exc = HTTPException(status_code=404, detail="Usuário não encontrado ou inativo.")
        exc.code = "usuario_not_found"
        raise exc
    return UsuarioAmbienteAmbientesOut(
        id_con=str(usuario_conv.id_con),
        nome_completo=usuario_conv.usuario.nome_completo,
        email=usuario_conv.usuario.email,
        ambientes=ambientes
    )

@router.post("/usuarios-ambientes", response_model=list[UsuarioAmbienteAmbientesOut])
def ambientes_de_usuarios(
    payload: UsuarioAmbienteVinculoIn = Body(...),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    resultados = []
    for id_con in payload.ids_usuarios:
        usuario_conv, ambientes = usuarios_ambientes_crud.listar_ambientes_usuario(db, id_con)
        if usuario_conv:
            resultados.append(UsuarioAmbienteAmbientesOut(
                id_con=str(usuario_conv.id_con),
                nome_completo=usuario_conv.usuario.nome_completo,
                email=usuario_conv.usuario.email,
                ambientes=ambientes
            ))
    return resultados 