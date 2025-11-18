import re

class LSTParser:
    def clean_content(self, content):
        """
        Limpia el contenido eliminando encabezados repetitivos y normalizando texto.
        """
        # 1. Eliminar bloques de encabezado de página
        content = re.sub(r'1\s+THORELLI-GRAVES-LOPEZ[\s\S]*?PAGINA:\s+\d+', '', content)
        # 2. Eliminar títulos intermedios
        content = re.sub(r'INTOPIA 2000 --', '', content)
        # 3. Eliminar caracteres de control numéricos al inicio de línea
        content = re.sub(r'\n\d', '\n', content)
        return content

    def parse_file(self, filepath):
        parsed_data = {}
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                raw_content = f.read()
        except Exception as e:
            print(f"Error al leer el archivo {filepath}: {e}")
            return {}

        content = self.clean_content(raw_content)

        # --- HELPER: Extraer último número de un bloque delimitado ---
        def get_last_number_in_block(start_tag, end_tag, text):
            # Busca todo el texto entre start_tag y end_tag
            pattern = f"{start_tag}([\\s\\S]*?){end_tag}"
            match = re.search(pattern, text)
            if match:
                block = match.group(1)
                # Extrae todos los números (enteros o negativos) seguidos de punto
                # Se usa [0-9\.\-]+ para capturar números que puedan estar cortados o con formato raro
                numeros = re.findall(r'(-?\d+)\.', block)
                if numeros:
                    return float(numeros[-1]) # El último siempre es el consolidado
            return 0.0

        # --- 1. BALANCE (Caja) ---
        # Busca desde "CAJA" hasta "CxC PERIODO" para capturar toda la fila(s)
        parsed_data['caja_total'] = get_last_number_in_block(r'CAJA', r'CxC', content)

        # --- 2. ESTADO DE RESULTADOS (Beneficio) ---
        # Busca desde "UTILIDAD DEL PERIODO" hasta "DIVIDENDOS" o "A UTILIDADES"
        # Esto captura el salto de línea donde cae el valor consolidado en el periodo 5
        parsed_data['utilidad_periodo'] = get_last_number_in_block(r'UTILIDAD\s+DEL\s+PERIODO', r'(?:DIVIDENDOS|A\s+UTILIDADES)', content)

        # --- 3. INFORMACIÓN NO CONTABLE (Inventarios y Ventas) ---
        ventas_propias = {}
        inventarios_detalle = {}
        patentes_poseidas = {}
        
        match_info = re.search(r'INFORMACION NO CONTABLE([\s\S]*?)CANTIDAD DE PLANTAS', content)
        if match_info:
            info_block = match_info.group(1)
            
            def get_six_cols(pattern, text):
                match = re.search(pattern, text)
                if match:
                    full_match = match.group(0)
                    vals = re.findall(r'(\d+)\.', full_match)
                    if len(vals) >= 6:
                        return list(map(int, vals[-6:]))
                return [0]*6

            keys_std = [('US','X',0), ('US','Y',0), ('EU','X',0), ('EU','Y',0), ('BR','X',0), ('BR','Y',0)]
            keys_lujo = [('US','X',1), ('US','Y',1), ('EU','X',1), ('EU','Y',1), ('BR','X',1), ('BR','Y',1)]

            v_std = get_six_cols(r'VENTAS\s+UNIDADES\s+ESTANDAR[\s\S]*?A\s+CONSUMIDORES[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            v_luj = get_six_cols(r'VENTA\s+UNIDADES\s+DE\s+LUJO[\s\S]*?A\s+CONSUMIDORES[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            i_std = get_six_cols(r'INVENTARIO\s+FINAL[\s\S]*?UNIDADES\s+ESTANDAR[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)
            i_luj = get_six_cols(r'INVENTARIO\s+FINAL[\s\S]*?UNIDADES\s+DE\s+LUJO[\s\S]*?(\d+\.[\s\S]*?){6}', info_block)

            for i in range(6):
                if v_std[i] > 0: ventas_propias[keys_std[i]] = v_std[i]
                if v_luj[i] > 0: ventas_propias[keys_lujo[i]] = v_luj[i]
                if i_std[i] > 0: inventarios_detalle[keys_std[i]] = i_std[i]
                if i_luj[i] > 0: inventarios_detalle[keys_lujo[i]] = i_luj[i]

        parsed_data['ventas_propias'] = ventas_propias
        parsed_data['inventarios_detalle'] = inventarios_detalle

        # --- 4. PATENTES ---
        match_pat = re.search(r'MAXIMO\s+GRADO\s+POSEIDO[\s\S]*?(\d+\.[\s\S]*?){6}', content)
        if match_pat:
            p_vals = re.findall(r'(\d+)\.', match_pat.group(0))
            if len(p_vals) >= 6:
                g = list(map(int, p_vals[-6:]))
                patentes_poseidas = {
                    ('US','X'): g[0], ('US','Y'): g[1],
                    ('EU','X'): g[2], ('EU','Y'): g[3],
                    ('BR','X'): g[4], ('BR','Y'): g[5]
                }
        parsed_data['patentes_poseidas'] = patentes_poseidas

        # --- 5. CUOTA DE MERCADO (Asesoría 3) ---
        # Buscamos el bloque entre "VENTAS TOTALES:" y "ASESORIA NUMERO 28" (o "COMPAÑIA")
        match_cuota = re.search(r'ASESORIA\s+NUMERO\s+3[\s\S]*?VENTAS\s+TOTALES:([\s\S]*?)(?:COMPA|ASESORIA)', content)
        if match_cuota:
            numeros_raw = match_cuota.group(1)
            # Busca números formato 00.00 (permitiendo espacios entre dígitos si el OCR falló, aunque aquí no es el caso)
            # En los LST el formato es .00 o 12.34
            cuotas = re.findall(r'(\d*\.\d{2})', numeros_raw)
            if len(cuotas) >= 6:
                # Tomamos los últimos 6 encontrados en ese bloque
                vals = [float(c) for c in cuotas[-6:]]
                parsed_data['cuota_mercado'] = sum(vals)
                parsed_data['mercado_ventas_totales'] = [v*1000 for v in vals]
            else:
                parsed_data['cuota_mercado'] = 0
        else:
            parsed_data['cuota_mercado'] = 0
        
        # --- 6. PRECIOS DE MERCADO (Asesoría 28) ---
        mercado_precios = {}
        # Buscamos hasta el siguiente titulo de Asesoría o fin de bloque
        match_precios = re.search(r'ASESORIA\s+NUMERO\s+28([\s\S]*?)(?:ASESORIA\s+NUMERO\s+17|GRADO\s+DE\s+LAS\s+VENTAS)', content)
        if match_precios:
            bloque_precios = match_precios.group(1)
            for m in re.finditer(r'(COMPA[NÑ¥]IA\s+\d+)([\s\S]*?)(?=COMPA[NÑ¥]IA|$)', bloque_precios):
                nombre = m.group(1).replace('¥','Ñ').strip()
                precios = re.findall(r'\s+(\d+)\.', m.group(2))
                if len(precios) >= 12:
                    mercado_precios[nombre] = [float(p) for p in precios[:12]]
        
        parsed_data['mercado_precios'] = mercado_precios
        
        return parsed_data