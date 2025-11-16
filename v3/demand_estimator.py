import numpy as np

# Mapeo de columnas de Asesoría 28 a claves
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
            if not data: continue
            
            precios_mercado = data.get('mercado_precios', {})
            ventas_totales_producto = data.get('mercado_ventas_totales', [0]*6)
            
            # CORRECCIÓN: Iterar por GRADO (clave de COL_MAP)
            for mercado_key_grado, col_precio in COL_MAP.items():
                area, prod, grado = mercado_key_grado
                
                if mercado_key_grado not in datos:
                    datos[mercado_key_grado] = {'precios_avg': [], 'ventas_total_grado': []}

                # 1. Calcular Precio Promedio del Mercado PARA ESE GRADO
                precios_periodo_grado = []
                for cia, precios in precios_mercado.items():
                    if precios[col_precio] > 0:
                        precios_periodo_grado.append(precios[col_precio])
                
                if not precios_periodo_grado:
                    continue # Nadie vendió este grado este periodo

                precio_promedio_grado = sum(precios_periodo_grado) / len(precios_periodo_grado)
                
                # 2. Obtener Ventas Totales del PRODUCTO (de Asesoria 3)
                col_ventas = VENTAS_MAP.get((area, prod))
                ventas_total_prod = ventas_totales_producto[col_ventas]
                
                # 3. Asumir que la venta del grado es proporcional al nro de vendedores
                # (Esta es una proxy simple. Idealmente, Asesoria 17 daría esta info)
                # Por ahora, asignamos la venta total del producto a ambos grados
                # para ver si encontramos una correlación.
                ventas_proxy = ventas_total_prod 
                
                if precio_promedio_grado > 0 and ventas_proxy > 0:
                    datos[mercado_key_grado]['precios_avg'].append(precio_promedio_grado)
                    datos[mercado_key_grado]['ventas_total_grado'].append(ventas_proxy)
                    
        return datos

    def _entrenar_modelos(self):
        modelos = {}
        for mercado_key_grado, data in self.datos_mercado.items():
            
            if len(data['precios_avg']) >= 3 and np.var(data['precios_avg']) > 0:
                try:
                    # m = pendiente, b = intersección
                    m, b = np.polyfit(data['precios_avg'], data['ventas_total_grado'], 1)
                    if m < 0: # Solo guardar si la pendiente es negativa
                        modelos[mercado_key_grado] = {'pendiente': m, 'interseccion': b, 'puntos_datos': len(data['precios_avg'])}
                except np.linalg.LinAlgError:
                    pass
        return modelos

    def get_demand_function(self, area, prod, grado):
        key = (area, prod, int(grado))
        
        # Modelo por defecto si no hay datos suficientes
        default_model = {'pendiente': -100.0, 'interseccion': 50000, 'puntos_datos': 0}
        
        # Si no hay modelo para el grado, probar el grado opuesto
        if key not in self.modelos_demanda:
            grado_opuesto = 1 - int(grado)
            key_opuesto = (area, prod, grado_opuesto)
            return self.modelos_demanda.get(key_opuesto, default_model)
            
        return self.modelos_demanda.get(key, default_model)