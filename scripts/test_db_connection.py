#!/usr/bin/env python3
"""
Script para testar a conexão com o banco de dados.
Útil para debug e verificação de conectividade.
"""

import sys
import os
from pathlib import Path

# Adicionar o diretório raiz ao path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from app.db.database import wait_for_database, engine
from app.core.config import settings

def test_connection():
    """Testa a conexão com o banco de dados"""
    print("🔍 Testando conexão com o banco de dados...")
    print(f"📡 URL de conexão: {settings.DATABASE_URL}")
    print()
    
    # Testar função de espera
    print("⏳ Aguardando banco estar pronto...")
    if wait_for_database(max_retries=10, retry_interval=3):
        print("✅ Conexão estabelecida com sucesso!")
        
        # Testar query simples
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                print(f"📊 Versão do PostgreSQL: {version}")
                
                # Testar se as tabelas existem
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result.fetchall()]
                
                if tables:
                    print(f"📋 Tabelas encontradas: {', '.join(tables)}")
                else:
                    print("📭 Nenhuma tabela encontrada (banco vazio)")
                    
        except Exception as e:
            print(f"❌ Erro ao executar queries: {e}")
            return False
            
        return True
    else:
        print("❌ Falha ao conectar com o banco de dados")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
