"""
Cache em memória para eventos do Activity API.
Armazena eventos coletados durante sincronização inicial para aplicação após WebDAV.
"""
from typing import List, Dict, Optional
import threading
import logging
from app.core.timezone import local_to_utc, now as tz_now

logger = logging.getLogger(__name__)


class EventCache:
    """
    Cache thread-safe para eventos do Activity API.
    Usado durante sincronização inicial: Activity API coleta eventos,
    WebDAV termina, então eventos são aplicados.
    """
    
    def __init__(self):
        """Inicializa cache vazio."""
        self._events: List[Dict] = []
        self._lock = threading.Lock()
        self._collected_at = None
        self._last_fetch_time = None  # Timestamp da última busca do Activity API
    
    def add_events(self, events: List[Dict], fetch_time=None):
        """
        Adiciona eventos ao cache (thread-safe).
        
        Args:
            events: Lista de eventos do Activity API
            fetch_time: Timestamp da busca (opcional, usa agora se não fornecido)
        """
        with self._lock:
            self._events.extend(events)
            if not self._collected_at and events:
                self._collected_at = local_to_utc(tz_now())
            # Atualizar timestamp da última busca
            if fetch_time is None:
                fetch_time = local_to_utc(tz_now())
            self._last_fetch_time = fetch_time
            logger.debug(f"📦 [EventCache] {len(events)} eventos adicionados (total: {len(self._events)})")
    
    def get_last_fetch_time(self):
        """Retorna timestamp da última busca do Activity API."""
        with self._lock:
            return self._last_fetch_time
    
    def set_last_fetch_time(self, timestamp):
        """Define timestamp da última busca do Activity API."""
        with self._lock:
            self._last_fetch_time = timestamp
    
    def get_events(self) -> List[Dict]:
        """
        Obtém todos os eventos do cache (thread-safe).
        
        Returns:
            Lista de eventos
        """
        with self._lock:
            return self._events.copy()
    
    def clear(self):
        """Limpa o cache (thread-safe)."""
        with self._lock:
            self._events.clear()
            self._collected_at = None
            logger.debug("🗑️ [EventCache] Cache limpo")
    
    def count(self) -> int:
        """Retorna número de eventos no cache."""
        with self._lock:
            return len(self._events)
    
    def is_empty(self) -> bool:
        """Verifica se cache está vazio."""
        return self.count() == 0

