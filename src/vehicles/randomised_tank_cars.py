from train import TankCarRandomisedConsist, FreightCar


def main():
    # --------------- pony ----------------------------------------------------------------------

    consist = TankCarRandomisedConsist(
        roster_id="pony",
        base_numeric_id=7930,
        gen=1,
        subtype="A",
        sprites_complete=False,
    )

    consist.add_unit(type=FreightCar, vehicle_length=4)

    # no new type A for gen 2, gen 1 type A continues

    consist = TankCarRandomisedConsist(
        roster_id="pony", base_numeric_id=7940, gen=2, subtype="B", sprites_complete=False
    )

    consist.add_unit(type=FreightCar, chassis="4_axle_gapped_24px")

    consist = TankCarRandomisedConsist(
        roster_id="pony", base_numeric_id=7950, gen=3, subtype="A", sprites_complete=False
    )

    consist.add_unit(type=FreightCar, chassis="2_axle_filled_16px")

    consist = TankCarRandomisedConsist(
        roster_id="pony",
        base_numeric_id=7960,
        gen=3,
        subtype="B",
        sprites_complete=False,
    )

    consist.add_unit(type=FreightCar, chassis="4_axle_filled_24px")

    consist = TankCarRandomisedConsist(
        roster_id="pony", base_numeric_id=7970, gen=4, subtype="A", sprites_complete=False
    )

    consist.add_unit(type=FreightCar, chassis="2_axle_filled_16px")

    consist = TankCarRandomisedConsist(
        roster_id="pony",
        base_numeric_id=7980,
        gen=4,
        subtype="B",
        sprites_complete=False,
    )

    consist.add_unit(type=FreightCar, chassis="2_axle_filled_24px")

    consist = TankCarRandomisedConsist(
        roster_id="pony",
        base_numeric_id=7990,
        gen=4,
        subtype="C",
        sprites_complete=False,
    )

    consist.add_unit(
        type=FreightCar,
        suppress_roof_sprite=False,  # non-standard roof for this wagon
        chassis="4_axle_1cc_filled_32px",
    )

    consist = TankCarRandomisedConsist(
        roster_id="pony",
        base_numeric_id=8000,
        gen=5,
        subtype="B",
        sprites_complete=False,
    )

    consist.add_unit(type=FreightCar, chassis="2_axle_filled_greebled_24px")

    consist = TankCarRandomisedConsist(
        roster_id="pony",
        base_numeric_id=8010,
        gen=5,
        subtype="C",
        sprites_complete=False,
    )

    consist.add_unit(type=FreightCar, chassis="4_axle_1cc_filled_32px")

    consist = TankCarRandomisedConsist(
        roster_id="pony",
        base_numeric_id=8020,
        gen=6,
        subtype="B",
        sprites_complete=False,
    )

    consist.add_unit(type=FreightCar, chassis="2_axle_filled_greebled_24px")

    consist = TankCarRandomisedConsist(
        roster_id="pony",
        base_numeric_id=8030,
        gen=6,
        subtype="C",
        sprites_complete=False,
    )

    consist.add_unit(type=FreightCar, chassis="4_axle_1cc_filled_32px")
