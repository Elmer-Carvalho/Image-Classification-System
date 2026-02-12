"""
Rotas para classificação de imagens em ambientes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.database import get_db
from app.services.auth_service import get_current_user
from app.schemas.classificacao_schema import (
    ImagensClassificacaoResponse,
    ImagemClassificacaoOut,
    ClassificacaoInfoOut,
    AvancarRequest,
    VoltarRequest,
    ClassificarRequest,
    ClassificarResponse
)
from app.crud import classificacao_crud
from app.db import models
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import uuid
from urllib.parse import quote

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classificacoes", tags=["Classificações"])

class HistoricoItemOut(BaseModel):
    content_hash: str
    nome_img: str
    url_img: str
    opcao_escolhida: str
    data_classificacao: datetime
    nome_ambiente: str
    id_amb: str

class HistoricoResponse(BaseModel):
    total: int
    items: List[HistoricoItemOut]

def _montar_resposta_imagens(
    db: Session,
    imagens: List[models.Imagem],
    id_con: str,
    tem_mais: bool
) -> ImagensClassificacaoResponse:
    """
    Monta resposta com imagens e suas classificações.
    """
    if not imagens:
        return ImagensClassificacaoResponse(
            imagens=[],
            total=0,
            tem_mais=False
        )
    
    # Buscar classificações do usuário para essas imagens
    classificacoes_dict = classificacao_crud.obter_classificacoes_imagens(
        db, id_con, imagens
    )
    
    # Montar lista de imagens com classificações
    imagens_out = []
    for img in imagens:
        classificacao = classificacoes_dict.get(img.content_hash)
        
        # Montar URL de download via proxy NextCloud
        # O caminho_img já está no formato relativo (ex: "pasta/arquivo.jpg")
        # A rota /nextcloud/images/{file_path:path} aceita o path diretamente
        path_limpo = img.caminho_img.lstrip('/')
        download_url = f"/nextcloud/images/{quote(path_limpo, safe='/')}"
        
        classificacao_out = None
        if classificacao:
            # Buscar texto da opção
            opcao = db.query(models.Opcao).filter_by(id_opc=classificacao.id_opc).first()
            texto_opcao = opcao.texto if opcao else "Opção não encontrada"
            
            classificacao_out = ClassificacaoInfoOut(
                id_cla=str(classificacao.id_cla),
                id_opc=str(classificacao.id_opc),
                texto_opcao=texto_opcao,
                data_criado=classificacao.data_criado,
                data_modificado=classificacao.data_modificado
            )
        
        imagens_out.append(
            ImagemClassificacaoOut(
                content_hash=img.content_hash,
                nome_img=img.nome_img,
                caminho_img=img.caminho_img,
                data_proc=img.data_proc,
                data_sinc=img.data_sinc,
                download_url=download_url,
                classificacao=classificacao_out
            )
        )
    
    return ImagensClassificacaoResponse(
        imagens=imagens_out,
        total=len(imagens_out),
        tem_mais=tem_mais
    )


def _obter_id_con_usuario(db: Session, usuario: models.Usuario) -> str:
    """
    Obtém o ID do usuário convencional a partir do usuário.
    """
    if not usuario.convencional:
        raise HTTPException(
            status_code=403,
            detail="Apenas usuários convencionais podem classificar imagens."
        )
    return str(usuario.convencional.id_con)


def _verificar_acesso_ambiente(db: Session, id_con: str, id_amb: str) -> bool:
    """
    Verifica se o usuário tem acesso ao ambiente (associação ativa).
    
    Args:
        db: Sessão do banco de dados
        id_con: ID do usuário convencional
        id_amb: ID do ambiente
    
    Returns:
        True se tem acesso, False caso contrário
    """
    try:
        id_con_uuid = uuid.UUID(id_con) if isinstance(id_con, str) else id_con
        id_amb_uuid = uuid.UUID(id_amb) if isinstance(id_amb, str) else id_amb
    except (ValueError, TypeError):
        return False
    
    associacao = db.query(models.UsuarioAmbiente).filter_by(
        id_con=id_con_uuid,
        id_amb=id_amb_uuid,
        ativo=True
    ).first()
    
    if not associacao:
        return False
    
    # Verificar se o ambiente está ativo
    ambiente = db.query(models.Ambiente).filter_by(
        id_amb=id_amb_uuid,
        ativo=True
    ).first()
    
    return ambiente is not None


@router.get("/ambiente/{id_amb}/inicializar", response_model=ImagensClassificacaoResponse)
def inicializar_classificacao(
    id_amb: str = Path(..., description="ID do ambiente"),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Inicializa a classificação de imagens de um ambiente.
    
    Retorna as primeiras 20 imagens não classificadas a partir do progresso do usuário.
    Se o usuário já tem progresso, retoma de onde parou.
    
    - **Acesso:** Usuários autenticados (convencionais)
    - **Autenticação:** JWT (via cookie HttpOnly ou Bearer token)
    - **Resposta:** Lista de até 20 imagens com suas classificações (se existirem)
    """
    try:
        id_con = _obter_id_con_usuario(db, usuario)
        
        # Verificar acesso ao ambiente
        if not _verificar_acesso_ambiente(db, id_con, id_amb):
            raise HTTPException(
                status_code=403,
                detail="Você não tem acesso a este ambiente ou o ambiente está inativo."
            )
        
        # Buscar imagens iniciais
        imagens, tem_mais = classificacao_crud.buscar_imagens_inicial(
            db, id_amb, id_con, limit=20
        )
        
        return _montar_resposta_imagens(db, imagens, id_con, tem_mais)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao inicializar classificação: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao inicializar classificação: {str(e)}"
        )

@router.get("/contagem", response_model=dict)
def obter_contagem_classificacoes(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna o total de IMAGENS ÚNICAS classificadas pelo usuário.
    Não importa se ele marcou 1 ou 10 opções na mesma imagem, conta como 1.
    """
    try:
        if not usuario.convencional:
            return {"total": 0}

        id_con = usuario.convencional.id_con
        
        # A MÁGICA ESTÁ AQUI:
        # 1. Selecionamos apenas a coluna do ID da Imagem (.id_img)
        # 2. Usamos .distinct() para remover duplicatas (se a mesma imagem aparecer 3x, vira 1)
        # 3. Contamos o resultado final
        total = db.query(models.Classificacao.id_img)\
            .filter(models.Classificacao.id_con == id_con)\
            .distinct()\
            .count()
            
        return {"total": total}
        
    except Exception as e:
        logger.error(f"Erro ao obter contagem: {e}")
        return {"total": 0}
@router.post("/ambiente/{id_amb}/avancar", response_model=ImagensClassificacaoResponse)
def avancar_imagens(
    id_amb: str = Path(..., description="ID do ambiente"),
    request: AvancarRequest = Body(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Avança na lista de imagens de um ambiente.
    
    Retorna as próximas 20 imagens após a imagem identificada pelo hash.
    Pode incluir imagens já classificadas.
    
    - **Acesso:** Usuários autenticados (convencionais)
    - **Autenticação:** JWT (via cookie HttpOnly ou Bearer token)
    - **Body:** Hash da imagem atual
    - **Resposta:** Lista de até 20 imagens com suas classificações (se existirem)
    """
    try:
        id_con = _obter_id_con_usuario(db, usuario)
        
        # Verificar acesso ao ambiente
        if not _verificar_acesso_ambiente(db, id_con, id_amb):
            raise HTTPException(
                status_code=403,
                detail="Você não tem acesso a este ambiente ou o ambiente está inativo."
            )
        
        # Buscar próximas imagens
        imagens, tem_mais = classificacao_crud.buscar_imagens_avancar(
            db, id_amb, id_con, request.content_hash, limit=20
        )
        
        if not imagens:
            raise HTTPException(
                status_code=404,
                detail="Não há mais imagens disponíveis ou a imagem de referência não foi encontrada."
            )
        
        return _montar_resposta_imagens(db, imagens, id_con, tem_mais)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao avançar imagens: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao avançar imagens: {str(e)}"
        )


@router.post("/ambiente/{id_amb}/voltar", response_model=ImagensClassificacaoResponse)
def voltar_imagens(
    id_amb: str = Path(..., description="ID do ambiente"),
    request: VoltarRequest = Body(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Volta na lista de imagens de um ambiente.
    
    Retorna as 20 imagens anteriores à imagem identificada pelo hash.
    Pode incluir imagens já classificadas.
    
    - **Acesso:** Usuários autenticados (convencionais)
    - **Autenticação:** JWT (via cookie HttpOnly ou Bearer token)
    - **Body:** Hash da imagem atual
    - **Resposta:** Lista de até 20 imagens com suas classificações (se existirem)
    """
    try:
        id_con = _obter_id_con_usuario(db, usuario)
        
        # Verificar acesso ao ambiente
        if not _verificar_acesso_ambiente(db, id_con, id_amb):
            raise HTTPException(
                status_code=403,
                detail="Você não tem acesso a este ambiente ou o ambiente está inativo."
            )
        
        # Buscar imagens anteriores
        imagens, tem_mais = classificacao_crud.buscar_imagens_voltar(
            db, id_amb, id_con, request.content_hash, limit=20
        )
        
        if not imagens:
            raise HTTPException(
                status_code=404,
                detail="Não há imagens anteriores ou a imagem de referência não foi encontrada."
            )
        
        return _montar_resposta_imagens(db, imagens, id_con, tem_mais)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao voltar imagens: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao voltar imagens: {str(e)}"
        )


@router.post("/ambiente/{id_amb}/classificar", response_model=ClassificarResponse)
def classificar_imagem(
    id_amb: str = Path(..., description="ID do ambiente"),
    request: ClassificarRequest = Body(...),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Classifica uma imagem.
    
    Cria uma nova classificação ou atualiza uma classificação existente.
    Atualiza o progresso do usuário automaticamente.
    
    - **Acesso:** Usuários autenticados (convencionais)
    - **Autenticação:** JWT (via cookie HttpOnly ou Bearer token)
    - **Body:** Hash da imagem e ID da opção escolhida
    - **Resposta:** Confirmação com informações da classificação
    """
    try:
        id_con = _obter_id_con_usuario(db, usuario)
        
        # Verificar acesso ao ambiente
        if not _verificar_acesso_ambiente(db, id_con, id_amb):
            raise HTTPException(
                status_code=403,
                detail="Você não tem acesso a este ambiente ou o ambiente está inativo."
            )
        
        # Verificar se a imagem pertence ao ambiente
        imagem = db.query(models.Imagem).filter_by(content_hash=request.content_hash).first()
        if imagem:
            conjuntos_ids = classificacao_crud.buscar_conjuntos_ambiente(db, id_amb)
            if imagem.id_cnj not in conjuntos_ids:
                raise HTTPException(
                    status_code=400,
                    detail="A imagem não pertence a este ambiente."
                )
        
        # Criar ou atualizar classificação
        classificacao, foi_criada = classificacao_crud.criar_ou_atualizar_classificacao(
            db, id_con, id_amb, request.content_hash, request.id_opc
        )
        
        if not classificacao:
            raise HTTPException(
                status_code=400,
                detail="Não foi possível criar/atualizar a classificação. Verifique se a imagem e a opção são válidas."
            )
        
        # Buscar texto da opção
        opcao = db.query(models.Opcao).filter_by(id_opc=classificacao.id_opc).first()
        texto_opcao = opcao.texto if opcao else "Opção não encontrada"
        
        # Buscar total de classificadas
        progresso = classificacao_crud.obter_progresso_usuario(db, id_con, id_amb)
        total_classificadas = progresso.total_classificadas if progresso else 0
        
        return ClassificarResponse(
            message="Classificação salva com sucesso." if foi_criada else "Classificação atualizada com sucesso.",
            classificacao=ClassificacaoInfoOut(
                id_cla=str(classificacao.id_cla),
                id_opc=str(classificacao.id_opc),
                texto_opcao=texto_opcao,
                data_criado=classificacao.data_criado,
                data_modificado=classificacao.data_modificado
            ),
            total_classificadas=total_classificadas
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao classificar imagem: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao classificar imagem: {str(e)}"
        )

@router.get("/historico", response_model=HistoricoResponse)
def listar_historico_usuario(
    id_amb: Optional[str] = Query(None, description="Filtrar por ID do ambiente (opcional)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna o histórico de imagens já classificadas pelo usuário.
    Conserta o erro 500 usando o ID do ambiente fornecido ou recuperando via Join seguro.
    """
    try:
        if not usuario.convencional:
            return {"total": 0, "items": []}

        id_con = usuario.convencional.id_con

        # 1. Monta a Query incluindo a tabela Ambiente
        query = db.query(
            models.Classificacao,
            models.Imagem,
            models.Opcao,
            models.ConjuntoImagens,
            models.Ambiente
        )\
        .join(models.Imagem, models.Classificacao.id_img == models.Imagem.content_hash)\
        .join(models.Opcao, models.Classificacao.id_opc == models.Opcao.id_opc)\
        .join(models.ConjuntoImagens, models.Imagem.id_cnj == models.ConjuntoImagens.id_cnj)\
        .join(models.Ambiente)\
        .filter(models.Classificacao.id_con == id_con)

        # 2. Filtro por ambiente
        if id_amb:
            # Filtra usando o ID do ambiente da tabela Ambiente
            query = query.filter(models.Ambiente.id_amb == id_amb)

        # 3. Ordenação
        query = query.order_by(desc(models.Classificacao.data_criado))

        resultados = query.offset((page - 1) * page_size).limit(page_size).all()

        # 4. AGRUPAMENTO
        grouped_items = {}

        for classificacao, imagem, opcao, conjunto, ambiente in resultados:
            
            # DEFINE O ID DO AMBIENTE DE FORMA SEGURA
            final_id_amb = id_amb if id_amb else str(ambiente.id_amb)

            if imagem.content_hash in grouped_items:
                item_existente = grouped_items[imagem.content_hash]
                if opcao.texto not in item_existente["opcoes_lista"]:
                    item_existente["opcoes_lista"].append(opcao.texto)
            else:
                path_limpo = imagem.caminho_img.lstrip('/')
                url_img = f"/nextcloud/images/{quote(path_limpo, safe='/')}"

                grouped_items[imagem.content_hash] = {
                    "content_hash": imagem.content_hash,
                    "nome_img": imagem.nome_img,
                    "url_img": url_img,
                    "opcoes_lista": [opcao.texto],
                    "data_classificacao": classificacao.data_criado,
                    "nome_ambiente": ambiente.titulo_amb,
                    "id_amb": final_id_amb
                }

        # 5. Formata a resposta final
        items_out = []
        for item in grouped_items.values():
            item["opcao_escolhida"] = ", ".join(item["opcoes_lista"])
            del item["opcoes_lista"] 
            items_out.append(item)

        total = query.count()

        return {"total": total, "items": items_out}

    except Exception as e:
        logger.error(f"Erro ao listar histórico: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")