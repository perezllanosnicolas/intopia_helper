import pulp
from src.params import AREAS, PRECIOS_TIPICOS, SALTO_MIN, TOPE_BR_Y_LE3, CAP_MAX, ALMACEN_MIN, COSTE_FIJO

class OptimizerV3:
    def __init__(self, current_state, scenario='hybrid'):
        self.scenario = scenario
        self.current_state = current_state  # Diccionario con datos actuales
        self.model = pulp.LpProblem('RankingOptimization', pulp.LpMaximize)
        self.variables = {}

    def build_model(self):
        # --- Variables (Sin cambios) ---
        for area in AREAS:
            for prod in ['X', 'Y']:
                for g in [0, 1]:
                    price_var = f'price_{area}_{prod}_{g}'
                    self.variables[price_var] = pulp.LpVariable(price_var, lowBound=SALTO_MIN[area][prod], cat='Integer')
                    ad_var = f'ad_{area}_{prod}_{g}'
                    self.variables[ad_var] = pulp.LpVariable(ad_var, lowBound=0, cat='Continuous')

        for area in AREAS:
            for prod in ['X', 'Y']:
                cap = CAP_MAX[area][prod]
                prod_var = f'prod_{area}_{prod}'
                self.variables[prod_var] = pulp.LpVariable(prod_var, lowBound=0, upBound=cap, cat='Integer')
                open_var = f'open_{area}_{prod}'
                self.variables[open_var] = pulp.LpVariable(open_var, cat='Binary')

        for area in AREAS:
            inv_var = f'inv_{area}'
            self.variables[inv_var] = pulp.LpVariable(inv_var, lowBound=0, cat='Integer')

        # --- Restricciones ---
        for g in [0, 1]:
            self.model += self.variables[f'price_BR_Y_{g}'] <= TOPE_BR_Y_LE3

        for area in AREAS:
            for prod in ['X', 'Y']:
                cap = CAP_MAX[area][prod] # Obtenemos la capacidad máxima
                
                # Restricción 1: Producción mínima si planta está abierta
                self.model += self.variables[f'prod_{area}_{prod}'] >= 10 * self.variables[f'open_{area}_{prod}']
                
                # *** CORRECCIÓN "BIG M" AÑADIDA AQUÍ ***
                # Restricción 2: Si produces (prod > 0), la planta DEBE estar abierta (open = 1)
                # Si open_var es 0, prod_var se ve forzado a ser 0.
                # Si open_var es 1, prod_var puede ser hasta 'cap'.
                self.model += self.variables[f'prod_{area}_{prod}'] <= cap * self.variables[f'open_{area}_{prod}']


        # --- Función Objetivo (Lógica de costes corregida) ---
        
        # 1. Calcular Ingresos y Costes Variables del periodo
        beneficio_terms = []
        coste_variable_terms = []
        
        for area in AREAS:
            for prod in ['X', 'Y']:
                prod_var = self.variables[f'prod_{area}_{prod}']
                precio_tipico = PRECIOS_TIPICOS[area][prod]
                
                ingreso = precio_tipico * prod_var
                beneficio_terms.append(ingreso)

                # Proxy de Coste Variable (basado en el manual)
                vc_rate = 0.155 if prod == 'X' else 0.30
                coste_variable = (precio_tipico * vc_rate) * prod_var
                coste_variable_terms.append(coste_variable)
        
        coste_variable_total = pulp.lpSum(coste_variable_terms)
        ingreso_total_periodo = pulp.lpSum(beneficio_terms)

        # 2. Calcular Costes Fijos del periodo (ahora se activarán correctamente)
        coste_fijo_terms = []
        for area in AREAS:
            for prod in ['X', 'Y']:
                costo_primera_planta = COSTE_FIJO[area][prod][0]
                coste_fijo_terms.append(costo_primera_planta * self.variables[f'open_{area}_{prod}'])
        
        coste_fijo_total = pulp.lpSum(coste_fijo_terms)
        
        # 3. Ligar Inventario Final a Inventario Actual
        # (Este modelo simple asume que vendemos todo y el inventario final es el actual)
        inventario_final_terms = []
        for area in AREAS:
            inv_var = self.variables[f'inv_{area}']
            current_inv_area = self.current_state.get('inventarios', {}).get(area, 0)
            self.model += inv_var == current_inv_area # Constraint: Final Inv = Current Inv
            inventario_final_terms.append(inv_var)
            
        inventarios_total_final = pulp.lpSum(inventario_final_terms)
        
        # 4. Calcular deltas del periodo
        penalizacion_inactividad = pulp.lpSum([1 - self.variables[f'open_{area}_{prod}'] for area in AREAS for prod in ['X','Y']]) * 1000

        beneficio_periodo = ingreso_total_periodo - coste_variable_total - coste_fijo_total - penalizacion_inactividad
        liquidez_periodo = beneficio_periodo * 0.5 # Proxy
        cuota_periodo = ingreso_total_periodo * 0.01 # Proxy

        # 5. Sumar deltas al estado actual para el ranking final
        beneficio_total_estimado = self.current_state.get('beneficio', 0) + beneficio_periodo
        liquidez_total_estimada = self.current_state.get('liquidez', 0) + liquidez_periodo
        cuota_total_estimada = self.current_state.get('cuota', 0) + cuota_periodo
        
        # 6. Aplicar la fórmula del ranking
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
        # CORRECCIÓN: Devolver TODAS las variables que no sean cero
        for v in self.model.variables():
            if v.value() is not None and v.value() != 0:
                solution[v.name] = v.value()
        return solution

    def summarize_current_state(self):
        print("Resumen del estado actual:")
        self.current_state['inventarios_total'] = sum(self.current_state.get('inventarios', {}).values())
        for k, v in self.current_state.items():
            print(f"{k}: {v}")

    def estimate_next_period(self, solution):
        print("\nEstimación del siguiente periodo si aplicamos decisiones:")
        beneficio_estimado = sum([PRECIOS_TIPICOS[a][p] * solution.get(f'prod_{a}_{p}', 0) for a in AREAS for p in ['X','Y']])
        print(f"Beneficio estimado (solo ingresos): {beneficio_estimado:.2f}")
        
        inv_list = [self.current_state.get('inventarios', {}).get(a, 0) for a in AREAS]
        print(f"Inventarios esperados (US, EU, BR): {inv_list}")