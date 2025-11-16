from typing import Dict, Any
from . import params

class Planner:
    def __init__(self, scenario:str='b2b'):
        assert scenario in ('b2b','retail_eu')
        self.scenario=scenario

    def _enforce_price(self, area:str, product:str, price:int, grade:int)->int:
        step=params.SALTO_MIN[area][product]
        if area=='BR' and product=='Y' and grade<=3:
            price=min(price, params.TOPE_BR_Y_LE3)
        base=params.PRECIOS_TIPICOS[area][product]
        k=round((price-base)/step)
        return max(base+k*step, step)

    def propose_A1(self, state:Dict[str,Any])->Dict[tuple, Dict[str,int]]:
        decisions={}
        for area in params.AREAS:
            for prod in ['X','Y']:
                for g in [0,1]:
                    if self.scenario=='b2b' and area=='EU' and prod=='X':
                        price=0
                    else:
                        p0=int(params.PRECIOS_TIPICOS[area][prod]*(1+0.10*g))
                        price=int(self._enforce_price(area,prod,p0,g))
                    decisions[(area,prod,g)]={'price':price,'ad':0}
        return decisions

    def propose_A2(self, state:Dict[str,Any])->Dict[str, Any]:
        last = self._last_period(state)
        EUX = state['parsed'][last]['prod_inv_eu']['EU'].get('X',{}) if last else {}
        pl = EUX.get('planta_unids',[0,0,0])
        if sum(pl)==0: pl=[15000,30000,0]
        grado_inf = EUX.get('grado_inf',1)
        mejora_k = self._last_mejora_metodos(state)
        return {'EU':{'X':{'nuevas':0,'mejora_k':mejora_k,'grado_inf':grado_inf,'prod_planta':pl,
                           'grado_sup':0,'prod_planta_sup':[0,0,0]}}}

    def _last_mejora_metodos(self, state)->int:
        last = self._last_period(state)
        if not last: return 0
        forms = state['parsed'][last].get('FORMS',[])
        for ln in forms:
            if ln.strip().startswith('A2') and 'CHIP' in ln:
                try:
                    toks=ln.split()
                    i=toks.index('CHIP')
                    val=float(toks[i+2])
                    return int(round(val))
                except Exception:
                    pass
        return 0

    def _last_period(self, state)->str:
        files=list(state['parsed'].keys())
        return files[-1] if files else None

    def propose_A3(self, state:Dict[str,Any])->list:
        return []

    def propose_A4(self, state:Dict[str,Any])->Dict[str,Any]:
        return {'EU':{'precio_comp_x_std':'','precio_comp_x_lujo':'',
                      'reserva_x_std_k':0,'reserva_x_lujo_k':0,
                      'prioridad_x':'S','prioridad_y':'S'}}

    def propose_H1(self, state:Dict[str,Any])->Dict[str,Any]:
        return {'I+D_X_kFS':320,'I+D_Y_kFS':0,'IM_monto_kFS':0,'IM_estudios':[],'dividendos_kFS':0}