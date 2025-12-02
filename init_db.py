from app import app, db
from sqlalchemy import text

def init_database():
    with app.app_context():
        try:
            print("🔧 Inicializando base de datos...")
            
            # Crear todas las tablas
            db.create_all()
            print("✓ Tablas creadas exitosamente:")
            
            # Verificar que las tablas existen
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            for table in tables:
                print(f"  ✓ {table}")
            
            # Verificar conexión
            result = db.session.execute(text('SELECT 1'))
            print("✓ Conexión a base de datos verificada")
            
            return True
            
        except Exception as e:
            print(f"❌ Error al inicializar base de datos: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = init_database()
    if success:
        print("\n✅ Base de datos inicializada correctamente")
    else:
        print("\n❌ Error al inicializar base de datos")
        exit(1)