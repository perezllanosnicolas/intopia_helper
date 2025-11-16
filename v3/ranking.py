
from src.params import AREAS, PRECIOS_TIPICOS, SALTO_MIN, TOPE_BR_Y_LE3, CAP_MAX
from src.demand import DemandModel


def calculate_ranking(state):
    beneficio = state.get('beneficio', 0)
    liquidez = state.get('liquidez', 0)
    cuota = state.get('cuota', 0)
    inventarios = state.get('inventarios', 0)
    inventarios_total = sum(inventarios.values()) if isinstance(inventarios, dict) else inventarios
    return 0.4*beneficio + 0.3*liquidez + 0.2*cuota + 0.1*inventarios_total
