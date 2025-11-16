import numpy as np

# Mapeo de columnas de Asesoría 28 a claves
# (STD, DEL, STD, DEL, STD, DEL, STD, DEL, STD, DEL, STD, DEL)
# (CHIP US, PC US, CHIP EU, PC EU, CHIP BR, PC BR)
COL_MAP = {
    ('US', 'X', 0): 0,  # US-CHIP-STD
    ('US', 'X', 1): 1,  # US-CHIP-DEL
    ('US', 'Y', 0): 2,  # US-PC-STD
    ('US', 'Y', 1): 3,  # US-PC-DEL
    ('EU', 'X', 0): 4,  # EU-CHIP-STD
    ('EU', 'X', 1): 5,  # EU-CHIP-DEL
    ('EU', 'Y', 0): 6,  # EU-PC-STD
    ('EU', 'Y', 1): 7,  # EU-PC-DEL
    ('BR', 'X', 0): 8,  # BR-CHIP-STD
    ('BR', 'X', 1): 9,  # BR-CHIP-DEL
    ('BR', 'Y', 0): 10, # BR-PC-STD
    ('BR', 'Y', 1): 11, # BR-PC-DEL
}
# Mapeo de Asesoría 3
VENTAS_MAP = {
    ('US', 'X'): 0,
    ('US', 'Y'): 1,
    ('EU', 'X'): 2,
    ('EU', 'Y'): 3,
    ('BR', 'X'): 4,
    ('BR', 'Y'): 5,
}

class DemandEstimator:
    def __init__(self, historicos_parseados):
        self.datos_mercado = self._extraer_datos(historicos_parseados)
        self.modelos_demanda = self._entrenar_modelos()

    def _extraer_datos(self, historicos):
        datos = {}
        # Itera sobre todos los archivos LST parseados
        for i, data in enumerate(historicos):
            periodo = i + 1
            
            # Extraer precios de la Compañía 4 (nuestra compañía)
            precios_cia_4 = data.get('mercado_precios', {}).get('COMPA¥IA  4', [0]*12)
            # Extraer ventas de la Compañía 4
            ventas_cia_4 = data.get('ventas_propias', {})
            # Extraer ventas totales del mercado (Asesoría 3)
            ventas_totales = data.get('mercado_ventas_totales', [0]*6)

            for (area, prod, grado), col_idx in COL_MAP.items():
                mercado_key = (area, prod, grado)
                
                if mercado_key not in datos:
                    datos[mercado_key] = {'precios': [], 'ventas': []}

                precio = precios_cia_4[col_idx]
                # Las ventas propias vienen por (area, prod, grado), ej: ('EU', 'X', 1)
                ventas = ventas_cia_4.get(mercado_key, 0)
                
                # Solo usamos el dato si la compañía vendió (o intentó vender)
                # O si queremos modelar el mercado total (más complejo)
                # Por ahora, modelamos NUESTRAS ventas vs NUESTRO precio
                if precio > 0:
                    datos[mercado_key]['precios'].append(precio)
                    datos[mercado_key]['ventas'].append(ventas)
                    
        return datos

    def _entrenar_modelos(self):
        modelos = {}
        for mercado, data in self.datos_mercado.items():
            # Necesitamos al menos 2 puntos de datos para una regresión lineal
            if len(data['precios']) > 1:
                try:
                    # m = pendiente (elasticidad), b = intersección
                    # np.polyfit(X, Y, grado)
                    m, b = np.polyfit(data['precios'], data['ventas'], 1)
                    
                    # Solo guardamos modelos con pendiente negativa (ley de demanda)
                    if m < 0:
                        modelos[mercado] = {'pendiente': m, 'interseccion': b, 'puntos_datos': len(data['precios'])}
                except np.linalg.LinAlgError:
                    pass # Error de regresión
        return modelos

    def get_demand_function(self, area, prod, grado):
        key = (area, prod, int(grado))
        # Devuelve el modelo aprendido, o un modelo por defecto si no hay datos
        default_model = {'pendiente': -1.0, 'interseccion': 5000, 'puntos_datos': 0}
        
        # Ejemplo: Si no tenemos datos para 'EU-X-1', usamos los de 'EU-X-0'
        if key not in self.modelos_demanda and grado == 1:
            key_std = (area, prod, 0)
            return self.modelos_demanda.get(key_std, default_model)
            
        return self.modelos_demanda.get(key, default_model)