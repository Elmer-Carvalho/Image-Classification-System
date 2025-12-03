"""
Rotas de teste para verificar sincronização com NextCloud.
Rotas públicas (sem autenticação) para validação.
"""
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import ConjuntoImagens, Imagem
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["Teste - Sincronização"])


# Schemas para resposta
class ConjuntoImagensOut(BaseModel):
    """Schema para informações de um ConjuntoImagens."""
    id_cnj: str
    nome_conj: str
    caminho_conj: str
    file_id: str
    imagens_sincronizadas: bool
    existe_no_nextcloud: bool
    data_proc: datetime
    data_sinc: datetime
    
    class Config:
        from_attributes = True


class ConjuntoImagensListResponse(BaseModel):
    """Schema para lista de ConjuntoImagens."""
    conjuntos: List[ConjuntoImagensOut]
    total: int


class ImagemOut(BaseModel):
    """Schema para informações de uma Imagem."""
    content_hash: str
    nome_img: str
    caminho_img: str
    existe_no_nextcloud: bool
    data_proc: datetime
    data_sinc: datetime
    metadados: Optional[dict] = None
    
    class Config:
        from_attributes = True


class ImagemListResponse(BaseModel):
    """Schema para resposta paginada de imagens."""
    imagens: List[ImagemOut]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool
    conjunto_info: Optional[ConjuntoImagensOut] = None


@router.get("/conjuntos", response_model=ConjuntoImagensListResponse)
def list_conjuntos_imagens(db: Session = Depends(get_db)):
    """
    Lista todos os ConjuntoImagens (pastas do NextCloud) no banco de dados.
    Rota pública para testes de sincronização.
    """
    try:
        conjuntos = db.query(ConjuntoImagens).order_by(ConjuntoImagens.data_proc.desc()).all()
        
        conjuntos_out = [
            ConjuntoImagensOut(
                id_cnj=str(conjunto.id_cnj),
                nome_conj=conjunto.nome_conj,
                caminho_conj=conjunto.caminho_conj,
                file_id=conjunto.file_id,
                imagens_sincronizadas=conjunto.imagens_sincronizadas,
                existe_no_nextcloud=conjunto.existe_no_nextcloud,
                data_proc=conjunto.data_proc,
                data_sinc=conjunto.data_sinc
            )
            for conjunto in conjuntos
        ]
        
        return ConjuntoImagensListResponse(
            conjuntos=conjuntos_out,
            total=len(conjuntos_out)
        )
    
    except Exception as e:
        logger.error(f"Erro ao listar conjuntos: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar conjuntos: {str(e)}"
        )


@router.get("/conjuntos/{id_cnj}/imagens", response_model=ImagemListResponse)
def list_imagens_conjunto(
    id_cnj: str = Path(..., description="UUID do ConjuntoImagens"),
    page: int = Query(default=1, ge=1, description="Número da página (começa em 1)"),
    page_size: int = Query(default=50, ge=1, le=200, description="Quantidade de imagens por página"),
    db: Session = Depends(get_db)
):
    """
    Lista imagens de um ConjuntoImagens específico com paginação.
    Rota pública para testes de sincronização.
    
    - **id_cnj**: UUID do ConjuntoImagens
    - **page**: Número da página (padrão: 1)
    - **page_size**: Quantidade de imagens por página (padrão: 50, máximo: 200)
    """
    try:
        # Buscar conjunto
        conjunto = db.query(ConjuntoImagens).filter(ConjuntoImagens.id_cnj == id_cnj).first()
        
        if not conjunto:
            raise HTTPException(
                status_code=404,
                detail=f"ConjuntoImagens com id {id_cnj} não encontrado"
            )
        
        # Buscar imagens do conjunto
        query = db.query(Imagem).filter(Imagem.id_cnj == id_cnj).order_by(Imagem.data_proc.desc())
        
        # Contar total
        total = query.count()
        
        # Calcular paginação
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        # Validar página
        if page > total_pages and total_pages > 0:
            raise HTTPException(
                status_code=404,
                detail=f"Página {page} não existe. Total de páginas: {total_pages}"
            )
        
        # Aplicar paginação
        start_idx = (page - 1) * page_size
        imagens = query.offset(start_idx).limit(page_size).all()
        
        # Converter para schema
        imagens_out = [
            ImagemOut(
                content_hash=img.content_hash,
                nome_img=img.nome_img,
                caminho_img=img.caminho_img,
                existe_no_nextcloud=img.existe_no_nextcloud,
                data_proc=img.data_proc,
                data_sinc=img.data_sinc,
                metadados=img.metadados
            )
            for img in imagens
        ]
        
        # Informações do conjunto
        conjunto_info = ConjuntoImagensOut(
            id_cnj=str(conjunto.id_cnj),
            nome_conj=conjunto.nome_conj,
            caminho_conj=conjunto.caminho_conj,
            file_id=conjunto.file_id,
            imagens_sincronizadas=conjunto.imagens_sincronizadas,
            existe_no_nextcloud=conjunto.existe_no_nextcloud,
            data_proc=conjunto.data_proc,
            data_sinc=conjunto.data_sinc
        )
        
        return ImagemListResponse(
            imagens=imagens_out,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
            conjunto_info=conjunto_info
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao listar imagens do conjunto {id_cnj}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar imagens: {str(e)}"
        )

