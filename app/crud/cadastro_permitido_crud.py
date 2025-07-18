from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone


def get_cadastro_permitido_by_email(db: Session, email: str):
    return db.query(models.CadastroPermitido).filter(models.CadastroPermitido.email == email, models.CadastroPermitido.ativo == True).first()


def create_cadastro_permitido(db: Session, email: str, id_tipo: int, id_adm):
    novo = models.CadastroPermitido(
        email=email,
        id_tipo=id_tipo,
        id_adm=id_adm,
        data_criado=datetime.now(timezone.utc),
        usado=False
    )
    db.add(novo)
    try:
        db.commit()
        db.refresh(novo)
        return novo
    except IntegrityError:
        db.rollback()
        return None 


def list_cadastros_permitidos(db: Session):
    return db.query(models.CadastroPermitido).all() 


def marcar_cadastro_como_usado(db: Session, email: str):
    cadastro = get_cadastro_permitido_by_email(db, email)
    if cadastro:
        cadastro.usado = True
        db.commit()
        db.refresh(cadastro)
    return cadastro 


def excluir_cadastro_permitido(db: Session, id_cad: int):
    cadastro = db.query(models.CadastroPermitido).filter(models.CadastroPermitido.id_cad == id_cad, models.CadastroPermitido.ativo == True).first()
    if cadastro:
        cadastro.ativo = False
        db.commit()
    return cadastro


def reativar_cadastro_permitido(db: Session, id_cad: int):
    cadastro = db.query(models.CadastroPermitido).filter(models.CadastroPermitido.id_cad == id_cad, models.CadastroPermitido.ativo == False).first()
    if cadastro:
        cadastro.ativo = True
        db.commit()
    return cadastro 