import math
class DemandModel:
    def __init__(self):
        self.delta={'US':0.6,'EU':0.4,'BR':0.2}
        self.elast_price={'US':-0.8,'EU':-1.1,'BR':-1.6}
        self.beta_grade=0.25
        self.beta_ad=0.05
        self.beta_channel=0.03

    def adstock(self, current:float, prev:float, area:str)->float:
        return current + self.delta.get(area,0.4)*prev

    def demand_share(self, price:float, grade:float, ad:float, channel:int, area:str)->float:
        u=self.elast_price.get(area,-1.0)*math.log(max(price,1.0)) + self.beta_grade*grade + self.beta_ad*ad + self.beta_channel*channel
        s=1/(1+math.exp(-u))
        return min(max(0.01, s*0.8), 0.8)