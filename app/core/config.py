from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/image_classification"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # File monitoring
    ALLOWED_EXTENSIONS: list = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    ADMIN_NOME_COMPLETO: str = "Administrador do Sistema"
    ADMIN_EMAIL: str = "admin@seudominio.com"
    ADMIN_SENHA: str = "senha_super_secreta"
    ADMIN_CPF: str = "00000000000"

    # JWT Settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    
    # Cookie Settings
    COOKIE_NAME: str = "access_token"
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = "lax"
    COOKIE_SECURE: bool = False  # True em produção com HTTPS
    COOKIE_DOMAIN: str = None  # None para localhost
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        # Path(self.RAW_IMAGES_PATH).mkdir(parents=True, exist_ok=True)
        # Path(self.PROCESSED_IMAGES_PATH).mkdir(parents=True, exist_ok=True)

settings = Settings() 