import numpy as np

# Mapeo de columnas de Asesoría 28 a claves
# (STD, DEL, STD, DEL, STD, DEL, STD, DEL, STD, DEL, STD, DEL)
# (CHIP US, PC US, CHIP EU, PC EU, CHIP BR, PC BR)
COL_MAP = {
    ('US', 'X', 0): 0, ('US', 'X', 1): 1,
    ('US', 'Y', 0): 2, ('US', 'Y', 1): 3,
    ('EU', 'X', 0): 4, ('EU', 'X', 1): 5,
    ('EU', 'Y', 0): 6, ('EU', 'Y', 1): 7,
    ('BR', 'X', 0): 8, ('BR', 'X', 1): 9,
    ('BR', 'Y', 0): 10, ('BR', 'Y', 1): 11,
}
# Mapeo de Asesoría 3 (Ventas Totales)
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
            if not data: continue # Omitir si el parser falló
            
            precios_mercado = data.get('mercado_precios', {})
            ventas_totales = data.get('mercado_ventas_totales', [0]*6)
            
            # Iterar sobre los mercados que nos interesan (EU-X, US-Y, etc.)
            for (area, prod), col_idx in VENTAS_MAP.items():
                mercado_key = (area, prod) # Clave simplificada: ('EU', 'X')
                
                if mercado_key not in datos:
                    datos[mercado_key] = {'precios_avg': [], 'ventas_total': []}

                # 1. Calcular Precio Promedio del Mercado
                precios_periodo = []
                # (Usamos el grado 0 y 1 para el precio promedio del producto)
                for grado in [0, 1]:
                    col_precio = COL_MAP.get((area, prod, grado))
                    if col_precio is None: continue
                    
                    for cia, precios in precios_mercado.items():
                        if precios[col_precio] > 0:
                            precios_periodo.append(precios[col_precio])
                
                if not precios_periodo:
                    continue # Nadie vendió en este mercado este periodo

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
            if len(data['precios_avg']) > 1: # Necesitamos 2+ puntos de datos
                try:
                    m, b = np.polyfit(data['precios_avg'], data['ventas_total'], 1)
                    if m < 0: # Solo guardar si la pendiente es negativa
                        modelos[mercado] = {'pendiente': m, 'interseccion': b, 'puntos_datos': len(data['precios_avg'])}
                except np.linalg.LinAlgError:
                    pass
        return modelos

    def get_demand_function(self, area, prod):
        key = (area, prod)
        # Modelo por defecto si no hay datos
        default_model = {'pendiente': -100.0, 'interseccion': 50000, 'puntos_datos': 0}
        return self.modelos_demanda.get(key, default_model)