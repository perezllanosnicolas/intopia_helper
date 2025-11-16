# En un nuevo archivo: v3/demand_estimator.py
import numpy as np

class DemandEstimator:
    def __init__(self, historicos_parseados):
        # historicos_parseados es una lista de los datos de parser.py de P1, P2, P3, P4...
        self.datos_mercado = self._extraer_datos(historicos_parseados)
        self.modelos_demanda = self._entrenar_modelos()

    def _extraer_datos(self, historicos):
        # Aquí va la lógica para extraer precios y ventas de las Asesorías
        # ...
        # Devuelve algo como:
        # {'EU-CHIP': {'precios': [40, 42, 39], 'ventas': [15000, 14000, 16000]}}
        return {} # Rellenar esto

    def _entrenar_modelos(self):
        modelos = {}
        for mercado, data in self.datos_mercado.items():
            if len(data['precios']) > 1:
                # Usar regresión lineal de Numpy (grado 1)
                # m = pendiente (elasticidad), b = intersección
                m, b = np.polyfit(data['precios'], data['ventas'], 1)
                modelos[mercado] = {'elasticidad': -m, 'interseccion': b}
        return modelos

    def get_demand_function(self, area, prod, grado):
        # Devuelve la elasticidad y la intersección para ese mercado
        mercado_id = f"{area}-{prod}-{grado}" # O la clave que uses
        return self.modelos_demanda.get(mercado_id, {'elasticidad': 0, 'interseccion': 0})