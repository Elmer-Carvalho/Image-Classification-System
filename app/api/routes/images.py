"""
Rotas para operações com imagens.
"""
import hashlib
import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Imagem
from app.schemas.image_schema import RespostaBuscaImagens, ResultadoBuscaImagem, ImagemEncontrada

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["Imagens"])


@router.post("/buscar-por-hash", response_model=RespostaBuscaImagens)
async def buscar_imagens_por_hash(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Busca imagens no banco de dados através do hash do conteúdo binário.
    
    - **Sem autenticação**: Esta rota é pública
    - **Upload**: Aceita 1 ou mais arquivos de imagem
    - **Processo**:
      1. Recebe as imagens via upload
      2. Calcula o hash SHA-256 do conteúdo binário de cada imagem
      3. Busca na tabela de imagens usando o hash como chave primária
      4. Retorna informações das imagens encontradas (nome e caminho)
      5. Descarta as imagens enviadas (não são salvas)
    
    - **Resposta**: Lista com informações das imagens correspondentes encontradas no banco
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma imagem foi enviada. Envie pelo menos uma imagem."
        )
    
    resultados: List[ResultadoBuscaImagem] = []
    total_encontradas = 0
    
    try:
        for file in files:
            # Validar que é uma imagem
            if not file.content_type or not file.content_type.startswith('image/'):
                logger.warning(f"Arquivo {file.filename} não é uma imagem (content-type: {file.content_type})")
                resultados.append(ResultadoBuscaImagem(
                    hash="",
                    encontrada=False,
                    imagem=None
                ))
                continue
            
            # Ler conteúdo binário da imagem
            image_data = await file.read()
            
            # Calcular hash SHA-256 (mesmo algoritmo usado na sincronização NextCloud)
            content_hash = hashlib.sha256(image_data).hexdigest()
            
            # Buscar imagem no banco de dados usando o hash como chave primária
            imagem = db.query(Imagem).filter_by(content_hash=content_hash).first()
            
            if imagem:
                total_encontradas += 1
                resultados.append(ResultadoBuscaImagem(
                    hash=content_hash,
                    encontrada=True,
                    imagem=ImagemEncontrada(
                        content_hash=imagem.content_hash,
                        nome_img=imagem.nome_img,
                        caminho_img=imagem.caminho_img
                    )
                ))
                logger.info(f"Imagem encontrada: {imagem.nome_img} (hash: {content_hash[:16]}...)")
            else:
                resultados.append(ResultadoBuscaImagem(
                    hash=content_hash,
                    encontrada=False,
                    imagem=None
                ))
                logger.debug(f"Imagem não encontrada no banco (hash: {content_hash[:16]}...)")
            
            # Limpar referência aos dados (ajuda GC)
            del image_data
        
        return RespostaBuscaImagens(
            total_enviadas=len(files),
            total_encontradas=total_encontradas,
            resultados=resultados
        )
    
    except Exception as e:
        logger.error(f"Erro ao processar upload de imagens: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar imagens: {str(e)}"
        )
