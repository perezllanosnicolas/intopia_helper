
from src.params import AREAS, PRECIOS_TIPICOS, SALTO_MIN, TOPE_BR_Y_LE3, CAP_MAX
from src.demand import DemandModel

from v3.ranking import calculate_ranking

class Negotiation:
    def evaluate_offer(self, offer, current_state):
        # Simula impacto en ranking si se acepta
        new_state = current_state.copy()
        new_state.update(offer)
        score = calculate_ranking(new_state)
        return score

    def generate_counteroffer(self, offer, current_state):
        # Ajusta precio y volumen para mejorar ranking
        counter = offer.copy()
        counter['price'] *= 1.05  # ejemplo: subir precio 5%
        counter['volume'] *= 0.9  # reducir volumen
        return counter

    def propose_commercial_pact(self, current_state):
        # Decide si conviene pacto y devuelve parámetros óptimos
        return {'price': 120, 'volume': 1000, 'conditions': 'Pago anticipado'}
