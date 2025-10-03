from sqlalchemy.orm import Session
from app.db import models
from app.core.utils import hash_password
from datetime import datetime, timezone

def get_user_by_email(db: Session, email: str) -> models.Usuario:
    """Busca um usuário pelo seu email."""
    return db.query(models.Usuario).filter(models.Usuario.email == email).first()

def get_user_by_id(db: Session, id_usu) -> models.Usuario:
    """Busca um usuário pelo seu id."""
    return db.query(models.Usuario).filter(models.Usuario.id_usu == id_usu).first()

def get_user_by_cpf(db: Session, cpf: str):
    """Busca usuário pelo CPF (tanto convencional quanto administrador)"""
    # Busca primeiro em convencionais
    convencional = db.query(models.UsuarioConvencional).filter(models.UsuarioConvencional.cpf == cpf).first()
    if convencional:
        return convencional.usuario
    
    # Se não encontrou, busca em administradores
    admin = db.query(models.UsuarioAdministrador).filter(models.UsuarioAdministrador.cpf == cpf).first()
    if admin:
        return admin.usuario
    
    return None

def create_usuario_convencional(db: Session, nome_completo: str, email: str, senha: str, cpf: str, id_tipo: int):
    senha_hash = hash_password(senha)
    cpf = ''.join(filter(str.isdigit, cpf))  # Sanitiza o CPF
    usuario = models.Usuario(
        nome_completo=nome_completo,
        email=email,
        senha_hash=senha_hash,
        data_criado=datetime.now(timezone.utc),
        ativo=True,
        id_tipo=id_tipo
    )
    db.add(usuario)
    db.flush()  # Para obter id_usu
    convencional = models.UsuarioConvencional(
        cpf=cpf,
        id_usu=usuario.id_usu
    )
    db.add(convencional)
    db.commit()
    db.refresh(usuario)
    return usuario

def create_usuario_administrador(db: Session, nome_completo: str, email: str, senha: str, cpf: str, id_tipo: int):
    senha_hash = hash_password(senha)
    cpf = ''.join(filter(str.isdigit, cpf))  # Sanitiza o CPF
    usuario = models.Usuario(
        nome_completo=nome_completo,
        email=email,
        senha_hash=senha_hash,
        data_criado=datetime.now(timezone.utc),
        ativo=True,
        id_tipo=id_tipo
    )
    db.add(usuario)
    db.flush()
    admin = models.UsuarioAdministrador(
        cpf=cpf,
        id_usu=usuario.id_usu
    )
    db.add(admin)
    db.commit()
    db.refresh(usuario)
    return usuario 