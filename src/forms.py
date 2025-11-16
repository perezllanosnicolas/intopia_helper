import csv, os
from typing import Dict, Any, List

class FormsExporter:
    def __init__(self, out_dir:str):
        self.out_dir=out_dir
        os.makedirs(out_dir, exist_ok=True)

    def export_A1(self, periodo:int, decisions:Dict[tuple, Dict[str,int]]):
        path=os.path.join(self.out_dir, f'A1_marketing_p{periodo}.csv')
        cols=['Area','Producto','Grado','Precio','Publicidad(miles)']
        with open(path,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(cols)
            for (area,prod,g),d in decisions.items():
                w.writerow([area,prod,g,d.get('price',0), d.get('ad',0)])
        return path

    def export_A2(self, periodo:int, a2:Dict[str,Any]):
        path=os.path.join(self.out_dir, f'A2_produccion_p{periodo}.csv')
        cols=['Area','Producto','PlantasNuevas','MejoraMetodos(miles)',
              'GradoInf','Prod_P1(k)','Prod_P2(k)','Prod_P3(k)',
              'GradoSup','ProdSup_P1(k)','ProdSup_P2(k)','ProdSup_P3(k)']
        with open(path,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(cols)
            for area,prod_dict in a2.items():
                for prod,val in prod_dict.items():
                    p=val.get('prod_planta',[0,0,0])
                    ps=val.get('prod_planta_sup',[0,0,0])
                    w.writerow([area,prod,val.get('nuevas',0),val.get('mejora_k',0),
                                val.get('grado_inf',0), p[0],p[1],p[2],
                                val.get('grado_sup',0), ps[0],ps[1],ps[2]])
        return path

    def export_A3(self, periodo:int, a3_list:List[Dict[str,Any]]):
        path=os.path.join(self.out_dir, f'A3_finanzas_p{periodo}.csv')
        cols=['Area','Tipo(F/T/R)','Moneda(1..4)','Monto(miles)','Conversion(S/N)']
        with open(path,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(cols)
            for r in a3_list:
                w.writerow([r['area'], r['tipo'], r['moneda'], r['monto_k'], r['conversion']])
        return path

    def export_A4(self, periodo:int, a4:Dict[str,Any]):
        path=os.path.join(self.out_dir, f'A4_prioridades_p{periodo}.csv')
        cols=['Area','PrecioCompX_std','PrecioCompX_lujo','ReservaX_std(k)','ReservaX_lujo(k)','PrioridadX(S/D)','PrioridadY(S/D)']
        with open(path,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(cols)
            for area,val in a4.items():
                w.writerow([area, val.get('precio_comp_x_std',''), val.get('precio_comp_x_lujo',''),
                            val.get('reserva_x_std_k',0), val.get('reserva_x_lujo_k',0),
                            val.get('prioridad_x','S'), val.get('prioridad_y','S')])
        return path

    def export_H1(self, periodo:int, h1:Dict[str,Any]):
        path=os.path.join(self.out_dir, f'H1_casa_matriz_p{periodo}.csv')
        cols=['I+D_X(kFS)','I+D_Y(kFS)','IM_monto(kFS)','IM_estudios(coma)','Dividendos(kFS)']
        with open(path,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(cols)
            w.writerow([h1.get('I+D_X_kFS',0), h1.get('I+D_Y_kFS',0),
                        h1.get('IM_monto_kFS',0), ','.join(map(str,h1.get('IM_estudios',[]))),
                        h1.get('dividendos_kFS',0)])
        return path