import os.path

currentdir = os.curdir

import sys

sys.path.append(os.path.join("src"))  # add to the module search path

import global_constants
import utils

makefile_args = utils.get_makefile_args(sys)

generated_files_path = os.path.join(currentdir, global_constants.generated_files_dir)
if not os.path.exists(generated_files_path):
    os.mkdir(generated_files_path)

# this format of import is weird, but I don't want the imported modules directly in the iron horse namespace, I want to nest in spritelayer_cargos
from spritelayer_cargos import registered_spritelayer_cargos
from spritelayer_cargos import intermodal_containers

from spritelayer_cargos import automobiles

# import railtypes
from railtypes import registered_railtypes
from railtypes import metro
from railtypes import narrow_gauge
from railtypes import lgv
from railtypes import lgv_electrified

# import rosters
from rosters import registered_rosters
from rosters import pony

from vehicles import numeric_id_defender

# import wagons
from vehicles import acid_tank_cars
from vehicles import aggregate_cars

# from vehicles import alignment_cars
from vehicles import automobile_cars
from vehicles import bolster_cars
from vehicles import box_cars
from vehicles import bulkhead_flat_cars
from vehicles import caboose_cars
from vehicles import goods_caboose_cars
from vehicles import carbon_black_hopper_cars
from vehicles import cement_silo_cars
from vehicles import chemical_covered_hopper_cars
from vehicles import coil_buggy_cars
from vehicles import coil_cars_covered
from vehicles import coil_cars_uncovered
from vehicles import covered_hopper_cars
from vehicles import cryo_tank_cars
from vehicles import curtain_side_box_cars
from vehicles import double_deck_automobile_cars
from vehicles import dry_powder_hopper_cars
from vehicles import dump_cars
from vehicles import dump_cars_high_side
from vehicles import edibles_tank_cars
from vehicles import express_cars
from vehicles import express_intermodal_cars
from vehicles import express_railcar_passenger_trailer_cars
from vehicles import farm_products_box_cars
from vehicles import farm_products_hopper_cars
from vehicles import flat_cars
from vehicles import goods_box_cars
from vehicles import hood_open_cars
from vehicles import hopper_cars
from vehicles import hst_mail_cars
from vehicles import hst_passenger_cars
from vehicles import ingot_cars
from vehicles import intermodal_cars
from vehicles import kaolin_hopper_cars
from vehicles import livestock_cars
from vehicles import log_cars
from vehicles import low_floor_automobile_cars
from vehicles import low_floor_intermodal_cars
from vehicles import mail_cars
from vehicles import merchandise_box_cars
from vehicles import merchandise_open_cars
from vehicles import mineral_covered_hopper_cars
from vehicles import mineral_hopper_cars
from vehicles import mgr_hopper_cars
from vehicles import open_cars
from vehicles import ore_dump_cars
from vehicles import ore_hopper_cars
from vehicles import passenger_cars
from vehicles import peat_cars
from vehicles import plate_cars
from vehicles import pressure_tank_cars
from vehicles import product_tank_cars
from vehicles import railbus_passenger_trailer_cars
from vehicles import railcar_passenger_trailer_cars
from vehicles import randomised_box_cars
from vehicles import randomised_bulk_cars
from vehicles import randomised_cold_metal_cars
from vehicles import randomised_dump_cars
from vehicles import randomised_flat_cars
from vehicles import randomised_hopper_cars
from vehicles import randomised_open_cars
from vehicles import randomised_piece_goods_cars
from vehicles import randomised_chemicals_tank_cars
from vehicles import reefer_cars
from vehicles import restaurant_cars
from vehicles import rock_hopper_cars
from vehicles import roller_roof_hopper_cars
from vehicles import scrap_metal_cars
from vehicles import silo_cars
from vehicles import skip_cars
from vehicles import slag_ladle_cars
from vehicles import sliding_roof_cars
from vehicles import sliding_wall_cars
from vehicles import suburban_passenger_cars
from vehicles import swing_roof_hopper_cars
from vehicles import tank_cars
from vehicles import tarpaulin_cars
from vehicles import torpedo_cars
from vehicles import vehicle_parts_box_cars


def vacant_numeric_ids_formatted():
    # when adding vehicles it's useful to know what the next free numeric ID is
    # tidy-mind problem, but do we have any vacant numeric ID slots in the currently used range?
    # 'print' eh? - but it's fine echo_message isn't intended for this kind of info, don't bother changing
    max_id = max(numeric_id_defender) - (max(numeric_id_defender) % 10)
    id_gaps = []
    for i in range(0, int(max_id / 10)):
        id = i * 10
        if id not in numeric_id_defender:
            id_gaps.append(str(id))
    return (
        "Vacant numeric ID slots: "
        + ", ".join(id_gaps)
        + (" and from " if len(id_gaps) > 0 else "")
        + str(max_id + 10)
        + " onwards"
    )


def get_active_railtypes():
    # this might want to mimic the ActiveRosters helper class, but eh, YAGNI?
    active_railtypes = [
        railtype for railtype in registered_railtypes if not railtype.disabled
    ]  # make sure it's iterable
    return active_railtypes


class ActiveRosters(list):
    """
    Sometimes we want to conveniently expose attributes that span active rosters.
    This is a class to manage that, intended for use as a singleton, which can be passed to templates etc.
    Extends default python list, as we also use it when we want a list of active rosters (the instantiated class instance behaves like a list object).
    """

    def __init__(self):
        active_rosters = []
        #  for a faster single-roster compiles when testing, optionally pass a roster id (lower case) as a makefile arg
        if makefile_args.get("roster", "ALL") == "ALL":
            active_rosters = [
                roster for roster in registered_rosters if not roster.disabled
            ]
        else:
            active_rosters = [
                roster
                for roster in registered_rosters
                if roster.id == makefile_args["roster"]
            ]  # make sure it's iterable

        for roster in active_rosters:
            self.append(roster)

    @property
    def consists_in_buy_menu_order(self):
        consists = []
        # first compose the buy menu order list
        buy_menu_sort_order = []
        for roster in self:
            buy_menu_sort_order.extend(roster.buy_menu_sort_order)
            consists.extend(roster.consists_in_buy_menu_order)

        # now guard against any consists missing from buy menu order or vice versa, as that wastes time asking 'wtf?' when they don't appear in game
        consist_id_defender = set([consist.id for consist in consists])
        buy_menu_defender = set(buy_menu_sort_order)
        for id in buy_menu_defender.difference(consist_id_defender):
            utils.echo_message(
                "Warning: consist "
                + id
                + " in buy_menu_sort_order, but not found in registered_consists"
            )
        for id in consist_id_defender.difference(buy_menu_defender):
            utils.echo_message(
                "Warning: consist "
                + id
                + " in consists, but not in buy_menu_sort_order - won't show in game"
            )
        return consists

    @property
    def restaurant_car_ids(self):
        result = []
        for roster in self:
            # could have abstracted the filtering element into a method on the roster, more encapsulated, but eh, code split over 2 places, so didn't
            # could also have been done by having restaurant cars register themselves directly into a list on roster but eh, that's a book-keeping headache
            for consists in roster.wagon_consists.values():
                for consist in consists:
                    if consist.__class__.__name__ == "PassengerRestaurantCarConsist":
                        result.append(consist.base_numeric_id)
        if len(result) > 255:
            utils.echo_message(
                "action 2 switch is limited to 255 values, restaurant_car_ids exceeds this - needs split across multiple switches"
            )
        return result

    @property
    def haulage_bonus_engine_id_tree(self):
        # supports a BAD FEATURE easter egg, where some railcar speeds are increased when hauled by express engine, and can be used as fast MUs
        express_engine_ids = []
        for roster in self:
            # could have abstracted the filtering element into a method on the roster, more encapsulated, but eh, code split over 2 places, so didn't
            for consist in roster.engine_consists:
                # check for express-type roles, which are determined by multiple role groups
                for role_group_mapping_key in [
                    "express",
                    "driving_cab",
                    "express_railcar",
                ]:
                    group_roles = global_constants.role_group_mapping[
                        role_group_mapping_key
                    ]
                    if consist.role in group_roles:
                        express_engine_ids.append(consist.id)
        return [(count, id) for count, id in enumerate(express_engine_ids)]

    @property
    def cargo_sprinter_ids(self):
        # find cargo_sprinters
        # used to switch wagon company colours
        result = []
        for roster in self:
            # could have abstracted the filtering element into a method on the roster, more encapsulated, but eh, code split over 2 places, so didn't
            for consist in roster.engine_consists:
                # abuse the spritelayer_cargo_layers property here, we're just looking for a string, this might be fragile, but eh
                if "cargo_sprinter" in getattr(consist, "spritelayer_cargo_layers", []):
                    result.append(consist.id)
        if len(result) > 255:
            utils.echo_message(
                "action 2 switch is limited to 255 values, cargo_sprinter_ids exceeds this - needs split across multiple switches"
            )
        return result

    @property
    def pax_car_ids(self):
        # for pax cars with consist-specific liveries
        # will check for other neighbouring pax cars before showing brake car
        result = []
        for roster in self:
            # could have abstracted the filtering element into a method on the roster, more encapsulated, but eh, code split over 2 places, so didn't
            for consists in roster.wagon_consists.values():
                for consist in consists:
                    if getattr(
                        consist,
                        "report_as_pax_car_to_neighbouring_vehicle_in_rulesets",
                        False,
                    ):
                        result.append(consist.base_numeric_id)
            for consist in roster.engine_consists:
                if getattr(consist, "treat_as_pax_car_for_var_41", False):
                    result.append(consist.id)
        if len(result) > 255:
            utils.echo_message(
                "action 2 switch is limited to 255 values, pax_car_ids result exceeds this - needs split across multiple switches"
            )
        return result

    @property
    def livery_2_engine_ids(self):
        # for vehicles with consist-specific liveries
        # will switch vehicle to livery 2 for specific roles of lead engine
        result = []
        for roster in self:
            # could have abstracted the filtering element into a method on the roster, more encapsulated, but eh, code split over 2 places, so didn't
            for consist in roster.engine_consists:
                if consist.force_default_pax_mail_livery == 1:
                    continue
                if consist.force_default_pax_mail_livery == 2:
                    result.append(consist.id)
                    continue
                # generally it's better to force the livery per engine as wanted, but some railcars automatically switch by role
                if (consist.role, consist.role_child_branch_num) in [
                    ("pax_railcar", 2),
                    ("mail_railcar", 2),
                ]:
                    result.append(consist.id)
        if len(result) > 255:
            utils.echo_message(
                "action 2 switch is limited to 255 values, livery_2_engine_ids exceeds this - needs split across multiple switches"
            )
        return result


def main():
    # railtypes - order is significant, as affects order in construction menu (order property not currently set)
    lgv.main(disabled=False)
    lgv_electrified.main(disabled=False)
    narrow_gauge.main(disabled=False)
    metro.main(disabled=False)

    # rosters
    pony.main(disabled=False)

    # spritelayer cargos
    intermodal_containers.main()
    automobiles.main()

    # wagons
    acid_tank_cars.main()
    aggregate_cars.main()
    """
    # only comment in if needed for debugging
    alignment_cars.main()
    """
    # automobile_cars.main()
    bolster_cars.main()
    box_cars.main()
    bulkhead_flat_cars.main()
    caboose_cars.main()
    carbon_black_hopper_cars.main()
    cement_silo_cars.main()
    chemical_covered_hopper_cars.main()
    coil_buggy_cars.main()
    coil_cars_covered.main()
    coil_cars_uncovered.main()
    covered_hopper_cars.main()
    cryo_tank_cars.main()
    curtain_side_box_cars.main()
    # double_deck_automobile_cars.main()
    dry_powder_hopper_cars.main()
    dump_cars.main()
    dump_cars_high_side.main()
    edibles_tank_cars.main()
    express_cars.main()
    express_intermodal_cars.main()
    express_railcar_passenger_trailer_cars.main()
    farm_products_box_cars.main()
    farm_products_hopper_cars.main()
    flat_cars.main()
    goods_box_cars.main()
    goods_caboose_cars.main()
    hood_open_cars.main()
    hopper_cars.main()
    hst_mail_cars.main()
    hst_passenger_cars.main()
    ingot_cars.main()
    intermodal_cars.main()
    kaolin_hopper_cars.main()
    livestock_cars.main()
    log_cars.main()
    # low_floor_automobile_cars.main()
    low_floor_intermodal_cars.main()
    mail_cars.main()
    merchandise_box_cars.main()
    merchandise_open_cars.main()
    mineral_covered_hopper_cars.main()
    # mineral_hopper_cars.main()
    mgr_hopper_cars.main()
    ore_dump_cars.main()
    ore_hopper_cars.main()
    open_cars.main()
    passenger_cars.main()
    peat_cars.main()
    plate_cars.main()
    pressure_tank_cars.main()
    product_tank_cars.main()
    reefer_cars.main()
    restaurant_cars.main()
    railbus_passenger_trailer_cars.main()
    railcar_passenger_trailer_cars.main()
    randomised_box_cars.main()
    randomised_bulk_cars.main()
    randomised_cold_metal_cars.main()
    randomised_dump_cars.main()
    randomised_flat_cars.main()
    randomised_hopper_cars.main()
    randomised_open_cars.main()
    randomised_piece_goods_cars.main()
    randomised_chemicals_tank_cars.main()
    rock_hopper_cars.main()
    roller_roof_hopper_cars.main()
    silo_cars.main()
    scrap_metal_cars.main()
    skip_cars.main()
    slag_ladle_cars.main()
    sliding_roof_cars.main()
    sliding_wall_cars.main()
    suburban_passenger_cars.main()
    swing_roof_hopper_cars.main()
    tank_cars.main()
    tarpaulin_cars.main()
    torpedo_cars.main()
    vehicle_parts_box_cars.main()
