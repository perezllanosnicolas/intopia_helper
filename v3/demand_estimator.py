import numpy as np

# Mapeos (sin cambios)
COL_MAP = {
    ('US', 'X', 0): 0, ('US', 'X', 1): 1,
    ('US', 'Y', 0): 2, ('US', 'Y', 1): 3,
    ('EU', 'X', 0): 4, ('EU', 'X', 1): 5,
    ('EU', 'Y', 0): 6, ('EU', 'Y', 1): 7,
    ('BR', 'X', 0): 8, ('BR', 'X', 1): 9,
    ('BR', 'Y', 0): 10, ('BR', 'Y', 1): 11,
}
VENTAS_MAP = {
    ('US', 'X'): 0, ('US', 'Y'): 1,
    ('EU', 'X'): 2, ('EU', 'Y'): 3,
    ('BR', 'X'): 4, ('BR', 'Y'): 5,
}

class DemandEstimator:
    def __init__(self, historicos_parseados):
        self.datos_mercado = self._extraer_datos(historicos_parseados)
        self.modelos_demanda = self._entrenar_modelos()

    def _extraer_datos(self, historicos):
        datos = {}
        
        for i, data in enumerate(historicos):
            if not data: continue
            
            precios_mercado = data.get('mercado_precios', {})
            ventas_totales = data.get('mercado_ventas_totales', [0]*6)
            
            for (area, prod), col_idx in VENTAS_MAP.items():
                mercado_key = (area, prod)
                
                if mercado_key not in datos:
                    datos[mercado_key] = {'precios_avg': [], 'ventas_total': []}

                # 1. Calcular Precio Promedio del Mercado
                precios_periodo = []
                for grado in [0, 1]:
                    col_precio = COL_MAP.get((area, prod, grado))
                    if col_precio is None: continue
                    
                    for cia, precios in precios_mercado.items():
                        if precios[col_precio] > 0:
                            precios_periodo.append(precios[col_precio])
                
                if not precios_periodo:
                    continue

                precio_promedio = sum(precios_periodo) / len(precios_periodo)
                
                # 2. Obtener Ventas Totales del Mercado
                ventas_total = ventas_totales[col_idx]
                
                if precio_promedio > 0 and ventas_total > 0:
                    datos[mercado_key]['precios_avg'].append(precio_promedio)
                    datos[mercado_key]['ventas_total'].append(ventas_total)
                    
        return datos

    def _entrenar_modelos(self):
        modelos = {}
        for mercado, data in self.datos_mercado.items():
            # CORRECCIÓN: Requerir 3 puntos de datos para una regresión más estable
            # y comprobar que los precios no sean todos iguales (varianza > 0)
            if len(data['precios_avg']) >= 3 and np.var(data['precios_avg']) > 0:
                try:
                    m, b = np.polyfit(data['precios_avg'], data['ventas_total'], 1)
                    if m < 0: 
                        modelos[mercado] = {'pendiente': m, 'interseccion': b, 'puntos_datos': len(data['precios_avg'])}
                except np.linalg.LinAlgError:
                    pass # Fallo en la regresión
        return modelos

    def get_demand_function(self, area, prod):
        key = (area, prod)
        # Modelo por defecto si no hay datos suficientes
        default_model = {'pendiente': -100.0, 'interseccion': 50000, 'puntos_datos': 0}
        return self.modelos_demanda.get(key, default_model)