import global_constants
from train import EngineConsist, ElectroDieselLoco

consist = EngineConsist(id = 'double_juice',
              base_numeric_id = 160,
              title = 'Double Juice [ElectroDiesel]',
              power = 1700,
              speed = 90,
              type_base_buy_cost_points = 60, # dibble buy cost for game balance
              vehicle_life = 40,
              intro_date = 1990,
              power_by_railtype = {'RAIL': 1700, 'ELRL': 3400})

consist.add_unit(ElectroDieselLoco(consist = consist,
                        weight = 120,
                        vehicle_length = 8,
                        spriterow_num = 0))

consist.add_model_variant(intro_date=0,
                       end_date=global_constants.max_game_date)
