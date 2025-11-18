import os
import glob
import re
import csv
from v3.optimizer_pulp import OptimizerV3
from v3.negotiation import Negotiation
from v3.ranking import calculate_ranking
from src.parser import LSTParser
from v3.demand_estimator import DemandEstimator 
from src.forms import FormsExporter
from src.params import PRECIOS_TIPICOS, AR_STRUCTURE

# Constantes para la simulación de estrategias
COSTE_ID_Y = 320000 
COSTE_ID_X = 320000 
COSTE_PUBLICIDAD_Y_EU = 50000 
ELASTICIDAD_PUBLICIDAD = 0.15 
COSTE_INFORME_IM2 = 60000 
COSTE_INFORME_IM17 = 10000 

# --- Valores Base para Normalizar ---
BASE_BENEFICIO = 500000.0
BASE_LIQUIDEZ = 20000000.0
BASE_INVENTARIO = 100000.0
BASE_CUOTA = 150000.0      

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

def find_best_strategy(current_state_norm, patentes, estimador, strategy_config):
    """
    Función helper para ejecutar el bucle de optimización
    """
    markets_to_test = strategy_config.get('markets_to_test', {})
    production_config = strategy_config.get('production_config', {})
    
    # --- Lógica de Patentes Dinámica ---
    gasto_ID = 0
    grado_req_X = production_config.get(('EU', 'X'), -1)
    if grado_req_X > patentes.get(('EU', 'X'), 0):
        gasto_ID += COSTE_ID_X
    
    grado_req_Y = production_config.get(('EU', 'Y'), -1)
    if grado_req_Y > patentes.get(('EU', 'Y'), 0):
        gasto_ID += COSTE_ID_Y
    
    gasto_publicidad = strategy_config.get('gasto_publicidad', 0)
    gasto_informes = strategy_config.get('gasto_informes', 0)
    # --- Fin Lógica de Patentes ---

    mejor_ranking = -float('inf')
    mejor_solucion = None
    mejores_precios = {}
    mejor_market_cond = {}

    if not markets_to_test:
        markets_to_test[()] = [0] # Iteración dummy para "No hacer nada"

    for mercado_key, precios in markets_to_test.items():
        
        if not mercado_key:
             precios = [0]
        else:
            area, prod, grado = mercado_key
            grado_poseido_prod = patentes.get((area, prod), 0)
            if grado > grado_poseido_prod:
                # No se puede VENDER un producto si no se tiene la patente
                continue

        for precio_prueba in precios:
            
            optimizer = OptimizerV3(current_state=current_state_norm)
            market_conditions_actual = {}
            
            if mercado_key: 
                area, prod, grado = mercado_key
                func_demanda = estimador.get_demand_function(area, prod, grado)
                demanda_total_mercado = func_demanda['interseccion'] + (func_demanda['pendiente'] * precio_prueba)
                
                if gasto_publicidad > 0:
                    demanda_total_mercado *= (1 + ELASTICIDAD_PUBLICIDAD * (gasto_publicidad / 100000))

                cuota_mercado_objetivo = 0.15 if grado == 1 else 0.10
                demanda_maxima_cia = max(0, int(demanda_total_mercado * cuota_mercado_objetivo))

                market_conditions_actual = {
                    mercado_key: { 'precio': precio_prueba, 'demanda': demanda_maxima_cia }
                }
            
            optimizer.set_strategy_costs(
                coste_publicidad=gasto_publicidad,
                coste_ID=gasto_ID, 
                coste_informes=gasto_informes
            )
            
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
                if mercado_key: 
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


# --- PASO 3: Preparar Estado Actual (CON NORMALIZACIÓN Y PATENTES) ---
beneficio_bruto = current_state_parsed.get('utilidad_periodo', 0)
liquidez_bruta = current_state_parsed.get('caja_total', 0)
inventarios_detalle = current_state_parsed.get('inventarios_detalle', {}) 
ventas_propias_total = sum(current_state_parsed.get('ventas_propias', {}).values())
inventarios_total_bruto = sum(v for v in inventarios_detalle.values() if v)

# ELIMINADO EL AVISO: El parser corregido debe encontrar las patentes (o un dict vacío)
patentes_poseidas = current_state_parsed.get('patentes_poseidas', {
    ('EU', 'X'): 0, ('EU', 'Y'): 0, ('US', 'X'): 0, ('US', 'Y'): 0, ('BR', 'X'): 0, ('BR', 'Y'): 0
})

current_state_normalized = {
    'beneficio': beneficio_bruto / BASE_BENEFICIO,
    'liquidez': liquidez_bruta / BASE_LIQUIDEZ,
    'inventarios_detalle': inventarios_detalle, 
    'inventarios_total': inventarios_total_bruto / BASE_INVENTARIO,
    'cuota': ventas_propias_total / BASE_CUOTA,
    'patentes_poseidas': patentes_poseidas 
}
print("\nResumen del estado actual (NORMALIZADO):")
print(f"beneficio: {current_state_normalized['beneficio']}")
print(f"liquidez: {current_state_normalized['liquidez']}")
print(f"inventarios_detalle: {current_state_normalized['inventarios_detalle']}")
print(f"inventarios_total (norm): {current_state_normalized['inventarios_total']}")
print(f"cuota (ventas propias norm): {current_state_normalized['cuota']}")
print(f"Patentes EU: X{patentes_poseidas.get(('EU', 'X'), 0)}, Y{patentes_poseidas.get(('EU', 'Y'), 0)}")


# --- PASO 4: Comparar Estrategias (CORREGIDAS CON LÓGICA DE PATENTES 1:1) ---
print("\n--- Evaluando Estrategias de Mercado ---")
estrategias_ranking = {}
todas_las_configs = {}

# Estrategia 1: "Vender Stock" (Vender X0)
strategy_1_config = {
    'markets_to_test': { ('EU', 'X', 0): [35, 40, 45, 50] },
    'production_config': { ('EU', 'X'): -1, ('EU', 'Y'): -1 }, 
    'gasto_publicidad': 0,
}
todas_las_configs['Vender Stock EU-X'] = strategy_1_config
r1, p1, s1, c1 = find_best_strategy(current_state_normalized, patentes_poseidas, estimador, strategy_1_config)
estrategias_ranking['Vender Stock EU-X'] = {'ranking': r1, 'precios': p1, 'solucion': s1, 'condiciones': c1}
print(f"Resultado Estrategia 'Vender Stock': Ranking Estimado = {r1:.4f} (Precio: {p1})")

# Estrategia 2: "Abrir PCs Estándar" (Producir Y0, que consume X0)
strategy_2_config = {
    'markets_to_test': { ('EU', 'Y', 0): [130, 140, 150] },
    'production_config': { ('EU', 'X'): 0, ('EU', 'Y'): 0 }, # Producir X0 e Y0
    'gasto_publicidad': 0, 
}
todas_las_configs['Abrir PCs Estándar EU'] = strategy_2_config
r2, p2, s2, c2 = find_best_strategy(current_state_normalized, patentes_poseidas, estimador, strategy_2_config)
estrategias_ranking['Abrir PCs Estándar EU'] = {'ranking': r2, 'precios': p2, 'solucion': s2, 'condiciones': c2}
print(f"Resultado Estrategia 'Abrir PCs Estándar': Ranking Estimado = {r2:.4f} (Precio: {p2})")

# Estrategia 3: "Abrir PCs Lujo con Publicidad" (Producir Y1, que consume X1)
strategy_3_config = {
    'markets_to_test': { ('EU', 'Y', 1): [150, 160, 170] },
    'production_config': { ('EU', 'X'): 1, ('EU', 'Y'): 1 }, # Producir X1 e Y1
    'gasto_publicidad': COSTE_PUBLICIDAD_Y_EU, 
}
todas_las_configs['Abrir PCs Lujo EU (con Pub)'] = strategy_3_config
r3, p3, s3, c3 = find_best_strategy(current_state_normalized, patentes_poseidas, estimador, strategy_3_config)
estrategias_ranking['Abrir PCs Lujo EU (con Pub)'] = {'ranking': r3, 'precios': p3, 'solucion': s3, 'condiciones': c3}
print(f"Resultado Estrategia 'Abrir PCs Lujo (con Pub)': Ranking Estimado = {r3:.4f} (Precio: {p3})")

# Estrategia 4: "Producir Chips Lujo (I+D) y vender" (Producir X1)
strategy_4_config = {
    'markets_to_test': { 
        ('EU', 'X', 1): [50, 55, 60]
    }, 
    'production_config': { ('EU', 'X'): 1, ('EU', 'Y'): -1 }, # Producir Chips Grado 1
    'gasto_publicidad': 0, 
}
todas_las_configs['Producir Chips Lujo EU'] = strategy_4_config
r4, p4, s4, c4 = find_best_strategy(current_state_normalized, patentes_poseidas, estimador, strategy_4_config)
estrategias_ranking['Producir Chips Lujo EU'] = {'ranking': r4, 'precios': p4, 'solucion': s4, 'condiciones': c4}
print(f"Resultado Estrategia 'Producir Chips Lujo EU': Ranking Estimado = {r4:.4f} (Precio: {p4})")

# Estrategia 5: "No hacer nada" (Mantener costes)
strategy_5_config = {
    'markets_to_test': {},
    'production_config': { ('EU', 'X'): -1, ('EU', 'Y'): -1 }, 
    'gasto_publicidad': 0, 
    'gasto_informes': 0
}
todas_las_configs['No hacer nada'] = strategy_5_config
r5, p5, s5, c5 = find_best_strategy(current_state_normalized, patentes_poseidas, estimador, strategy_5_config)
estrategias_ranking['No hacer nada'] = {'ranking': r5, 'precios': p5, 'solucion': s5, 'condiciones': c5}
print(f"Resultado Estrategia 'No hacer nada': Ranking Estimado = {r5:.4f} (Precio: {p5})")


# --- PASO 5: Mostrar la MEJOR Solución ---
print("\n--- Recomendación Estratégica ---")
mejor_estrategia_nombre = max(estrategias_ranking, key=lambda k: estrategias_ranking[k]['ranking'])
mejor_estrategia = estrategias_ranking[mejor_estrategia_nombre]

print(f"RECOMENDACIÓN: **{mejor_estrategia_nombre}** es la estrategia más rentable.")
print(f"Mejor Ranking Estimado: {mejor_estrategia['ranking']:.4f}")
print(f"Mejor Estrategia de Precios: {mejor_estrategia['precios']}")

print("\nDecisiones de Producción y Venta Recomendadas:")
if not mejor_estrategia.get('solucion'):
    print("(Ninguna acción recomendada, no se encontró beneficio)")
else:
    for k, v in mejor_estrategia['solucion'].items():
        if v > 0: 
            print(f"{k}: {v}")
    
    optimizer_estimador = OptimizerV3(current_state=current_state_normalized)
    optimizer_estimador.estimate_next_period(mejor_estrategia['solucion'], mejor_estrategia['condiciones'])

# --- PASO 5.5: Generar Formularios de Decisión ---
print("\n--- Generando Archivos de Decisión ---")

try:
    periodo_actual = int(re.search(r'[Dd]ecisión (\d+)', os.path.basename(files[-1])).group(1))
    periodo_siguiente = periodo_actual + 1
    
    output_dir = os.path.join(os.getcwd(), 'outputs', 'forms')
    exporter = FormsExporter(output_dir)
    
    config_ganadora = todas_las_configs.get(mejor_estrategia_nombre, {})
    solucion_ganadora = mejor_estrategia.get('solucion', {})
    
    # --- 1. Preparar datos H1 (I+D, Informes, Dividendos) ---
    h1_data = {
        'I+D_X_kFS': 0,
        'I+D_Y_kFS': 0,
        'IM_monto_kFS': config_ganadora.get('gasto_informes', 0) / 1000,
        'IM_estudios': [], 
        'dividendos_kFS': 0 
    }
    
    grado_req_X_ganador = config_ganadora.get('production_config', {}).get(('EU', 'X'), -1)
    if grado_req_X_ganador > patentes_poseidas.get(('EU', 'X'), 0):
        h1_data['I+D_X_kFS'] = COSTE_ID_X / 1000
        
    grado_req_Y_ganador = config_ganadora.get('production_config', {}).get(('EU', 'Y'), -1)
    if grado_req_Y_ganador > patentes_poseidas.get(('EU', 'Y'), 0):
        h1_data['I+D_Y_kFS'] = COSTE_ID_Y / 1000
    
    if modelo_eu_x0['puntos_datos'] == 0:
        h1_data['IM_estudios'].extend([2, 17])
        h1_data['IM_monto_kFS'] += (COSTE_INFORME_IM2 + COSTE_INFORME_IM17) / 1000


    # --- 2. Preparar datos A1 (Marketing) ---
    a1_data = {}
    for area in ['US', 'EU', 'BR']:
        for prod in ['X', 'Y']:
            for g in [0, 1]:
                a1_data[(area, prod, g)] = {'price': 0, 'ad': 0}

    for mercado_key, precio in mejor_estrategia.get('precios', {}).items():
        area, prod, g = mercado_key
        pub_asignada = config_ganadora.get('gasto_publicidad', 0) / 1000 if area == 'EU' else 0
        
        a1_data[mercado_key] = {
            'price': int(precio),
            'ad': pub_asignada 
        }

    # --- 3. Preparar datos A2 (Producción) ---
    a2_data = { 'US': {'X': {}, 'Y': {}}, 'EU': {'X': {}, 'Y': {}}, 'BR': {'X': {}, 'Y': {}} }
    
    prod_config_ganadora = config_ganadora.get('production_config', {})
    
    for (area, prod), grado in prod_config_ganadora.items():
        if grado != -1: 
            prod_var_name = f'prod_{area}_{prod}'
            unidades_produccion = int(solucion_ganadora.get(prod_var_name, 0))
            
            if unidades_produccion == 0:
                continue

            prod_data = {
                'nuevas': 0, 'mejora_k': 0,
                'grado_inf': 0, 'prod_planta': [0,0,0],
                'grado_sup': 0, 'prod_planta_sup': [0,0,0]
            }
            
            if grado == 0:
                prod_data['grado_inf'] = 0
                prod_data['prod_planta'] = [unidades_produccion, 0, 0] # Asigna a planta 1
            else:
                prod_data['grado_sup'] = grado
                prod_data['prod_planta_sup'] = [unidades_produccion, 0, 0] # Asigna a planta 1
            
            a2_data[area][prod] = prod_data

    # --- 4. Exportar Archivos ---
    path_h1 = exporter.export_H1(periodo_siguiente, h1_data)
    path_a1 = exporter.export_A1(periodo_siguiente, a1_data)
    path_a2 = exporter.export_A2(periodo_siguiente, a2_data)
    
    print(f"Archivos de decisión para el Periodo {periodo_siguiente} generados en:")
    print(f"-> {path_h1}")
    print(f"-> {path_a1}")
    print(f"-> {path_a2}")

except Exception as e:
    print(f"\nERROR al generar los archivos de decisión: {e}")
    import traceback
    traceback.print_exc()


# --- PASO 6: Negociación Interactiva (B2B) ---

print("\n--- Negociación Interactiva (B2B) ---")

ranking_actual = calculate_ranking(current_state_normalized)
stock_actual_eu_x = inventarios_detalle.get(('EU', 'X', 0), 0)

costo_var_eu_x = PRECIOS_TIPICOS['EU']['X'] * 0.155 
cash_ratio_eu = AR_STRUCTURE['EU']['cash'] 

print(f"Stock actual de ('EU', 'X', 0): {stock_actual_eu_x} unidades.")
print(f"Ranking base (sin pactos): {ranking_actual:.4f}")

while True:
    try:
        respuesta = input("\n¿Has recibido una nueva oferta B2B por tu stock de EU-X-Std? (s/n): ").strip().lower()
        if respuesta != 's':
            break
        
        offer_price = float(input("  > Precio unitario ofertado (€): "))
        offer_volume = float(input(f"  > Volumen (unidades) ofertado (max {stock_actual_eu_x}): "))

        if offer_volume > stock_actual_eu_x:
            print(f"  [!] Error: El volumen ofertado ({offer_volume}) supera el stock disponible ({stock_actual_eu_x}).")
            continue
        
        if offer_price <= costo_var_eu_x:
            print(f"  [!] Advertencia: El precio ofertado ({offer_price:.2f}€) es menor o igual al coste variable ({costo_var_eu_x:.2f}€).")
            print("      Aceptar resultará en pérdidas de beneficio.")

        ingreso_pacto = offer_price * offer_volume
        costo_pacto = costo_var_eu_x * offer_volume
        beneficio_pacto = ingreso_pacto - costo_pacto
        liquidez_pacto = ingreso_pacto * cash_ratio_eu 
        
        nuevo_beneficio_bruto = beneficio_bruto + beneficio_pacto
        nueva_liquidez_bruta = liquidez_bruta + liquidez_pacto
        nuevo_inventario_bruto = inventarios_total_bruto - offer_volume
        nueva_cuota_bruta = ventas_propias_total + offer_volume
        
        nuevo_beneficio_norm = nuevo_beneficio_bruto / BASE_BENEFICIO
        nueva_liquidez_norm = nueva_liquidez_bruta / BASE_LIQUIDEZ
        nuevo_inventario_norm = nuevo_inventario_bruto / BASE_INVENTARIO
        nueva_cuota_norm = nueva_cuota_bruta / BASE_CUOTA
        
        nuevo_ranking_calculado = calculate_ranking({
            'beneficio': nuevo_beneficio_norm,
            'liquidez': nueva_liquidez_norm,
            'cuota': nueva_cuota_norm,
            'inventarios': nuevo_inventario_norm
        })
        
        print(f"\n  --- Evaluación de la Oferta ---")
        print(f"  Ranking Actual:   {ranking_actual:.4f}")
        print(f"  Ranking Aceptando: {nuevo_ranking_calculado:.4f}")
        print(f"  Impacto en Ranking: {nuevo_ranking_calculado - ranking_actual:+.4f}")
        
        counter_price = offer_price * 1.10 
        counter_volume = offer_volume
        print(f"\n  Sugerencia de Contraoferta: Precio={counter_price:.2f}, Volumen={counter_volume:.0f}")

        accion = input("  ¿Qué deseas hacer? (1=Aceptar, 2=Rechazar/Ignorar, 3=Contraofertar): ").strip()
        if accion == '1':
            print("  (Oferta aceptada - Lógica de formulario H6 pendiente de implementar)")
        else:
            print("  (Oferta ignorada, puedes evaluar otra)")

    except ValueError:
        print("[!] Error: Introduce solo números para precio y volumen.")
    except Exception as e:
        print(f"Ha ocurrido un error inesperado: {e}")

# --- Propuesta de Pacto Comercial (Req 3) ---
print("\n--- Propuesta de Pacto Comercial (Venta de Stock EU-X) ---")
print(f"Analizando rentabilidad de vender el stock de {stock_actual_eu_x} unidades...")
print(f"El coste variable (VC) mínimo por unidad es: {costo_var_eu_x:.2f} €")
print(f"El cobro al contado (cash ratio) en EU es: {cash_ratio_eu * 100:.0f}%")
print(f"Para que un pacto sea rentable, el precio unitario DEBE ser superior a {costo_var_eu_x:.2f} €.")

mejor_pacto = {'price': 0, 'volume': 0, 'ranking': ranking_actual}

precio_minimo = int(costo_var_eu_x) + 1
precio_maximo = int(PRECIOS_TIPICOS['EU']['X'])

if stock_actual_eu_x > 0:
    for test_price in range(precio_minimo, precio_maximo + 1):
        test_volume = stock_actual_eu_x 
        
        ingreso_pacto = test_price * test_volume
        costo_pacto = costo_var_eu_x * test_volume
        beneficio_pacto = ingreso_pacto - costo_pacto
        liquidez_pacto = ingreso_pacto * cash_ratio_eu 
        
        nuevo_beneficio_bruto = beneficio_bruto + beneficio_pacto
        nueva_liquidez_bruta = liquidez_bruta + liquidez_pacto
        nuevo_inventario_bruto = inventarios_total_bruto - test_volume
        nueva_cuota_bruta = ventas_propias_total + test_volume
        
        nuevo_ranking_calculado = calculate_ranking({
            'beneficio': (nuevo_beneficio_bruto / BASE_BENEFICIO),
            'liquidez': (nueva_liquidez_bruta / BASE_LIQUIDEZ),
            'cuota': (nueva_cuota_bruta / BASE_CUOTA),
            'inventarios': (nuevo_inventario_bruto / BASE_INVENTARIO)
        })
        
        if nuevo_ranking_calculado > mejor_pacto['ranking']:
            mejor_pacto = {'price': test_price, 'volume': test_volume, 'ranking': nuevo_ranking_calculado}

if mejor_pacto['price'] > 0:
    print(f"\nPropuesta ÓPTIMA para maximizar ranking (vendiendo todo el stock):")
    print(f"  Precio Mínimo Rentable: {mejor_pacto['price']:.2f} €")
    print(f"  Volumen: {mejor_pacto['volume']:.0f} unidades")
    print(f"  Ranking Estimado: {mejor_pacto['ranking']:.4f} (Mejora: {mejor_pacto['ranking'] - ranking_actual:+.4f})")
    print(f"  Condiciones: Pago 50% contado, 50% a crédito (según AR_STRUCTURE['EU']).")
else:
    print("\nNo se ha encontrado un pacto rentable que mejore el ranking actual vendiendo solo el stock.")

print("\n--- Fin de la Ejecución ---")