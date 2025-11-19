"""
Serviço de sincronização via WebDAV (fallback).
Processa todas as pastas e imagens do NextCloud e compara com o banco de dados.
Todas as operações são feitas em memória para garantir segurança e limpeza automática.
"""
import hashlib
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
import logging
import requests
from PIL import Image as PILImage
import io

from app.db.models import ConjuntoImagens, Imagem
from app.services.nextcloud_service import NextCloudClient
from app.core.config import settings
from app.core.timezone import local_to_utc, now as tz_now

logger = logging.getLogger(__name__)


class WebDAVSync:
    """Sincronização completa via WebDAV."""
    
    # Tipos MIME de imagens permitidas
    ALLOWED_MIME_TYPES = [
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
        'image/bmp', 'image/tiff', 'image/webp'
    ]
    
    # Extensões de arquivo permitidas
    ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    
    def __init__(self, nextcloud_client: NextCloudClient, db: Session):
        """
        Inicializa sincronização WebDAV.
        
        Args:
            nextcloud_client: Cliente NextCloud configurado
            db: Sessão do banco de dados
        """
        self.client = nextcloud_client
        self.db = db
    
    def _calculate_hash_from_bytes(self, data: bytes) -> str:
        """
        Calcula SHA-256 hash de dados em memória.
        
        Args:
            data: Dados binários
            
        Returns:
            Hash SHA-256 em hexadecimal (64 caracteres)
        """
        return hashlib.sha256(data).hexdigest()
    
    def _validate_image(self, file_info: Dict) -> bool:
        """
        Valida se o arquivo é uma imagem válida.
        
        Args:
            file_info: Dicionário com informações do arquivo do NextCloud
            
        Returns:
            True se for imagem válida, False caso contrário
        """
        # Validação por extensão
        name = file_info.get('name', '').lower()
        if not any(name.endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
            return False
        
        # Validação por content_type
        content_type = file_info.get('content_type', '').lower()
        if not any(mime in content_type for mime in self.ALLOWED_MIME_TYPES):
            return False
        
        return True
    
    def _get_image_metadata(self, image_data: bytes) -> Dict:
        """
        Extrai metadados da imagem usando PIL.
        
        Args:
            image_data: Dados binários da imagem
            
        Returns:
            Dicionário com metadados (width, height, format, mode)
        """
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
    
    def sync_all_folders(self) -> Dict[str, any]:
        """
        Sincroniza todas as pastas e imagens do NextCloud.
        
        Returns:
            Dicionário com estatísticas da sincronização
        """
        stats = {
            'folders_processed': 0,
            'folders_created': 0,
            'folders_updated': 0,
            'images_processed': 0,
            'images_created': 0,
            'images_updated': 0,
            'images_marked_removed': 0,
            'errors': []
        }
        
        try:
            # Listar todas as pastas na raiz
            logger.info("📂 [WebDAV] Listando pastas na raiz do NextCloud...")
            root_items = self.client.list_folder('', depth=1)
            folders = [item for item in root_items if item.get('is_collection', False)]
            
            logger.info(f"📂 [WebDAV] Encontradas {len(folders)} pastas para sincronizar")
            
            # Processar cada pasta
            for idx, folder in enumerate(folders, 1):
                folder_name = folder.get('name', 'unknown')
                try:
                    logger.info(f"📁 [WebDAV] [{idx}/{len(folders)}] Sincronizando pasta: {folder_name}")
                    folder_stats = self.sync_folder(folder)
                    stats['folders_processed'] += 1
                    stats['folders_created'] += folder_stats.get('created', 0)
                    stats['folders_updated'] += folder_stats.get('updated', 0)
                    stats['images_processed'] += folder_stats.get('images_processed', 0)
                    stats['images_created'] += folder_stats.get('images_created', 0)
                    stats['images_updated'] += folder_stats.get('images_updated', 0)
                    stats['images_marked_removed'] += folder_stats.get('images_marked_removed', 0)
                    
                    # Log resumido da pasta
                    img_count = folder_stats.get('images_processed', 0)
                    if img_count > 0:
                        logger.info(f"  ✅ [{idx}/{len(folders)}] {folder_name}: {img_count} imagens processadas")
                except Exception as e:
                    error_msg = f"Erro ao sincronizar pasta {folder_name}: {e}"
                    logger.error(f"  ❌ [{idx}/{len(folders)}] {folder_name}: {error_msg}")
                    stats['errors'].append(error_msg)
                    # Continuar com próxima pasta mesmo em caso de erro
            
            # Marcar pastas que não existem mais no NextCloud
            self._mark_missing_folders(folders, stats)
            
            # Log resumido final
            logger.info(f"✅ [WebDAV] Sincronização completa: {stats['folders_processed']}/{len(folders)} pastas, "
                       f"{stats['images_processed']} imagens ({stats['images_created']} novas, "
                       f"{stats['images_updated']} atualizadas, {stats['images_marked_removed']} removidas)")
            
        except Exception as e:
            error_msg = f"Erro na sincronização completa: {e}"
            logger.error(f"❌ [WebDAV] {error_msg}")
            stats['errors'].append(error_msg)
        
        return stats
    
    def sync_folder(self, folder_info: Dict) -> Dict[str, any]:
        """
        Sincroniza uma pasta específica.
        
        Args:
            folder_info: Informações da pasta do NextCloud
            
        Returns:
            Dicionário com estatísticas da sincronização da pasta
        """
        stats = {
            'created': 0,
            'updated': 0,
            'images_processed': 0,
            'images_created': 0,
            'images_updated': 0,
            'images_marked_removed': 0
        }
        
        folder_path = folder_info.get('path', '')
        folder_name = folder_info.get('name', '')
        folder_file_id = folder_info.get('file_id', '')
        
        if not folder_file_id:
            logger.warning(f"Pasta {folder_name} não tem file_id, pulando...")
            return stats
        
        # Buscar ou criar ConjuntoImagens
        conjunto = self.db.query(ConjuntoImagens).filter_by(file_id=folder_file_id).first()
        now = local_to_utc(tz_now())
        
        if not conjunto:
            # Criar novo conjunto
            conjunto = ConjuntoImagens(
                id_cnj=uuid.uuid4(),
                nome_conj=folder_name,
                caminho_conj=folder_path,
                file_id=folder_file_id,
                imagens_sincronizadas=False,
                existe_no_nextcloud=True,
                data_proc=now,
                data_sinc=now
            )
            self.db.add(conjunto)
            self.db.flush()
            stats['created'] = 1
            logger.debug(f"  ➕ [WebDAV] ConjuntoImagens criado: {folder_name}")
        else:
            # Atualizar conjunto existente
            conjunto.nome_conj = folder_name
            conjunto.caminho_conj = folder_path
            conjunto.existe_no_nextcloud = True
            conjunto.data_sinc = now
            stats['updated'] = 1
        
        # Sincronizar imagens da pasta
        image_stats = self.sync_images_in_folder(folder_path, conjunto.id_cnj)
        stats.update(image_stats)
        
        # Marcar pasta como sincronizada (sempre, mesmo se houver erros parciais)
        try:
            conjunto.imagens_sincronizadas = True
            self.db.commit()
        except Exception as e:
            logger.warning(f"  ⚠️ [WebDAV] Erro ao marcar pasta como sincronizada: {e}")
            self.db.rollback()
            # Tentar novamente
            try:
                conjunto = self.db.query(ConjuntoImagens).filter_by(file_id=folder_file_id).first()
                if conjunto:
                    conjunto.imagens_sincronizadas = True
                    self.db.commit()
            except Exception as e2:
                logger.error(f"  ❌ [WebDAV] Erro crítico ao marcar pasta como sincronizada: {e2}")
        
        return stats
    
    def sync_images_in_folder(self, folder_path: str, conjunto_id) -> Dict[str, any]:
        """
        Sincroniza imagens de uma pasta específica.
        
        Args:
            folder_path: Caminho da pasta no NextCloud
            conjunto_id: UUID do ConjuntoImagens
            
        Returns:
            Dicionário com estatísticas
        """
        stats = {
            'images_processed': 0,
            'images_created': 0,
            'images_updated': 0,
            'images_marked_removed': 0
        }
        
        try:
            # Listar todos os itens da pasta
            items = self.client.list_folder(folder_path, depth=1)
            images = self.client.filter_images(items)
            
            logger.debug(f"  📸 [WebDAV] Sincronizando {len(images)} imagens da pasta {folder_path}")
            
            # Processar em lotes
            batch_size = settings.NEXTCLOUD_SYNC_BATCH_SIZE
            for i in range(0, len(images), batch_size):
                batch = images[i:i + batch_size]
                batch_stats = self._process_image_batch(batch, folder_path, conjunto_id)
                
                stats['images_processed'] += batch_stats['processed']
                stats['images_created'] += batch_stats['created']
                stats['images_updated'] += batch_stats['updated']
                
                # Commit após cada lote
                self.db.commit()
            
            # Identificar imagens removidas
            removed_count = self._mark_removed_images(folder_path, conjunto_id, images)
            stats['images_marked_removed'] = removed_count
            
        except Exception as e:
            logger.error(f"Erro ao sincronizar imagens da pasta {folder_path}: {e}")
            self.db.rollback()
            raise
        
        return stats
    
    def _process_image_batch(self, images: List[Dict], folder_path: str, conjunto_id) -> Dict[str, int]:
        """
        Processa um lote de imagens.
        
        Args:
            images: Lista de informações de imagens do NextCloud
            folder_path: Caminho da pasta
            conjunto_id: UUID do ConjuntoImagens
            
        Returns:
            Estatísticas do lote
        """
        stats = {'processed': 0, 'created': 0, 'updated': 0}
        now = local_to_utc(tz_now())
        
        for image_info in images:
            try:
                # Validar imagem
                if not self._validate_image(image_info):
                    continue
                
                # Download temporário seguro
                content_hash, metadata = self._download_and_process_image(image_info)
                
                if not content_hash:
                    continue
                
                # Buscar imagem no banco (usar merge para evitar duplicatas)
                imagem = self.db.query(Imagem).filter_by(content_hash=content_hash).first()
                
                if not imagem:
                    # Nova imagem - usar flush para detectar duplicatas antes do commit
                    try:
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
                                    'sync_method': 'webdav',
                                    'sync_timestamp': now.isoformat()
                                }
                            },
                            existe_no_nextcloud=True,
                            data_proc=now,
                            data_sinc=now,
                            id_cnj=conjunto_id
                        )
                        self.db.add(imagem)
                        self.db.flush()  # Flush para detectar duplicatas antes do commit
                        stats['created'] += 1
                    except IntegrityError:
                        # Imagem foi adicionada por outro processo, fazer merge
                        self.db.rollback()
                        imagem = self.db.query(Imagem).filter_by(content_hash=content_hash).first()
                        if imagem:
                            # Atualizar imagem existente
                            imagem.nome_img = image_info.get('name', '')
                            imagem.caminho_img = image_info.get('path', '')
                            imagem.existe_no_nextcloud = True
                            imagem.data_sinc = now
                            stats['updated'] += 1
                        else:
                            # Não deveria acontecer, mas se acontecer, pular
                            logger.debug(f"  ⚠️ [WebDAV] Imagem com hash {content_hash[:16]}... não encontrada após IntegrityError")
                            continue
                else:
                    # Imagem existente - atualizar
                    imagem.nome_img = image_info.get('name', '')
                    imagem.caminho_img = image_info.get('path', '')
                    imagem.existe_no_nextcloud = True
                    imagem.data_sinc = now
                    
                    # Atualizar metadados
                    if imagem.metadados:
                        if 'nextcloud' in imagem.metadados:
                            imagem.metadados['nextcloud'].update({
                                'file_id': image_info.get('file_id', ''),
                                'etag': image_info.get('etag', ''),
                                'last_modified': image_info.get('last_modified').isoformat() if image_info.get('last_modified') else None
                            })
                        else:
                            imagem.metadados['nextcloud'] = {
                                'file_id': image_info.get('file_id', ''),
                                'etag': image_info.get('etag', ''),
                                'content_type': image_info.get('content_type', ''),
                                'size': image_info.get('content_length', 0),
                                'last_modified': image_info.get('last_modified').isoformat() if image_info.get('last_modified') else None
                            }
                        imagem.metadados['sync'] = {
                            'sync_method': 'webdav',
                            'sync_timestamp': now.isoformat()
                        }
                    
                    stats['updated'] += 1
                
                stats['processed'] += 1
                
            except IntegrityError as e:
                # Tratar duplicatas explicitamente
                self.db.rollback()
                logger.debug(f"  ⚠️ [WebDAV] Duplicata detectada para {image_info.get('name', 'unknown')}, fazendo merge...")
                # Tentar buscar novamente e atualizar
                try:
                    content_hash, _ = self._download_and_process_image(image_info)
                    if content_hash:
                        imagem = self.db.query(Imagem).filter_by(content_hash=content_hash).first()
                        if imagem:
                            imagem.nome_img = image_info.get('name', '')
                            imagem.caminho_img = image_info.get('path', '')
                            imagem.existe_no_nextcloud = True
                            imagem.data_sinc = now
                            stats['updated'] += 1
                            stats['processed'] += 1
                except Exception as e2:
                    logger.debug(f"  ⚠️ [WebDAV] Erro ao fazer merge de duplicata: {e2}")
                continue
            except Exception as e:
                logger.debug(f"  ⚠️ [WebDAV] Erro ao processar imagem {image_info.get('name', 'unknown')}: {e}")
                self.db.rollback()
                continue
        
        return stats
    
    def _download_and_process_image(self, image_info: Dict) -> Tuple[Optional[str], Dict]:
        """
        Faz download da imagem em memória, calcula hash e extrai metadados.
        Não usa arquivos temporários - tudo em memória para garantir limpeza automática.
        
        Args:
            image_info: Informações da imagem do NextCloud
            
        Returns:
            Tupla (content_hash, metadata) ou (None, {}) em caso de erro
        """
        try:
            # Download da imagem diretamente em memória
            response = self.client.get_file(image_info.get('path', ''))
            image_data = response.content
            
            # Calcular hash em memória (mais eficiente e seguro)
            content_hash = self._calculate_hash_from_bytes(image_data)
            
            # Extrair metadados
            metadata = self._get_image_metadata(image_data)
            
            # Limpar referência aos dados (ajuda GC)
            del image_data
            
            return content_hash, metadata
            
        except requests.exceptions.ConnectionError as e:
            # Erro de conexão - não é crítico, apenas logar e continuar
            logger.warning(f"⚠️ [WebDAV] Erro de conexão ao baixar {image_info.get('name', 'unknown')}: {e}")
            return None, {}
        except requests.exceptions.Timeout as e:
            logger.warning(f"⚠️ [WebDAV] Timeout ao baixar {image_info.get('name', 'unknown')}: {e}")
            return None, {}
        except Exception as e:
            # Outros erros - logar mas não interromper o processo
            logger.debug(f"⚠️ [WebDAV] Erro ao processar imagem {image_info.get('name', 'unknown')}: {e}")
            return None, {}
    
    def _mark_removed_images(self, folder_path: str, conjunto_id, current_images: List[Dict]) -> int:
        """
        Marca imagens que não existem mais no NextCloud.
        
        Args:
            folder_path: Caminho da pasta
            conjunto_id: UUID do ConjuntoImagens
            current_images: Lista de imagens atuais no NextCloud
            
        Returns:
            Número de imagens marcadas como removidas
        """
        # Obter file_ids das imagens atuais
        current_file_ids = {img.get('file_id') for img in current_images if img.get('file_id')}
        
        # Buscar todas as imagens do conjunto no banco que ainda existem no NextCloud
        imagens_banco = self.db.query(Imagem).filter(
            and_(
                Imagem.id_cnj == conjunto_id,
                Imagem.existe_no_nextcloud == True
            )
        ).all()
        
        removed_count = 0
        for imagem in imagens_banco:
            file_id = imagem.metadados.get('nextcloud', {}).get('file_id') if imagem.metadados else None
            if file_id and file_id not in current_file_ids:
                imagem.existe_no_nextcloud = False
                imagem.data_sinc = local_to_utc(tz_now())
                removed_count += 1
        
        if removed_count > 0:
            self.db.commit()
            if removed_count > 0:
                logger.debug(f"  🗑️ [WebDAV] {removed_count} imagens marcadas como removidas na pasta {folder_path}")
        
        return removed_count
    
    def _mark_missing_folders(self, current_folders: List[Dict], stats: Dict):
        """
        Marca pastas que não existem mais no NextCloud.
        
        Args:
            current_folders: Lista de pastas atuais no NextCloud
            stats: Dicionário de estatísticas (para atualizar)
        """
        current_file_ids = {folder.get('file_id') for folder in current_folders if folder.get('file_id')}
        
        # Buscar todas as pastas que ainda existem no NextCloud
        pastas_banco = self.db.query(ConjuntoImagens).filter(
            ConjuntoImagens.existe_no_nextcloud == True
        ).all()
        
        now = local_to_utc(tz_now())
        for pasta in pastas_banco:
            if pasta.file_id not in current_file_ids:
                pasta.existe_no_nextcloud = False
                pasta.data_sinc = now
                # Marcar todas as imagens da pasta como removidas também
                self.db.query(Imagem).filter(Imagem.id_cnj == pasta.id_cnj).update({
                    'existe_no_nextcloud': False,
                    'data_sinc': now
                })
        
        self.db.commit()

