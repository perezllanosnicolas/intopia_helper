# Parámetros (URJC 2024-25)
AREAS = ['US','EU','BR']
MONEDAS = {'US':'$','EU':'€','BR':'BRL','CM':'FS'}

# Capacidades por planta (unidades/trim)
CAP_MAX = {'US':{'X':50000,'Y':25000}, 'EU':{'X':30000,'Y':18000}, 'BR':{'X':12000,'Y':9000}}

# Coste adquisición plantas (moneda local)
CAPEX_PLANTA = {'US':{'X':2000000,'Y':1800000}, 'EU':{'X':1000000,'Y':800000}, 'BR':{'X':4000000,'Y':4000000}}

# Coste fijo por nº de plantas (moneda local)
COSTE_FIJO = {
 'US':{'X':[80000,110000,120000], 'Y':[100000,125000,135000]},
 'EU':{'X':[40000, 54000, 64000], 'Y':[ 30000, 50000, 60000]},
 'BR':{'X':[150000,250000,300000], 'Y':[150000,250000,300000]},
}

DEPRE = {'X':0.08,'Y':0.05}

PRECIOS_TIPICOS = {'US':{'X':45,'Y':155}, 'EU':{'X':40,'Y':130}, 'BR':{'X':380,'Y':2000}}
SALTO_MIN = {'US':{'X':1,'Y':5}, 'EU':{'X':1,'Y':10}, 'BR':{'X':25,'Y':50}}
TOPE_BR_Y_LE3 = 3500

# Transporte: superficie/aéreo y puntos críticos (moneda vendedor)
TRANSP_SUP = {
 ('US','EU','X'):0.25,('US','EU','Y'):10,  ('US','BR','X'):1.0, ('US','BR','Y'):22,
 ('EU','US','X'):0.65,('EU','US','Y'):14,  ('EU','BR','X'):0.25,('EU','BR','Y'):8,
 ('BR','US','X'):5.0, ('BR','US','Y'):150, ('BR','EU','X'):7.5, ('BR','EU','Y'):200,
}
TRANSP_AIR = {
 ('US','EU','X'):3.0, ('US','EU','Y'):30, ('US','BR','X'):3.6,('US','BR','Y'):55,
 ('EU','US','X'):2.4, ('EU','US','Y'):35, ('EU','BR','X'):2.4,('EU','BR','Y'):30,
 ('BR','US','X'):15.0,('BR','US','Y'):300,('BR','EU','X'):15.0,('BR','EU','Y'):275,
}
PUNTOS_SUP = {
 ('US','EU','X'):18000,('US','EU','Y'):4000,('US','BR','X'):20000,('US','BR','Y'):4000,
 ('EU','US','X'):20000,('EU','US','Y'):4000,('EU','BR','X'):19000,('EU','BR','Y'):4000,
 ('BR','US','X'):16000,('BR','US','Y'):3000,('BR','EU','X'):16000,('BR','EU','Y'):3000,
}
PUNTOS_AIR = {
 ('US','EU','X'):10000,('US','EU','Y'):2000,('US','BR','X'):10000,('US','BR','Y'):2000,
 ('EU','US','X'):10000,('EU','US','Y'):2000,('EU','BR','X'):10000,('EU','BR','Y'):2000,
 ('BR','US','X'): 8000,('BR','US','Y'):1500,('BR','EU','X'): 8000,('BR','EU','Y'):1500,
}

ALMACEN_MIN = {'US':{'X':1.0,'Y':10.0}, 'EU':{'X':0.8,'Y':8.0}, 'BR':{'X':4.0,'Y':40.0}}

AR_STRUCTURE = {'US':{'cash':0.40,'cxc1':0.60,'cxc2':0.00}, 'EU':{'cash':0.50,'cxc1':0.20,'cxc2':0.30}, 'BR':{'cash':0.30,'cxc1':0.30,'cxc2':0.40}}
AP_STRUCTURE = AR_STRUCTURE.copy()

IMPUESTOS = {'US':0.50,'EU':0.40,'BR':0.30,'CM':0.15}

INTERES_SALDO_POS = {'US':0.007,'EU':0.007,'BR':0.015,'CM':0.006}
INTERES_SALDO_NEG_MENOR = {'US':0.035,'EU':0.035,'BR':0.045,'CM':0.025}
INTERES_SALDO_NEG_MAYOR = {'US':0.08,'EU':0.07,'BR':0.09,'CM':0.065}
SUMAS_CRITICAS = {'US':1200,'EU':700,'BR':1500}

# Compatibilidad X->Y (chips por 1 PC)
X_TO_Y = [
 [1,1,2,3,4,0,0,0,0,0],
 [1,1,2,2,3,0,0,0,0,0],
 [0,1,1,2,2,3,3,5,0,0],
 [0,1,1,1,2,3,3,4,0,0],
 [0,0,0,1,1,2,2,3,0,0],
 [0,0,0,0,0,2,1,2,3,0],
 [0,0,0,0,0,1,1,2,3,0],
 [0,0,0,0,0,0,0,1,2,3],
 [0,0,0,0,0,0,0,0,1,2],
 [0,0,0,0,0,0,0,0,0,1],
]