from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

def associar_todos_usuarios_ao_ambiente(db: Session, id_amb):
    ambiente = db.query(models.Ambiente).filter(models.Ambiente.id_amb == id_amb, models.Ambiente.ativo == True).first()
    if not ambiente:
        return None
    usuarios = db.query(models.UsuarioConvencional).join(models.Usuario).filter(models.Usuario.ativo == True).all()
    count = 0
    for usuario in usuarios:
        vinculo = db.query(models.UsuarioAmbiente).filter_by(id_con=usuario.id_con, id_amb=id_amb).first()
        if vinculo:
            if not vinculo.ativo:
                vinculo.ativo = True
                vinculo.data_associado = datetime.now(timezone.utc)
                count += 1
        else:
            novo = models.UsuarioAmbiente(
                id_con=usuario.id_con,
                id_amb=id_amb,
                data_associado=datetime.now(timezone.utc),
                ativo=True
            )
            db.add(novo)
            count += 1
    db.commit()
    return count

def associar_usuarios_ao_ambiente(db: Session, id_amb, ids_usuarios: list[str]):
    ambiente = db.query(models.Ambiente).filter(models.Ambiente.id_amb == id_amb, models.Ambiente.ativo == True).first()
    if not ambiente:
        return None, []
    associados = []
    for id_con in ids_usuarios:
        usuario = db.query(models.UsuarioConvencional).join(models.Usuario).filter(models.UsuarioConvencional.id_con == id_con, models.Usuario.ativo == True).first()
        if not usuario:
            continue
        vinculo = db.query(models.UsuarioAmbiente).filter_by(id_con=id_con, id_amb=id_amb).first()
        if vinculo:
            if not vinculo.ativo:
                vinculo.ativo = True
                vinculo.data_associado = datetime.now(timezone.utc)
                associados.append(id_con)
        else:
            novo = models.UsuarioAmbiente(
                id_con=id_con,
                id_amb=id_amb,
                data_associado=datetime.now(timezone.utc),
                ativo=True
            )
            db.add(novo)
            associados.append(id_con)
    db.commit()
    return ambiente, associados

def excluir_vinculo(db: Session, id_amb, id_con):
    vinculo = db.query(models.UsuarioAmbiente).filter_by(id_amb=id_amb, id_con=id_con, ativo=True).first()
    if vinculo:
        vinculo.ativo = False
        db.commit()
    return vinculo

def reativar_vinculo(db: Session, id_amb, id_con):
    vinculo = db.query(models.UsuarioAmbiente).filter_by(id_amb=id_amb, id_con=id_con, ativo=False).first()
    if vinculo:
        vinculo.ativo = True
        db.commit()
    return vinculo

def listar_vinculos_admin(db: Session):
    ambientes = db.query(models.Ambiente).all()
    result = []
    for amb in ambientes:
        usuarios = []
        for vinc in amb.usuarios:
            if vinc.ativo:
                usu = db.query(models.UsuarioConvencional).filter_by(id_con=vinc.id_con).first()
                if usu and usu.usuario.ativo:
                    usuarios.append({
                        "id_con": str(usu.id_con),
                        "nome_completo": usu.usuario.nome_completo,
                        "email": usu.usuario.email,
                        "ativo": usu.usuario.ativo
                    })
        result.append({
            "id_amb": str(amb.id_amb),
            "titulo_amb": amb.titulo_amb,
            "descricao": amb.descricao,
            "usuarios": usuarios,
            "ativo": amb.ativo
        })
    return result

def listar_ambientes_usuario(db: Session, id_con):
    usuario = db.query(models.UsuarioConvencional).filter_by(id_con=id_con).first()
    if not usuario or not usuario.usuario.ativo:
        return None
    ambientes = []
    for vinc in usuario.ambientes:
        if vinc.ativo:
            amb = db.query(models.Ambiente).filter_by(id_amb=vinc.id_amb).first()
            if amb and amb.ativo:
                ambientes.append({
                    "id_amb": str(amb.id_amb),
                    "titulo_amb": amb.titulo_amb,
                    "descricao": amb.descricao,
                    "ativo": amb.ativo
                })
    return usuario, ambientes 