import os
import glob
import re  # <--- ¡AÑADE ESTA LÍNEA!
from v3.optimizer_pulp import OptimizerV3
from v3.negotiation import Negotiation
from v3.ranking import calculate_ranking
from src.parser import LSTParser
from v3.demand_estimator import DemandEstimator

# --- PASO 1: Cargar todos los datos históricos ---

# Ruta de la carpeta data
DATA_DIR = os.path.join(os.getcwd(), 'data')

# Identificar TODOS los archivos de decisión, ordenados
# Usamos glob para encontrar cualquier archivo que coincida con el patrón
files = sorted(
    glob.glob(os.path.join(DATA_DIR, 'Decisión [0-9].lst.txt')) + 
    glob.glob(os.path.join(DATA_DIR, 'Descisión [0-9].lst.txt')),
    # Esta línea ahora funcionará porque 're' está importado
    key=lambda x: int(re.search(r'[Dd]ecisión (\d+)', x).group(1)) 
)

if not files:
    print("Error: No se encontraron archivos de Decisión (ej: 'Decisión 1.lst.txt') en la carpeta /data.")
    exit()

print(f"Archivos LST detectados: {[os.path.basename(f) for f in files]}")

# Parsear todos los archivos históricos
parser = LSTParser()
datos_historicos = [parser.parse_file(f) for f in files]

# El 'current_state' son los datos del último archivo
current_state_parsed = datos_historicos[-1]
last_file = files[-1]
print(f"Última decisión detectada: {os.path.basename(last_file)}")

# --- PASO 2: Entrenar el Modelo de Demanda ---

print("\nEntrenando modelo de demanda con datos históricos...")
estimador = DemandEstimator(datos_historicos)
# Mostramos un modelo de ejemplo que haya aprendido
print(estimador.get_demand_function('EU', 'X', 1)) # Imprime el modelo para EU-Chip-Grado 1


# --- PASO 3: Preparar el Estado Actual para el Optimizador ---

beneficio = current_state_parsed.get('utilidad_periodo', 0)
liquidez = current_state_parsed.get('caja_total', 0)
# Usamos el inventario detallado del nuevo parser
inventarios = current_state_parsed.get('inventarios_detalle', {}) 
cuota = current_state_parsed.get('cuota_mercado', 0)
inventarios_total = sum(inventarios.values())

current_state_optimizer = {
    'beneficio': beneficio,
    'liquidez': liquidez,
    'inventarios_detalle': inventarios, # El dict detallado
    'inventarios_total': inventarios_total,
    'cuota': cuota
}

print("\nResumen del estado actual:")
for k, v in current_state_optimizer.items():
    print(f"{k}: {v}")


# --- PASO 4: Bucle de Optimización (Probar Precios) ---

# Aquí definimos qué mercados y qué precios queremos probar
# (Añade más mercados y precios aquí)
mercados_a_probar = {
    ('EU', 'X', 1): [35, 40, 45, 50] # Probar 4 precios para Chip Grado 1 en EU
    # ('US', 'Y', 0): [150, 160, 170] # Ejemplo para PC Estándar en US
}

mejor_ranking_total = -float('inf')
mejor_solucion_final = None
mejores_precios_final = None

# Bucle principal para probar diferentes estrategias de precios
for mercado_key, precios in mercados_a_probar.items():
    area, prod, grado = mercado_key
    
    for precio_prueba in precios:
        
        # 1. Obtener función de demanda y calcular demanda para este precio
        func_demanda = estimador.get_demand_function(area, prod, grado)
        demanda_maxima = func_demanda['interseccion'] + (func_demanda['pendiente'] * precio_prueba)
        demanda_maxima = max(0, int(demanda_maxima)) # Asegurar que no sea negativa

        # 2. Configurar el optimizador con estas condiciones de mercado
        optimizer = OptimizerV3(current_state=current_state_optimizer)
        
        # Le decimos al optimizador: "PARA ESTA VUELTA, asume este precio y esta demanda"
        optimizer.set_market_conditions(
            area=area, prod=prod, grado=grado, 
            precio_fijo=precio_prueba, 
            demanda_maxima=demanda_maxima
        )
        
        # 3. Construir y resolver el modelo
        optimizer.build_model()
        solucion_actual = optimizer.solve()
        ranking_actual = optimizer.get_objective_value()

        # 4. Guardar la mejor solución
        if ranking_actual > mejor_ranking_total:
            mejor_ranking_total = ranking_actual
            mejor_solucion_final = solucion_actual
            mejores_precios_final = {mercado_key: precio_prueba}


# --- PASO 5: Mostrar Resultados ---

print("\n--- Solución Óptima Encontrada ---")
print(f"Mejor Ranking Estimado: {mejor_ranking_total:.2f}")
print(f"Mejor Estrategia de Precios: {mejores_precios_final}")

print("\nDecisiones de Producción y Venta Recomendadas:")
for k, v in mejor_solucion_final.items():
    print(f"{k}: {v}")

optimizer.estimate_next_period(mejor_solucion_final, current_state_optimizer)


# --- PASO 6: Negociación (esto no cambia) ---
# (La negociación ahora usa el 'current_state_parsed' que tiene el formato que 'ranking.py' espera)
current_state_ranking = {
    'beneficio': beneficio,
    'liquidez': liquidez,
    'inventarios': inventarios_total, # ranking.py espera un número, no un dict
    'cuota': cuota
}

negotiation = Negotiation()
offer = {'price': 100, 'volume': 1200}
score = negotiation.evaluate_offer(offer, current_state_ranking)
print("\nRanking si se acepta oferta:", score)
counter = negotiation.generate_counteroffer(offer, current_state_ranking)
print("Contraoferta:", counter)
pact = negotiation.propose_commercial_pact(current_state_ranking)
print("Propuesta de pacto:", pact)