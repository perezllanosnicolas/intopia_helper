import re

class LSTParser:
    def clean_content(self, content):
        """
        Homogeneiza el contenido eliminando encabezados de página repetitivos
        y normalizando espacios y saltos de línea.
        """
        # 1. Eliminar los bloques de encabezado de página que rompen las tablas
        content = re.sub(r'1\s+THORELLI-GRAVES-LOPEZ[\s\S]*?PAGINA:\s+\d+', '', content)
        
        # 2. Eliminar líneas que solo contienen fechas o títulos irrelevantes sueltos
        content = re.sub(r'INTOPIA 2000 --', '', content)
        
        # 3. Limpiar caracteres de control de impresora (ej. '0' al inicio de línea en tablas)
        content = re.sub(r'\n0', '\n', content)
        
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
        content = self.clean_content(raw_content)

        # --- Bloque 1: BALANCE ---
        match_caja_line = re.search(r'CAJA\s+([\d\.\s\-\,]+)', content)
        if match_caja_line:
            numeros = re.findall(r'(-?\d+)\.', match_caja_line.group(1))
            parsed_data['caja_total'] = float(numeros[-1]) if numeros else 0.0
        else:
            parsed_data['caja_total'] = 0.0

        # --- Bloque 2: ESTADO DE RESULTADOS ---
        match_utilidad = re.search(r'UTILIDAD DEL PERIODO\s+([\d\.\s\-\,]+)', content)
        if match_utilidad:
            numeros = re.findall(r'(-?\d+)\.', match_utilidad.group(1))
            parsed_data['utilidad_periodo'] = float(numeros[-1]) if numeros else 0.0
        else:
            parsed_data['utilidad_periodo'] = 0.0

        # --- Bloque 3: INFORMACION NO CONTABLE ---
        ventas_propias = {}
        inventarios_detalle = {}
        patentes_poseidas = {}
        
        # Extraemos todo el bloque hasta que empiece otra sección grande
        match_info_block = re.search(r'INFORMACION NO CONTABLE([\s\S]*?)(?:CANTIDAD DE PLANTAS|ANALISIS DE COSTO DE PRODUCCION)', content)
        
        if match_info_block:
            info_block = match_info_block.group(1)
            
            # Función auxiliar para extraer 6 valores consecutivos (que pueden estar en varias líneas)
            def get_six_values(regex_pattern, text):
                match = re.search(regex_pattern, text)
                if match:
                    # Capturamos todo el bloque de números encontrado
                    full_match = match.group(0)
                    # Extraemos todos los números que terminan en punto
                    vals = re.findall(r'(\d+)\.', full_match)
                    # Tomamos los últimos 6 (que corresponden a las columnas US(X,Y), EU(X,Y), BR(X,Y))
                    if len(vals) >= 6:
                        return list(map(int, vals[-6:]))
                return [0]*6

            # MAPEO DE COLUMNAS: US(X,Y), EU(X,Y), BR(X,Y)
            cols_std = [('US', 'X', 0), ('US', 'Y', 0), ('EU', 'X', 0), ('EU', 'Y', 0), ('BR', 'X', 0), ('BR', 'Y', 0)]
            cols_lujo = [('US', 'X', 1), ('US', 'Y', 1), ('EU', 'X', 1), ('EU', 'Y', 1), ('BR', 'X', 1), ('BR', 'Y', 1)]

            # 1. Ventas Propias (Usamos \s+ para tolerar saltos de línea entre palabras)
            # El patrón busca la etiqueta y luego captura cualquier cosa hasta encontrar 6 patrones de números
            vals_std = get_six_values(r'VENTAS\s+UNIDADES\s+ESTANDAR[\s\S]*?A\s+CONSUMIDORES[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            for i, val in enumerate(vals_std):
                if val > 0: ventas_propias[cols_std[i]] = val

            vals_lujo = get_six_values(r'VENTA\s+UNIDADES\s+DE\s+LUJO[\s\S]*?A\s+CONSUMIDORES[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            for i, val in enumerate(vals_lujo):
                if val > 0: ventas_propias[cols_lujo[i]] = val
            
            parsed_data['ventas_propias'] = ventas_propias

            # 2. Inventarios (CORREGIDO: Regex independiente y flexible)
            # Buscamos 'UNIDADES ESTANDAR' dentro del bloque, sin depender de 'INVENTARIO FINAL' pegado
            vals_inv_std = get_six_values(r'INVENTARIO\s+FINAL[\s\S]*?UNIDADES\s+ESTANDAR[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            for i, val in enumerate(vals_inv_std):
                if val > 0: inventarios_detalle[cols_std[i]] = val

            # Buscamos 'UNIDADES DE LUJO' permitiendo saltos de línea (\s+) y texto intermedio desde 'INVENTARIO FINAL'
            # Nota: [\s\S]*? permite saltar la sección de Estándar que está en medio
            vals_inv_lujo = get_six_values(r'INVENTARIO\s+FINAL[\s\S]*?UNIDADES\s+DE\s+LUJO[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            for i, val in enumerate(vals_inv_lujo):
                if val > 0: inventarios_detalle[cols_lujo[i]] = val
            
            parsed_data['inventarios_detalle'] = inventarios_detalle

            # 3. Patentes
            # Buscamos en todo el contenido limpio por si se salió del bloque
            match_patentes = re.search(r'MAXIMO\s+GRADO\s+POSEIDO[\s\S]*?(\d+\.[\s\S]*?){6}', content)
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
        match_ventas_block = re.search(r'ASESORIA NUMERO 3[\s\S]*?VENTAS TOTALES:([\s\S]*?)COMPA', content)
        if match_ventas_block:
            numeros_raw = match_ventas_block.group(1)
            match_ventas = re.findall(r'(\d*\.\d{2})', numeros_raw)
            if match_ventas and len(match_ventas) >= 6:
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
            lineas_cias = re.finditer(r'(COMPA[NÑ¥]IA\s+\d+)([\s\S]*?)(?=COMPA[NÑ¥]IA|$)', precios_content)
            for match in lineas_cias:
                nombre_cia = match.group(1).replace('¥', 'Ñ').strip()
                datos_cia = match.group(2)
                precios_encontrados = re.findall(r'\s+(\d+)\.', datos_cia)
                if len(precios_encontrados) >= 12:
                    precios_num = [float(p) for p in precios_encontrados[:12]]
                    mercado_precios[nombre_cia] = precios_num

        parsed_data['mercado_precios'] = mercado_precios
        
        return parsed_data