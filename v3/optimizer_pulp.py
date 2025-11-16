import pulp
from src.params import AREAS, PRECIOS_TIPICOS, SALTO_MIN, TOPE_BR_Y_LE3, CAP_MAX, ALMACEN_MIN, COSTE_FIJO

class OptimizerV3:
    def __init__(self, current_state, scenario='hybrid'):
        self.scenario = scenario
        self.current_state = current_state  # Diccionario con datos actuales
        self.model = pulp.LpProblem('RankingOptimization', pulp.LpMaximize)
        self.variables = {}

    def build_model(self):
        # Variables: precios, publicidad, producción, inventarios, apertura de planta
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
            self.variables[inv_var] = pulp.LpVariable(inv_var, lowBound=ALMACEN_MIN[area]['X'], cat='Integer')

        # Restricciones: tope BR-Y
        for g in [0, 1]:
            self.model += self.variables[f'price_BR_Y_{g}'] <= TOPE_BR_Y_LE3

        # Restricción: producción mínima si planta está abierta
        for area in AREAS:
            for prod in ['X', 'Y']:
                self.model += self.variables[f'prod_{area}_{prod}'] >= 10 * self.variables[f'open_{area}_{prod}']

        # Objetivo: RankingScore aproximado con penalización por inactividad
        beneficio_terms = []
        for area in AREAS:
            for prod in ['X', 'Y']:
                prod_var = self.variables[f'prod_{area}_{prod}']
                ingreso = PRECIOS_TIPICOS[area][prod] * prod_var
                beneficio_terms.append(ingreso)

        coste_fijo_total = pulp.lpSum([sum(vals) for area in COSTE_FIJO.keys() for vals in COSTE_FIJO[area].values()])
        penalizacion_inactividad = pulp.lpSum([1 - self.variables[f'open_{area}_{prod}'] for area in AREAS for prod in ['X','Y']]) * 1000

        beneficio_neto = pulp.lpSum(beneficio_terms) - coste_fijo_total - penalizacion_inactividad

        liquidez = beneficio_neto * 0.5
        cuota = pulp.lpSum(beneficio_terms) * 0.01
        inventarios_score = pulp.lpSum([self.variables[f'inv_{a}'] for a in AREAS]) * 0.001

        ranking_score = 0.4 * beneficio_neto + 0.3 * liquidez + 0.2 * cuota + 0.1 * inventarios_score
        self.model += ranking_score

    def solve(self):
        self.model.solve(pulp.PULP_CBC_CMD(msg=0))
        return {v.name: v.value() for v in self.model.variables()}

    def summarize_current_state(self):
        print("Resumen del estado actual:")
        for k, v in self.current_state.items():
            print(f"{k}: {v}")

    def estimate_next_period(self, solution):
        print("\nEstimación del siguiente periodo si aplicamos decisiones:")
        beneficio_estimado = sum([PRECIOS_TIPICOS[a][p] * solution[f'prod_{a}_{p}'] for a in AREAS for p in ['X','Y']])
        print(f"Beneficio estimado: {beneficio_estimado:.2f}")
        print(f"Inventarios esperados: {[solution[f'inv_{a}'] for a in AREAS]}")