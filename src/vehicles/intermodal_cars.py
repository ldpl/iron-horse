from train import IntermodalCarConsist, FreightCar


def main():
    #--------------- pony ----------------------------------------------------------------------
    consist = IntermodalCarConsist(roster='pony',
                                   base_numeric_id=1600,
                                   gen=4,
                                   subtype='A')

    consist.add_unit(type=FreightCar,
                     vehicle_length=6)

    consist = IntermodalCarConsist(roster='pony',
                                   base_numeric_id=2800,
                                   gen=4,
                                   subtype='B')

    consist.add_unit(type=FreightCar,
                     vehicle_length=8)

    consist = IntermodalCarConsist(roster='pony',
                                   base_numeric_id=2810,
                                   gen=5,
                                   subtype='A')

    consist.add_unit(type=FreightCar,
                     vehicle_length=6)

    consist = IntermodalCarConsist(roster='pony',
                                   base_numeric_id=2820,
                                   gen=5,
                                   subtype='B')

    consist.add_unit(type=FreightCar,
                     vehicle_length=8)

    consist = IntermodalCarConsist(roster='pony',
                                   base_numeric_id=1610,
                                   gen=6,
                                   subtype='A')

    consist.add_unit(type=FreightCar,
                     vehicle_length=6)

    consist = IntermodalCarConsist(roster='pony',
                                   base_numeric_id=1620,
                                   gen=6,
                                   subtype='B')

    consist.add_unit(type=FreightCar,
                     vehicle_length=8)

    #--------------- llama ----------------------------------------------------------------------
