import os
import glob
import re
import csv # <--- AÑADIR IMPORT
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
    # Busca archivos como "Ranking 4.txt"
    ranking_files = glob.glob(os.path.join(data_dir, 'Ranking [0-9].txt'))
    
    for r_file in ranking_files:
        try:
            # Extraer el número de periodo del nombre del archivo
            periodo_num_match = re.search(r'Ranking (\d+)\.txt', r_file)
            if not periodo_num_match:
                continue
            
            periodo = int(periodo_num_match.group(1))
            
            # Encontrar el LST correspondiente (Decisión X.LST.txt)
            # (periodo - 1 porque los índices de lista empiezan en 0)
            if (periodo - 1) < len(historicos_parseados):
                estado_lst = historicos_parseados[periodo - 1]
                
                # Leer el archivo Ranking (es un CSV con ; y ' como separador de miles)
                with open(r_file, 'r') as f:
                    reader = csv.reader(f, delimiter=';')
                    next(reader) # Saltar cabecera
                    for row in reader:
                        if not row: continue
                        # Encontrar nuestra compañía (Asumimos ID=4)
                        if int(row[0].strip()) == 4:
                            # Limpiar el número: quitar ' y reemplazar , con .
                            score_str = row[1].strip().replace("'", "").replace(",", ".")
                            score = float(score_str)
                            
                            # Guardar el punto de dato
                            ranking_data.append({
                                'periodo': periodo,
                                'score': score,
                                'estado': estado_lst # Guardamos todos los datos del LST
                            })
                            break # Dejar de leer este archivo
        except Exception as e:
            print(f"Error procesando el archivo de ranking {r_file}: {e}")
            
    return ranking_data

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

# --- AÑADIDO: PASO 1.5: Cargar Datos de Ranking ---
print("\nCargando datos históricos de ranking...")
puntos_ranking = load_ranking_data(DATA_DIR, datos_historicos)
if puntos_ranking:
    print(f"Encontrados {len(puntos_ranking)} puntos de datos para calibrar el ranking.")
    # Imprimir el último punto de dato encontrado
    ultimo_punto = puntos_ranking[-1]
    print(f"  -> Último punto: Periodo {ultimo_punto['periodo']}, Score: {ultimo_punto['score']}")
    print(f"     Datos LST: B: {ultimo_punto['estado']['utilidad_periodo']}, L: {ultimo_punto['estado']['caja_total']}, C: {ultimo_punto['estado']['cuota_mercado']}")
else:
    print("No se encontraron archivos de Ranking (ej: 'Ranking 4.txt'). Usando fórmula de ranking por defecto.")


# --- PASO 2: Entrenar el Modelo de Demanda ---
print("\nEntrenando modelo de demanda con datos históricos...")
estimador = DemandEstimator(datos_historicos)
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
mercados_a_probar = {
    ('EU', 'X'): [35, 40, 45, 50] 
}
mejor_ranking_total = -float('inf')
mejor_solucion_final = None
mejores_precios_final = {}
mejor_market_conditions = {}

for mercado_key, precios in mercados_a_probar.items():
    area, prod = mercado_key
    for grado_a_vender in [0, 1]:
        for precio_prueba in precios:
            func_demanda = estimador.get_demand_function(area, prod)
            demanda_total_mercado = func_demanda['interseccion'] + (func_demanda['pendiente'] * precio_prueba)
            demanda_maxima_cia = max(0, int(demanda_total_mercado * 0.10)) 

            optimizer = OptimizerV3(current_state=current_state_optimizer)
            
            market_conditions_actual = {
                (area, prod, grado_a_vender): {
                    'precio': precio_prueba,
                    'demanda': demanda_maxima_cia
                }
            }
            # (Simplificación: Asumimos que solo probamos un mercado a la vez)
            
            optimizer.set_market_conditions(
                area=area, prod=prod, grado=grado_a_vender, 
                precio_fijo=precio_prueba, 
                demanda_maxima=demanda_maxima_cia,
                producir_grado=0 
            )
            
            optimizer.build_model()
            solucion_actual = optimizer.solve()
            ranking_actual = optimizer.get_objective_value()

            if ranking_actual > mejor_ranking_total:
                mejor_ranking_total = ranking_actual
                mejor_solucion_final = solucion_actual
                mejores_precios_final = {(area, prod, grado_a_vender): precio_prueba}
                mejor_market_conditions = market_conditions_actual

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
    optimizer.estimate_next_period(mejor_solucion_final, mejor_market_conditions)

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