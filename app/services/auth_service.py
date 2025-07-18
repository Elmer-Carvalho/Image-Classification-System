from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from app.core.utils import verify_password
from app.crud.user_crud import get_user_by_email
from sqlalchemy.orm import Session
from app.db import models
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.db.database import get_db
from app.crud.user_crud import get_user_by_id

# Configura logging
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.Usuario]:
    """Autentica o usuário, verificando email, senha e se está ativo."""
    user = get_user_by_email(db, email)
    if not user:
        logger.warning(f"Tentativa de login falhou: usuário não encontrado com email {email}")
        return None
    if not user.ativo:
        logger.warning(f"Tentativa de login falhou: conta desativada para o email {email}")
        return "inativo"
    if not verify_password(password, user.senha_hash):
        logger.warning(f"Tentativa de login falhou: senha incorreta para o email {email}")
        return None
    logger.info(f"Usuário com email {email} autenticado com sucesso.")
    return user

def create_access_token(data: dict) -> str:
    """Cria um novo token de acesso JWT."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    logger.info(f"Token de acesso criado para: {data.get('sub')}")
    return encoded_jwt 


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    return user


def require_admin(user = Depends(get_current_user)):
    if not user.id_tipo:
        raise HTTPException(status_code=403, detail="Usuário sem tipo definido.")
    if user.tipo.nome.lower() != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores podem realizar esta ação.")
    return user 