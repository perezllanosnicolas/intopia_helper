import pulp
from src.params import AREAS, PRECIOS_TIPICOS, SALTO_MIN, TOPE_BR_Y_LE3, CAP_MAX, ALMACEN_MIN, COSTE_FIJO

class OptimizerV3:
    def __init__(self, current_state, scenario='hybrid'):
        self.scenario = scenario
        self.current_state = current_state
        self.model = pulp.LpProblem('RankingOptimization', pulp.LpMaximize)
        self.variables = {}
        self.market_conditions = {} 
        self.production_grade_map = {}
        self.coste_publicidad_total = 0
        self.coste_ID_total = 0
        self.coste_informes_total = 0

    def set_market_conditions(self, area, prod, grado, precio_fijo, demanda_maxima, producir_grado):
        key = (area, prod, int(grado))
        self.market_conditions[key] = {
            'precio': precio_fijo,
            'demanda': demanda_maxima
        }
        if producir_grado != -1: 
            self.production_grade_map[(area, prod)] = int(producir_grado)

    def set_strategy_costs(self, coste_publicidad=0, coste_ID=0, coste_informes=0):
        self.coste_publicidad_total = coste_publicidad
        self.coste_ID_total = coste_ID
        self.coste_informes_total = coste_informes

    def build_model(self):
        
        # --- Variables ---
        for area in AREAS:
            for prod in ['X', 'Y']:
                cap = CAP_MAX[area][prod]
                self.variables[f'prod_{area}_{prod}'] = pulp.LpVariable(f'prod_{area}_{prod}', lowBound=0, upBound=cap, cat='Integer')
                self.variables[f'open_{area}_{prod}'] = pulp.LpVariable(f'open_{area}_{prod}', cat='Binary')
                for g in [0, 1]:
                    self.variables[f'ventas_{area}_{prod}_{g}'] = pulp.LpVariable(f'ventas_{area}_{prod}_{g}', lowBound=0, cat='Integer')
                    self.variables[f'inv_final_{area}_{prod}_{g}'] = pulp.LpVariable(f'inv_final_{area}_{prod}_{g}', lowBound=0, cat='Integer')

        # --- Restricciones ---
        ingreso_terms = []
        coste_variable_terms = []
        coste_fijo_terms = []
        inventario_final_terms = []
        coste_almacen_terms = [] 
        
        inv_actual_dict = self.current_state.get('inventarios_detalle', {})
        
        # --- Bucle por ÁREA para manejar la dependencia X -> Y ---
        for area in AREAS:
            
            # --- Definir variables de producto (X e Y) ---
            prod_X_var = self.variables[f'prod_{area}_X']
            open_X_var = self.variables[f'open_{area}_X']
            
            prod_Y_var = self.variables[f'prod_{area}_Y']
            open_Y_var = self.variables[f'open_{area}_Y']

            # --- Costes y 'Big M' (aplicable a ambos) ---
            for prod, prod_var, open_var in [('X', prod_X_var, open_X_var), ('Y', prod_Y_var, open_Y_var)]:
                cap = CAP_MAX[area][prod]
                self.model += prod_var <= cap * open_var
                self.model += prod_var >= 10 * open_var # Producción mínima si está abierta
                
                coste_fijo_terms.append(COSTE_FIJO[area][prod][0] * open_var)
                precio_tipico = PRECIOS_TIPICOS[area][prod]
                vc_rate = 0.155 if prod == 'X' else 0.30
                coste_variable_terms.append((precio_tipico * vc_rate) * prod_var)

            # --- Lógica de Flujo de Inventario de CHIPS (X) ---
            grado_a_producir_X = self.production_grade_map.get((area, 'X'), -1)
            prod_X_std = prod_X_var if grado_a_producir_X == 0 else 0
            prod_X_lujo = prod_X_var if grado_a_producir_X == 1 else 0

            inv_X_actual_std = inv_actual_dict.get((area, 'X', 0), 0)
            ventas_X_std = self.variables[f'ventas_{area}_X_0']
            inv_final_X_std = self.variables[f'inv_final_{area}_X_0']
            
            inv_X_actual_lujo = inv_actual_dict.get((area, 'X', 1), 0)
            ventas_X_lujo = self.variables[f'ventas_{area}_X_1']
            inv_final_X_lujo = self.variables[f'inv_final_{area}_X_1']

            # Restricciones de venta de X (no puedes vender más de lo que tienes/produces)
            self.model += ventas_X_std <= inv_X_actual_std + prod_X_std
            self.model += ventas_X_lujo <= inv_X_actual_lujo + prod_X_lujo
            
            # --- Lógica de Flujo de Inventario de PCs (Y) ---
            grado_a_producir_Y = self.production_grade_map.get((area, 'Y'), -1)
            prod_Y_std = prod_Y_var if grado_a_producir_Y == 0 else 0
            prod_Y_lujo = prod_Y_var if grado_a_producir_Y == 1 else 0

            inv_Y_actual_std = inv_actual_dict.get((area, 'Y', 0), 0)
            ventas_Y_std = self.variables[f'ventas_{area}_Y_0']
            inv_final_Y_std = self.variables[f'inv_final_{area}_Y_0']
            
            inv_Y_actual_lujo = inv_actual_dict.get((area, 'Y', 1), 0)
            ventas_Y_lujo = self.variables[f'ventas_{area}_Y_1']
            inv_final_Y_lujo = self.variables[f'inv_final_{area}_Y_1']
            
            # Restricciones de venta de Y
            self.model += ventas_Y_std <= inv_Y_actual_std + prod_Y_std
            self.model += ventas_Y_lujo <= inv_Y_actual_lujo + prod_Y_lujo
            
            # --- Lógica de Consumo (La restricción clave) ---
            # Asumir que 1 PC (Y) requiere 1 Chip (X) [cite: 742-743, 957-959, 1033-1035]
            chips_necesarios_para_Y = prod_Y_var
            
            # Chips disponibles para la producción de Y (Stock + Prod - Ventas)
            chips_disponibles_para_Y = (inv_X_actual_std + prod_X_std - ventas_X_std) + \
                                       (inv_X_actual_lujo + prod_X_lujo - ventas_X_lujo)
            
            # **RESTRICCIÓN DE CONSUMO**
            self.model += chips_necesarios_para_Y <= chips_disponibles_para_Y
            
            # --- Inventarios Finales y Costes de Almacén ---
            
            # Inventario Final de X (se reduce por las ventas de X Y la producción de Y)
            self.model += inv_final_X_std + inv_final_X_lujo == chips_disponibles_para_Y - chips_necesarios_para_Y
            
            # Inventario Final de Y (se reduce solo por las ventas de Y)
            self.model += inv_final_Y_std == inv_Y_actual_std + prod_Y_std - ventas_Y_std
            self.model += inv_final_Y_lujo == inv_Y_actual_lujo + prod_Y_lujo - ventas_Y_lujo
            
            # Añadir costes de almacén e ingresos para los 4 productos (X_std, X_lujo, Y_std, Y_lujo)
            for key, inv_final_var in [
                ((area, 'X', 0), inv_final_X_std),
                ((area, 'X', 1), inv_final_X_lujo),
                ((area, 'Y', 0), inv_final_Y_std),
                ((area, 'Y', 1), inv_final_Y_lujo)
            ]:
                inventario_final_terms.append(inv_final_var)
                coste_almacen_terms.append(inv_final_var * ALMACEN_MIN[key[0]][key[1]])
                
                cond = self.market_conditions.get(key)
                if cond:
                    ingreso_terms.append(cond['precio'] * self.variables[f'ventas_{key[0]}_{key[1]}_{key[2]}'])
                    # Forzar a que la venta no supere la demanda
                    self.model += self.variables[f'ventas_{key[0]}_{key[1]}_{key[2]}'] <= cond['demanda']
                else:
                    # Si no es un mercado activo en esta estrategia, no se vende
                    self.model += self.variables[f'ventas_{key[0]}_{key[1]}_{key[2]}'] == 0


        # --- Función Objetivo (Ranking) ---
        ingreso_total_periodo = pulp.lpSum(ingreso_terms)
        coste_variable_total = pulp.lpSum(coste_variable_terms)
        coste_fijo_total = pulp.lpSum(coste_fijo_terms)
        coste_almacen_total = pulp.lpSum(coste_almacen_terms)
        penalizacion_inactividad = pulp.lpSum([1 - self.variables[f'open_{area}_{prod}'] for area in AREAS for prod in ['X','Y']]) * 1000

        beneficio_periodo = (
            ingreso_total_periodo 
            - coste_variable_total 
            - coste_fijo_total 
            - coste_almacen_total
            - self.coste_publicidad_total
            - self.coste_ID_total
            - self.coste_informes_total
            - penalizacion_inactividad
        )
        
        liquidez_periodo = beneficio_periodo * 0.5 
        cuota_periodo = ingreso_total_periodo * 0.01
        inventarios_total_final = pulp.lpSum(inventario_final_terms)

        beneficio_total_estimado = self.current_state.get('beneficio', 0) + beneficio_periodo
        liquidez_total_estimada = self.current_state.get('liquidez', 0) + liquidez_periodo
        cuota_total_estimada = self.current_state.get('cuota', 0) + cuota_periodo
        
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
        if self.model.objective:
            return self.model.objective.value()
        return -float('inf')

    def estimate_next_period(self, solution, market_conditions):
        print("\nEstimación del siguiente periodo si aplicamos decisiones:")
        
        ingreso_estimado = 0
        inv_final_total = 0
        for k, v in solution.items():
            if k.startswith('ventas_'):
                parts = k.split('_')
                key = (parts[1], parts[2], int(parts[3]))
                precio_fijo = market_conditions.get(key, {}).get('precio', 0)
                ingreso_estimado += precio_fijo * v
            
            if k.startswith('inv_final_'):
                inv_final_total += v

        print(f"Ingreso estimado (solo ventas): {ingreso_estimado:.2f}")
        print(f"Inventario final total estimado: {inv_final_total:.0f}")