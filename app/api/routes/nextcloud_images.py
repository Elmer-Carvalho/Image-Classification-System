"""
Rotas para acesso a imagens do NextCloud via WebDAV.
Rotas livres (sem autenticação) para testes iniciais.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import logging
from urllib.parse import unquote
from app.services.nextcloud_service import get_nextcloud_client
from app.schemas.nextcloud_schema import ImageListResponse, ImageItem
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nextcloud", tags=["NextCloud"])


@router.get("/images", response_model=ImageListResponse)
def list_images(
    folder_path: Optional[str] = Query(
        default="",
        description="Path relativo da pasta no NextCloud (vazio = raiz do usuário)"
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Número da página (começa em 1)"
    ),
    page_size: int = Query(
        default=50,
        ge=1,
        description="Quantidade de imagens por página"
    )
):
    """
    Lista imagens de uma pasta no NextCloud com paginação.
    
    - **folder_path**: Path relativo da pasta (ex: "pasta/subpasta" ou "" para raiz)
    - **page**: Número da página (padrão: 1)
    - **page_size**: Quantidade de imagens por página (padrão: 50, máximo: conforme config)
    
    Retorna lista paginada de imagens com metadados.
    """
    try:
        # Valida e limita o page_size
        max_page_size = settings.NEXTCLOUD_MAX_PAGE_SIZE
        if page_size > max_page_size:
            page_size = max_page_size
            logger.warning(f"page_size limitado a {max_page_size}")
        
        # Obtém cliente NextCloud
        client = get_nextcloud_client()
        
        # Lista todos os itens da pasta
        all_items = client.list_folder(folder_path, depth=1)
        
        # Filtra apenas imagens
        all_images = client.filter_images(all_items)
        
        # Calcula paginação
        total = len(all_images)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        # Valida página
        if page > total_pages and total_pages > 0:
            raise HTTPException(
                status_code=404,
                detail=f"Página {page} não existe. Total de páginas: {total_pages}"
            )
        
        # Aplica paginação
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_images = all_images[start_idx:end_idx]
        
        # Converte para schemas
        image_items = [
            ImageItem(
                name=img['name'],
                path=img['path'],
                content_type=img['content_type'],
                size=img.get('content_length', 0),
                last_modified=img.get('last_modified'),
                file_id=img.get('file_id', ''),
                etag=img.get('etag', ''),
                download_url=img['path']  # Path já está correto para usar na rota de download
            )
            for img in paginated_images
        ]
        
        return ImageListResponse(
            images=image_items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
    
    except ValueError as e:
        logger.error(f"Erro de validação/configuração: {e}")
        # Se for erro de configuração, retorna 500 com mensagem clara
        error_msg = str(e)
        if "não configurado" in error_msg or "deve começar com" in error_msg:
            raise HTTPException(
                status_code=500,
                detail=f"Erro de configuração do NextCloud: {error_msg}"
            )
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Erro ao listar imagens: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao acessar NextCloud: {str(e)}"
        )


@router.get("/images/{file_path:path}")
def get_image(file_path: str):
    """
    Faz download de uma imagem do NextCloud.
    
    - **file_path**: Path relativo do arquivo (use o campo `path` ou `download_url` retornado pela listagem)
      - Exemplo: "Crescentes/FIOCRUZ20190122%20(10).jpg" (com URL encoding)
      - Ou: "Crescentes/FIOCRUZ20190122 (10).jpg" (FastAPI decodifica automaticamente)
    
    **Como usar:**
    1. Liste as imagens com `GET /nextcloud/images`
    2. Use o campo `path` ou `download_url` da resposta
    3. Faça GET nesta rota com o path: `GET /nextcloud/images/{path}`
    
    Retorna o arquivo como stream de imagem (binário).
    """
    try:
        # Obtém cliente NextCloud
        client = get_nextcloud_client()
        
        # Faz download do arquivo
        response = client.get_file(file_path)
        
        # Determina content-type
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        
        # Extrai nome do arquivo do path (decodifica URL encoding se necessário)
        filename = unquote(file_path.split('/')[-1])
        
        # Retorna como streaming response
        return StreamingResponse(
            response.iter_content(chunk_size=8192),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Content-Length": response.headers.get('Content-Length', ''),
                "Cache-Control": "public, max-age=3600"  # Cache por 1 hora
            }
        )
    
    except ValueError as e:
        logger.error(f"Erro de validação/configuração: {e}")
        error_msg = str(e)
        # Se for erro de configuração, retorna 500
        if "não configurado" in error_msg or "deve começar com" in error_msg:
            raise HTTPException(
                status_code=500,
                detail=f"Erro de configuração do NextCloud: {error_msg}"
            )
        # Caso contrário, é erro de arquivo não encontrado
        raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        logger.error(f"Erro ao baixar imagem: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao acessar NextCloud: {str(e)}"
        )

