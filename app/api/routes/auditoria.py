from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import require_admin
from app.schemas.auth_schema import LogAuditoriaOut, EventoAuditoriaOut, LogAuditoriaPage
from app.crud import auditoria_crud
from app.db.models import LogAuditoria, EventoAuditoria, Usuario
from typing import Optional

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])

@router.get("/logs", response_model=LogAuditoriaPage)
def listar_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    id_usuario: Optional[str] = Query(None),
    id_evento: Optional[int] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db)
):
    logs, total = auditoria_crud.listar_logs(db, page, page_size, id_usuario, id_evento, data_inicio, data_fim)
    log_out = []
    for log in logs:
        usuario = db.query(Usuario).filter_by(id_usu=log.id_usu).first()
        evento = db.query(EventoAuditoria).filter_by(id_evento=log.evento_id).first()
        log_out.append(LogAuditoriaOut(
            id_log=str(log.id_log),
            id_usu=str(log.id_usu),
            nome_usuario=usuario.nome_completo if usuario else "(desconhecido)",
            id_evento=log.evento_id,
            nome_evento=evento.nome if evento else "(desconhecido)",
            data_evento=log.data_evento,
            detalhes=log.detalhes or {}
        ))
    is_last_page = (page * page_size) >= total
    return LogAuditoriaPage(
        logs=log_out,
        page=page,
        page_size=page_size,
        total=total,
        is_last_page=is_last_page
    )

@router.get("/eventos", response_model=list[EventoAuditoriaOut])
def listar_eventos(admin: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    eventos = auditoria_crud.listar_eventos(db)
    return [EventoAuditoriaOut(
        id_evento=e.id_evento,
        nome=e.nome,
        descricao=e.descricao
    ) for e in eventos] 