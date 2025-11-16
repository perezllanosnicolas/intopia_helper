INTOPIA Helper v0.2

Descripción
-----------
Asistente para planificar decisiones en INTOPIA 2000:
- Lee ficheros .lst/.txt (Decisión 1..4).
- Extrae IM03/IM28/Información no contable y contratos H6.
- Propone decisiones y exporta A1, A2, A3, A4, H1 en CSV.
- Dos escenarios de uso:
  • --scenario b2b       -> solo B2B (sin retail).
  • --scenario retail_eu -> abre retail de chips (X) en UE.

Estructura del proyecto
-----------------------
intopia_helper_v02/
  src/intopia/
    __init__.py
    params.py      (tablas del juego)
    parser.py      (lee IM03/IM28/INFO-NC/H6)
    demand.py      (demanda: placeholder + anclas)
    planner.py     (lógica B2B vs retail EU)
    forms.py       (exporta A1, A2, A3, A4, H1)
  data/            (coloca aquí Decisión 1..4 .txt)
  outputs/forms/   (CSV de formularios)
  quickstart.py    (CLI: lee, planifica y exporta)
  requirements.txt

Uso rápido
----------
1) Copia tus ficheros Decisión 1..4 .txt en la carpeta data/.
2) Instala dependencias con: pip install -r requirements.txt
3) Ejecuta uno de los escenarios:
   - Solo B2B (A1=0 en EU para X)
     python quickstart.py --periodo 5 --scenario b2b
   - Abrir retail en UE (chips X)
     python quickstart.py --periodo 5 --scenario retail_eu

Ficheros generados en outputs/forms/
------------------------------------
- A1_marketing_p5.csv
- A2_produccion_p5.csv
- A3_finanzas_p5.csv
- A4_prioridades_p5.csv
- H1_casa_matriz_p5.csv

Notas
-----
- Las reglas (capacidades, 2 grados por producto/área, compatibilidad X→Y,
  saltos mínimos de precio, tope 3.500 BRL en Y<=Y3, transporte CIF con
  puntos críticos, AR/AP e impuestos) vienen de la guía del curso 2024-25.
- Si la “gaceta” del curso introduce cambios, actualiza src/intopia/params.py.