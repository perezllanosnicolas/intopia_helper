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
            
            # (Inventarios y Ventas están en unidades reales, no en miles)

            # 1. Ventas Propias (A Consumidores - Estándar)
            match_ventas_std = re.search(r'A CONSUMIDORES\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            if match_ventas_std:
                vals = list(map(int, match_ventas_std.groups()))
                if vals[0] > 0: ventas_propias[('US', 'X', 0)] = vals[0]
                if vals[1] > 0: ventas_propias[('US', 'Y', 0)] = vals[1]
                if vals[2] > 0: ventas_propias[('EU', 'X', 0)] = vals[2]
                if vals[3] > 0: ventas_propias[('EU', 'Y', 0)] = vals[3]
                if vals[4] > 0: ventas_propias[('BR', 'X', 0)] = vals[4]
                if vals[5] > 0: ventas_propias[('BR', 'Y', 0)] = vals[5]

            # 2. Ventas Propias (A Consumidores - Lujo)
            match_ventas_lujo = re.search(r'VENTA UNIDADES DE LUJO\s+A CONSUMIDORES\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            if match_ventas_lujo:
                vals = list(map(int, match_ventas_lujo.groups()))
                if vals[0] > 0: ventas_propias[('US', 'X', 1)] = vals[0]
                if vals[1] > 0: ventas_propias[('US', 'Y', 1)] = vals[1]
                if vals[2] > 0: ventas_propias[('EU', 'X', 1)] = vals[2]
                if vals[3] > 0: ventas_propias[('EU', 'Y', 1)] = vals[3]
                if vals[4] > 0: ventas_propias[('BR', 'X', 1)] = vals[4]
                if vals[5] > 0: ventas_propias[('BR', 'Y', 1)] = vals[5]
            
            parsed_data['ventas_propias'] = ventas_propias

            # 3. Inventarios (Estándar)
            match_inv_std = re.search(r'INVENTARIO FINAL\s+UNIDADES ESTANDAR\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            if match_inv_std:
                vals = list(map(int, match_inv_std.groups()))
                if vals[0] > 0: inventarios_detalle[('US', 'X', 0)] = vals[0]
                if vals[1] > 0: inventarios_detalle[('US', 'Y', 0)] = vals[1]
                if vals[2] > 0: inventarios_detalle[('EU', 'X', 0)] = vals[2]
                if vals[3] > 0: inventarios_detalle[('EU', 'Y', 0)] = vals[3]
                if vals[4] > 0: inventarios_detalle[('BR', 'X', 0)] = vals[4]
                if vals[5] > 0: inventarios_detalle[('BR', 'Y', 0)] = vals[5]

            # 4. Inventarios (Lujo)
            match_inv_lujo = re.search(r'INVENTARIO FINAL\s+UNIDADES DE LUJO\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            if match_inv_lujo:
                vals = list(map(int, match_inv_lujo.groups()))
                if vals[0] > 0: inventarios_detalle[('US', 'X', 1)] = vals[0]
                if vals[1] > 0: inventarios_detalle[('US', 'Y', 1)] = vals[1]
                if vals[2] > 0: inventarios_detalle[('EU', 'X', 1)] = vals[2]
                if vals[3] > 0: inventarios_detalle[('EU', 'Y', 1)] = vals[3]
                if vals[4] > 0: inventarios_detalle[('BR', 'X', 1)] = vals[4]
                if vals[5] > 0: inventarios_detalle[('BR', 'Y', 1)] = vals[5]
            
            parsed_data['inventarios_detalle'] = inventarios_detalle


        # --- Bloque 4: ASESORIA NUMERO 3 (Cuota de Mercado y Ventas Totales) ---
        match_ventas_block = re.search(r'ASESORIA NUMERO 3([\s\S]*?)(?:ASESORIA NUMERO 28|COMPAÑIA\s+\d+\s+ASESORIA NUMERO 28)', content)
        if match_ventas_block:
            ventas_content = match_ventas_block.group(1)
            match_ventas = re.findall(r'(\d*\.\d{2})', ventas_content) 
            
            if match_ventas and len(match_ventas) == 6:
                parsed_data['cuota_mercado'] = sum([float(v) for v in match_ventas])
                parsed_data['mercado_ventas_totales'] = [float(v) * 1000 for v in match_ventas] # ESTE SÍ es * 1000
            else:
                parsed_data['cuota_mercado'] = 0
                parsed_data['mercado_ventas_totales'] = [0]*6
        
        # --- Bloque 5: ASESORIA NUMERO 28 (Precios de Mercado) ---
        mercado_precios = {}
        match_precios_block = re.search(r'ASESORIA NUMERO 28([\s\S]*?)(?:ASESORIA NUMERO 17|COMPAÑIA\s+\d+\s+ASESORIA NUMERO 17)', content)
        if match_precios_block:
            precios_content = match_precios_block.group(1)
            
            # *** CORRECCIÓN CRÍTICA DE REGEX ***
            # Procesar línea por línea
            for line in precios_content.splitlines():
                # Buscar líneas que empiecen con "COMPA¥IA" y un número
                cia_match = re.match(r'^\s*(COMPA¥IA\s+\d+)', line)
                if cia_match:
                    cia_nombre = cia_match.group(1).strip()
                    
                    # Encontrar todos los números (enteros o '0') en el resto de la línea
                    # Esta regex busca cualquier grupo de dígitos o espacios, seguido de un punto
                    # CÓDIGO CORREGIDO
                    numeros_str = re.findall(r'(\s*[\d]+)\.', line[len(cia_match.group(0)):])
                    
                    if len(numeros_str) == 12:
                        # Limpiar espacios y convertir a float (' ' o '' se vuelve '0')
                        precios_num = [float(n.strip() or '0') for n in numeros_str]
                        mercado_precios[cia_nombre] = precios_num
        
        parsed_data['mercado_precios'] = mercado_precios

        # --- Imprimir Resumen ---
        print_data = parsed_data.copy()
        print_data.pop('mercado_ventas_totales', None)
        print_data.pop('mercado_precios', None)
        print_data.pop('ventas_propias', None)
        print(f"Parsed data from {filepath}: {print_data}")
        return parsed_data