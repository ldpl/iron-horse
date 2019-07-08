from train import EngineConsist, DieselEngineUnit


def main(roster):
    consist = EngineConsist(roster=roster,
                            id='scorcher',
                            base_numeric_id=3320,
                            name='Scorcher HST',
                            role='hst_express_1', # quite a specific role, may or may not scale to other rosters
                            power=6600,
                            joker=True,  # this engine doesn't fit the set roster pattern, by design it's to mix things up
                            dual_headed=True,
                            intro_date_offset=-10,  # let's be a little bit earlier for this one - keep match to HST coaches
                            gen=6,
                            sprites_complete=False)

    consist.add_unit(type=DieselEngineUnit,
                     weight=70,
                     vehicle_length=8,
                     spriterow_num=0)

    return consist
