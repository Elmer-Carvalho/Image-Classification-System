from sqlalchemy.orm import Session
from app.db.models import LogAuditoria, EventoAuditoria, Usuario
from sqlalchemy import and_, desc
from typing import Optional

def listar_logs(db: Session, page: int = 1, page_size: int = 50, id_usuario: Optional[str] = None, id_evento: Optional[int] = None, data_inicio: Optional[str] = None, data_fim: Optional[str] = None):
    query = db.query(LogAuditoria)
    if id_usuario:
        query = query.filter(LogAuditoria.id_usu == id_usuario)
    if id_evento:
        query = query.filter(LogAuditoria.evento_id == id_evento)
    if data_inicio:
        query = query.filter(LogAuditoria.data_evento >= data_inicio)
    if data_fim:
        query = query.filter(LogAuditoria.data_evento <= data_fim)
    total = query.count()
    query = query.order_by(desc(LogAuditoria.data_evento))
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    return logs, total

def listar_eventos(db: Session):
    return db.query(EventoAuditoria).order_by(EventoAuditoria.id_evento).all() 