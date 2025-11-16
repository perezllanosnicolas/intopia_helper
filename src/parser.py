import re

class LSTParser:
    def parse_file(self, filepath):
        parsed_data = {}
        with open(filepath, 'r', encoding='latin-1') as f:
            content = f.read()

        # Beneficio consolidado (último número en la línea UTILIDAD DEL PERIODO)
        match_beneficio = re.search(r'UTILIDAD DEL PERIODO[\\s\\S]*?(\\d+[\\.,]?\\d*)\\.', content)
        parsed_data['utilidad_periodo'] = float(match_beneficio.group(1).replace(',', '.')) if match_beneficio else 0

        # Caja consolidada (último número en la línea CAJA)
        match_caja = re.search(r'CAJA[\\s\\S]*?(\\d+[\\.,]?\\d*)\\.', content)
        parsed_data['caja_total'] = float(match_caja.group(1).replace(',', '.')) if match_caja else 0

        # Inventarios por área (tres números en la línea INVENTARIO FINAL UNIDADES ESTANDAR)
        inventarios = {'US': 0, 'EU': 0, 'BR': 0}
        match_inv = re.search(r'INVENTARIO FINAL UNIDADES ESTANDAR\\s+(\\d+)\\.\\s+(\\d+)\\.\\s+(\\d+)\\.', content)
        if match_inv:
            inventarios['US'], inventarios['EU'], inventarios['BR'] = map(int, match_inv.groups())
        parsed_data['inventarios'] = inventarios

        # Cuota de mercado (sumar todos los números en la línea VENTAS TOTALES)
        match_ventas = re.findall(r'VENTAS TOTALES:[^\\n]*?(\\d+[\\.,]?\\d*)', content)
        parsed_data['cuota_mercado'] = sum([float(v.replace(',', '.')) for v in match_ventas]) if match_ventas else 0
        print(f"Parsed data from {filepath}: {parsed_data}")
        return parsed_data
