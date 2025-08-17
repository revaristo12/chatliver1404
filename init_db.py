#!/usr/bin/env python3
"""
Script para inicializar o banco de dados do sistema de bate-papo.
"""

import os
import sys
from app import create_app, db
from models import Base

def init_database():
    """Inicializa o banco de dados criando todas as tabelas"""
    app = create_app()
    
    with app.app_context():
        try:
            # Criar diretório instance se não existir
            instance_path = os.path.join(os.getcwd(), 'instance')
            os.makedirs(instance_path, exist_ok=True)
            
            # Criar todas as tabelas
            Base.metadata.create_all(db.engine)
            
            print("✅ Banco de dados inicializado com sucesso!")
            print(f"📁 Arquivo do banco: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            # Verificar se as tabelas foram criadas
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"📊 Tabelas criadas: {', '.join(tables)}")
            
        except Exception as e:
            print(f"❌ Erro ao inicializar banco de dados: {e}")
            sys.exit(1)

def reset_database():
    """Reseta o banco de dados (apaga e recria todas as tabelas)"""
    app = create_app()
    
    with app.app_context():
        try:
            # Apagar todas as tabelas
            Base.metadata.drop_all(db.engine)
            print("🗑️  Tabelas removidas.")
            
            # Recriar todas as tabelas
            Base.metadata.create_all(db.engine)
            print("✅ Banco de dados resetado com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao resetar banco de dados: {e}")
            sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        print("🔄 Resetando banco de dados...")
        reset_database()
    else:
        print("🚀 Inicializando banco de dados...")
        init_database()
