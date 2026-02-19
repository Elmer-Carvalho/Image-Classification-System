from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    # Environment
    ENV: str = "development"  # "development" ou "production"
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/image_classification"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # CORS: origens permitidas para requisições do navegador (separadas por vírgula)
    # Ex.: "https://meuapp.com,https://www.meuapp.com" ou em dev "http://localhost:5173,http://127.0.0.1:5173"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    
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
    COOKIE_DOMAIN: str | None = None  # None para localhost
    
    # NextCloud WebDAV Settings
    NEXTCLOUD_BASE_URL: str = ""
    NEXTCLOUD_USERNAME: str = ""
    NEXTCLOUD_PASSWORD: str = ""
    NEXTCLOUD_WEBDAV_PATH: str = "/remote.php/dav"
    NEXTCLOUD_USER_PATH: str = ""  # Path do usuário (ex: /files/username)
    NEXTCLOUD_MAX_PAGE_SIZE: int = 100  # Tamanho máximo de página para paginação
    NEXTCLOUD_VERIFY_SSL: bool = True  # Verificar certificado SSL (False apenas para desenvolvimento)
    
    # NextCloud Sync Settings
    NEXTCLOUD_SYNC_ACTIVITY_API_INTERVAL: int = 5  # Intervalo em minutos para sincronização via Activity API (padrão: 5)
    NEXTCLOUD_SYNC_WEBDAV_INTERVAL: int = 300  # Intervalo em minutos para sincronização via WebDAV (padrão: 300 = 5 horas)
    NEXTCLOUD_SYNC_INITIAL_ON_STARTUP: bool = True  # Executar sincronização completa ao iniciar o sistema (true/false, padrão: true)
    NEXTCLOUD_SYNC_MAX_RETRIES: int = 3  # Número máximo de tentativas em caso de erro (padrão: 3)
    NEXTCLOUD_SYNC_RETRY_DELAY: int = 30  # Delay em segundos entre tentativas (padrão: 30)
    NEXTCLOUD_SYNC_BATCH_SIZE: int = 50  # Tamanho do lote para processamento de imagens (padrão: 50)
    
    # Timezone Settings
    TIMEZONE: str = "America/Sao_Paulo"  # Fuso horário padrão (Brasília), pode ser alterado via .env (ex: "UTC", "America/New_York")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignora campos extras do .env que não estão no modelo

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        # Path(self.RAW_IMAGES_PATH).mkdir(parents=True, exist_ok=True)
        # Path(self.PROCESSED_IMAGES_PATH).mkdir(parents=True, exist_ok=True)

    def get_cors_origins_list(self) -> list[str]:
        """
        Retorna lista de origens permitidas para CORS.
        Apenas URLs que começam com http:// ou https:// são aceitas (segurança).
        """
        origins: list[str] = []
        for raw in self.CORS_ORIGINS.split(","):
            origin = raw.strip()
            if not origin:
                continue
            if origin.startswith("http://") or origin.startswith("https://"):
                origins.append(origin)
        return origins if origins else ["http://localhost:5173", "http://127.0.0.1:5173"]

settings = Settings() 