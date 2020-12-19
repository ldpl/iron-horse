# spritelayer cargos are sandboxed into their own module to avoid them spawning tentacles into gestalt graphics, global constants, train.py etc

# this is *specifically* cargos that look like vehicles (trucks etc to suit FIRS automotive chain) *not* general cargos to go on vehicles, confusing eh?

from gestalt_graphics.pipelines import GenerateCompositedVehiclesCargos
from gestalt_graphics.gestalt_graphics import GestaltGraphicsIntermodal


class VehiclesCargoGestalt(object):
    """ Sparse class to hold vehicles cargos gestalts """

    # a gestalt is a set of vehicles cargos (trucks etc.) of specific length and appearance
    # each set corresponds to a spritesheet which will be generated by the graphics processor
    # each set is used for a specific group of cargo labels
    # ====== #

    # each gestalt is named for a type of vehicles cargo, e.g. trucks, cars, tractors, bulldozers etc
    # each gestalt is for a specific length, 16px, 24px, 32px
    # each gestalt has variants
    # each variant is composed from source spritesheets
    # e.g. small truck cc, small truck blue, box truck, etc
    # each variant has n rows, corresponding to a standard number of date changes
    # the date change rows are provided directly in each source spritesheet
    # each variant is asssociated with one of the templates that contain location pixels for the cargo sprites

    # there is a mapping of gestalts to cargo labels and a default

    # !!!!!! are these up to date for vehicles - remove this when done !!!!!

    # each container set may have one or more spriterows
    # spriterows are chosen randomly when vehicles load new cargo
    # rows are composed by the graphics processor, and may include variations for
    # - combinations of container lengths
    # - combinations of container types
    # - container colours
    # !!! containers are going to need 'base sets' to allow double stack, cropped for well cars etc
    # !!! the consist needs to encode the set type to fetch the right spritesets
    # !!! base sets will also have to be encoded in gestalts here, unless they're done by (sets * gestalts) combinatorially?
    def __init__(self, vehicles_cargo_subtype):
        self.pipeline = GenerateCompositedVehiclesCargos()
        self.vehicles_cargo_subtype = vehicles_cargo_subtype

    @property
    def floor_height_variants(self):
        # !! this is refactored to use platform_types in intermodal pipeline

        # used to handle, e.g. low floor, narrow gauge etc by putting a yoffset in the generated container sprites
        # extend to accomodate double stack later (only one floor height probably)?
        # format is (label, yoffset for floor-height) - leave floor height as 0 for default floor heights
        return (("default", 0), ("low_floor", 1))

    @property
    def id(self):
        return (
            "vehicles_cargo_"
            + self.vehicles_cargo_subtype
            + "_"
            + str(self.length)
            + "px"
        )


class Trucks16px(VehiclesCargoGestalt):
    def __init__(self, vehicles_cargo_subtype):
        super().__init__(vehicles_cargo_subtype)
        self.length = 16
        self.variants = [["trucks_1_1CC"], ["trucks_1_1CC"], ["trucks_1_1CC"]]


class Trucks24px(VehiclesCargoGestalt):
    def __init__(self, vehicles_cargo_subtype):
        super().__init__(vehicles_cargo_subtype)
        self.length = 24
        self.variants = [["trucks_1_1CC", "trucks_1_1CC"], ["trucks_1_1CC"]]


class Trucks32px(VehiclesCargoGestalt):
    def __init__(self, vehicles_cargo_subtype):
        super().__init__(vehicles_cargo_subtype)
        self.length = 32
        self.variants = [
            ["trucks_1_1CC", "trucks_1_1CC", "trucks_1_1CC"],
            ["trucks_1_1CC", "trucks_1_1CC", "trucks_1_1CC"],
        ]


def get_container_gestalts_by_length(vehicle_length):
    result = []
    for container_gestalt in registered_container_gestalts:
        if container_gestalt.length == 4 * vehicle_length:
            result.append(container_gestalt)
    return result


registered_container_gestalts = []

vehicles_cargo_type_gestalt_mapping = {"box": [Trucks16px, Trucks24px, Trucks32px]}


def register_container_gestalt(vehicles_cargo_type, vehicles_cargo_subtype):
    for gestalt in vehicles_cargo_type_gestalt_mapping[vehicles_cargo_type]:
        registered_container_gestalts.append(gestalt(vehicles_cargo_subtype))


def main():
    # yeah this is fiddly
    # we need to generate both cargo-specific sprites (visible cargo or specific recolour
    # and semi-generic fallback sprites, with specific type of container - tank, box, etc (and generic cargo and/or default recolour)
    # first do the defaults, which will be named xxxxxx_DFLT

    # !! not clear that we need the subtypes in this way, there's no cargo-specific variation once we're into the vehicles_cargo_type

    for vehicles_cargo_type in vehicles_cargo_type_gestalt_mapping.keys():
        if vehicles_cargo_type not in [
            "bulk"
        ]:  # exclude some types which have no meaningful default (and will fall back to box)
            vehicles_cargo_subtype = vehicles_cargo_type + "_DFLT"
            register_container_gestalt(vehicles_cargo_type, vehicles_cargo_subtype)

    """
    commented by design, this is just for debugging / project management
    # for knowing how many containers combinations we have in total
    total = 0
    for gestalt in registered_container_gestalts:
        total += len(gestalt.variants)
    print('total variants', total)
    """
