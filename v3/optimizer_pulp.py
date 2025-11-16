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
        # Nuevos: Costes fijos de la estrategia
        self.coste_publicidad_total = 0
        self.coste_ID_total = 0
        self.coste_informes_total = 0

    def set_market_conditions(self, area, prod, grado, precio_fijo, demanda_maxima, producir_grado):
        key = (area, prod, int(grado))
        self.market_conditions[key] = {
            'precio': precio_fijo,
            'demanda': demanda_maxima
        }
        # Guardamos qué grado se va a producir
        if producir_grado != -1: # -1 significa no producir
            self.production_grade_map[(area, prod)] = int(producir_grado)

    def set_strategy_costs(self, coste_publicidad=0, coste_ID=0, coste_informes=0):
        # Recibe los costes de la estrategia (Formulario H1 y A1)
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

        for area in AREAS:
            for prod in ['X', 'Y']:
                prod_var = self.variables[f'prod_{area}_{prod}']
                open_var = self.variables[f'open_{area}_{prod}']
                cap = CAP_MAX[area][prod]

                self.model += prod_var <= cap * open_var
                self.model += prod_var >= 10 * open_var

                coste_fijo_terms.append(COSTE_FIJO[area][prod][0] * open_var)
                precio_tipico = PRECIOS_TIPICOS[area][prod]
                vc_rate = 0.155 if prod == 'X' else 0.30
                coste_variable_terms.append((precio_tipico * vc_rate) * prod_var)

                grado_a_producir = self.production_grade_map.get((area, prod), -1)
                prod_std = prod_var if grado_a_producir == 0 else 0
                prod_lujo = prod_var if grado_a_producir == 1 else 0

                # Grado 0 (Estándar)
                key_std = (area, prod, 0)
                inv_actual_std = inv_actual_dict.get(key_std, 0)
                ventas_std = self.variables.get(f'ventas_{area}_{prod}_0')
                inv_final_std = self.variables.get(f'inv_final_{area}_{prod}_0')
                
                cond_std = self.market_conditions.get(key_std)
                if ventas_std is not None:
                    if cond_std:
                        self.model += ventas_std <= cond_std['demanda']
                        self.model += ventas_std <= inv_actual_std + prod_std
                        ingreso_terms.append(cond_std['precio'] * ventas_std)
                    else:
                        self.model += ventas_std == 0
                    
                    if inv_final_std is not None:
                        self.model += inv_final_std == inv_actual_std + prod_std - ventas_std
                        inventario_final_terms.append(inv_final_std)
                        coste_almacen_terms.append(inv_final_std * ALMACEN_MIN[area][prod])

                # Grado 1 (Lujo)
                key_lujo = (area, prod, 1)
                inv_actual_lujo = inv_actual_dict.get(key_lujo, 0)
                ventas_lujo = self.variables.get(f'ventas_{area}_{prod}_1')
                inv_final_lujo = self.variables.get(f'inv_final_{area}_{prod}_1')

                cond_lujo = self.market_conditions.get(key_lujo)
                if ventas_lujo is not None:
                    if cond_lujo:
                        self.model += ventas_lujo <= cond_lujo['demanda']
                        self.model += ventas_lujo <= inv_actual_lujo + prod_lujo
                        ingreso_terms.append(cond_lujo['precio'] * ventas_lujo)
                    else:
                        self.model += ventas_lujo == 0
                    
                    if inv_final_lujo is not None:
                        self.model += inv_final_lujo == inv_actual_lujo + prod_lujo - ventas_lujo
                        inventario_final_terms.append(inv_final_lujo)
                        coste_almacen_terms.append(inv_final_lujo * ALMACEN_MIN[area][prod])


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
            - self.coste_publicidad_total  # <-- Coste de Estrategia
            - self.coste_ID_total          # <-- Coste de Estrategia
            - self.coste_informes_total    # <-- Coste de Estrategia
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