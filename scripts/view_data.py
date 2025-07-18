#!/usr/bin/env python3
"""
Script para visualizar dados das tabelas do sistema de classificação de imagens.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Adicionar o diretório raiz ao path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from app.db.database import SessionLocal
from app.db.models import Image
from app.crud.image_crud import ImageCRUD

def format_file_size(size_bytes):
    """Formata tamanho de arquivo em formato legível"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def view_images_table():
    """Visualiza a tabela de imagens"""
    db = SessionLocal()
    try:
        print("📊 TABELA DE IMAGENS")
        print("=" * 80)
        
        # Obter todas as imagens
        images = ImageCRUD.get_all_images(db, limit=1000)
        total = ImageCRUD.get_total_count(db)
        
        print(f"Total de imagens: {total}")
        print()
        
        if not images:
            print("📭 Nenhuma imagem encontrada na tabela.")
            return
        
        # Cabeçalho da tabela
        print(f"{'ID':<4} {'Nome':<25} {'Tipo':<6} {'Tamanho':<10} {'Status':<12} {'Criado em':<20}")
        print("-" * 80)
        
        # Dados das imagens
        for img in images:
            created_at = img.created_at.strftime("%Y-%m-%d %H:%M:%S") if img.created_at else "N/A"
            file_size = format_file_size(img.file_size)
            
            print(f"{img.id:<4} {img.filename:<25} {img.file_type:<6} {file_size:<10} {img.status:<12} {created_at:<20}")
        
        print("-" * 80)
        
    except Exception as e:
        print(f"❌ Erro ao acessar banco de dados: {e}")
    finally:
        db.close()

def view_status_summary():
    """Visualiza resumo por status"""
    db = SessionLocal()
    try:
        print("📈 RESUMO POR STATUS")
        print("=" * 40)
        
        total = ImageCRUD.get_total_count(db)
        pending = len(ImageCRUD.get_images_by_status(db, "pending"))
        processed = len(ImageCRUD.get_images_by_status(db, "processed"))
        error = len(ImageCRUD.get_images_by_status(db, "error"))
        
        print(f"📊 Total: {total}")
        print(f"⏳ Pendentes: {pending}")
        print(f"✅ Processadas: {processed}")
        print(f"❌ Com erro: {error}")
        
        if total > 0:
            print()
            print("📊 Percentuais:")
            print(f"   Processadas: {(processed/total)*100:.1f}%")
            print(f"   Pendentes: {(pending/total)*100:.1f}%")
            print(f"   Com erro: {(error/total)*100:.1f}%")
        
    except Exception as e:
        print(f"❌ Erro ao acessar banco de dados: {e}")
    finally:
        db.close()

def view_recent_images(limit=10):
    """Visualiza imagens mais recentes"""
    db = SessionLocal()
    try:
        print(f"🕒 ÚLTIMAS {limit} IMAGENS ADICIONADAS")
        print("=" * 60)
        
        # Buscar imagens ordenadas por data de criação
        images = db.query(Image).order_by(Image.created_at.desc()).limit(limit).all()
        
        if not images:
            print("📭 Nenhuma imagem encontrada.")
            return
        
        for i, img in enumerate(images, 1):
            created_at = img.created_at.strftime("%Y-%m-%d %H:%M:%S") if img.created_at else "N/A"
            file_size = format_file_size(img.file_size)
            
            print(f"{i:2}. {img.filename}")
            print(f"    ID: {img.id} | Tipo: {img.file_type} | Tamanho: {file_size}")
            print(f"    Status: {img.status} | Criado: {created_at}")
            if img.error_message:
                print(f"    ❌ Erro: {img.error_message}")
            print()
        
    except Exception as e:
        print(f"❌ Erro ao acessar banco de dados: {e}")
    finally:
        db.close()

def view_table_structure():
    """Visualiza estrutura da tabela"""
    print("🏗️  ESTRUTURA DA TABELA 'images'")
    print("=" * 50)
    print("Campo           | Tipo         | Nullable | Default")
    print("-" * 50)
    print("id              | INTEGER      | NO       | PRIMARY KEY")
    print("filename        | VARCHAR(255) | NO       | -")
    print("original_path   | VARCHAR(500) | NO       | -")
    print("processed_path  | VARCHAR(500) | YES      | NULL")
    print("file_size       | INTEGER      | NO       | -")
    print("file_type       | VARCHAR(10)  | NO       | -")
    print("status          | VARCHAR(20)  | YES      | 'pending'")
    print("created_at      | TIMESTAMP    | YES      | NOW()")
    print("processed_at    | TIMESTAMP    | YES      | NULL")
    print("error_message   | TEXT         | YES      | NULL")

def main():
    """Menu principal"""
    print("🔍 VISUALIZADOR DE DADOS - SISTEMA DE CLASSIFICAÇÃO DE IMAGENS")
    print("=" * 70)
    print()
    
    while True:
        print("Escolha uma opção:")
        print("1. 📊 Ver tabela completa de imagens")
        print("2. 📈 Ver resumo por status")
        print("3. 🕒 Ver últimas imagens adicionadas")
        print("4. 🏗️  Ver estrutura da tabela")
        print("5. 🔄 Atualizar dados")
        print("0. ❌ Sair")
        print()
        
        choice = input("Digite sua escolha (0-5): ").strip()
        print()
        
        if choice == "1":
            view_images_table()
        elif choice == "2":
            view_status_summary()
        elif choice == "3":
            limit = input("Quantas imagens mostrar? (padrão: 10): ").strip()
            limit = int(limit) if limit.isdigit() else 10
            view_recent_images(limit)
        elif choice == "4":
            view_table_structure()
        elif choice == "5":
            print("🔄 Atualizando...")
            continue
        elif choice == "0":
            print("👋 Saindo...")
            break
        else:
            print("❌ Opção inválida!")
        
        print()
        input("Pressione ENTER para continuar...")
        print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main() 