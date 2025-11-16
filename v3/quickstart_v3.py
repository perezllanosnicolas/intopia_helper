import os
from v3.optimizer_pulp import OptimizerV3
from v3.negotiation import Negotiation
from v3.ranking import calculate_ranking
from src.parser import LSTParser

# Ruta de la carpeta data
DATA_DIR = os.path.join(os.getcwd(), 'data')

# Identificar la última decisión (mayor número)
files = [f for f in os.listdir(DATA_DIR) if f.lower().startswith('decisión')]
last_file = sorted(files, key=lambda x: int(x.split()[1].split('.')[0]))[-1]
file_path = os.path.join(DATA_DIR, last_file)

print(f"Última decisión detectada: {last_file}")

# Parsear archivo LST
parser = LSTParser()
parsed_data = parser.parse_file(file_path)

# Extraer datos clave para current_state
# Si parser.py no tiene estas claves, deberás extenderlo para obtenerlas
beneficio = parsed_data.get('utilidad_periodo', 0)
caja_total = parsed_data.get('caja_total', 0)
inventarios = parsed_data.get('inventarios', {'US': 0, 'EU': 0, 'BR': 0})
cuota = parsed_data.get('cuota_mercado', 0)

current_state = {
    'beneficio': beneficio,
    'liquidez': caja_total,
    'inventarios': inventarios,
    'cuota': cuota
}

# Ejecutar optimizador
optimizer = OptimizerV3(current_state=current_state)
optimizer.summarize_current_state()
optimizer.build_model()
solution = optimizer.solve()

print("\nSolución óptima:")
for k, v in solution.items():
    print(f"{k}: {v}")

optimizer.estimate_next_period(solution)

# Simular negociación
negotiation = Negotiation()
offer = {'price': 100, 'volume': 1200}
score = negotiation.evaluate_offer(offer, current_state)
print("\nRanking si se acepta oferta:", score)
counter = negotiation.generate_counteroffer(offer, current_state)
print("Contraoferta:", counter)
pact = negotiation.propose_commercial_pact(current_state)
print("Propuesta de pacto:", pact)