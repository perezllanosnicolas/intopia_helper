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
        # Aisla el bloque del Balance para evitar capturar números de otros sitios
        balance_block_match = re.search(r'BALANCE([\s\S]*?)NOTE: CASH IS IN A SENSE', content, re.IGNORECASE)
        balance_block = balance_block_match.group(1) if balance_block_match else ""

        # Caja consolidada (último número en la línea CAJA dentro del bloque)
        match_caja = re.search(r'CAJA([\s\S]*) ([-]?\d+[\.,]?\d*)\.', balance_block)
        parsed_data['caja_total'] = float(match_caja.group(2).replace(',', '.')) if match_caja else 0

        # --- Bloque 2: ESTADO DE RESULTADOS ---
        # Aisla el bloque de Estado de Resultados
        resultados_block_match = re.search(r'ESTADO DE RESULTADOS([\s\S]*?)INFORMACION NO CONTABLE', content, re.IGNORECASE)
        resultados_block = resultados_block_match.group(1) if resultados_block_match else ""

        # Beneficio consolidado (último número en la línea UTILIDAD DEL PERIODO dentro del bloque)
        match_beneficio = re.search(r'UTILIDAD DEL PERIODO([\s\S]*) ([-]?\d+[\.,]?\d*)\.', resultados_block)
        parsed_data['utilidad_periodo'] = float(match_beneficio.group(2).replace(',', '.')) if match_beneficio else 0

        # --- Bloque 3: INFORMACION NO CONTABLE (Inventarios) ---
        inventarios = {'US': 0, 'EU': 0, 'BR': 0}
        match_info_block = re.search(r'INFORMACION NO CONTABLE([\s\S]*?)CANTIDAD DE PLANTAS', content, re.IGNORECASE)
        if match_info_block:
            info_block = match_info_block.group(1)
            
            # 1. Buscar Unidades Estándar (6 valores)
            match_inv_std = re.search(r'UNIDADES ESTANDAR\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            inv_std_vals = list(map(int, match_inv_std.groups())) if match_inv_std else [0]*6

            # 2. Buscar Unidades de Lujo (6 valores)
            match_inv_lujo = re.search(r'UNIDADES DE LUJO\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.\s+(\d+)\.', info_block)
            inv_lujo_vals = list(map(int, match_inv_lujo.groups())) if match_inv_lujo else [0]*6

            inventarios['US'] = inv_std_vals[0] + inv_std_vals[1] + inv_lujo_vals[0] + inv_lujo_vals[1]
            inventarios['EU'] = inv_std_vals[2] + inv_std_vals[3] + inv_lujo_vals[2] + inv_lujo_vals[3]
            inventarios['BR'] = inv_std_vals[4] + inv_std_vals[5] + inv_lujo_vals[4] + inv_lujo_vals[5]
        
        parsed_data['inventarios'] = inventarios

        # --- Bloque 4: ASESORIA NUMERO 3 (Cuota de Mercado) ---
        match_ventas_block = re.search(r'ASESORIA NUMERO 3([\s\S]*?)(?:ASESORIA NUMERO 28|COMPAÑIA\s+\d+\s+ASESORIA NUMERO 28)', content)
        if match_ventas_block:
            ventas_content = match_ventas_block.group(1)
            match_ventas = re.findall(r'(\d+\.\d{2})', ventas_content) 
            parsed_data['cuota_mercado'] = sum([float(v.replace(',', '.')) for v in match_ventas]) if match_ventas else 0
        else:
             parsed_data['cuota_mercado'] = 0

        print(f"Parsed data from {filepath}: {parsed_data}")
        return parsed_data 