from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

def criar_ambiente(db: Session, titulo_amb: str, descricao: str, id_adm):
    novo = models.Ambiente(
        titulo_amb=titulo_amb,
        descricao=descricao,
        data_criado=datetime.now(timezone.utc),
        id_adm=id_adm,
        ativo=True
    )
    db.add(novo)
    try:
        db.commit()
        db.refresh(novo)
        return novo
    except IntegrityError:
        db.rollback()
        return None

def listar_ambientes(db: Session):
    return db.query(models.Ambiente).all()

def buscar_ambiente_por_titulo(db: Session, titulo_amb: str):
    return db.query(models.Ambiente).filter(models.Ambiente.titulo_amb == titulo_amb).first()

def excluir_ambiente(db: Session, id_amb):
    ambiente = db.query(models.Ambiente).filter(models.Ambiente.id_amb == id_amb, models.Ambiente.ativo == True).first()
    if ambiente:
        ambiente.ativo = False
        db.commit()
    return ambiente

def reativar_ambiente(db: Session, id_amb):
    ambiente = db.query(models.Ambiente).filter(models.Ambiente.id_amb == id_amb, models.Ambiente.ativo == False).first()
    if ambiente:
        ambiente.ativo = True
        db.commit()
    return ambiente 