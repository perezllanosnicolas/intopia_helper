import os
import glob
import re
from v3.optimizer_pulp import OptimizerV3
from v3.negotiation import Negotiation
from v3.ranking import calculate_ranking
from src.parser import LSTParser
from v3.demand_estimator import DemandEstimator 

# --- PASO 1: Cargar todos los datos históricos ---
DATA_DIR = os.path.join(os.getcwd(), 'data')
files = sorted(
    glob.glob(os.path.join(DATA_DIR, 'Decisión [0-9].lst.txt')) + 
    glob.glob(os.path.join(DATA_DIR, 'Descisión [0-9].lst.txt')),
    key=lambda x: int(re.search(r'[Dd]ecisión (\d+)', x).group(1))
)

if not files:
    print("Error: No se encontraron archivos de Decisión (ej: 'Decisión 1.lst.txt') en la carpeta /data.")
    exit()

print(f"Archivos LST detectados: {[os.path.basename(f) for f in files]}")

parser = LSTParser()
datos_historicos = [parser.parse_file(f) for f in files]

current_state_parsed = datos_historicos[-1]
last_file = files[-1]
print(f"Última decisión detectada: {os.path.basename(last_file)}")

# --- PASO 2: Entrenar el Modelo de Demanda ---
print("\nEntrenando modelo de demanda con datos históricos...")
estimador = DemandEstimator(datos_historicos)
# Mostramos el modelo aprendido para el mercado total de 'EU', 'X'
print(f"Modelo de demanda para ('EU', 'X'): {estimador.get_demand_function('EU', 'X')}")


# --- PASO 3: Preparar el Estado Actual para el Optimizador ---
beneficio = current_state_parsed.get('utilidad_periodo', 0)
liquidez = current_state_parsed.get('caja_total', 0)
inventarios = current_state_parsed.get('inventarios_detalle', {}) 
cuota = current_state_parsed.get('cuota_mercado', 0)
inventarios_total = sum(inventarios.values())

current_state_optimizer = {
    'beneficio': beneficio,
    'liquidez': liquidez,
    'inventarios_detalle': inventarios,
    'inventarios_total': inventarios_total,
    'cuota': cuota
}

print("\nResumen del estado actual:")
for k, v in current_state_optimizer.items():
    print(f"{k}: {v}")

# --- PASO 4: Bucle de Optimización (Probar Precios) ---

# CORRECCIÓN: Probar el mercado ('EU', 'X', 0) donde SÍ tenemos inventario.
# (Tu inventario es: {('EU', 'X', 0): 37000})
mercados_a_probar = {
    ('EU', 'X'): [35, 40, 45, 50] # Probar 4 precios para Chips en EU
}

mejor_ranking_total = -float('inf')
mejor_solucion_final = None
mejores_precios_final = {}

# Bucle principal: Itera sobre MERCADOS (EU-X, US-Y, etc.)
for mercado_key, precios in mercados_a_probar.items():
    area, prod = mercado_key
    
    # Probar vender como Grado 0 (Estándar) o Grado 1 (Lujo)
    for grado_a_vender in [0, 1]:
        
        for precio_prueba in precios:
            
            # 1. Obtener función de demanda y calcular demanda para este precio
            # (Usamos el modelo de mercado total)
            func_demanda = estimador.get_demand_function(area, prod)
            # Asumimos que podemos capturar 1/11 (aprox 9%) del mercado
            demanda_total_mercado = func_demanda['interseccion'] + (func_demanda['pendiente'] * precio_prueba)
            demanda_maxima_cia = max(0, int(demanda_total_mercado * 0.09)) 

            # 2. Configurar el optimizador
            optimizer = OptimizerV3(current_state=current_state_optimizer)
            
            optimizer.set_market_conditions(
                area=area, prod=prod, grado=grado_a_vender, 
                precio_fijo=precio_prueba, 
                demanda_maxima=demanda_maxima_cia,
                producir_grado=0 # Simplificación: seguimos produciendo solo Grado 0
            )
            
            # 3. Construir y resolver el modelo
            optimizer.build_model()
            solucion_actual = optimizer.solve()
            ranking_actual = optimizer.get_objective_value()

            # 4. Guardar la mejor solución
            if ranking_actual > mejor_ranking_total:
                mejor_ranking_total = ranking_actual
                mejor_solucion_final = solucion_actual
                mejores_precios_final = {(area, prod, grado_a_vender): precio_prueba}

# --- PASO 5: Mostrar Resultados ---
print("\n--- Solución Óptima Encontrada ---")
print(f"Mejor Ranking Estimado: {mejor_ranking_total:.2f}")
print(f"Mejor Estrategia de Precios: {mejores_precios_final}")

print("\nDecisiones de Producción y Venta Recomendadas:")
if not mejor_solucion_final:
    print("(Ninguna acción recomendada, no se encontró beneficio)")
else:
    for k, v in mejor_solucion_final.items():
        print(f"{k}: {v}")
    optimizer.estimate_next_period(mejor_solucion_final, current_state_optimizer)

# --- PASO 6: Negociación (esto no cambia) ---
current_state_ranking = {
    'beneficio': beneficio,
    'liquidez': liquidez,
    'inventarios': inventarios_total,
    'cuota': cuota
}

print("\n--- Negociación ---")
negotiation = Negotiation()
offer = {'price': 100, 'volume': 1200}
score = negotiation.evaluate_offer(offer, current_state_ranking)
print(f"Ranking si se acepta oferta: {score:.2f}")
counter = negotiation.generate_counteroffer(offer, current_state_ranking)
print(f"Contraoferta: {counter}")
pact = negotiation.propose_commercial_pact(current_state_ranking)
print(f"Propuesta de pacto: {pact}")