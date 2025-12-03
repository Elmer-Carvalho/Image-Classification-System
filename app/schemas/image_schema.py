"""
Schemas para operações com imagens.
"""
from pydantic import BaseModel
from typing import List, Optional


class ImagemEncontrada(BaseModel):
    """Informações de uma imagem encontrada no banco de dados."""
    content_hash: str
    nome_img: str
    caminho_img: str

    class Config:
        from_attributes = True


class ResultadoBuscaImagem(BaseModel):
    """Resultado da busca de uma imagem específica."""
    hash: str
    encontrada: bool
    imagem: Optional[ImagemEncontrada] = None


class RespostaBuscaImagens(BaseModel):
    """Resposta da rota de busca de imagens por hash."""
    total_enviadas: int
    total_encontradas: int
    resultados: List[ResultadoBuscaImagem]
