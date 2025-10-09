import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os

class EntrenadorModeloVuelos:
    def __init__(self, archivo_datos='datos_vuelos_peru.xlsx'):
        """Inicializa el entrenador del modelo"""
        self.archivo_datos = archivo_datos
        self.df = None
        self.modelo = None
        self.scaler = None
        self.label_encoders = {}
        self.features = None
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        
    def cargar_datos(self):
        """Carga los datos desde Excel o CSV"""
        print(f"📁 Cargando datos desde {self.archivo_datos}...")
        
        try:
            if self.archivo_datos.endswith('.xlsx'):
                self.df = pd.read_excel(self.archivo_datos)
            else:
                self.df = pd.read_csv(self.archivo_datos)
            
            print(f"✓ Datos cargados: {len(self.df)} registros")
            print(f"✓ Columnas: {self.df.columns.tolist()}")
            return True
        except FileNotFoundError:
            print(f"✗ Error: Archivo {self.archivo_datos} no encontrado")
            return False
    
    def preprocesar_datos(self):
        """Preprocesa los datos para el modelo"""
        print("\n🔄 Preprocesando datos...")
        
        df = self.df.copy()
        
        # Convertir fecha a datetime
        df['Fecha_del_viaje'] = pd.to_datetime(df['Fecha_del_viaje'])
        
        # Extraer características de fecha
        df['Día_semana'] = df['Fecha_del_viaje'].dt.dayofweek
        df['Mes'] = df['Fecha_del_viaje'].dt.month
        df['Trimestre'] = df['Fecha_del_viaje'].dt.quarter
        df['Es_fin_de_semana'] = (df['Día_semana'] >= 5).astype(int)
        
        # Días de anticipación (respecto al primer día del dataset)
        fecha_min = df['Fecha_del_viaje'].min()
        df['Días_desde_inicio'] = (df['Fecha_del_viaje'] - fecha_min).dt.days
        
        # Extraer hora como número
        df['Hora_salida_num'] = df['Hora_de_salida'].apply(lambda x: int(str(x).split(':')[0]))
        df['Minuto_salida'] = df['Hora_de_salida'].apply(lambda x: int(str(x).split(':')[1]))
        
        # Extraer longitud de ruta
        df['Longitud_ruta'] = df['Ruta'].apply(lambda x: len(str(x)))
        
        # Codificar variables categóricas
        variables_categoricas = ['Aerolínea', 'Origen', 'Destino', 'Ruta', 'Información_adicional']
        
        for col in variables_categoricas:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            self.label_encoders[col] = le
        
        # Features para el modelo
        self.features = ['Aerolínea', 'Día_semana', 'Mes', 'Trimestre', 'Es_fin_de_semana',
                        'Origen', 'Destino', 'Duración', 'Total_de_escalas', 
                        'Información_adicional', 'Hora_salida_num', 'Minuto_salida',
                        'Días_desde_inicio', 'Longitud_ruta']
        
        self.X = df[self.features]
        self.y = df['Precio (S/)']
        
        print(f"✓ Features extraídos: {len(self.features)}")
        print(f"✓ Features: {self.features}")
        
    def dividir_datos(self, test_size=0.2):
        """Divide los datos en entrenamiento y prueba"""
        print(f"\n📊 Dividiendo datos (80-20)...")
        
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            self.X, self.y, test_size=test_size, random_state=42
        )
        
        print(f"✓ Datos de entrenamiento: {len(self.X_train)}")
        print(f"✓ Datos de prueba: {len(self.X_test)}")
    
    def escalar_datos(self):
        """Escala los datos para mejorar el rendimiento"""
        print("\n📈 Escalando datos...")
        
        self.scaler = StandardScaler()
        self.X_train_scaled = self.scaler.fit_transform(self.X_train)
        self.X_test_scaled = self.scaler.transform(self.X_test)
        
        print("✓ Datos escalados con StandardScaler")
    
    def entrenar_modelo(self):
        """Entrena el modelo RandomForest"""
        print("\n🤖 Entrenando modelo RandomForest...")
        
        self.modelo = RandomForestRegressor(
            n_estimators=200,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
            verbose=1
        )
        
        self.modelo.fit(self.X_train_scaled, self.y_train)
        print("✓ Modelo entrenado exitosamente")
    
    def evaluar_modelo(self):
        """Evalúa el rendimiento del modelo"""
        print("\n📋 Evaluando modelo...")
        
        # Predicciones
        y_train_pred = self.modelo.predict(self.X_train_scaled)
        y_test_pred = self.modelo.predict(self.X_test_scaled)
        
        # Métricas de entrenamiento
        train_mse = mean_squared_error(self.y_train, y_train_pred)
        train_rmse = np.sqrt(train_mse)
        train_mae = mean_absolute_error(self.y_train, y_train_pred)
        train_r2 = r2_score(self.y_train, y_train_pred)
        
        # Métricas de prueba
        test_mse = mean_squared_error(self.y_test, y_test_pred)
        test_rmse = np.sqrt(test_mse)
        test_mae = mean_absolute_error(self.y_test, y_test_pred)
        test_r2 = r2_score(self.y_test, y_test_pred)
        
        print("\n" + "="*50)
        print("MÉTRICAS DE ENTRENAMIENTO")
        print("="*50)
        print(f"R² Score (Entrenamiento): {train_r2:.4f}")
        print(f"RMSE (Entrenamiento): S/ {train_rmse:.2f}")
        print(f"MAE (Entrenamiento): S/ {train_mae:.2f}")
        
        print("\n" + "="*50)
        print("MÉTRICAS DE PRUEBA")
        print("="*50)
        print(f"R² Score (Prueba): {test_r2:.4f}")
        print(f"RMSE (Prueba): S/ {test_rmse:.2f}")
        print(f"MAE (Prueba): S/ {test_mae:.2f}")
        
        # Importancia de features
        print("\n" + "="*50)
        print("TOP 10 FEATURES MÁS IMPORTANTES")
        print("="*50)
        feature_importance = pd.DataFrame({
            'Feature': self.features,
            'Importance': self.modelo.feature_importances_
        }).sort_values('Importance', ascending=False)
        
        print(feature_importance.head(10).to_string(index=False))
        
        return {
            'train_r2': train_r2,
            'train_rmse': train_rmse,
            'train_mae': train_mae,
            'test_r2': test_r2,
            'test_rmse': test_rmse,
            'test_mae': test_mae
        }
    
    def guardar_modelo(self):
        """Guarda el modelo y sus componentes"""
        print("\n💾 Guardando modelo...")
        
        joblib.dump(self.modelo, 'modelo_vuelos.pkl')
        joblib.dump(self.scaler, 'scaler.pkl')
        joblib.dump(self.label_encoders, 'label_encoders.pkl')
        joblib.dump(self.features, 'features.pkl')
        
        print("✓ modelo_vuelos.pkl")
        print("✓ scaler.pkl")
        print("✓ label_encoders.pkl")
        print("✓ features.pkl")
    
    def generar_reporte(self, metricas):
        """Genera un reporte de entrenamiento"""
        print("\n" + "="*50)
        print("REPORTE FINAL DE ENTRENAMIENTO")
        print("="*50)
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Archivo de datos: {self.archivo_datos}")
        print(f"Total de registros: {len(self.df)}")
        print(f"Features usados: {len(self.features)}")
        print(f"\nModelo: RandomForestRegressor")
        print(f"Estimadores: 200")
        print(f"Profundidad máxima: 20")
        print(f"\nRendimiento en PRUEBA:")
        print(f"  R² Score: {metricas['test_r2']:.4f}")
        print(f"  RMSE: S/ {metricas['test_rmse']:.2f}")
        print(f"  MAE: S/ {metricas['test_mae']:.2f}")
        print("="*50)
    
    def entrenar_completo(self):
        """Ejecuta el pipeline completo de entrenamiento"""
        if not self.cargar_datos():
            return False
        
        self.preprocesar_datos()
        self.dividir_datos()
        self.escalar_datos()
        self.entrenar_modelo()
        metricas = self.evaluar_modelo()
        self.guardar_modelo()
        self.generar_reporte(metricas)
        
        print("\n✅ ¡Modelo entrenado y guardado exitosamente!")
        return True

def main():
    # Verificar si existen los datos
    archivo = 'datos_vuelos.xlsx'
    if not os.path.exists(archivo):
        print(f"⚠️  {archivo} no encontrado")
        print("Ejecuta primero: python generar_datos.py")
        return
    
    # Entrenar modelo
    entrenador = EntrenadorModeloVuelos(archivo)
    entrenador.entrenar_completo()

if __name__ == "__main__":
    main()