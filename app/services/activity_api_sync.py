"""
Serviço de sincronização via Activity API do NextCloud.
Processa eventos de mudanças (file_created, file_deleted, file_changed).
"""
import hashlib
import io
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
import logging
import requests
from PIL import Image as PILImage

from app.db.models import ConjuntoImagens, Imagem
from app.services.nextcloud_service import NextCloudClient
from app.core.config import settings
from app.core.timezone import local_to_utc, now as tz_now

logger = logging.getLogger(__name__)


class ActivityAPISync:
    """Sincronização incremental via Activity API."""
    
    # Tipos MIME de imagens permitidas
    ALLOWED_MIME_TYPES = [
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
        'image/bmp', 'image/tiff', 'image/webp'
    ]
    
    # Extensões de arquivo permitidas
    ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    
    def __init__(self, nextcloud_client: NextCloudClient, db: Session):
        """
        Inicializa sincronização Activity API.
        
        Args:
            nextcloud_client: Cliente NextCloud configurado
            db: Sessão do banco de dados
        """
        self.client = nextcloud_client
        self.db = db
        self.base_url = nextcloud_client.base_url
        self.auth = nextcloud_client.auth
        self.verify_ssl = nextcloud_client.verify_ssl
        # Cache de arquivos já processados nesta sessão (evita logs repetitivos)
        self._processed_files = set()  # Set de caminhos já processados
        self._failed_files = set()  # Set de caminhos que falharam (não tentar novamente)
    
    def fetch_events_since(self, since_timestamp: Optional[datetime] = None) -> List[Dict]:
        """
        Busca eventos da Activity API desde um timestamp.
        
        Args:
            since_timestamp: Timestamp para buscar eventos desde então (None = todos)
            
        Returns:
            Lista de eventos
        """
        activity_url = f"{self.base_url}/ocs/v2.php/apps/activity/api/v2/activity"
        
        headers = {
            'OCS-APIRequest': 'true',
            'Accept': 'application/json'
        }
        
        # Activity API usa 'since' como timestamp Unix (segundos)
        since_param = int(since_timestamp.timestamp()) if since_timestamp else 0
        
        params = {
            'format': 'json',
            'limit': 100,  # Limite por requisição
            'since': since_param
        }
        
        try:
            logger.debug(f"📡 Buscando eventos Activity API desde timestamp: {since_param}")
            
            # Usar retry para requisições críticas
            from app.services.nextcloud_service import retry_request
            
            def _make_request():
                response = requests.get(
                    activity_url,
                    auth=self.auth,
                    headers=headers,
                    params=params,
                    timeout=30,
                    verify=self.verify_ssl
                )
                response.raise_for_status()
                return response
            
            response = retry_request(_make_request)
            data = response.json()
            
            if 'ocs' in data and 'data' in data['ocs']:
                events = data['ocs']['data']
                logger.info(f"✅ Recebidos {len(events)} eventos da Activity API")
                
                # Log detalhado dos primeiros eventos para debug
                if events and logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"📋 Estrutura do primeiro evento: {events[0]}")
                    for i, event in enumerate(events[:3]):  # Primeiros 3 eventos
                        logger.debug(f"  Evento {i+1}: type={event.get('type')}, object_name={event.get('object_name')}, subject={event.get('subject')}")
                
                return events
            else:
                logger.warning(f"⚠️ Resposta da Activity API em formato inesperado: {list(data.keys())}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Resposta completa: {data}")
                return []
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao buscar eventos da Activity API: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao buscar eventos: {e}")
            raise
    
    def process_events(self, events: List[Dict]) -> Dict[str, any]:
        """
        Processa uma lista de eventos.
        
        Args:
            events: Lista de eventos da Activity API
            
        Returns:
            Dicionário com estatísticas do processamento
        """
        stats = {
            'events_processed': 0,
            'images_created': 0,
            'images_updated': 0,
            'images_deleted': 0,
            'folders_created': 0,
            'folders_updated': 0,
            'errors': []
        }
        
        if not events:
            logger.debug("📭 Nenhum evento para processar")
            return stats
        
        # Filtrar eventos relevantes (arquivos e pastas)
        relevant_events = [
            event for event in events
            if event.get('type') in ['file_created', 'file_deleted', 'file_changed', 'file_moved', 
                                     'folder_created', 'folder_deleted', 'folder_changed']
        ]
        
        # Log de todos os tipos de eventos recebidos para debug
        if logger.isEnabledFor(logging.DEBUG):
            event_types = {}
            for event in events:
                event_type = event.get('type', 'unknown')
                event_types[event_type] = event_types.get(event_type, 0) + 1
            logger.debug(f"📊 Tipos de eventos recebidos: {event_types}")
        
        # Separar eventos de arquivos e pastas
        file_events = [e for e in relevant_events if e.get('type', '').startswith('file_')]
        folder_events = [e for e in relevant_events if e.get('type', '').startswith('folder_')]
        
        # Log objetivo dos eventos identificados
        if file_events or folder_events:
            event_summary = []
            if folder_events:
                created_folders = [e for e in folder_events if e.get('type') == 'folder_created']
                deleted_folders = [e for e in folder_events if e.get('type') == 'folder_deleted']
                if created_folders:
                    event_summary.append(f"{len(created_folders)} pasta(s) criada(s)")
                if deleted_folders:
                    event_summary.append(f"{len(deleted_folders)} pasta(s) deletada(s)")
            
            if file_events:
                created_files = [e for e in file_events if e.get('type') == 'file_created']
                deleted_files = [e for e in file_events if e.get('type') == 'file_deleted']
                changed_files = [e for e in file_events if e.get('type') == 'file_changed']
                if created_files:
                    event_summary.append(f"{len(created_files)} arquivo(s) criado(s)")
                if deleted_files:
                    event_summary.append(f"{len(deleted_files)} arquivo(s) deletado(s)")
                if changed_files:
                    event_summary.append(f"{len(changed_files)} arquivo(s) modificado(s)")
            
            if event_summary:
                logger.info(f"📋 [Activity API] Eventos identificados: {', '.join(event_summary)}")
        else:
            logger.info(f"📭 [Activity API] Nenhum evento relevante encontrado (de {len(events)} eventos totais)")
        
        # Processar eventos de pastas primeiro (para garantir que pastas existam antes de processar arquivos)
        for event in folder_events:
            try:
                event_type = event.get('type')
                if event_type == 'folder_created':
                    result = self.process_folder_created(event)
                    if result:
                        stats['folders_created'] += 1
                elif event_type == 'folder_deleted':
                    result = self.process_folder_deleted(event)
                    if result:
                        stats['folders_updated'] += 1
                elif event_type == 'folder_changed':
                    result = self.process_folder_changed(event)
                    if result:
                        stats['folders_updated'] += 1
                
                stats['events_processed'] += 1
                
            except Exception as e:
                error_msg = f"Erro ao processar evento {event.get('type', 'unknown')}: {e}"
                logger.warning(f"  ⚠️ {error_msg}")
                stats['errors'].append(error_msg)
        
        # Processar eventos de arquivos
        for event in file_events:
            try:
                event_type = event.get('type')
                
                if event_type == 'file_created':
                    result = self.process_file_created(event)
                    if result:
                        stats['images_created'] += 1
                elif event_type == 'file_deleted':
                    result = self.process_file_deleted(event)
                    if result:
                        stats['images_deleted'] += 1
                elif event_type == 'file_changed':
                    result = self.process_file_changed(event)
                    if result:
                        stats['images_updated'] += 1
                elif event_type == 'file_moved':
                    result = self.process_file_moved(event)
                    if result:
                        stats['images_updated'] += 1
                
                stats['events_processed'] += 1
                
            except Exception as e:
                error_msg = f"Erro ao processar evento {event.get('type', 'unknown')}: {e}"
                logger.warning(f"  ⚠️ {error_msg}")
                stats['errors'].append(error_msg)
        
        # Log resumido e visual
        summary_parts = []
        if stats['folders_created'] > 0:
            summary_parts.append(f"📁 {stats['folders_created']} pastas")
        if stats['images_created'] > 0:
            summary_parts.append(f"➕ {stats['images_created']} novas")
        if stats['images_updated'] > 0:
            summary_parts.append(f"🔄 {stats['images_updated']} atualizadas")
        if stats['images_deleted'] > 0:
            summary_parts.append(f"🗑️ {stats['images_deleted']} removidas")
        
        if summary_parts:
            logger.info(f"✅ [Activity API] {' | '.join(summary_parts)}")
        else:
            logger.info(f"✅ [Activity API] Nenhuma mudança detectada")
        
        return stats
    
    def process_file_created(self, event: Dict) -> bool:
        """
        Processa evento de arquivo criado.
        
        Args:
            event: Dados do evento
            
        Returns:
            True se processado com sucesso, False caso contrário
        """
        # Na Activity API do NextCloud, o caminho do arquivo está em 'object_name' ou pode ser extraído de 'subject'
        # O formato do subject é uma string como "user criou arquivo.txt"
        # O caminho real está em 'object_name' ou precisa ser construído
        
        if not isinstance(event, dict):
            logger.warning(f"⚠️ Evento em formato inválido (não é dict)")
            return False
        
        # Tentar obter caminho do arquivo - múltiplos métodos
        file_path = None
        
        # Método 1: object_name (caminho relativo) - mais comum
        if 'object_name' in event and event['object_name']:
            file_path = event['object_name']
            logger.debug(f"  📍 Caminho extraído de 'object_name': {file_path}")
        
        # Método 2: object_type e object_name
        if not file_path and 'object_type' in event and 'object_name' in event:
            if event['object_type'] == 'files' and event['object_name']:
                file_path = event['object_name']
                logger.debug(f"  📍 Caminho extraído de 'object_type' + 'object_name': {file_path}")
        
        # Método 3: Tentar extrair do subject (formato pode variar)
        if not file_path and 'subject' in event:
            subject = event['subject']
            if isinstance(subject, str):
                # Tentar extrair caminho do subject (formato: "user criou pasta/arquivo.jpg" ou similar)
                # Isso é menos confiável, mas pode funcionar em alguns casos
                logger.debug(f"  📍 Tentando extrair caminho do 'subject': {subject}")
        
        if not file_path or not file_path.strip():
            logger.warning(f"  ⚠️ Evento sem caminho válido - type: {event.get('type')}, object_name: {event.get('object_name')}, subject: {event.get('subject')}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"  📋 Evento completo: {event}")
            return False
        
        # Remover prefixo do user_path se presente
        if file_path.startswith(self.client.user_path):
            file_path = file_path[len(self.client.user_path):].lstrip('/')
        
        # Validar se é imagem
        if not self._is_image_path(file_path):
            return False  # Não é imagem, silenciosamente ignorar
        
        # Verificar se já foi processado ou falhou nesta sessão
        if file_path in self._processed_files:
            return True  # Já processado com sucesso
        if file_path in self._failed_files:
            return False  # Já falhou, não tentar novamente
        
        logger.debug(f"  📥 Processando nova imagem: {file_path}")
        
        try:
            # Extrair pasta pai do caminho
            if '/' in file_path:
                folder_path = file_path.rsplit('/', 1)[0]
            else:
                folder_path = ''  # Arquivo na raiz
            
            # Buscar informações do arquivo via WebDAV
            try:
                items = self.client.list_folder(folder_path, depth=1)
            except Exception as e:
                logger.debug(f"  ⚠️ Erro ao listar pasta {folder_path}: {e}")
                self._failed_files.add(file_path)
                return False
            
            # Normalizar caminhos para comparação
            normalized_file_path = file_path.lstrip('/')
            image_info = None
            
            for item in items:
                item_path = item.get('path', '').lstrip('/')
                # Remover user_path do item_path se presente
                if item_path.startswith(self.client.user_path.lstrip('/')):
                    item_path = item_path[len(self.client.user_path.lstrip('/')):].lstrip('/')
                
                if item_path == normalized_file_path or item_path.endswith('/' + normalized_file_path):
                    image_info = item
                    break
            
            if not image_info:
                # Arquivo não encontrado - adicionar ao cache de falhas para não tentar novamente
                self._failed_files.add(file_path)
                logger.debug(f"  ⏭️ Arquivo não encontrado (ignorado): {file_path}")
                return False
            
            # Processar imagem
            result = self._process_new_image(image_info)
            if result:
                self._processed_files.add(file_path)
                logger.debug(f"  ✅ Imagem processada: {file_path}")
            else:
                self._failed_files.add(file_path)
            return result
        
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar arquivo criado {file_path}: {e}")
            return False
    
    def process_file_deleted(self, event: Dict) -> bool:
        """
        Processa evento de arquivo deletado.
        
        Args:
            event: Dados do evento
            
        Returns:
            True se processado com sucesso
        """
        if not isinstance(event, dict):
            return False
        
        # Obter caminho do arquivo
        file_path = event.get('object_name', '')
        if not file_path:
            logger.debug(f"  ⏭️ Evento deletado sem caminho válido")
            return False
        
        # Remover prefixo do user_path se presente
        if file_path.startswith(self.client.user_path):
            file_path = file_path[len(self.client.user_path):].lstrip('/')
        
        logger.info(f"  🗑️ Processando imagem deletada: {file_path}")
        
        try:
            # Buscar imagem pelo caminho no banco (pode ter mudado, então buscar por hash também)
            # Primeiro tentar pelo caminho exato
            imagem = self.db.query(Imagem).filter_by(caminho_img=file_path).first()
            
            # Se não encontrar, tentar buscar por caminho que termina com o nome do arquivo
            if not imagem and '/' in file_path:
                filename = file_path.rsplit('/', 1)[1]
                imagem = self.db.query(Imagem).filter(Imagem.caminho_img.like(f'%/{filename}')).first()
            
            if imagem:
                imagem.existe_no_nextcloud = False
                imagem.data_sinc = local_to_utc(tz_now())
                self.db.commit()
                logger.info(f"  ✅ Imagem marcada como removida: {file_path}")
                return True
            else:
                logger.debug(f"  ⏭️ Imagem não encontrada no banco: {file_path}")
        
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar arquivo deletado {file_path}: {e}")
            self.db.rollback()
        
        return False
    
    def process_file_changed(self, event: Dict) -> bool:
        """
        Processa evento de arquivo modificado.
        
        Args:
            event: Dados do evento
            
        Returns:
            True se processado com sucesso
        """
        if not isinstance(event, dict):
            return False
        
        # Obter caminho do arquivo
        file_path = event.get('object_name', '')
        if not file_path:
            logger.debug(f"  ⏭️ Evento modificado sem caminho válido")
            return False
        
        # Remover prefixo do user_path se presente
        if file_path.startswith(self.client.user_path):
            file_path = file_path[len(self.client.user_path):].lstrip('/')
        
        # Validar se é imagem
        if not self._is_image_path(file_path):
            return False
        
        logger.info(f"  🔄 Processando imagem modificada: {file_path}")
        
        try:
            # Buscar imagem pelo caminho
            imagem = self.db.query(Imagem).filter_by(caminho_img=file_path).first()
            
            if imagem:
                # Extrair pasta pai do caminho
                if '/' in file_path:
                    folder_path = file_path.rsplit('/', 1)[0]
                else:
                    folder_path = ''  # Arquivo na raiz
                
                # Atualizar metadados
                items = self.client.list_folder(folder_path, depth=1)
                
                # Normalizar caminhos para comparação
                normalized_file_path = file_path.lstrip('/')
                image_info = None
                
                for item in items:
                    item_path = item.get('path', '').lstrip('/')
                    if item_path.startswith(self.client.user_path.lstrip('/')):
                        item_path = item_path[len(self.client.user_path.lstrip('/')):].lstrip('/')
                    
                    if item_path == normalized_file_path or item_path.endswith('/' + normalized_file_path):
                        image_info = item
                        break
                
                if image_info:
                    imagem.data_sinc = local_to_utc(tz_now())
                    if imagem.metadados and 'nextcloud' in imagem.metadados:
                        imagem.metadados['nextcloud'].update({
                            'etag': image_info.get('etag', ''),
                            'last_modified': image_info.get('last_modified').isoformat() if image_info.get('last_modified') else None
                        })
                    self.db.commit()
                    logger.debug(f"  ✅ Imagem atualizada: {file_path}")
                    return True
                else:
                    # Arquivo não encontrado - adicionar ao cache
                    self._failed_files.add(file_path)
                    logger.debug(f"  ⏭️ Arquivo não encontrado (ignorado): {file_path}")
            else:
                logger.debug(f"  ⏭️ Imagem não encontrada no banco: {file_path}")
        
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar arquivo modificado {file_path}: {e}")
            self.db.rollback()
        
        return False
    
    def process_file_moved(self, event: Dict) -> bool:
        """
        Processa evento de arquivo movido/renomeado.
        
        Args:
            event: Dados do evento
            
        Returns:
            True se processado com sucesso
        """
        # Similar ao file_changed, mas atualiza caminho
        return self.process_file_changed(event)
    
    def process_folder_created(self, event: Dict) -> bool:
        """
        Processa evento de pasta criada.
        
        Args:
            event: Dados do evento
            
        Returns:
            True se processado com sucesso
        """
        if not isinstance(event, dict):
            logger.debug(f"  ⏭️ Evento não é dict: {type(event)}")
            return False
        
        # Obter caminho da pasta - tentar múltiplos campos
        folder_path = event.get('object_name', '')
        if not folder_path:
            # Tentar extrair do subject (formato: "user criou pasta/nome")
            subject = event.get('subject', '')
            if isinstance(subject, str) and 'criou' in subject.lower():
                # Tentar extrair nome da pasta do subject
                parts = subject.split()
                if len(parts) > 2:
                    folder_path = '/'.join(parts[2:])  # Tudo após "user criou"
        
        if not folder_path:
            logger.debug(f"  ⏭️ Evento sem caminho válido: {event.get('type', 'unknown')}")
            return False
        
        # Normalizar caminho: remover prefixo do user_path se presente
        original_path = folder_path
        if folder_path.startswith(self.client.user_path):
            folder_path = folder_path[len(self.client.user_path):].lstrip('/')
        elif folder_path.startswith('/'):
            # Se começa com / mas não tem user_path, pode ser caminho absoluto
            # Tentar remover prefixo comum
            folder_path = folder_path.lstrip('/')
        
        logger.info(f"  📁 Nova pasta detectada: {folder_path} (original: {original_path})")
        
        try:
            # Buscar informações da pasta via WebDAV
            # Primeiro tentar listar a pasta diretamente
            try:
                items = self.client.list_folder(folder_path, depth=0)
            except Exception as e:
                logger.warning(f"  ⚠️ Erro ao listar pasta {folder_path}: {e}")
                # Tentar listar pasta pai e encontrar a pasta
                if '/' in folder_path:
                    parent_path = folder_path.rsplit('/', 1)[0]
                    folder_name = folder_path.rsplit('/', 1)[1]
                    try:
                        items = self.client.list_folder(parent_path, depth=1)
                        folder_info = next((item for item in items 
                                          if item.get('name', '') == folder_name and item.get('is_collection', False)), None)
                        if folder_info:
                            items = [folder_info]
                        else:
                            logger.warning(f"  ⚠️ Pasta não encontrada no NextCloud: {folder_path}")
                            return False
                    except Exception as e2:
                        logger.error(f"  ❌ Erro ao buscar pasta pai: {e2}")
                        return False
                else:
                    return False
            
            folder_info = next((item for item in items if item.get('is_collection', False)), None)
            
            if not folder_info:
                logger.warning(f"  ⚠️ Pasta não encontrada no NextCloud: {folder_path}")
                return False
            
            folder_file_id = folder_info.get('file_id', '')
            if not folder_file_id:
                logger.warning(f"  ⚠️ Pasta sem file_id: {folder_path}")
                return False
            
            # Verificar se já existe no banco
            conjunto = self.db.query(ConjuntoImagens).filter_by(file_id=folder_file_id).first()
            
            if not conjunto:
                # Criar novo ConjuntoImagens
                now = local_to_utc(tz_now())
                conjunto = ConjuntoImagens(
                    id_cnj=uuid.uuid4(),
                    nome_conj=folder_info.get('name', ''),
                    caminho_conj=folder_path,
                    file_id=folder_file_id,
                    imagens_sincronizadas=False,
                    existe_no_nextcloud=True,
                    data_proc=now,
                    data_sinc=now
                )
                self.db.add(conjunto)
                try:
                    self.db.commit()
                    logger.info(f"  ✅ Pasta criada no banco: {folder_path}")
                    
                    # Sincronizar imagens da pasta recém-criada
                    self._sync_folder_images(folder_path, conjunto.id_cnj)
                    return True
                except IntegrityError:
                    # Pasta já existe (race condition ou duplicata)
                    self.db.rollback()
                    # Buscar novamente
                    conjunto = self.db.query(ConjuntoImagens).filter_by(file_id=folder_file_id).first()
                    if conjunto:
                        conjunto.existe_no_nextcloud = True
                        conjunto.data_sinc = now
                        self.db.commit()
                        logger.debug(f"  ℹ️ Pasta já existe (duplicata tratada): {folder_path}")
                        return True
                    else:
                        logger.warning(f"  ⚠️ Erro ao criar pasta (IntegrityError): {folder_path}")
                        return False
            else:
                # Pasta já existe, apenas atualizar
                conjunto.existe_no_nextcloud = True
                conjunto.data_sinc = local_to_utc(tz_now())
                self.db.commit()
                logger.debug(f"  ℹ️ Pasta já existe: {folder_path}")
                return True
        
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar pasta criada {folder_path}: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def process_folder_deleted(self, event: Dict) -> bool:
        """
        Processa evento de pasta deletada.
        
        Args:
            event: Dados do evento
            
        Returns:
            True se processado com sucesso
        """
        if not isinstance(event, dict):
            logger.debug(f"  ⏭️ Evento não é dict: {type(event)}")
            return False
        
        # Obter caminho da pasta - tentar múltiplos campos
        folder_path = event.get('object_name', '')
        if not folder_path:
            # Tentar extrair do subject (formato: "user deletou pasta/nome")
            subject = event.get('subject', '')
            if isinstance(subject, str) and ('deletou' in subject.lower() or 'remov' in subject.lower()):
                # Tentar extrair nome da pasta do subject
                parts = subject.split()
                if len(parts) > 2:
                    folder_path = '/'.join(parts[2:])  # Tudo após "user deletou"
        
        if not folder_path:
            logger.debug(f"  ⏭️ Evento deletado sem caminho válido: {event.get('type', 'unknown')}")
            return False
        
        # Normalizar caminho: remover prefixo do user_path se presente
        original_path = folder_path
        if folder_path.startswith(self.client.user_path):
            folder_path = folder_path[len(self.client.user_path):].lstrip('/')
        elif folder_path.startswith('/'):
            folder_path = folder_path.lstrip('/')
        
        logger.info(f"  🗑️ Pasta deletada detectada: {folder_path} (original: {original_path})")
        
        try:
            # Buscar pasta no banco pelo caminho (exato ou parcial)
            conjunto = self.db.query(ConjuntoImagens).filter(
                ConjuntoImagens.caminho_conj == folder_path
            ).first()
            
            # Se não encontrar pelo caminho exato, tentar buscar pelo nome da pasta
            if not conjunto and '/' in folder_path:
                folder_name = folder_path.rsplit('/', 1)[1]
                conjunto = self.db.query(ConjuntoImagens).filter(
                    ConjuntoImagens.nome_conj == folder_name
                ).first()
            
            # Se ainda não encontrar, buscar todas as pastas que não existem mais no NextCloud
            # e marcar como deletadas (fallback)
            if not conjunto:
                logger.warning(f"  ⚠️ Pasta não encontrada no banco: {folder_path}")
                # Tentar buscar por file_id se disponível no evento
                # Mas geralmente eventos de deletado não têm file_id
                return False
            
            if conjunto:
                conjunto.existe_no_nextcloud = False
                conjunto.data_sinc = local_to_utc(tz_now())
                # Marcar imagens da pasta como removidas também
                for imagem in conjunto.imagens:
                    imagem.existe_no_nextcloud = False
                    imagem.data_sinc = local_to_utc(tz_now())
                self.db.commit()
                logger.info(f"  ✅ Pasta marcada como removida: {folder_path} ({len(conjunto.imagens)} imagens)")
                return True
        
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar pasta deletada {folder_path}: {e}", exc_info=True)
            self.db.rollback()
        
        return False
    
    def process_folder_changed(self, event: Dict) -> bool:
        """
        Processa evento de pasta modificada (renomeada/movida).
        
        Args:
            event: Dados do evento
            
        Returns:
            True se processado com sucesso
        """
        # Similar ao folder_created, mas atualiza informações
        return self.process_folder_created(event)
    
    def _sync_folder_images(self, folder_path: str, conjunto_id) -> None:
        """
        Sincroniza imagens de uma pasta específica.
        Usado quando uma nova pasta é detectada via Activity API.
        
        Args:
            folder_path: Caminho da pasta
            conjunto_id: UUID do ConjuntoImagens
        """
        try:
            # Listar imagens da pasta
            items = self.client.list_folder(folder_path, depth=1)
            images = self.client.filter_images(items)
            
            if not images:
                return
            
            logger.info(f"  📸 Sincronizando {len(images)} imagens da nova pasta...")
            
            # Processar cada imagem
            for image_info in images:
                try:
                    self._process_new_image(image_info)
                except Exception as e:
                    logger.debug(f"  ⚠️ Erro ao processar imagem {image_info.get('name', 'unknown')}: {e}")
                    continue
            
            # Marcar pasta como sincronizada
            conjunto = self.db.query(ConjuntoImagens).filter_by(id_cnj=conjunto_id).first()
            if conjunto:
                conjunto.imagens_sincronizadas = True
                self.db.commit()
            
            logger.info(f"  ✅ {len(images)} imagens sincronizadas")
        
        except Exception as e:
            logger.warning(f"  ⚠️ Erro ao sincronizar imagens da pasta {folder_path}: {e}")
            self.db.rollback()
    
    def _is_image_path(self, file_path: str) -> bool:
        """Verifica se o caminho é de uma imagem."""
        file_path_lower = file_path.lower()
        return any(file_path_lower.endswith(ext) for ext in self.ALLOWED_EXTENSIONS)
    
    def _process_new_image(self, image_info: Dict) -> bool:
        """
        Processa uma nova imagem (download, hash, inserção no banco).
        
        Args:
            image_info: Informações da imagem do NextCloud
            
        Returns:
            True se processado com sucesso
        """
        try:
            # Validar imagem
            if not self._validate_image(image_info):
                return False
            
            # Download e cálculo de hash
            response = self.client.get_file(image_info.get('path', ''))
            image_data = response.content
            
            content_hash = hashlib.sha256(image_data).hexdigest()
            
            # Verificar se já existe
            imagem = self.db.query(Imagem).filter_by(content_hash=content_hash).first()
            now = local_to_utc(tz_now())
            
            # Buscar pasta pai
            image_path = image_info.get('path', '')
            if '/' in image_path:
                folder_path = image_path.rsplit('/', 1)[0]
            else:
                folder_path = ''  # Arquivo na raiz
            
            folder_items = self.client.list_folder(folder_path, depth=0)
            folder_info = next((item for item in folder_items if item.get('is_collection', False)), None)
            
            if not folder_info:
                logger.warning(f"Pasta não encontrada para {image_info.get('path', '')}")
                return False
            
            # Buscar ou criar ConjuntoImagens
            conjunto = self.db.query(ConjuntoImagens).filter_by(file_id=folder_info.get('file_id', '')).first()
            
            if not conjunto:
                conjunto = ConjuntoImagens(
                    id_cnj=uuid.uuid4(),
                    nome_conj=folder_info.get('name', ''),
                    caminho_conj=folder_path,
                    file_id=folder_info.get('file_id', ''),
                    imagens_sincronizadas=False,
                    existe_no_nextcloud=True,
                    data_proc=now,
                    data_sinc=now
                )
                self.db.add(conjunto)
                try:
                    self.db.flush()
                except IntegrityError:
                    # Pasta já existe (race condition)
                    self.db.rollback()
                    conjunto = self.db.query(ConjuntoImagens).filter_by(file_id=folder_info.get('file_id', '')).first()
                    if not conjunto:
                        logger.warning(f"Erro ao criar pasta para imagem {image_info.get('name', 'unknown')}")
                        return False
            
            if not imagem:
                # Extrair metadados
                metadata = self._get_image_metadata(image_data)
                
                # Nova imagem
                imagem = Imagem(
                    content_hash=content_hash,
                    nome_img=image_info.get('name', ''),
                    caminho_img=image_info.get('path', ''),
                    metadados={
                        'nextcloud': {
                            'file_id': image_info.get('file_id', ''),
                            'etag': image_info.get('etag', ''),
                            'content_type': image_info.get('content_type', ''),
                            'size': image_info.get('content_length', 0),
                            'last_modified': image_info.get('last_modified').isoformat() if image_info.get('last_modified') else None
                        },
                        'image': metadata,
                        'sync': {
                            'sync_method': 'activity_api',
                            'sync_timestamp': now.isoformat()
                        }
                    },
                    existe_no_nextcloud=True,
                    data_proc=now,
                    data_sinc=now,
                    id_cnj=conjunto.id_cnj
                )
                self.db.add(imagem)
                try:
                    self.db.commit()
                    return True
                except IntegrityError:
                    # Imagem já existe (duplicata)
                    self.db.rollback()
                    # Buscar e atualizar
                    imagem = self.db.query(Imagem).filter_by(content_hash=content_hash).first()
                    if imagem:
                        imagem.nome_img = image_info.get('name', '')
                        imagem.caminho_img = image_info.get('path', '')
                        imagem.existe_no_nextcloud = True
                        imagem.data_sinc = now
                        self.db.commit()
                        return True
                    return False
            else:
                # Atualizar imagem existente
                imagem.nome_img = image_info.get('name', '')
                imagem.caminho_img = image_info.get('path', '')
                imagem.existe_no_nextcloud = True
                imagem.data_sinc = now
                self.db.commit()
                return True
        
        except Exception as e:
            logger.error(f"Erro ao processar nova imagem: {e}")
            self.db.rollback()
            return False
    
    def _validate_image(self, file_info: Dict) -> bool:
        """Valida se o arquivo é uma imagem válida."""
        name = file_info.get('name', '').lower()
        if not any(name.endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
            return False
        
        content_type = file_info.get('content_type', '').lower()
        if not any(mime in content_type for mime in self.ALLOWED_MIME_TYPES):
            return False
        
        return True
    
    def _get_image_metadata(self, image_data: bytes) -> Dict:
        """Extrai metadados da imagem usando PIL."""
        try:
            img = PILImage.open(io.BytesIO(image_data))
            return {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode
            }
        except Exception as e:
            logger.warning(f"Erro ao extrair metadados da imagem: {e}")
            return {}

