import pulp
from src.params import AREAS, PRECIOS_TIPICOS, SALTO_MIN, TOPE_BR_Y_LE3, CAP_MAX, ALMACEN_MIN, COSTE_FIJO

class OptimizerV3:
    def __init__(self, current_state, scenario='hybrid'):
        self.scenario = scenario
        self.current_state = current_state
        self.model = pulp.LpProblem('RankingOptimization', pulp.LpMaximize)
        self.variables = {}
        # Nuevo: Guarda las condiciones del mercado (precio, demanda)
        self.market_conditions = {} 

    def set_market_conditions(self, area, prod, grado, precio_fijo, demanda_maxima):
        """
        Esta función es llamada por quickstart_v3.py ANTES de build_model().
        Fija el precio y la demanda máxima para un mercado específico.
        """
        key = (area, prod, int(grado))
        self.market_conditions[key] = {
            'precio': precio_fijo,
            'demanda': demanda_maxima
        }

    def build_model(self):
        
        # --- Variables ---
        # (Se eliminan las variables de precio y publicidad, ya que se fijan fuera)
        for area in AREAS:
            for prod in ['X', 'Y']:
                # Variables de Producción y Apertura
                cap = CAP_MAX[area][prod]
                self.variables[f'prod_{area}_{prod}'] = pulp.LpVariable(f'prod_{area}_{prod}', lowBound=0, upBound=cap, cat='Integer')
                self.variables[f'open_{area}_{prod}'] = pulp.LpVariable(f'open_{area}_{prod}', cat='Binary')

                for g in [0, 1]: # Grado 0 (Estándar), Grado 1 (Lujo)
                    # Variables de Ventas
                    self.variables[f'ventas_{area}_{prod}_{g}'] = pulp.LpVariable(f'ventas_{area}_{prod}_{g}', lowBound=0, cat='Integer')
        
        # Variables de Inventario Final (por Área-Producto-Grado)
        for key in self.current_state.get('inventarios_detalle', {}).keys():
            area, prod, g = key
            self.variables[f'inv_final_{area}_{prod}_{g}'] = pulp.LpVariable(f'inv_final_{area}_{prod}_{g}', lowBound=0, cat='Integer')

        # --- Restricciones ---
        
        ingreso_terms = []
        coste_variable_terms = []
        coste_fijo_terms = []
        inventario_final_terms = []

        # Cargar inventarios actuales
        inv_actual_dict = self.current_state.get('inventarios_detalle', {})

        for area in AREAS:
            for prod in ['X', 'Y']:
                prod_var = self.variables[f'prod_{area}_{prod}']
                open_var = self.variables[f'open_{area}_{prod}']
                cap = CAP_MAX[area][prod]

                # Restricción "Big M": Si produces, la planta debe estar abierta
                self.model += prod_var <= cap * open_var
                # (Opcional: producción mínima si está abierta)
                self.model += prod_var >= 10 * open_var

                # Costes Fijos (solo se pagan si open_var = 1)
                costo_primera_planta = COSTE_FIJO[area][prod][0]
                coste_fijo_terms.append(costo_primera_planta * open_var)

                # Costes Variables (basados en la PRODUCCIÓN)
                precio_tipico = PRECIOS_TIPICOS[area][prod]
                vc_rate = 0.155 if prod == 'X' else 0.30
                coste_variable_terms.append((precio_tipico * vc_rate) * prod_var)

                # Lógica de Flujo de Inventario y Ventas
                # (Simplificación: toda la producción es de grado 0-Estándar)
                # (Esto debe mejorarse para soportar producción de lujo)
                
                # Grado 0 (Estándar)
                key_std = (area, prod, 0)
                inv_actual_std = inv_actual_dict.get(key_std, 0)
                ventas_std = self.variables.get(f'ventas_{area}_{prod}_0')
                inv_final_std = self.variables.get(f'inv_final_{area}_{prod}_0')
                
                # Grado 1 (Lujo)
                key_lujo = (area, prod, 1)
                inv_actual_lujo = inv_actual_dict.get(key_lujo, 0)
                ventas_lujo = self.variables.get(f'ventas_{area}_{prod}_1')
                inv_final_lujo = self.variables.get(f'inv_final_{area}_{prod}_1')

                # Asumir que la producción (prod_var) es SOLO del grado que probamos
                # Esta es una simplificación grande
                prod_std = prod_var 
                prod_lujo = 0
                
                # Restricciones de Venta y Demanda
                cond_std = self.market_conditions.get(key_std)
                if ventas_std is not None and cond_std:
                    self.model += ventas_std <= cond_std['demanda'] # No vender más que la demanda
                    self.model += ventas_std <= inv_actual_std + prod_std # No vender más que lo disponible
                    ingreso_terms.append(cond_std['precio'] * ventas_std)
                    
                    if inv_final_std is not None:
                        self.model += inv_final_std == inv_actual_std + prod_std - ventas_std
                        inventario_final_terms.append(inv_final_std)

                cond_lujo = self.market_conditions.get(key_lujo)
                if ventas_lujo is not None and cond_lujo:
                    self.model += ventas_lujo <= cond_lujo['demanda']
                    self.model += ventas_lujo <= inv_actual_lujo + prod_lujo
                    ingreso_terms.append(cond_lujo['precio'] * ventas_lujo)
                    
                    if inv_final_lujo is not None:
                        self.model += inv_final_lujo == inv_actual_lujo + prod_lujo - ventas_lujo
                        inventario_final_terms.append(inv_final_lujo)


        # --- Función Objetivo (Ranking) ---
        ingreso_total_periodo = pulp.lpSum(ingreso_terms)
        coste_variable_total = pulp.lpSum(coste_variable_terms)
        coste_fijo_total = pulp.lpSum(coste_fijo_terms)
        
        # Penalización por no abrir plantas (para evitar que todo sea 0)
        penalizacion_inactividad = pulp.lpSum([1 - self.variables[f'open_{area}_{prod}'] for area in AREAS for prod in ['X','Y']]) * 1000

        beneficio_periodo = ingreso_total_periodo - coste_variable_total - coste_fijo_total - penalizacion_inactividad
        
        # Proxies
        liquidez_periodo = beneficio_periodo * 0.5 
        cuota_periodo = ingreso_total_periodo * 0.01
        
        inventarios_total_final = pulp.lpSum(inventario_final_terms)

        # 2. Sumar deltas al estado actual
        beneficio_total_estimado = self.current_state.get('beneficio', 0) + beneficio_periodo
        liquidez_total_estimada = self.current_state.get('liquidez', 0) + liquidez_periodo
        cuota_total_estimada = self.current_state.get('cuota', 0) + cuota_periodo
        
        # 3. Aplicar la fórmula del ranking
        ranking_score = (
            0.4 * beneficio_total_estimado +
            0.3 * liquidez_total_estimada +
            0.2 * cuota_total_estimada +
            0.1 * inventarios_total_final
        )
        
        self.model += ranking_score

    def solve(self):
        self.model.solve(pulp.PULP_CBC_CMD(msg=0))
        solution = {}
        for v in self.model.variables():
            if v.value() is not None and v.value() > 0:
                solution[v.name] = v.value()
        return solution

    def get_objective_value(self):
        return self.model.objective.value()

    def summarize_current_state(self):
        print("Resumen del estado actual:")
        for k, v in self.current_state.items():
            print(f"{k}: {v}")

    def estimate_next_period(self, solution, state):
        print("\nEstimación del siguiente periodo si aplicamos decisiones:")
        
        # Recalcular ingresos basados en la solución
        ingreso_estimado = 0
        for k, v in solution.items():
            if k.startswith('ventas_'):
                # Extraer clave del nombre de la variable
                parts = k.split('_')
                key = (parts[1], parts[2], int(parts[3]))
                precio_fijo = self.market_conditions.get(key, {}).get('precio', 0)
                ingreso_estimado += precio_fijo * v
        
        print(f"Ingreso estimado (solo ventas): {ingreso_estimado:.2f}")
        
        inv_list = [solution.get(f'inv_final_{key[0]}_{key[1]}_{key[2]}', 0) for key in self.market_conditions.keys()]
        print(f"Inventarios finales esperados (mercados probados): {inv_list}")