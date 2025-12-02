"""
Script para inicializar la base de datos en Render
"""
import os
import sys

def main():
    print("🔧 Inicializando base de datos...")
    
    try:
        # Importar app después de establecer variable de entorno
        from app import app, db
        
        with app.app_context():
            # Crear todas las tablas
            db.create_all()
            print("✓ Tablas creadas exitosamente")
            
            # Verificar tablas
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tablas = inspector.get_table_names()
            print(f"✓ Tablas encontradas: {tablas}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)