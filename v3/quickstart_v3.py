import os
import glob
import re
import csv
from v3.optimizer_pulp import OptimizerV3
from v3.negotiation import Negotiation
from v3.ranking import calculate_ranking
from src.parser import LSTParser
from v3.demand_estimator import DemandEstimator 

# Constantes para la simulación de estrategias
COSTE_ID_Y = 320000 # Coste de I+D para PCs (proxy basado en H1, P4 [cite: 3081, 3083])
COSTE_PUBLICIDAD_Y_EU = 50000 # 50k € en publicidad para PCs en EU (proxy)
ELASTICIDAD_PUBLICIDAD = 0.15 # Asumir una elasticidad de 0.15 (Manual: 0.1-0.5 [cite: 2028])
COSTE_INFORME_IM2 = 60000 # [cite: 2064]
COSTE_INFORME_IM17 = 10000 # [cite: 2066]

def load_ranking_data(data_dir, historicos_parseados):
    ranking_data = []
    ranking_files = glob.glob(os.path.join(data_dir, 'Ranking [0-9].txt'))
    
    for r_file in ranking_files:
        try:
            periodo_num_match = re.search(r'Ranking (\d+)\.txt', r_file)
            if not periodo_num_match: continue
            periodo = int(periodo_num_match.group(1))
            
            if (periodo - 1) < len(historicos_parseados):
                estado_lst = historicos_parseados[periodo - 1]
                with open(r_file, 'r') as f:
                    reader = csv.reader(f, delimiter=';')
                    next(reader) 
                    for row in reader:
                        if not row or len(row) < 2: continue
                        if int(row[0].strip()) == 4:
                            score_str = row[1].strip().replace("'", ".")
                            score = float(score_str)
                            ranking_data.append({ 'periodo': periodo, 'score': score, 'estado': estado_lst })
                            break 
        except Exception as e:
            print(f"Error procesando el archivo de ranking {r_file}: {e}")
            
    return ranking_data

def find_best_strategy(current_state, estimador, strategy_config):
    """
    Función helper para ejecutar el bucle de optimización
    para una estrategia y un conjunto de mercados dados.
    """
    markets_to_test = strategy_config['markets_to_test']
    production_config = strategy_config['production_config']
    gasto_publicidad = strategy_config.get('gasto_publicidad', 0)
    gasto_ID = strategy_config.get('gasto_ID', 0)
    gasto_informes = strategy_config.get('gasto_informes', 0)

    mejor_ranking = -float('inf')
    mejor_solucion = None
    mejores_precios = {}
    mejor_market_cond = {}

    # Itera sobre los mercados a probar (ej. ('EU', 'Y', 0))
    for mercado_key, precios in markets_to_test.items():
        area, prod, grado = mercado_key
        
        for precio_prueba in precios:
            func_demanda = estimador.get_demand_function(area, prod, grado)
            
            demanda_total_mercado = func_demanda['interseccion'] + (func_demanda['pendiente'] * precio_prueba)
            
            # Ajustar demanda por publicidad
            if gasto_publicidad > 0:
                # Proxy: (1 + 0.15 * (gasto_pub / 100k))
                demanda_total_mercado *= (1 + ELASTICIDAD_PUBLICIDAD * (gasto_publicidad / 100000))

            # Asumir que podemos capturar una cuota (ej. 10%) del mercado total
            # El manual dice que productos de mayor grado venden más[cite: 1902], 
            # así que le damos un bonus de cuota a los de Grado 1
            cuota_mercado_objetivo = 0.15 if grado == 1 else 0.10
            demanda_maxima_cia = max(0, int(demanda_total_mercado * cuota_mercado_objetivo))

            optimizer = OptimizerV3(current_state=current_state)
            
            market_conditions_actual = {
                mercado_key: { 'precio': precio_prueba, 'demanda': demanda_maxima_cia }
            }
            
            # Pasar costes de la estrategia al optimizador
            optimizer.set_strategy_costs(
                coste_publicidad=gasto_publicidad,
                coste_ID=gasto_ID,
                coste_informes=gasto_informes
            )
            
            # Aplicar configuración de producción (qué grado producir)
            for (p_area, p_prod), p_grado in production_config.items():
                 optimizer.set_market_conditions(
                    area=p_area, prod=p_prod, grado=p_grado, 
                    precio_fijo=market_conditions_actual.get((p_area, p_prod, p_grado), {}).get('precio', 0), 
                    demanda_maxima=market_conditions_actual.get((p_area, p_prod, p_grado), {}).get('demanda', 0),
                    producir_grado=p_grado # p_grado = 0, 1, or -1 (no producir)
                )
            
            optimizer.build_model()
            solucion_actual = optimizer.solve()
            ranking_actual = optimizer.get_objective_value()

            if ranking_actual > mejor_ranking:
                mejor_ranking = ranking_actual
                mejor_solucion = solucion_actual
                mejores_precios = {mercado_key: precio_prueba}
                mejor_market_cond = market_conditions_actual
                
    return mejor_ranking, mejores_precios, mejor_solucion, mejor_market_cond

# --- PASO 1: Cargar LSTs ---
DATA_DIR = os.path.join(os.getcwd(), 'data')
files = sorted(
    glob.glob(os.path.join(DATA_DIR, 'Decisión [0-9].lst.txt')) + 
    glob.glob(os.path.join(DATA_DIR, 'Descisión [0-9].lst.txt')),
    key=lambda x: int(re.search(r'[Dd]ecisión (\d+)', x).group(1))
)
if not files: exit("Error: No se encontraron archivos de Decisión en /data.")

print(f"Archivos LST detectados: {[os.path.basename(f) for f in files]}")
parser = LSTParser()
datos_historicos = [parser.parse_file(f) for f in files]
current_state_parsed = datos_historicos[-1]
print(f"Última decisión detectada: {os.path.basename(files[-1])}")

# --- PASO 1.5: Cargar Rankings ---
print("\nCargando datos históricos de ranking...")
puntos_ranking = load_ranking_data(DATA_DIR, datos_historicos)
if puntos_ranking:
    print(f"Encontrados {len(puntos_ranking)} puntos de datos para calibrar el ranking.")
    ultimo_punto = puntos_ranking[-1]
    print(f"  -> Último punto: Periodo {ultimo_punto['periodo']}, Score: {ultimo_punto['score']}")
else:
    print("No se encontraron archivos de Ranking. Usando fórmula de ranking por defecto.")

# --- PASO 2: Entrenar Modelo de Demanda ---
print("\nEntrenando modelo de demanda con datos históricos...")
estimador = DemandEstimator(datos_historicos)
modelo_eu_x0 = estimador.get_demand_function('EU', 'X', 0)
modelo_eu_y0 = estimador.get_demand_function('EU', 'Y', 0)
modelo_eu_y1 = estimador.get_demand_function('EU', 'Y', 1)
print(f"Modelo de demanda para ('EU', 'X', 0): {modelo_eu_x0}")
print(f"Modelo de demanda para ('EU', 'Y', 0): {modelo_eu_y0}")
print(f"Modelo de demanda para ('EU', 'Y', 1): {modelo_eu_y1}")


# --- PASO 3: Preparar Estado Actual ---
beneficio = current_state_parsed.get('utilidad_periodo', 0)
liquidez = current_state_parsed.get('caja_total', 0)
inventarios = current_state_parsed.get('inventarios_detalle', {}) 
cuota = current_state_parsed.get('cuota_mercado', 0)
inventarios_total = sum(v for v in inventarios.values() if v)

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

# --- PASO 4: Comparar Estrategias ---
print("\n--- Evaluando Estrategias de Mercado ---")
estrategias_ranking = {}

# Estrategia 1: "Vender Stock"
# (Vender el stock de 37k de ('EU', 'X', 0))
strategy_1_config = {
    'markets_to_test': { ('EU', 'X', 0): [35, 40, 45, 50] },
    'production_config': { ('EU', 'X'): -1 }, # -1 = No Producir
    'gasto_publicidad': 0,
    'gasto_ID': 0
}
r1, p1, s1, c1 = find_best_strategy(current_state_optimizer, estimador, strategy_1_config)
estrategias_ranking['Vender Stock EU-X'] = {'ranking': r1, 'precios': p1, 'solucion': s1, 'condiciones': c1}
print(f"Resultado Estrategia 'Vender Stock': Ranking Estimado = {r1:.2f} (Precio: {p1})")

# Estrategia 2: "Abrir PCs Estándar"
# (Producir y vender ('EU', 'Y', 0))
strategy_2_config = {
    'markets_to_test': { ('EU', 'Y', 0): [130, 140, 150] }, # Precios de PC Estándar
    'production_config': { ('EU', 'Y'): 0 }, # Producir Grado 0
    'gasto_publicidad': 0, # Sin publicidad
    'gasto_ID': COSTE_ID_Y # Gasto para habilitar producción de PCs
}
r2, p2, s2, c2 = find_best_strategy(current_state_optimizer, estimador, strategy_2_config)
estrategias_ranking['Abrir PCs Estándar EU'] = {'ranking': r2, 'precios': p2, 'solucion': s2, 'condiciones': c2}
print(f"Resultado Estrategia 'Abrir PCs Estándar': Ranking Estimado = {r2:.2f} (Precio: {p2})")

# Estrategia 3: "Abrir PCs Lujo con Publicidad"
# (Producir y vender ('EU', 'Y', 1))
strategy_3_config = {
    'markets_to_test': { ('EU', 'Y', 1): [150, 160, 170] }, # Precios más altos para Lujo
    'production_config': { ('EU', 'Y'): 1 }, # Producir Grado 1
    'gasto_publicidad': COSTE_PUBLICIDAD_Y_EU, # Invertir en Publicidad
    'gasto_ID': COSTE_ID_Y # Gasto para habilitar producción de PCs
}
r3, p3, s3, c3 = find_best_strategy(current_state_optimizer, estimador, strategy_3_config)
estrategias_ranking['Abrir PCs Lujo EU (con Pub)'] = {'ranking': r3, 'precios': p3, 'solucion': s3, 'condiciones': c3}
print(f"Resultado Estrategia 'Abrir PCs Lujo (con Pub)': Ranking Estimado = {r3:.2f} (Precio: {p3})")


# --- PASO 5: Mostrar la MEJOR Solución ---
print("\n--- Recomendación Estratégica ---")
mejor_estrategia_nombre = max(estrategias_ranking, key=lambda k: estrategias_ranking[k]['ranking'])
mejor_estrategia = estrategias_ranking[mejor_estrategia_nombre]

print(f"RECOMENDACIÓN: **{mejor_estrategia_nombre}** es la estrategia más rentable.")
print(f"Mejor Ranking Estimado: {mejor_estrategia['ranking']:.2f}")
print(f"Mejor Estrategia de Precios: {mejor_estrategia['precios']}")

print("\nDecisiones de Producción y Venta Recomendadas:")
if not mejor_estrategia['solucion']:
    print("(Ninguna acción recomendada, no se encontró beneficio)")
else:
    for k, v in mejor_estrategia['solucion'].items():
        print(f"{k}: {v}")
    
    # Usar una nueva instancia de optimizer solo para llamar a la función de estimación
    optimizer_estimador = OptimizerV3(current_state=current_state_optimizer)
    optimizer_estimador.estimate_next_period(mejor_estrategia['solucion'], mejor_estrategia['condiciones'])

# --- PASA 5.5: Recomendación de Informes ---
print("\n--- Recomendación de Informes (Asesorías) ---")
if modelo_eu_x0['puntos_datos'] == 0:
    print(f"ADVERTENCIA: El modelo de demanda para 'EU-Chip' (Stock) falló ('puntos_datos': 0).")
    print(f"  -> Causa: No hay suficientes datos históricos de precios de la competencia (Asesoría 28).")
    print(f"  -> RECOMENDACIÓN: Comprar el informe **IM 2** (60k FS) y **IM 17** (10k FS) [cite: 2064, 2066] para obtener datos precisos de ventas por grado y mejorar esta estimación.")
else:
    print("El modelo de demanda para 'EU-Chip' se ha calibrado correctamente.")


# --- PASO 6: Negociación ---
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