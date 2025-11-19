"""
Utilitários para gerenciamento de timezone.
"""
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache do timezone
_cached_timezone: Optional[ZoneInfo] = None


def get_timezone() -> ZoneInfo:
    """
    Obtém o timezone configurado (padrão: America/Sao_Paulo - Brasília).
    
    Returns:
        ZoneInfo com o timezone configurado
    """
    global _cached_timezone
    
    if _cached_timezone is None:
        try:
            _cached_timezone = ZoneInfo(settings.TIMEZONE)
            logger.info(f"🌍 Timezone configurado: {settings.TIMEZONE}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao configurar timezone {settings.TIMEZONE}, usando UTC: {e}")
            _cached_timezone = dt_timezone.utc
    
    return _cached_timezone


def now() -> datetime:
    """
    Obtém o datetime atual no timezone configurado.
    
    Returns:
        datetime no timezone configurado
    """
    return datetime.now(get_timezone())


def utc_to_local(utc_dt: datetime) -> datetime:
    """
    Converte datetime UTC para o timezone local configurado.
    
    Args:
        utc_dt: datetime em UTC
        
    Returns:
        datetime no timezone local
    """
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=dt_timezone.utc)
    return utc_dt.astimezone(get_timezone())


def local_to_utc(local_dt: datetime) -> datetime:
    """
    Converte datetime do timezone local para UTC.
    
    Args:
        local_dt: datetime no timezone local
        
    Returns:
        datetime em UTC
    """
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=get_timezone())
    return local_dt.astimezone(dt_timezone.utc)

