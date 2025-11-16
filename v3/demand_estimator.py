import numpy as np

# Mapeo de columnas de Asesoría 28 (Precios)
COL_MAP = {
    ('US', 'X', 0): 0, ('US', 'X', 1): 1,
    ('US', 'Y', 0): 2, ('US', 'Y', 1): 3,
    ('EU', 'X', 0): 4, ('EU', 'X', 1): 5,
    ('EU', 'Y', 0): 6, ('EU', 'Y', 1): 7,
    ('BR', 'X', 0): 8, ('BR', 'X', 1): 9,
    ('BR', 'Y', 0): 10, ('BR', 'Y', 1): 11,
}
# Mapeo de Asesoría 3 (Ventas Totales del Producto)
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
            
            precios_mercado_periodo = data.get('mercado_precios', {})
            ventas_totales_producto_periodo = data.get('mercado_ventas_totales', [0]*6)
            
            # Iterar por CADA GRADO (ej. 'EU', 'X', 0)
            for mercado_key_grado, col_precio in COL_MAP.items():
                area, prod, grado = mercado_key_grado
                
                if mercado_key_grado not in datos:
                    datos[mercado_key_grado] = {'precios_avg': [], 'ventas_total_proxy': []}

                # 1. Calcular Precio Promedio del Mercado PARA ESE GRADO
                precios_periodo_grado = []
                for cia, precios in precios_mercado_periodo.items():
                    if len(precios) == 12 and precios[col_precio] > 0: # Asegurarse que la lista de precios está completa
                        precios_periodo_grado.append(precios[col_precio])
                
                if not precios_periodo_grado:
                    continue # Nadie vendió este grado en este periodo

                precio_promedio_grado = sum(precios_periodo_grado) / len(precios_periodo_grado)
                
                # 2. Obtener Ventas Totales del PRODUCTO (de Asesoria 3)
                col_ventas = VENTAS_MAP.get((area, prod))
                if col_ventas is None: continue
                
                ventas_total_prod = ventas_totales_producto_periodo[col_ventas]
                
                # 3. Usar Ventas Totales del Producto como proxy para la demanda de este grado
                #    (Es una simplificación, pero mejor que nada)
                if precio_promedio_grado > 0 and ventas_total_prod > 0:
                    datos[mercado_key_grado]['precios_avg'].append(precio_promedio_grado)
                    datos[mercado_key_grado]['ventas_total_proxy'].append(ventas_total_prod)
                    
        return datos

    def _entrenar_modelos(self):
        modelos = {}
        for mercado_key_grado, data in self.datos_mercado.items():
            
            # CORRECCIÓN: Bajar a 2 puntos de datos si la varianza es > 0
            if len(data['precios_avg']) >= 2 and np.var(data['precios_avg']) > 0:
                try:
                    m, b = np.polyfit(data['precios_avg'], data['ventas_total_proxy'], 1)
                    if m < 0: # Solo guardar si la pendiente es negativa
                        modelos[mercado_key_grado] = {'pendiente': m, 'interseccion': b, 'puntos_datos': len(data['precios_avg'])}
                except np.linalg.LinAlgError:
                    pass
        return modelos

    def get_demand_function(self, area, prod, grado):
        key = (area, prod, int(grado))
        default_model = {'pendiente': -100.0, 'interseccion': 50000, 'puntos_datos': 0}
        
        modelo_encontrado = self.modelos_demanda.get(key)
        
        if modelo_encontrado:
            return modelo_encontrado
        else:
            # Si no hay modelo para este grado, probar el grado opuesto
            grado_opuesto = 1 - int(grado)
            key_opuesto = (area, prod, grado_opuesto)
            return self.modelos_demanda.get(key_opuesto, default_model)