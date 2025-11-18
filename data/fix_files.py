import os
import re
import glob

def fix_intopia_files():
    # Busca todos los archivos de Decisión (1 a 5) con extensión .txt
    files = glob.glob("Decisión *.txt") + glob.glob("Decisión *.LST.txt")
    # Filtra para no volver a procesar los que ya digan "_fixed"
    files = [f for f in files if "_fixed" not in f]

    if not files:
        print("No se encontraron archivos 'Decisión X.txt' en la carpeta actual.")
        return

    print(f"Procesando {len(files)} archivos...")

    for filepath in files:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
            
            original_len = len(content)

            # --- 1. Eliminar Encabezados de Página Repetitivos ---
            # Elimina bloques tipo "1 THORELLI... PAGINA: 022" que cortan las tablas
            content = re.sub(r'1\s+THORELLI-GRAVES-LOPEZ[\s\S]*?PAGINA:\s+\d+', '', content)
            
            # --- 2. Eliminar Títulos Intermedios ---
            content = re.sub(r'INTOPIA 2000 --', '', content)

            # --- 3. Corregir Saltos de Línea en Etiquetas (El error principal del Periodo 5) ---
            # Une "UNIDADES" y "DE LUJO" si están separados por salto de línea
            content = re.sub(r'UNIDADES\s+\n\s+DE\s+LUJO', 'UNIDADES DE LUJO', content)
            
            # Une "CxP PERIODO" y el número si están separados
            content = re.sub(r'(CxP PERIODO)\s+\n\s+(\d+)', r'\1 \2', content)
            content = re.sub(r'(CxC PERIODO)\s+\n\s+(\d+)', r'\1 \2', content)

            # --- 4. Limpiar Caracteres de Control ---
            # Elimina el '0' o '1' que a veces aparece al inicio de línea (control de impresora antigua)
            content = re.sub(r'\n[01]', '\n', content)

            # --- 5. Normalizar Espacios Múltiples (Opcional, ayuda visual) ---
            # (Mantenemos los espacios de tabla, solo arreglamos saltos extraños)
            
            # Guardar el archivo corregido
            new_filename = os.path.splitext(filepath)[0] + "_fixed.txt"
            with open(new_filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f" -> Generado: {new_filename} (Limpiado)")

        except Exception as e:
            print(f"Error procesando {filepath}: {e}")

if __name__ == "__main__":
    fix_intopia_files()