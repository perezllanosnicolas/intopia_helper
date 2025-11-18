import re

class LSTParser:
    def clean_content(self, content):
        """
        Homogeneiza el contenido eliminando encabezados de página repetitivos
        y normalizando espacios y saltos de línea.
        """
        # 1. Eliminar los bloques de encabezado de página que rompen las tablas
        # Busca desde "1... THORELLI" hasta "PAGINA: XXX" y lo borra
        content = re.sub(r'1\s+THORELLI-GRAVES-LOPEZ[\s\S]*?PAGINA:\s+\d+', '', content)
        
        # 2. Eliminar líneas que solo contienen fechas o títulos irrelevantes sueltos
        content = re.sub(r'INTOPIA 2000 --', '', content)
        
        # 3. Unir líneas rotas: Si una línea termina abruptamente con texto y la siguiente sigue con números
        # Esto ayuda cuando "CxP PERIODO" queda en una línea y el "5" en la siguiente.
        # Simplemente reemplazamos múltiples espacios/newlines por un solo espacio para el análisis
        # (Opcional: dependerá de si necesitas mantener estructura de columnas estricta, 
        # pero para regex flexibles es mejor tener todo "plano")
        return content

    def parse_file(self, filepath):
        parsed_data = {}
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                raw_content = f.read()
        except Exception as e:
            print(f"Error al leer el archivo {filepath}: {e}")
            return {}

        # --- PASO DE LIMPIEZA ---
        # Limpiamos el contenido antes de intentar buscar nada
        content = self.clean_content(raw_content)

        # --- Bloque 1: BALANCE ---
        # Buscamos la sección de Activos/Caja. 
        # Al haber limpiado los headers, el bloque es continuo.
        
        # Regex más flexible para CAJA: busca "CAJA" seguido de espacios y toma el último número de la línea
        # El formato suele ser: CAJA [espacios] 0. [espacios] VALOR. [espacios] 0. ...
        # Buscaremos específicamente el valor bajo la columna CONSOLIDADO (generalmente la última o penúltima columna grande)
        # Nota: En tus archivos, la Caja total suele ser el último o penúltimo valor numérico grande en la línea de CAJA.
        
        match_caja_line = re.search(r'CAJA\s+([\d\.\s\-\,]+)', content)
        if match_caja_line:
            # Extraemos todos los números de la línea de caja
            numeros = re.findall(r'(-?\d+)\.', match_caja_line.group(1))
            if numeros:
                # Asumimos que el consolidado es la suma o el valor más relevante (último de la derecha)
                parsed_data['caja_total'] = float(numeros[-1])
            else:
                parsed_data['caja_total'] = 0.0
        else:
            parsed_data['caja_total'] = 0.0

        # --- Bloque 2: ESTADO DE RESULTADOS ---
        # Utilidad del periodo
        match_utilidad = re.search(r'UTILIDAD DEL PERIODO\s+([\d\.\s\-\,]+)', content)
        if match_utilidad:
            numeros = re.findall(r'(-?\d+)\.', match_utilidad.group(1))
            if numeros:
                parsed_data['utilidad_periodo'] = float(numeros[-1])
            else:
                parsed_data['utilidad_periodo'] = 0.0
        else:
            parsed_data['utilidad_periodo'] = 0.0

        # --- Bloque 3: INFORMACION NO CONTABLE ---
        ventas_propias = {}
        inventarios_detalle = {}
        patentes_poseidas = {}
        
        # Extraer bloque limpio
        match_info_block = re.search(r'INFORMACION NO CONTABLE([\s\S]*?)(?:CANTIDAD DE PLANTAS|ANALISIS DE COSTO DE PRODUCCION)', content)
        
        if match_info_block:
            info_block = match_info_block.group(1)
            
            # Función auxiliar para extraer 6 valores de una línea
            def get_six_values(regex_pattern, text):
                match = re.search(regex_pattern, text)
                if match:
                    # Busca todos los números que terminan en punto
                    vals = re.findall(r'(\d+)\.', match.group(0))
                    # A veces captura más números, nos quedamos con los últimos 6 que corresponden a las columnas
                    if len(vals) >= 6:
                        return list(map(int, vals[-6:]))
                return [0]*6

            # 1. Ventas Propias (A Consumidores - Estándar)
            # Buscamos "A CONSUMIDORES" y nos aseguramos de estar en la sección de VENTAS UNIDADES ESTANDAR
            # Usamos un regex que permita saltos de línea entre el texto y los números
            vals_std = get_six_values(r'VENTAS UNIDADES ESTANDAR[\s\S]*?A CONSUMIDORES[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            
            columnas = [('US', 'X', 0), ('US', 'Y', 0), ('EU', 'X', 0), ('EU', 'Y', 0), ('BR', 'X', 0), ('BR', 'Y', 0)]
            for i, val in enumerate(vals_std):
                if val > 0: ventas_propias[columnas[i]] = val

            # 2. Ventas Propias (A Consumidores - Lujo)
            vals_lujo = get_six_values(r'VENTA UNIDADES DE LUJO[\s\S]*?A CONSUMIDORES[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            columnas_lujo = [('US', 'X', 1), ('US', 'Y', 1), ('EU', 'X', 1), ('EU', 'Y', 1), ('BR', 'X', 1), ('BR', 'Y', 1)]
            for i, val in enumerate(vals_lujo):
                if val > 0: ventas_propias[columnas_lujo[i]] = val
            
            parsed_data['ventas_propias'] = ventas_propias

            # 3. Inventarios (Estándar)
            # Nota: La regex original fallaba porque INVENTARIO FINAL a veces está lejos de los números
            vals_inv_std = get_six_values(r'INVENTARIO FINAL[\s\S]*?UNIDADES ESTANDAR[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            for i, val in enumerate(vals_inv_std):
                if val > 0: inventarios_detalle[columnas[i]] = val

            # 4. Inventarios (Lujo)
            vals_inv_lujo = get_six_values(r'INVENTARIO FINAL[\s\S]*?UNIDADES DE LUJO[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            for i, val in enumerate(vals_inv_lujo):
                if val > 0: inventarios_detalle[columnas_lujo[i]] = val
            
            parsed_data['inventarios_detalle'] = inventarios_detalle

            # 5. Patentes
            # Buscamos en todo el contenido porque a veces cae fuera del bloque recortado anteriormente
            match_patentes = re.search(r'MAXIMO GRADO POSEIDO[\s\S]*?(\d+\.[\s\S]*?){6}', content)
            if match_patentes:
                vals = re.findall(r'(\d+)\.', match_patentes.group(0))
                if len(vals) >= 6:
                    g = list(map(int, vals[-6:]))
                    patentes_poseidas[('US', 'X')] = g[0]
                    patentes_poseidas[('US', 'Y')] = g[1]
                    patentes_poseidas[('EU', 'X')] = g[2]
                    patentes_poseidas[('EU', 'Y')] = g[3]
                    patentes_poseidas[('BR', 'X')] = g[4]
                    patentes_poseidas[('BR', 'Y')] = g[5]
            
            parsed_data['patentes_poseidas'] = patentes_poseidas


        # --- Bloque 4: CUOTA DE MERCADO (Asesoría 3) ---
        # Buscamos el bloque específico. Al limpiar headers, es más seguro.
        match_ventas_block = re.search(r'ASESORIA NUMERO 3[\s\S]*?VENTAS TOTALES:([\s\S]*?)COMPA', content)
        if match_ventas_block:
            numeros_raw = match_ventas_block.group(1)
            # Buscamos números decimales (ej: 37.38)
            match_ventas = re.findall(r'(\d*\.\d{2})', numeros_raw)
            
            if match_ventas and len(match_ventas) >= 6:
                # Tomamos los últimos 6 por si acaso capturó basura antes
                vals = [float(v) for v in match_ventas[-6:]]
                parsed_data['cuota_mercado'] = sum(vals)
                parsed_data['mercado_ventas_totales'] = [v * 1000 for v in vals]
            else:
                parsed_data['cuota_mercado'] = 0
                parsed_data['mercado_ventas_totales'] = [0]*6
        
        # --- Bloque 5: PRECIOS DE MERCADO (Asesoría 28) ---
        mercado_precios = {}
        match_precios_block = re.search(r'ASESORIA NUMERO 28([\s\S]*?)(?:ASESORIA NUMERO 17|GRADO DE LAS VENTAS)', content)
        
        if match_precios_block:
            precios_content = match_precios_block.group(1)
            # Regex para capturar línea por línea: COMPAÑIA X ..... numeros
            # Usamos re.finditer para recorrer cada coincidencia
            
            # Normalizamos la palabra COMPA¥IA a COMPAÑIA para uniformidad si hiciera falta, 
            # pero el regex manejará ambos.
            lineas_cias = re.finditer(r'(COMPA[NÑ¥]IA\s+\d+)([\s\S]*?)(?=COMPA[NÑ¥]IA|$)', precios_content)
            
            for match in lineas_cias:
                nombre_cia = match.group(1).replace('¥', 'Ñ').strip()
                datos_cia = match.group(2)
                
                # Extraer todos los precios (números enteros seguidos de punto)
                precios_encontrados = re.findall(r'\s+(\d+)\.', datos_cia)
                
                # Esperamos 12 precios. Si hay saltos de línea, findall los ignorará y cogerá los números igual.
                if len(precios_encontrados) >= 12:
                    # Tomamos los primeros 12 encontrados para esa compañía
                    precios_num = [float(p) for p in precios_encontrados[:12]]
                    mercado_precios[nombre_cia] = precios_num

        parsed_data['mercado_precios'] = mercado_precios

        # --- Debug (opcional) ---
        # print(f"Procesado {filepath}")
        
        return parsed_data

if __name__ == "__main__":
    # Bloque de prueba
    import os
    parser = LSTParser()
    # Listar archivos txt en el directorio actual
    files = [f for f in os.listdir('.') if f.endswith('.txt') and 'parser' not in f]
    for f in files:
        print(f"--- {f} ---")
        data = parser.parse_file(f)
        # Imprimir solo claves principales para verificar
        keys_to_show = ['caja_total', 'utilidad_periodo', 'cuota_mercado']
        print({k: data.get(k) for k in keys_to_show})