import global_constants
from train import EngineConsist, SteamLoco, SteamLocoTender

consist = EngineConsist(id = 'oubangui',
              base_numeric_id = 2010,
              title = '2-6-6-2 Oubangui [Steam]',
              replacement_id = '-none',
              power = 1500,
              track_type = 'NG',
              speed = 55,
              vehicle_life = 40,
              intro_date = 1920)

consist.add_unit(SteamLoco(consist = consist,
                        weight = 90,
                        vehicle_length = 8,
                        spriterow_num = 0))

consist.add_model_variant(intro_date=0,
                       end_date=global_constants.max_game_date,
                       spritesheet_suffix=0)
