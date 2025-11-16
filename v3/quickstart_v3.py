import os
import glob
import re
import csv
from v3.optimizer_pulp import OptimizerV3
from v3.negotiation import Negotiation
from v3.ranking import calculate_ranking
from src.parser import LSTParser
from v3.demand_estimator import DemandEstimator 

def load_ranking_data(data_dir, historicos_parseados):
    """
    Carga los archivos Ranking X.txt, los parsea y los alinea con
    los datos parseados del LST correspondiente.
    """
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
                    next(reader) # Saltar cabecera
                    for row in reader:
                        if not row or len(row) < 2: continue
                        
                        if int(row[0].strip()) == 4: # Asumimos ID=4
                            # El formato es 0'2620339, la comilla es el decimal.
                            score_str = row[1].strip().replace("'", ".") 
                            score = float(score_str)
                            
                            ranking_data.append({
                                'periodo': periodo,
                                'score': score,
                                'estado': estado_lst
                            })
                            break 
        except Exception as e:
            print(f"Error procesando el archivo de ranking {r_file}: {e}")
            
    return ranking_data

def find_best_strategy(current_state, estimador, markets_to_test, production_config):
    """
    Función helper para ejecutar el bucle de optimización
    para una estrategia y un conjunto de mercados dados.
    """
    mejor_ranking = -float('inf')
    mejor_solucion = None
    mejores_precios = {}
    mejor_market_cond = {}

    # Itera sobre los mercados a probar (ej. ('EU', 'Y', 0))
    for mercado_key, precios in markets_to_test.items():
        area, prod, grado = mercado_key
        
        for precio_prueba in precios:
            # Obtiene la función de demanda para este mercado específico
            func_demanda = estimador.get_demand_function(area, prod, grado)
            
            demanda_total_mercado = func_demanda['interseccion'] + (func_demanda['pendiente'] * precio_prueba)
            # Asumir que podemos capturar una cuota (ej. 10%) del mercado total
            demanda_maxima_cia = max(0, int(demanda_total_mercado * 0.10)) 

            optimizer = OptimizerV3(current_state=current_state)
            
            market_conditions_actual = {
                mercado_key: { 'precio': precio_prueba, 'demanda': demanda_maxima_cia }
            }
            
            # Aplicar configuración de producción (qué grado producir)
            for (p_area, p_prod), p_grado in production_config.items():
                 optimizer.set_market_conditions(
                    area=p_area, prod=p_prod, grado=p_grado, 
                    precio_fijo=market_conditions_actual.get((p_area, p_prod, p_grado), {}).get('precio', 0), 
                    demanda_maxima=market_conditions_actual.get((p_area, p_prod, p_grado), {}).get('demanda', 0),
                    producir_grado=p_grado
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
    # TODO: Usar puntos_ranking para ajustar la fórmula del ranking (W1, W2, W3, W4)
else:
    print("No se encontraron archivos de Ranking. Usando fórmula de ranking por defecto.")

# --- PASO 2: Entrenar Modelo de Demanda ---
print("\nEntrenando modelo de demanda con datos históricos...")
estimador = DemandEstimator(datos_historicos)
print(f"Modelo de demanda para ('EU', 'X', 0): {estimador.get_demand_function('EU', 'X', 0)}")
print(f"Modelo de demanda para ('EU', 'Y', 0): {estimador.get_demand_function('EU', 'Y', 0)}")


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

# Estrategia 1: Vender el stock existente en ('EU', 'X', 0)
mercados_stock = {
    ('EU', 'X', 0): [35, 40, 45, 50]
}
prod_config_stock = { ('EU', 'X'): -1 } # -1 = No Producir

ranking_stock, precios_stock, sol_stock, cond_stock = find_best_strategy(
    current_state_optimizer, estimador, mercados_stock, prod_config_stock
)
print(f"Resultado Estrategia 'Vender Stock': Ranking Estimado = {ranking_stock:.2f} (Precio: {precios_stock})")


# Estrategia 2: Abrir un nuevo mercado de PCs en EU
mercados_nuevos = {
    ('EU', 'Y', 0): [130, 140, 150] # Precios típicos para PC en EU (fuente: 448)
}
prod_config_nuevos = { ('EU', 'Y'): 0 } # Producir Grado 0 de PCs en EU

ranking_nuevo, precios_nuevo, sol_nuevo, cond_nuevo = find_best_strategy(
    current_state_optimizer, estimador, mercados_nuevos, prod_config_nuevos
)
print(f"Resultado Estrategia 'Abrir PCs EU': Ranking Estimado = {ranking_nuevo:.2f} (Precio: {precios_nuevo})")

# --- PASO 5: Mostrar la MEJOR Solución ---
print("\n--- Recomendación Estratégica ---")
if ranking_nuevo > ranking_stock:
    print("RECOMENDACIÓN: **Abrir el mercado de PCs en EU** es la estrategia más rentable.")
    mejor_solucion_final = sol_nuevo
    mejores_precios_final = precios_nuevo
    mejor_market_conditions = cond_nuevo
    mejor_ranking_total = ranking_nuevo
else:
    print("RECOMENDACIÓN: **Vender el stock de Chips en EU** es la estrategia más rentable.")
    mejor_solucion_final = sol_stock
    mejores_precios_final = precios_stock
    mejor_market_conditions = cond_stock
    mejor_ranking_total = ranking_stock

print(f"\nMejor Ranking Estimado: {mejor_ranking_total:.2f}")
print(f"Mejor Estrategia de Precios: {mejores_precios_final}")

print("\nDecisiones de Producción y Venta Recomendadas:")
if not mejor_solucion_final:
    print("(Ninguna acción recomendada, no se encontró beneficio)")
else:
    for k, v in mejor_solucion_final.items():
        print(f"{k}: {v}")
    
    # *** CORRECCIÓN DEL BUG "NameError" ***
    # Creamos una instancia de Optimizer solo para llamar a estimate_next_period
    optimizer_estimador = OptimizerV3(current_state=current_state_optimizer)
    optimizer_estimador.estimate_next_period(mejor_solucion_final, mejor_market_conditions)

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