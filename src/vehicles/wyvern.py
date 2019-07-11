from train import EngineConsist, DieselEngineUnit


def main(roster):
    consist = EngineConsist(roster=roster,
                            id='wyvern',
                            base_numeric_id=2950,
                            name='Wyvern',
                            role='heavy_express_3',
                            power=2000,
                            joker=True,  # this engine doesn't fit the set roster pattern, by design it's to mix things up
                            random_reverse=True,
                            gen=4,
                            intro_date_offset=-5,  # let's not have everything turn up in 1960
                            sprites_complete=False)

    consist.add_unit(type=DieselEngineUnit,
                     weight=110,
                     vehicle_length=8,
                     spriterow_num=0)

    return consist
