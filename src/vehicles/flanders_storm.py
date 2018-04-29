from train import EngineConsist, ElectricEngineUnit

consist = EngineConsist(id='flanders_storm',
                        base_numeric_id=1740,
                        name='Flanders Storm',
                        role='heavy_freight_2',
                        power=7500,
                        # dibble for game balance, assume super-slip control
                        tractive_effort_coefficient=0.36,
                        type_base_buy_cost_points=63,  # dibble buy cost for game balance
                        random_reverse=True,
                        joker=True, # this engine doesn't fit the set roster pattern, by design it's to mix things up
                        gen=6,
                        intro_date_offset=-15) # introduce earlier than gen epoch by design

consist.add_unit(type=ElectricEngineUnit,
                 weight=120,
                 vehicle_length=8,
                 spriterow_num=0)

