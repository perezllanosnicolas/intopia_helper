import re

class LSTParser:
    def parse_file(self, filepath):
        parsed_data = {}
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            print(f"Error al leer el archivo {filepath}: {e}")
            return {}

        # --- Bloque 1: BALANCE ---
        balance_block_match = re.search(r'BALANCE([\s\S]*?)NOTE: CASH IS IN A SENSE', content, re.IGNORECASE)
        balance_block = balance_block_match.group(1) if balance_block_match else ""
        match_caja = re.search(r'CAJA([\s\S]*) ([-]?\d+[\.,]?\d*)\.', balance_block)
        parsed_data['caja_total'] = float(match_caja.group(2).replace(',', '.')) if match_caja else 0

        # --- Bloque 2: ESTADO DE RESULTADOS ---
        resultados_block_match = re.search(r'ESTADO DE RESULTADOS([\s\S]*?)INFORMACION NO CONTABLE', content, re.IGNORECASE)
        resultados_block = resultados_block_match.group(1) if resultados_block_match else ""
        match_beneficio = re.search(r'UTILIDAD DEL PERIODO([\s\S]*) ([-]?\d+[\.,]?\d*)\.', resultados_block)
        parsed_data['utilidad_periodo'] = float(match_beneficio.group(2).replace(',', '.')) if match_beneficio else 0

        # --- Bloque 3: INFORMACION NO CONTABLE (Inventarios y Ventas Propias) ---
        inventarios_detalle = {}
        ventas_propias = {}
        match_info_block = re.search(r'INFORMACION NO CONTABLE([\s\S]*?)CANTIDAD DE PLANTAS', content, re.IGNORECASE)
        
        if match_info_block:
            info_block = match_info_block.group(1)
            
            # 1. Ventas Propias (A Consumidores - Estándar)
            match_ventas_std = re.search(r'A CONSUMIDORES\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            if match_ventas_std:
                vals = list(map(int, match_ventas_std.groups()))
                if vals[0] > 0: ventas_propias[('US', 'X', 0)] = vals[0] * 1000 # Convertir k a unidades
                if vals[1] > 0: ventas_propias[('US', 'Y', 0)] = vals[1] * 1000
                if vals[2] > 0: ventas_propias[('EU', 'X', 0)] = vals[2] * 1000
                if vals[3] > 0: ventas_propias[('EU', 'Y', 0)] = vals[3] * 1000
                if vals[4] > 0: ventas_propias[('BR', 'X', 0)] = vals[4] * 1000
                if vals[5] > 0: ventas_propias[('BR', 'Y', 0)] = vals[5] * 1000

            # 2. Ventas Propias (A Consumidores - Lujo)
            match_ventas_lujo = re.search(r'VENTA UNIDADES DE LUJO\s+A CONSUMIDORES\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            if match_ventas_lujo:
                vals = list(map(int, match_ventas_lujo.groups()))
                if vals[0] > 0: ventas_propias[('US', 'X', 1)] = vals[0] * 1000
                if vals[1] > 0: ventas_propias[('US', 'Y', 1)] = vals[1] * 1000
                if vals[2] > 0: ventas_propias[('EU', 'X', 1)] = vals[2] * 1000
                if vals[3] > 0: ventas_propias[('EU', 'Y', 1)] = vals[3] * 1000
                if vals[4] > 0: ventas_propias[('BR', 'X', 1)] = vals[4] * 1000
                if vals[5] > 0: ventas_propias[('BR', 'Y', 1)] = vals[5] * 1000
            
            parsed_data['ventas_propias'] = ventas_propias

            # 3. Inventarios (Estándar)
            match_inv_std = re.search(r'INVENTARIO FINAL\s+UNIDADES ESTANDAR\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            if match_inv_std:
                vals = list(map(int, match_inv_std.groups()))
                if vals[0] > 0: inventarios_detalle[('US', 'X', 0)] = vals[0] * 1000
                if vals[1] > 0: inventarios_detalle[('US', 'Y', 0)] = vals[1] * 1000
                if vals[2] > 0: inventarios_detalle[('EU', 'X', 0)] = vals[2] * 1000
                if vals[3] > 0: inventarios_detalle[('EU', 'Y', 0)] = vals[3] * 1000
                if vals[4] > 0: inventarios_detalle[('BR', 'X', 0)] = vals[4] * 1000
                if vals[5] > 0: inventarios_detalle[('BR', 'Y', 0)] = vals[5] * 1000

            # 4. Inventarios (Lujo)
            match_inv_lujo = re.search(r'INVENTARIO FINAL\s+UNIDADES DE LUJO\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            if match_inv_lujo:
                vals = list(map(int, match_inv_lujo.groups()))
                if vals[0] > 0: inventarios_detalle[('US', 'X', 1)] = vals[0] * 1000
                if vals[1] > 0: inventarios_detalle[('US', 'Y', 1)] = vals[1] * 1000
                if vals[2] > 0: inventarios_detalle[('EU', 'X', 1)] = vals[2] * 1000
                if vals[3] > 0: inventarios_detalle[('EU', 'Y', 1)] = vals[3] * 1000
                if vals[4] > 0: inventarios_detalle[('BR', 'X', 1)] = vals[4] * 1000
                if vals[5] > 0: inventarios_detalle[('BR', 'Y', 1)] = vals[5] * 1000
            
            parsed_data['inventarios_detalle'] = inventarios_detalle

        # --- Bloque 4: ASESORIA NUMERO 3 (Cuota de Mercado y Ventas Totales) ---
        match_ventas_block = re.search(r'ASESORIA NUMERO 3([\s\S]*?)(?:ASESORIA NUMERO 28|COMPAÑIA\s+\d+\s+ASESORIA NUMERO 28)', content)
        if match_ventas_block:
            ventas_content = match_ventas_block.group(1)
            match_ventas = re.findall(r'(\d*\.\d{2})', ventas_content) 
            
            if match_ventas and len(match_ventas) == 6:
                parsed_data['cuota_mercado'] = sum([float(v) for v in match_ventas])
                parsed_data['mercado_ventas_totales'] = [float(v) * 1000 for v in match_ventas] 
            else:
                parsed_data['cuota_mercado'] = 0
                parsed_data['mercado_ventas_totales'] = [0]*6
        
        # --- Bloque 5: ASESORIA NUMERO 28 (Precios de Mercado) ---
        mercado_precios = {}
        match_precios_block = re.search(r'ASESORIA NUMERO 28([\s\S]*?)(?:ASESORIA NUMERO 17|COMPAÑIA\s+\d+\s+ASESORIA NUMERO 17)', content)
        if match_precios_block:
            precios_content = match_precios_block.group(1)
            
            # *** CORRECCIÓN CRÍTICA DE REGEX ***
            # Esta regex busca la línea de la compañía y los 12 valores numéricos
            matches = re.findall(r'COMPA¥IA\s+\d+([\s\.\d]+)', precios_content)
            
            for i, match_str in enumerate(matches):
                # Limpiar la cadena de números
                numeros = [val.strip() for val in match_str.strip().split('.')]
                # Filtrar valores vacíos (resultado de '..') y convertir a float
                precios_num = [float(n) for n in numeros if n]
                
                if len(precios_num) == 12:
                    # El nombre de la compañía se basa en el índice (ej. "COMPA¥IA  1")
                    # Los LSTs a veces omiten compañías, así que buscamos el nombre
                    cia_match = re.search(r'(COMPA¥IA\s+\d+)', precios_content.splitlines()[i+1]) # +1 para saltar la cabecera del bloque
                    if cia_match:
                         cia_nombre = cia_match.group(1).strip()
                         mercado_precios[cia_nombre] = precios_num
        
        parsed_data['mercado_precios'] = mercado_precios

        # --- Imprimir Resumen ---
        print_data = parsed_data.copy()
        print_data.pop('mercado_ventas_totales', None)
        print_data.pop('mercado_precios', None)
        print_data.pop('ventas_propias', None)
        print(f"Parsed data from {filepath}: {print_data}")
        return parsed_data