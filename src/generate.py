from datetime import date
from pathlib import Path

import grf
from grf import TRAIN, RV, SHIP, AIRCRAFT, STATION, CANAL, BRIDGE, HOUSE, GLOBAL_VAR, INDUSTRY_TILE, INDUSTRY, CARGO, SOUND_EFFECT, AIRPORT, SIGNAL, OBJECT, RAILTYPE, AIRPORT_TILE, ROADTYPE, TRAMTYPE
from grf import Ref, CB, ImageFile, FileSprite, RAWSound, TrainFlags

# ---------- horse guts -----------

import math

import utils
from gestalt_graphics.gestalt_graphics import (
    GestaltGraphics,
    GestaltGraphicsVisibleCargo,
    GestaltGraphicsBoxCarOpeningDoors,
    GestaltGraphicsEngine,
    GestaltGraphicsCaboose,
    GestaltGraphicsSimpleBodyColourRemaps,
    GestaltGraphicsOnlyAddPantographs,
    GestaltGraphicsRandomisedWagon,
    GestaltGraphicsConsistSpecificLivery,
    GestaltGraphicsIntermodalContainerTransporters,
    GestaltGraphicsAutomobilesTransporter,
    GestaltGraphicsCustom,
)
import gestalt_graphics.graphics_constants as graphics_constants
from vehicles import numeric_id_defender
from rosters import registered_rosters
import global_constants


class Consist(grf.SpriteGenerator):
    """
    'Vehicles' (appearing in buy menu) are composed as articulated consists.
    Each consist comprises one or more 'units' (visible).
    """

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", None)
        # setup properties for this consist (props either shared for all vehicles, or placed on lead vehicle of consist)
        # private var, used to store a name substr for engines, composed into name with other strings as needed
        self._name = kwargs.get("name", None)
        self.base_numeric_id = kwargs.get("base_numeric_id", None)
        # roster is set when the vehicle is registered to a roster, only one roster per vehicle
        # persist roster id for lookups, not roster obj directly, because of multiprocessing problems with object references
        self.roster_id = kwargs.get("roster_id")  # just fail if there's no roster
        # either gen xor intro_date is required, don't set both, one will be interpolated from the other
        self._intro_date = kwargs.get("intro_date", None)
        self._gen = kwargs.get("gen", None)
        # if gen is used, the calculated intro date can be adjusted with +ve or -ve offset
        self.intro_date_offset = kwargs.get("intro_date_offset", None)
        # used for synchronising / desynchronising intro dates for groups vehicles, see https://github.com/OpenTTD/OpenTTD/pull/7147
        self._intro_date_days_offset = (
            None  # defined in subclasses, no need for instances to define this
        )
        self.vehicle_life = kwargs.get("vehicle_life", 40)
        #  most consists are automatically replaced by the next consist in the role tree
        # ocasionally we need to merge two branches of the role, in this case set replacement consist id
        self._replacement_consist_id = kwargs.get("replacement_consist_id", None)
        # default loading speed multiplier, over-ride in subclasses as needed
        self._loading_speed_multiplier = 1
        self.power = kwargs.get("power", 0)
        self.base_track_type = kwargs.get("base_track_type", "RAIL")
        # modify base_track_type for electric engines when writing out the actual rail type
        # without this, RAIL and ELRL have to be specially handled whenever a list of compatible consists is wanted
        # this *does* need a specific flag, can't rely on unit visual effect or unit engine type props - they are used for other things
        self.requires_electric_rails = (
            False  # set by unit subclasses as needed, not a kwarg
        )
        self.tractive_effort_coefficient = kwargs.get(
            "tractive_effort_coefficient", 0.3
        )  # 0.3 is recommended default value
        # private var, can be used to over-rides default (per generation, per class) speed
        self._speed = kwargs.get("speed", None)
        # used by multi-mode engines such as electro-diesel, otherwise ignored
        self.power_by_railtype = kwargs.get("power_by_railtype", None)
        # some engines require pantograph sprites composited, don't bother setting this unless required
        self.pantograph_type = kwargs.get("pantograph_type", None)
        self.dual_headed = kwargs.get("dual_headed", False)
        self.tilt_bonus = False  # over-ride in subclass as needed
        self.lgv_capable = False  # over-ride in subclass as needed
        # solely used for ottd livery (company colour) selection, set in subclass as needed
        self.train_flag_mu = False
        # some wagons will provide power if specific engine IDs are in the consist
        self.wagons_add_power = False
        self.buy_menu_hint_wagons_add_power = False
        # some vehicles will get a higher speed if hauled by an express engine (use rarely)
        self.easter_egg_haulage_speed_bonus = kwargs.get(
            "easter_egg_haulage_speed_bonus", False
        )
        # engines will automatically detemine role string, but to force it on certain coach/wagon types use _buy_menu_role_string
        self._buy_menu_role_string = None
        # simple buy menu hint flag for driving cabs
        self.buy_menu_hint_driving_cab = False
        # simple buy menu hint flag for restaurant cars
        self.buy_menu_hint_restaurant_car = False
        # random_reverse means (1) randomised reversing of sprites when vehicle is built (2) player can also flip vehicle
        # random_reverse is not supported in some templates
        self.random_reverse = kwargs.get("random_reverse", False)
        # random_reverse vehicles can always be flipped, but flip can also be set in other cases (by subclass, or directly by consist)
        self.allow_flip = kwargs.get("allow_flip", self.random_reverse)
        # just a simple buy cost tweak, only use when needed
        self.electro_diesel_buy_cost_malus = None
        # arbitrary multiplier to the calculated buy cost, e.g. 1.1, 0.9 etc
        # set to 1 by default, over-ride in subclasses as needed
        self.buy_cost_adjustment_factor = 1
        # fixed (baseline) buy costs on this subtype, 10 points
        # leave this alone except for edge cases (e.g. driving van trailers which are implemented as engines, but need wagon costs)
        self.fixed_buy_cost_points = 10
        # arbitrary multiplier to the calculated run cost, e.g. 1.1, 0.9 etc
        # set to 1 by default, over-ride in subclasses as needed
        self.floating_run_cost_multiplier = 1
        # fixed (baseline) run costs on this subtype, 100 points
        self.fixed_run_cost_points = 30  # default, over-ride in subclass as needed
        # create structure to hold the units
        self.units = []
        # one default cargo for the whole consist, no mixed cargo shenanigans, it fails with auto-replace
        self.default_cargos = []
        self.class_refit_groups = []
        self.label_refits_allowed = []
        self.label_refits_disallowed = []
        # create a structure for cargo /livery graphics options
        self.gestalt_graphics = GestaltGraphics()
        # option to provide automatic roof for all units in the consist, leave as None for no generation
        self.roof_type = None
        # role is e.g. Heavy Freight, Express etc, and is used to automatically set model life as well as in docs
        self.role = kwargs.get("role", None)
        # role child branch num places this vehicle on a specific child branch of the tech tree, where the role is the parent branch
        # 1..n for branches with calculated replacements, -1..-n for jokers which are not automatically replaced in the tree, 0 reserved
        self.role_child_branch_num = kwargs.get("role_child_branch_num", 0)
        # optionally suppress nmlc warnings about animated pixels for consists where they're intentional
        self.suppress_animated_pixel_warnings = kwargs.get(
            "suppress_animated_pixel_warnings", False
        )
        # extended description (and a cite from a made up person) for docs etc
        self.description = """"""  # to be set per vehicle, multi-line supported
        self._cite = ""  # optional, set per subclass as needed
        # for 'inspired by' stuff
        self.foamer_facts = """"""  # to be set per vehicle, multi-line supported
        # occasionally we want to force a specific spriterow for docs, not needed often, set in kwargs as needed, see also buy_menu_spriterow_num
        self.docs_image_spriterow = kwargs.get(
            "docs_image_spriterow", 0
        )  # 0 indexed spriterows, position in generated spritesheet
        # aids 'project management'
        self.sprites_complete = kwargs.get("sprites_complete", False)

    def add_unit(self, type, repeat=1, **kwargs):
        unit = type(consist=self, **kwargs)
        count = len(self.unique_units)
        if count == 0:
            # first vehicle gets no numeric id suffix - for compatibility with buy menu list ids etc
            unit.id = self.id
        else:
            unit.id = self.id + "_" + str(count)
        unit.numeric_id = self.get_and_verify_numeric_id(count)
        for repeat_num in range(repeat):
            self.units.append(unit)

    @property
    def unique_units(self):
        # units may be repeated in the consist, sometimes we need an ordered list of unique units
        # set() doesn't preserve list order, which matters, so do it the hard way
        unique_units = []
        for unit in self.units:
            if unit not in unique_units:
                unique_units.append(unit)
        return unique_units

    @property
    def unique_spriterow_nums(self):
        # find the unique spriterow numbers, used in graphics generation
        result = []
        for unit in set([unit.spriterow_num for unit in self.units]):
            result.append(unit)
            # extend with alternative cc livery if present, spritesheet format assumes unit_1_default, unit_1_alternative_cc_livery, unit_2_default, unit_2_alternative_cc_livery if present
            if self.gestalt_graphics.alternative_cc_livery is not None:
                result.append(unit + 1)
        return result

    def get_and_verify_numeric_id(self, offset):
        numeric_id = self.base_numeric_id + offset
        # guard against the ID being too large to build in an articulated consist
        if numeric_id > 16383:
            utils.echo_message(
                "Error: numeric_id "
                + str(numeric_id)
                + " for "
                + self.id
                + " can't be used (16383 is max ID for articulated vehicles)"
            )
        # non-blocking guard on duplicate IDs
        for id in numeric_id_defender:
            if id == numeric_id:
                utils.echo_message(
                    "Error: consist "
                    + self.id
                    + " unit id collides ("
                    + str(numeric_id)
                    + ") with units in another consist"
                )
        numeric_id_defender.append(numeric_id)
        return numeric_id

    @property
    def reversed_variants(self):
        # Handles 'unreversed' and optional 'reversed' variant, which if provided, will be chosen at random per consist
        # NOT the same as 'flipped' which is a player choice in-game, and handled separately
        # Previous model_variant approach for this was deprecated March 2018, needlessly complicated
        result = ["unreversed"]
        if self.random_reverse:
            result.append("reversed")
        return result

    @property
    def name(self):
        if self.str_name_suffix is not None:
            return (
                "string(STR_NAME_CONSIST_PARENTHESES, string(STR_NAME_"
                + self.id
                + "), string("
                + self.str_name_suffix
                + "))"
            )
        else:
            return "string(STR_NAME_" + self.id + ")"

    def engine_varies_power_by_railtype(self, vehicle):
        if self.power_by_railtype is not None and vehicle.is_lead_unit_of_consist:
            # as of Dec 2018, can't use both variable power and wagon power
            # that could be changed if https://github.com/OpenTTD/OpenTTD/pull/7000 is done
            # would require quite a bit of refactoring though eh
            assert self.wagons_add_power == False, (
                "%s consist has both engine_varies_power_by_railtype and power_by_railtype, which conflict"
                % self.id
            )
            return True
        else:
            return False

    @property
    def buy_cost(self):
        # stub only
        # vehicle classes should over-ride this to provide class-appropriate cost calculation
        return 0

    @property
    def running_cost(self):
        # stub only
        # vehicle classes should over-ride this to provide class-appropriate running cost calculation
        return 0

    @property
    def intro_date(self):
        # automatic intro_date, but can over-ride by passing in kwargs for consist
        if self._intro_date:
            assert self._gen == None, (
                "%s consist has both gen and intro_date set, which is incorrect"
                % self.id
            )
            assert self.intro_date_offset == None, (
                "%s consist has both intro_date and intro_date_offset set, which is incorrect"
                % self.id
            )
            return self._intro_date
        else:
            assert self._gen != None, (
                "%s consist has neither gen nor intro_date set, which is incorrect"
                % self.id
            )
            result = self.roster.intro_dates[self.base_track_type][self.gen - 1]
            if self.intro_date_offset is not None:
                result = result + self.intro_date_offset
            return result

    @property
    def intro_date_days_offset(self):
        # days offset is used to control *synchronising* (or not) intro dates across groups of vehicles where needed
        # see https://github.com/OpenTTD/OpenTTD/pull/7147 for explanation
        # this does *not* use the role group mapping in global constants, as it's more fragmented to avoid too many new vehicle messages at once
        # JOKERS: note that not all jokers have to be in the jokers group here, they can be in other groups if intro dates need to sync
        role_to_role_groups_mapping = {
            "express_core": {
                "express": [1],
                "heavy_express": [1],
                "super_heavy_express": [1],
            },
            "express_non_core": {
                "branch_express": [1, 2, -2],
                "express": [2],
                "heavy_express": [2, 3, 4, 5],
                "super_heavy_express": [2, 3],
                "express_pax_railcar": [-1],
            },
            "driving_cab": {
                "driving_cab_express_pax": [-1],
                "driving_cab_express_mail": [-1],
                "driving_cab_express_mixed": [-1],
            },
            "freight_core": {
                "freight": [1],
                "heavy_freight": [1],
                "super_heavy_freight": [1],
            },
            "freight_non_core": {
                "branch_freight": [1, 2],
                "freight": [2],
                "heavy_freight": [2, 3, 4],
                "super_heavy_freight": [2],
            },
            "hst": {"hst": [1, 2]},
            "jokers": {
                "gronk!": [-1, -2],
                "branch_express": [-1],
                "express": [-1],
                "heavy_express": [-1, -2, -3, -4],
                "super_heavy_express": [-1, -2, -3],
                "freight": [-1, -2],
                "branch_freight": [-1],
                "heavy_freight": [-1, -2, -3, -4],
                "super_heavy_freight": [-1, -2],
                "snoughplough!": [-1],
            },
            "metro": {"mail_metro": [1], "pax_metro": [1]},
            "railcar": {
                "mail_railcar": [1, 2, -1, -2],
                "pax_railbus": [1, -1],
                "pax_railcar": [1, 2],
            },
            "very_high_speed": {"very_high_speed": [1, 2, 3]},
            "universal": {"universal": [1, 2]},
        }
        if self.gen == 1:
            # to ensure a fully playable roster is available for gen 1, force the days offset to 0
            # for explanation see https://www.tt-forums.net/viewtopic.php?f=26&t=68616&start=460#p1224299
            return 0
        elif self._intro_date_days_offset is not None:
            # offset defined in class (probably a wagon)
            return self._intro_date_days_offset
        else:
            result = None
            # assume role is defined (_probably_ fine)
            for group_key, group_role_list in role_to_role_groups_mapping.items():
                if self.role in group_role_list.keys():
                    if self.role_child_branch_num in group_role_list[self.role]:
                        result = global_constants.intro_date_offsets_by_role_group[
                            group_key
                        ]
            # check we actually got a result
            assert result != None, "no role group found for role %s for consist %s" % (
                self.role,
                self.id,
            )
        return result

    @property
    def gen(self):
        # gen is usually set in the vehicle, but can be left unset if intro_date is set
        if self._gen:
            assert self._intro_date == None, (
                "%s consist has both gen and intro_date set, which is incorrect"
                % self.id
            )
            return self._gen
        else:
            assert self._intro_date != None, (
                "%s consist has neither gen nor intro_date set, which is incorrect"
                % self.id
            )
            for gen_counter, intro_date in enumerate(
                self.roster.intro_dates[self.base_track_type]
            ):
                if self.intro_date < intro_date:
                    return gen_counter
            # if no result is found in list, it's last gen
            return len(self.roster.intro_dates[self.base_track_type])

    @property
    def equivalent_ids_alt_var_41(self):
        # only implemented in subclasses that require it - easiest thing when writing it, change if needed
        return None

    @property
    def replacement_consist(self):
        # option exists to force a replacement consist, this is used to merge tech tree branches
        if self.role_child_branch_num == 0:
            print("OOF", self.id, self.role_child_branch_num)

        if self._replacement_consist_id is not None:
            for consist in self.roster.engine_consists:
                if consist.id == self._replacement_consist_id:
                    return consist
            # if we don't return a valid result, that's an error, probably a broken replacement id
            raise Exception(
                "replacement consist id "
                + self._replacement_consist_id
                + " not found for consist "
                + self.id
            )
        else:
            similar_consists = []
            replacement_consist = None
            for consist in self.roster.engine_consists:
                if (
                    (consist.role == self.role)
                    and (consist.role_child_branch_num == self.role_child_branch_num)
                    and (consist.base_track_type == self.base_track_type)
                ):
                    similar_consists.append(consist)
            for consist in sorted(
                similar_consists, key=lambda consist: consist.intro_date
            ):
                if consist.intro_date > self.intro_date:
                    replacement_consist = consist
                    break
            return replacement_consist

    @property
    def replaces_consists(self):
        # note that this depends on replacement_consist property in other consists, and may not work in all cases
        # a consist can replace more than one other consist
        result = []
        for consist in self.roster.engine_consists:
            if consist.replacement_consist is not None:
                if consist.replacement_consist.id == self.id:
                    result.append(consist)
        return result

    @property
    def similar_consists(self):
        # quite a crude guess at similar engines by role
        result = []
        for consist in self.roster.engine_consists:
            if (
                (consist.base_track_type == self.base_track_type)
                and (consist.gen == self.gen)
                and (consist != self)
            ):
                if (
                    (consist.role == self.role)
                    or (0 <= (consist.power - self.power) < 500)
                    or (0 <= (self.power - consist.power) < 500)
                ):
                    result.append(consist)
        return result

    @property
    def model_life(self):
        if self.replacement_consist is None:
            return 0xff  # "VEHICLE_NEVER_EXPIRES"
        else:
            return self.replacement_consist.intro_date - self.intro_date

    @property
    def retire_early(self):
        # affects when vehicle is removed from buy menu (in combination with model life)
        # to understand why this is needed see https://newgrf-specs.tt-wiki.net/wiki/NML:Vehicles#Engine_life_cycle
        # retire at end of model life + 10 (fudge factor - no need to be more precise than that)
        return -10

    @property
    def track_type(self):
        # are you sure you don't want base_track_type instead? (generally you do want base_track_type)
        # track_type handles converting base_track_type to an actual railtype label
        # this is done by looking up a railtype mapping in global constants, via internal labels
        # e.g. electric engines with "RAIL" as base_track_type will be translated to "ELRL"
        # narrow gauge trains will be similarly have "NG" translated to an appropriate NG railytpe label
        if self.requires_electric_rails:
            # for electrified vehicles, translate base_track_type before getting the mapping to labels
            # iff electrification types ever gain subtypes (AC, DC, etc), add further checks here
            mapping_key = self.base_track_type + "_ELECTRIFIED"
        else:
            mapping_key = self.base_track_type
        valid_railtype_labels = global_constants.base_track_type_to_railtype_mapping[
            mapping_key
        ]
        # assume that the label we want for the vehicle is the first in the list of valid types (the rest are fallbacks if the first railtype is missing)
        result = valid_railtype_labels[0]
        # set modifiers on the label by modifying the last byte
        # modifiers are not orthogonal and the byte can only be set to a single value
        # if multiple modifiers need to be combined, that needs to be explicitly handled
        # generally that would be a sign we're doing something unwise and with combinatorial problems
        modifier = "_"
        if self.lgv_capable:
            modifier = "A"
        result = result[0:3] + modifier
        return result

    def get_speed_by_class(self, speed_class):
        # automatic speed, but can over-ride by passing in kwargs for consist
        speeds_by_track_type = self.roster.speeds[self.base_track_type]
        return speeds_by_track_type[speed_class][self.gen - 1]

    @property
    def speed(self):
        if self._speed:
            return self._speed
        elif getattr(self, "speed_class", None):
            # speed by class, if speed_class is set explicitly (and not None)
            # !! this doesn't handle RAIL / ELRL correctly
            # could be fixed by checking a list of railtypes
            return self.get_speed_by_class(self.speed_class)
        elif self.role:
            # first check for express roles, which are determined by multiple role groups
            for role_group_mapping_key in ["express", "driving_cab", "express_railcar"]:
                group_roles = global_constants.role_group_mapping[
                    role_group_mapping_key
                ]
                if self.role in group_roles:
                    return self.get_speed_by_class("express")
            # then check other specific roles
            if self.role in ["mail_railcar", "pax_railcar"]:
                return self.get_speed_by_class("suburban")
            elif self.role in ["hst"]:
                return self.get_speed_by_class("hst")
            elif self.role in ["very_high_speed"]:
                return self.get_speed_by_class("very_high_speed")
            else:
                return self.get_speed_by_class("standard")
        else:
            # assume no speed limit
            return None

    @property
    def speed_on_lgv(self):
        if not self.lgv_capable:
            raise Exception(
                self.id, "is not lgv capable, but is attempting to set speed on lgv"
            )

        # mildly JDFI hacky
        if self.role in ["hst"]:
            return self.get_speed_by_class("hst_on_lgv")
        elif self.role in ["very_high_speed"]:
            return self.get_speed_by_class("very_high_speed_on_lgv")
        else:
            return self.get_speed_by_class(self.speed_class + "_on_lgv")

    @property
    def power_speed_ratio(self):
        # used in docs, as a way of comparing performance between vehicles, especially across generations in same branch of tech tree
        # see also: http://cs.trains.com/trn/f/111/t/188661.aspx
        # "on a 1% grade, MPH / 18.75 = HP (per ton); the HP requirement will increase roughly proportionally to the grade and speed."
        if self.power is None or self.speed is None:
            return None
        else:
            return int(self.power / self.speed)

    @property
    def weight(self):
        return sum([getattr(unit, "weight", 0) for unit in self.units])

    @property
    def length(self):
        # total length of the consist
        return sum([unit.vehicle_length for unit in self.units])

    @property
    def loading_speed_multiplier(self):
        # over-ride in subclass as needed
        return self._loading_speed_multiplier

    @property
    def roster(self):
        for roster in registered_rosters:
            if roster.id == self.roster_id:
                return roster
        else:
            raise Exception("no roster found for ", self.id)

    def get_expression_for_availability(self):
        result = []
        # rosters: the working definition is one and only one roster per vehicle
        result.append("param[1]==" + str(self.roster.numeric_id - 1))
        if self.joker:
            result.append("param_simplified_gameplay==0")
        return " && ".join(result)

    def get_nml_expression_for_default_cargos(self):
        # sometimes first default cargo is not available, so we use a list
        # this avoids unwanted cases like box cars defaulting to mail when goods cargo not available
        # if there is only one default cargo, the list just has one entry, that's no problem
        if len(self.default_cargos) == 1:
            return self.default_cargos[0]
        else:
            # build stacked ternary operators for cargos
            result = self.default_cargos[-1]
            for cargo in reversed(self.default_cargos[0:-1]):
                result = 'cargotype_available("' + cargo + '")?' + cargo + ":" + result
            return result

    def get_nml_expression_for_tile_powers_railtype(self):
        # 1) all railtypes must be known in the railtypetable (by brute force if necessary)
        # 2) extend this as necessary in future if more fine-grained checks are needed specific to the consist
        # 3) if procedure support is needed, make that parameterised for the appropriate railtypes to the consist
        # for example, adding IHE_ for electrified narrow gauge would be relevant
        # this could also interrogate the vehicle label to find the appropriate types to add
        # but that would need to be cautious about e.g. electro-diesel has tracktype IHA_, but would need IHB_ and ELRL here
        # so perhaps Yet Another Mapping for table lookup
        railtypes_to_check = ["ELRL", "IHB_"]
        result = []
        for railtype in railtypes_to_check:
            result.append('tile_powers_railtype("' + railtype + '")')
        result = " || ".join(result)
        result = "[" + result + "]"
        return result

    @property
    def buy_menu_x_loc(self):
        # automatic buy menu sprite if single-unit consist
        # extend this to check an auto_buy_menu_sprite property if manual over-rides are needed in future
        if len(self.units) > 1:
            # custom buy menu sprite for articulated vehicles
            return 360
        elif (
            self.gestalt_graphics.__class__.__name__ == "GestaltGraphicsRandomisedWagon"
        ):
            # possibly fragile class name check, but eh
            return 360
        else:
            # default to just using 6th angle of vehicle
            return global_constants.spritesheet_bounding_boxes_asymmetric_unreversed[6][
                0
            ]

    @property
    def buy_menu_width(self):
        # max sensible width in buy menu is 64px
        if 4 * self.length < 64:
            return 4 * self.length
        else:
            return 64

    @property
    def num_sprite_layers(self):
        # always at least one layer
        result = 1
        # order of adding extra layers doesn't matter here, it's just a number,
        # the switch chain for the vehicle type will need to take care of switching to correct layers
        # gestalt may add extra sprites layer for e.g. visible cargo, vehicle masks
        if (
            getattr(
                self.gestalt_graphics, "num_extra_layers_for_spritelayer_cargos", None
            )
            != None
        ):
            result = (
                result + self.gestalt_graphics.num_extra_layers_for_spritelayer_cargos
            )
        # add a layer for a masked overlay as needed (usually applied over cargo sprites)
        if self.gestalt_graphics.add_masked_overlay:
            result = result + 1
        # add a layer for pantographs as needed, note this is not done in the gestalt as it's more convenient to treat separarely
        if self.pantograph_type is not None:
            result = result + 1
        # OpenTTD has a limited number of layers in the sprite stack, we can't exceed them
        if result > 8:
            raise Exception("Too many sprite layers ", result, " defined for ", self.id)
        return result

    def get_nml_for_spriteset_template(self, y_offset):
        template_subtype = "dual_headed" if self.dual_headed else "default"
        args = []
        args.append(self.buy_menu_x_loc)
        args.append(10 + y_offset)
        args.append(1 + self.buy_menu_width)  # add 1 to account for buffers / couplers
        args.append(-1 * int(self.buy_menu_width / 2))  # x_offset
        args.append("ANIM" if self.suppress_animated_pixel_warnings else "NOANIM")
        return (
            "spriteset_template_purchase_"
            + template_subtype
            + "("
            + ",".join([str(arg) for arg in args])
            + ")"
        )

    def get_buy_menu_format(self, vehicle):
        # keep the template logic simple, present strings for a switch/case tree
        # variable_power and wagons_add_power are mutually exclusive (asserted by engine_varies_power_by_railtype as of August 2019)
        if self.engine_varies_power_by_railtype(vehicle):
            return "variable_power"
        elif self.lgv_capable:
            # yeah, simplicity failed when lgv_capable was added, this simple tree needs rethought to allow better composition of arbitrary strings
            if self.buy_menu_hint_wagons_add_power:
                return "lgv_capable_and_wagons_add_power"
            else:
                return "lgv_capable"
        elif self.buy_menu_hint_driving_cab:
            return "driving_cab"
        elif self.buy_menu_hint_restaurant_car:
            return "restaurant_car"
        else:
            return "default"

    def get_buy_menu_string(self, vehicle):
        result = []
        # optional string if engine varies power by railtype
        if self.engine_varies_power_by_railtype(vehicle):
            result.append("STR_POWER_BY_RAILTYPE")
        # optional string if consist is lgv-capable
        if self.lgv_capable:
            result.append("STR_SPEED_BY_RAILTYPE_LGV_CAPABLE")
        # optional string if dedicated wagons add power
        if self.buy_menu_hint_wagons_add_power:
            result.append(self.buy_menu_distributed_power_substring)

        # engines will always show a role string
        # !! this try/except is all wrong, I just want to JFDI to add buy menu strings to wagons which previously didn't support them, and can do regret later
        # !! this may not be used / or required as of April 2021 - _buy_menu_role_string is available instead
        try:
            result.append(self.buy_menu_role_string)
        except:
            pass

        # some wagons (mostly railcar trailers and pax coaches) might want to show an optional role string
        if self._buy_menu_role_string is not None:
            result.append("STR_ROLE, string(" + self._buy_menu_role_string + ")")

        # driving cab hint comes after role string
        if self.buy_menu_hint_driving_cab:
            result.append("STR_BUY_MENU_HINT_DRIVING_CAB")

        # driving cab hint comes after role string
        if self.buy_menu_hint_restaurant_car:
            result.append("STR_BUY_MENU_HINT_RESTAURANT_CAR")

        if len(result) == 1:
            return "STR_BUY_MENU_WRAPPER_ONE_SUBSTR, string(" + result[0] + ")"
        if len(result) == 2:
            return (
                "STR_BUY_MENU_WRAPPER_TWO_SUBSTR, string("
                + result[0]
                + "), string("
                + result[1]
                + ")"
            )
        if len(result) == 3:
            return (
                "STR_BUY_MENU_WRAPPER_THREE_SUBSTR, string("
                + result[0]
                + "), string("
                + result[1]
                + "), string("
                + result[2]
                + ")"
            )
        # should never be reached, extend this if we do
        raise Exception("Unsupported number of buy menu strings for ", self.id)

    @property
    def buy_menu_role_string(self):
        for role_group, roles in global_constants.role_group_mapping.items():
            if self.role in roles:
                return (
                    "STR_ROLE, string("
                    + global_constants.role_string_mapping[role_group]
                    + ")"
                )
        raise Exception("no role string found for ", self.id)

    @property
    def cite(self):
        # this assumes that NG and Metro always return the same, irrespective of consist cite
        # that makes sense for Pony roster, but might not work in other rosters, deal with that if it comes up eh?
        # don't like how much content (text) is in code here, but eh
        if self.base_track_type == "NG":
            cite_name = "Roberto Flange"
            cite_titles = [
                "Narrow Gauge Superintendent",
                "Works Manager (Narrow Gauge)",
                "Traction Controller, Narrow Gauge Lines",
            ]
        elif self.base_track_type == "METRO":
            cite_name = "JJ Transit"
            cite_titles = [
                "Superintendent (Metro Division)",
                "Chief Engineer, Mass Mobility Systems",
            ]
        else:
            if self._cite == "Arabella Unit":
                cite_name = self._cite
                cite_titles = [
                    "General Manager (Railcars)",
                    "Senior Engineer, Self-Propelled Traction",
                    "Director, Suburban and Rural Lines",
                ]
            elif self._cite == "Dr Constance Speed":
                cite_name = self._cite
                cite_titles = [
                    "Lead Engineer, High Speed Projects",
                    "Director, Future Traction Concepts",
                ]
            else:
                cite_name = "Mr Train"
                cite_titles = [
                    "Acting Superintendent of Engines",
                    "Provisional Chief Engineer",
                    "Interim Head of Works",
                    "Transitional General Manager (Traction)",
                ]
        return cite_name + ", " + random.choice(cite_titles)

    def render_articulated_switch(self, templates):
        if len(self.units) > 1:
            template = templates["articulated_parts.pynml"]
            nml_result = template(consist=self, global_constants=global_constants)
            return nml_result
        else:
            return ""

    def freeze_cross_roster_lookups(self):
        # graphics processing can't depend on roster object reliably, as it blows up multiprocessing (can't pickle roster), for reasons I never figured out
        # this freezes any necessary roster items in place
        self.frozen_roster_items = {}
        if self.gestalt_graphics.__class__.__name__ == "GestaltGraphicsRandomisedWagon":
            self.frozen_roster_items[
                "wagon_randomisation_candidates"
            ] = self.roster.get_wagon_randomisation_candidates(self)
        # no return

    def assert_speed(self):
        # speed is assumed to be limited to 200mph
        # this isn't an OpenTTD limit, it's used to give a scale for buy and run cost spreads
        if self.speed is not None:
            if self.speed > 200:
                utils.echo_message(
                    "Consist " + self.id + " has speed > 200, which is too much"
                )

    def assert_power(self):
        # power is assumed to be limited to 10,000hp
        # this isn't an OpenTTD limit, it's used to give a scale for buy and run cost spreads
        if self.speed is not None:
            if self.power > 10000:
                utils.echo_message(
                    "Consist " + self.id + " has power > 10000hp, which is too much"
                )

    def assert_weight(self):
        # weight is assumed to be limited to 500t
        # this isn't an OpenTTD limit, it's used to give a scale for buy and run cost spreads
        if self.weight is not None:
            if self.weight > 500:
                utils.echo_message(
                    "Consist " + self.id + " has weight > 500t, which is too much"
                )

    def assert_description_foamer_facts(self):
        # if these are too noisy, comment them out temporarily
        if self.power > 0:
            if len(self.description) == 0:
                utils.echo_message("Consist " + self.id + " has no description")
            if len(self.foamer_facts) == 0:
                utils.echo_message("Consist " + self.id + " has no foamer_facts")
            if "." in self.foamer_facts:
                utils.echo_message(
                    "Consist " + self.id + " foamer_facts has a '.' in it."
                )

    def get_sprites(self, g):
        self.assert_speed()
        self.assert_power()
        return sum((u.get_sprites(g) for u in self.unique_units), [])
        # templating
        # nml_result = ""
        # if len(self.units) > 1:
        #     nml_result = nml_result + self.render_articulated_switch(templates)
        # for unit in self.unique_units:
        #     nml_result = nml_result + unit.render(templates)
        # return nml_result

        # Check in case property was changed after add_articulated
        # if self._props.get('is_dual_headed') and self._articulated_parts:
        #     raise RuntimeError('Articulated parts are not allowed for dual-headed engines (vehicle id {self.id})')


class EngineConsist(Consist):
    """
    Intermediate class for engine consists to subclass from, provides some common properties.
    This class should be sparse - only declare the most limited set of properties common to engine consists.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # arbitrary multiplier to floating run costs (factors are speed, power, weight)
        # adjust per subtype as needed
        self.floating_run_cost_multiplier = 8.5
        # fixed (baseline) run costs on this subtype, or more rarely instances can over-ride this
        self.fixed_run_cost_points = kwargs.get("fixed_run_cost_points", 180)
        # pax/mail cars will default to the alternative 2nd livery automatically using role and branch, or it can be forced here (set in engines as needed)
        # (player can always invert the choice by flipping vehicles)
        self.force_default_pax_mail_livery = kwargs.get(
            "force_default_pax_mail_livery", None
        )
        # caboose families are used to match engines to caboose variants
        # family name strings are arbitrary and all shame the namespace, how each caboose type uses them is potentially unique
        # we first populate using default from the roster, selected by base track type and vehicle gen
        # self.caboose_families = self.roster.caboose_default_family_by_generation[
        #     self.base_track_type
        # ][self.gen - 1].copy()

        self.caboose_families = [
            {
                "caboose_car": "pony_caboose_car_default_1",
                "goods_caboose_car": "pony_goods_caboose_car_default_1",
            },
            {
                "caboose_car": "pony_caboose_car_default_2",
                "goods_caboose_car": "pony_goods_caboose_car_default_2",
            },
            {
                "caboose_car": "pony_caboose_car_default_3",
                "goods_caboose_car": "pony_goods_caboose_car_default_3",
            },
            {
                "caboose_car": "pony_caboose_car_default_4",
                "goods_caboose_car": "pony_goods_caboose_car_default_4",
            },
            {
                "caboose_car": "pony_caboose_car_default_5",
                "goods_caboose_car": "pony_goods_caboose_car_default_5",
            },
            {
                "caboose_car": "pony_caboose_car_default_6",
                "goods_caboose_car": "pony_goods_caboose_car_default_6",
            },
        ][self.gen - 1].copy()
        # caboose families can be over-ridden on a per engine, per caboose type basis
        for caboose_type, family_name in kwargs.get(
            "force_caboose_families", {}
        ).items():
            self.caboose_families[caboose_type] = family_name
        # Graphics configuration only as required
        # (pantographs can also be generated by other gestalts as needed, this isn't the exclusive gestalt for it)
        # note that this Gestalt might get replaced by subclasses as needed
        alternative_cc_livery = None
        # alternative_cc_livery = self.roster.livery_presets.get(
        #     kwargs.get("alternative_cc_livery", None), None
        # )
        self.gestalt_graphics = GestaltGraphicsEngine(
            pantograph_type=self.pantograph_type,
            alternative_cc_livery=alternative_cc_livery,
            default_livery_extra_docs_examples=kwargs.get(
                "default_livery_extra_docs_examples", []
            ),
        )

    @property
    def buy_cost(self):
        # max speed = 200mph by design - see assert_speed()
        # multiplier for speed, max value will be 25
        speed_cost_points = self.speed / 8
        # max power 10000hp by design - see assert_power()
        # malus for electric engines, ~33% higher equipment costs
        # !! this is an abuse of requires_electric_rails, but it's _probably_ fine :P
        if self.requires_electric_rails:
            power_factor = self.power / 800
        # malus for complex electro-diesels, ~33% higher equipment costs, based on elrl power
        # this sometimes causes a steep jump from non-electro-diesels in a tech tree (due to power jump), but eh, fine
        elif self.electro_diesel_buy_cost_malus is not None:
            power_factor = (
                self.electro_diesel_buy_cost_malus * self.power_by_railtype["ELRL"]
            ) / 750
        # multiplier for non-electric power, max value will be 10
        else:
            power_factor = self.power / 1000
        # basic cost from speed, power, subclass factor (e.g. engine with pax capacity might cost more to buy)
        buy_cost_points = (
            speed_cost_points * power_factor * self.buy_cost_adjustment_factor
        )
        # if I set cost base as high as I want for engines, wagon costs aren't fine grained enough
        # so just apply arbitrary multiplier to engine costs, which works
        buy_cost_points = 2 * buy_cost_points
        # start from an arbitrary baseline of 10 points, add points for gen, cost points, seems to work
        # cap to int for nml
        return int(self.fixed_buy_cost_points + self.gen + buy_cost_points)

    @property
    def running_cost(self):
        # algorithmic calculation of engine run costs
        # as of Feb 2019, it's fixed cost (set by subtype) + floating costs (derived from power, speed, weight)
        # note some string to handle NG trains, which tend to have a smaller range of speed, cost, power
        is_NG = True if self.base_track_type == "NG" else False
        # max speed = 200mph by design - see assert_speed() - (NG assumes 100mph max)
        # multiplier for speed, max value will be 12.5
        speed_cost_factor = self.speed / (8 if is_NG else 16)
        # max power 10000hp by design - see assert_power() - (NG assumes 4000hp max)
        # multiplier for power, max value will be ~18
        power_factor = self.power / (250 if is_NG else 555)
        # max weight = 500t by design - see assert_weight() - (NG assumes 200t max)
        # multiplier for weight, max value will be 8
        weight_factor = self.weight / (32 if is_NG else 62.5)

        # !! this is an abuse of requires_electric_rails, but it's _probably_ fine :P
        if self.requires_electric_rails:
            if "railcar" in self.role:
                # massive bonus to el railcars
                power_factor = 0.33 * power_factor
            else:
                # small bonus to electric engines
                # they already tend to be lighter per unit power (so cheaper to run) than similar power types
                power_factor = 0.75 * power_factor

        # basic cost from speed, power, weight
        floating_run_cost_points = speed_cost_factor * power_factor * weight_factor
        # then multiply by a factor specific to the subtype, so that we can control how much floating costs matter for this subtype
        # be aware that engines cost base is nerfed down, otherwise, wagon costs aren't fine grained enough
        # this means that floating_run_cost_multiplier might need to be > 3 to reset the base cost nerf
        floating_run_cost_points = (
            floating_run_cost_points * self.floating_run_cost_multiplier
        )
        fixed_run_cost_points = self.fixed_run_cost_points
        # add floating cost to the fixed (baseline) cost (which is arbitrary points, range 0-200-ish)
        # do an arbitrary calculation using gen to give the results I want (tried values in a spreadsheet until looked right)
        # the aim is to space costs widely across types within a generation, but only have slight increase (or flat) across generations of same type
        gen_multiplier = 8.52 - math.pow(1.22, self.gen)
        run_cost = gen_multiplier * (fixed_run_cost_points + floating_run_cost_points)
        # freight engines get a run cost bonus as they'll often be sat waiting for loads, so balance (also super realism!!)
        # doing this is preferable to doing variable run costs, which are weird and confusing (can't trust the costs showin in vehicle window)
        if self.role in [
            "heavy_freight",
            "super_heavy_freight",
        ]:  # smaller bonus for heavy_freight
            run_cost = 0.9 * run_cost
        elif self.role in [
            "branch_freight",
            "freight",
        ]:  # bigger bonus for other freight
            run_cost = 0.8 * run_cost
        # massive bonus for NG
        if is_NG:
            run_cost = 0.33 * run_cost
        # cap to int for nml
        return int(run_cost)

    @property
    def joker(self):
        # jokers are bonus vehicles (mostly) engines which don't fit strict tech tree progression
        # for engines, jokers use -ve value for role_child_branch_num, tech tree vehicles use +ve
        return self.role_child_branch_num < 0


class Train(object):
    """
    Base class for all types of trains
    """

    def __init__(self, **kwargs):
        self.consist = kwargs.get("consist")

        # setup properties for this train
        self.numeric_id = kwargs.get("numeric_id", None)
        # vehicle_length is either derived from chassis length or similar, or needs to be set explicitly as kwarg
        self._vehicle_length = kwargs.get("vehicle_length", None)
        self._weight = kwargs.get("weight", None)
        self.capacity = kwargs.get("capacity", 0)
        # spriterow_num allows assigning sprites for multi-part vehicles, and is not supported in all vehicle templates (by design - TMWFTLB to support)
        self.spriterow_num = kwargs.get("spriterow_num", 0)  # first row = 0;
        # sometimes we want to offset the buy menu spriterow (!! this is incomplete hax, not supported by generated buy menu sprites etc)
        self.buy_menu_spriterow_num = (
            0  # set in the subclass as needed, (or extend to kwargs in future)
        )
        # !! the need to copy cargo refits from the consist is legacy from the default multi-unit articulated consists in Iron Horse 1
        # !! could likely be refactored !!
        self.label_refits_allowed = self.consist.label_refits_allowed
        self.label_refits_disallowed = self.consist.label_refits_disallowed
        self.autorefit = True
        # nml constant (STEAM is sane default)
        self.engine_class = "ENGINE_CLASS_STEAM"
        # structure for effect spawn and sprites, default and per railtype as needed
        self.effects = {}  # empty if no effects, set in subtypes as needed
        # optional, use to over-ride automatic effect positioning
        # expects a list of offset pairs [(x, y), (x, y)] etc
        # n.b max 4 effects (nml limit)
        self._effect_offsets = kwargs.get("effect_offsets", None)
        # z offset is rarely used and is handled separately, mostly just for low-height engines
        self._effect_z_offset = kwargs.get("effect_z_offset", None)
        self.default_effect_z_offset = (
            12  # optimised for Pony diesel and electric trains
        )
        # optional - only set if the graphics processor generates the vehicle chassis
        self.chassis = kwargs.get("chassis", None)
        # optional - occasionally we need to suppress composited roof sprites and just draw our own
        self.suppress_roof_sprite = kwargs.get("suppress_roof_sprite", False)
        # optional - some engine units need to set explicit tail light spritesheets
        # subclasses may over-ride this, e.g. wagons have an automatic tail light based on vehicle length
        self.tail_light = kwargs.get("tail_light", "empty")
        # 'symmetric' or 'asymmetric'?
        # defaults to symmetric, over-ride in sub-classes or per vehicle as needed
        self._symmetry_type = kwargs.get("symmetry_type", "symmetric")
        # optional - a switch name to trigger re-randomising vehicle random bits - over-ride as need in subclasses
        self.random_trigger_switch = None

    def get_capacity_variations(self, capacity):
        # capacity is variable, controlled by a newgrf parameter
        # allow that integer maths is needed for newgrf cb results; round up for safety
        return [
            int(math.ceil(capacity * multiplier))
            for multiplier in global_constants.capacity_multipliers
        ]

    @property
    def capacities(self):
        return self.get_capacity_variations(self.capacity)

    @property
    def default_cargo_capacity(self):
        return self.capacities[2]

    @property
    def has_cargo_capacity(self):
        if self.default_cargo_capacity != 0:
            return True
        else:
            return False

    def get_pax_car_capacity(self):
        # magic to set capacity subject to length
        base_capacity = self.consist.roster.pax_car_capacity_per_unit_length[
            self.consist.base_track_type
        ][self.consist.gen - 1]
        result = int(
            self.vehicle_length
            * base_capacity
            * self.consist.pax_car_capacity_type["multiplier"]
        )
        return result

    @property
    def weight(self):
        # weight can be set explicitly or by methods on subclasses
        return self._weight

    @property
    def vehicle_length(self):
        # length of this unit, either derived from from chassis length, or set explicitly via keyword
        # first guard that one and only one of these props is set
        if self._vehicle_length is not None and self.chassis is not None:
            utils.echo_message(
                self.consist.id
                + " has units with both chassis and length properties set"
            )
        if self._vehicle_length is None and self.chassis is None:
            utils.echo_message(
                self.consist.id
                + " has units with neither chassis nor length properties set"
            )

        if self.chassis is not None:
            # assume that chassis name format is 'foo_bar_ham_eggs_24px' or similar - true as of Nov 2020
            # if chassis name format changes / varies in future, just update the string slice accordingly, safe enough
            # splits on _, then takes last entry, then slices to remove 'px'
            result = int(self.chassis.split("_")[-1][0:-2])
            return int(result / 4)
        else:
            return self._vehicle_length

    @property
    def availability(self):
        # only show vehicle in buy menu if it is first vehicle in consist
        if self.is_lead_unit_of_consist:
            return "ALL_CLIMATES"
        else:
            return "NO_CLIMATE"

    @property
    def is_lead_unit_of_consist(self):
        # first unit in the complete multi-unit consist
        if self.numeric_id == self.consist.base_numeric_id:
            return True
        else:
            return False

    @property
    def symmetry_type(self):
        assert self._symmetry_type in [
            "symmetric",
            "asymmetric",
        ], "symmetry_type '%s' is invalid in %s" % (
            self._symmetry_type,
            self.consist.id,
        )
        return self._symmetry_type

    @property
    def nml_special_flags(self):
        special_flags = ["TRAIN_FLAG_2CC", "TRAIN_FLAG_SPRITE_STACK"]
        if self.consist.allow_flip:
            special_flags.append("TRAIN_FLAG_FLIP")
        if self.autorefit:
            special_flags.append("TRAIN_FLAG_AUTOREFIT")
        if self.consist.tilt_bonus:
            special_flags.append("TRAIN_FLAG_TILT")
        if self.consist.train_flag_mu:
            special_flags.append("TRAIN_FLAG_MU")
        return ",".join(special_flags)

    @property
    def grfpy_special_flags(self):
        special_flags = TrainFlags.USE_2CC | TrainFlags.USE_SPRITE_STACK
        if self.consist.allow_flip:
            special_flags |= TrainFlags.ALLOW_FLIPPING
        if self.autorefit:
            special_flags |= TrainFlags.AUTOREFIT
        if self.consist.tilt_bonus:
            special_flags |= TrainFlags.TILT
        if self.consist.train_flag_mu:
            special_flags |= TrainFlags.MULTIPLE_UNIT
        return special_flags

    @property
    def nml_refittable_classes(self):
        cargo_classes = []
        # maps lists of allowed classes.  No equivalent for disallowed classes, that's overly restrictive and damages the viability of class-based refitting
        if hasattr(self, "articulated_unit_different_class_refit_groups"):
            # in *rare* cases an articulated unit might need different refit classes to its parent consist
            class_refit_groups = self.articulated_unit_different_class_refit_groups
        else:
            # by default get the refit classes from the consist
            class_refit_groups = self.consist.class_refit_groups
        for i in class_refit_groups:
            [
                cargo_classes.append(cargo_class)
                for cargo_class in global_constants.base_refits_by_class[i]
            ]
        return ",".join(set(cargo_classes))  # use set() here to dedupe

    @property
    def grfpy_refittable_classes(self):
        cargo_classes = []
        # maps lists of allowed classes.  No equivalent for disallowed classes, that's overly restrictive and damages the viability of class-based refitting
        if hasattr(self, "articulated_unit_different_class_refit_groups"):
            # in *rare* cases an articulated unit might need different refit classes to its parent consist
            class_refit_groups = self.articulated_unit_different_class_refit_groups
        else:
            # by default get the refit classes from the consist
            class_refit_groups = self.consist.class_refit_groups
        for i in class_refit_groups:
            [
                cargo_classes.append(cargo_class)
                for cargo_class in global_constants.base_refits_by_class[i]
            ]
        res = grf.CargoClass.NONE
        for x in set(cargo_classes):  # use set() here to dedupe
            res |= getattr(grf.CargoClass, x)
        return res

    @property
    def loading_speed(self):
        # ottd vehicles load at different rates depending on type, train default is 5
        # Iron Horse uses 5 as default, with some vehicle types adjusting that up or down
        return int(5 * self.consist.loading_speed_multiplier)

    @property
    def running_cost_base(self):
        # all engines use the same RUNNING_COST_STEAM, and Iron Horse provides the variation between steam/electric/diesel
        # this will break base cost mod grfs, but "Pikka says it's ok"
        # wagons will use RUNNING_COST_DIESEL - set in wagon subclass
        return "RUNNING_COST_STEAM"

    def get_offsets(self, flipped=False):
        # offsets can also be over-ridden on a per-model basis by providing this property in the model class
        base_offsets = global_constants.default_spritesheet_offsets[
            str(self.vehicle_length)
        ]
        if flipped:
            flipped_offsets = list(base_offsets[4:8])
            flipped_offsets.extend(base_offsets[0:4])
            return flipped_offsets
        else:
            return base_offsets

    @property
    def vehicle_nml_template(self):
        # optionally drop the cargos in the compile, can save substantial compile time
        if utils.get_makefile_args(sys).get("suppress_cargo_sprites", False):
            return "vehicle_default.pynml"

        if self.consist.gestalt_graphics.nml_template:
            return self.consist.gestalt_graphics.nml_template
        # default case
        return "vehicle_default.pynml"

    @property
    def location_of_random_bits_for_random_variant(self):
        # articulated vehicles should get random bits from first unit, so that all units randomise consistently
        # IMPORTANT: cannot rely on returning FORWARD_SELF(0), it causes register 0x100 to be read and cleared, where 0x100 is needed for graphics layers
        # https://newgrf-specs.tt-wiki.net/wiki/NML:Random_switch#cite_note-expression-1
        if (
            len(self.consist.units) > 1
            and self.numeric_id != self.consist.base_numeric_id
        ):
            return (
                "FORWARD_SELF("
                + str(self.numeric_id - self.consist.base_numeric_id)
                + ")"
            )
        else:
            return "SELF"

    @property
    def roof(self):
        # fetch spritesheet name to use for roof when generating graphics
        if self.consist.roof_type is not None:
            if self.consist.base_track_type == "NG":
                ng_prefix = "ng_"
            else:
                ng_prefix = ""
            return (
                str(4 * self.vehicle_length)
                + "px_"
                + ng_prefix
                + self.consist.roof_type
            )
        else:
            return None

    @property
    def requires_colour_mapping_cb(self):
        # bit weird and janky, various conditions to consider eh
        if getattr(self.consist, "use_colour_randomisation_strategies", False):
            return "use_colour_randomisation_strategies"
        elif (
            getattr(self.consist.gestalt_graphics, "colour_mapping_switch", None)
            is not None
        ):
            if self.consist.gestalt_graphics.alternative_cc_livery is not None:
                return "colour_mapping_switch_with_purchase"
            else:
                return "colour_mapping_switch_without_purchase"
        else:
            return None

    @property
    def default_effect_offsets(self):
        # over-ride this in subclasses as needed (e.g. to move steam engine smoke to front by default
        # vehicles can also over-ride this on init (stored on each model_variant as _effect_offsets)
        return [(0, 0)]

    def get_nml_expression_for_effects(self, reversed_variant, railtype="default"):
        # provides part of nml switch for effects (smoke)

        # effects can be over-ridden per vehicle, or use a default from the vehicle subclass
        if self._effect_offsets is not None:
            effect_offsets = self._effect_offsets
        else:
            effect_offsets = self.default_effect_offsets

        # when vehicles (e.g. steam engines) are reversed, invert the effect x position
        if reversed_variant == "reversed":
            effect_offsets = [
                (offsets[0] * -1, offsets[1]) for offsets in effect_offsets
            ]

        # z offset is handled independently to x, y for simplicity, option to over-ride z offset default per vehicle
        if self._effect_z_offset is not None:
            z_offset = self._effect_z_offset
        else:
            z_offset = self.default_effect_z_offset

        # changing sprite by railtype is supported, changing position is *not* as of August 2019
        effect_sprite = self.effects[railtype][1]

        result = []
        for index, offset_pair in enumerate(effect_offsets):
            items = [
                effect_sprite,
                str(offset_pair[0]),
                str(offset_pair[1]),
                str(z_offset),
            ]
            result.append(
                "STORE_TEMP(create_effect("
                + ",".join(items)
                + "), 0x10"
                + str(index)
                + ")"
            )
        return [
            "[" + ",".join(result) + "]",
            str(len(result)) + " + CB_RESULT_CREATE_EFFECT_CENTER",
        ]

    @property
    def switch_id_for_create_effect(self):
        # randomly reversed vehicles need to use a dependent random switch, this doesn't exist for non-reversible vehicles, so need to conditionally handle switch routing
        if len(self.consist.reversed_variants) > 1:
            return self.id + "_switch_create_effect_reversed_variants"
        else:
            return (
                self.id
                + "_switch_create_effect_check_railtype_"
                + self.consist.reversed_variants[0]
            )

    def get_nml_expression_for_grfid_of_neighbouring_unit(self, unit_offset):
        expression_template = Template(
            "[STORE_TEMP(${unit_offset}, 0x10F), var[0x61, 0, 0xFFFFFFFF, 0x25]]"
        )
        return expression_template.substitute(unit_offset=unit_offset)

    def get_nml_expression_for_id_of_neighbouring_unit(self, unit_offset):
        # best used with the check for same grfid, but eh
        expression_template = Template(
            "[STORE_TEMP(${unit_offset}, 0x10F), var[0x61, 0, 0x0000FFFF, 0xC6]]"
        )
        return expression_template.substitute(unit_offset=unit_offset)

    def get_spriteset_template_name(self, reversed, flipped, y):
        template_name = "_".join(
            [
                "spriteset_template",
                self.symmetry_type,
                reversed,
                str(self.vehicle_length),
                "8",
                flipped,
            ]
        )
        anim_flag = (
            "ANIM" if self.consist.suppress_animated_pixel_warnings else "NOANIM"
        )
        args = ",".join([str(y), anim_flag])
        return template_name + "(" + args + ")"

    def nml_get_label_refits_allowed(self):
        # allowed labels, for fine-grained control in addition to classes
        return ",".join(self.label_refits_allowed)

    def nml_get_label_refits_disallowed(self):
        # disallowed labels, for fine-grained control, knocking out cargos that are allowed by classes, but don't fit for gameplay reasons
        return ",".join(self.label_refits_disallowed)

    def get_cargo_suffix(self):
        return "string(" + self.cargo_units_refit_menu + ")"

    def assert_random_reverse(self):
        # some templates don't support the random_reverse (by design, they're symmetrical sprites, and reversing bloats the template)
        if self.consist.random_reverse:
            if hasattr(self.consist, "gestalt_graphics"):
                for nml_template in [
                    "vehicle_with_visible_cargo.pynml",
                    "vehicle_box_car_with_opening_doors.pynml",
                    "vehicle_caboose.pynml",
                    "vehicle_with_cargo_specific_liveries.pynml",
                    "vehicle_with_consist_specific_liveries.pynml",
                ]:
                    assert self.consist.gestalt_graphics.nml_template != nml_template, (
                        "%s has 'random_reverse set True, which isn't supported by nml_template %s"
                        % (self.consist.id, nml_template)
                    )

    def assert_cargo_labels(self, cargo_labels):
        for i in cargo_labels:
            if i not in global_constants.cargo_labels:
                utils.echo_message(
                    "Warning: vehicle "
                    + self.id
                    + " references cargo label "
                    + i
                    + " which is not defined in the cargo table"
                )

    def get_sprites(self, g):
        # integrity tests
        self.assert_cargo_labels(self.label_refits_allowed)
        self.assert_cargo_labels(self.label_refits_disallowed)
        self.assert_random_reverse()
        # test interpolated gen and intro_date
        assert self.consist.gen, (
            "%s consist.gen is None, which is invalid.  Set gen or intro_date" % self.id
        )
        assert self.consist.intro_date, (
            "%s consist.gen is None, which is invalid.  Set gen or intro_date" % self.id
        )
        # templating
        # template_name = self.vehicle_nml_template
        # template = templates[template_name]
        # nml_result = template(
        #     vehicle=self,
        #     consist=self.consist,
        #     global_constants=global_constants,
        #     temp_storage_ids=global_constants.temp_storage_ids,  # convenience measure
        #     graphics_path=global_constants.graphics_path,
        #     spritelayer_cargos=spritelayer_cargos,
        # )
        # return nml_result

        callbacks = grf.CallbackManager(grf.Callback.Vehicle)

        if self.is_lead_unit_of_consist and (self.consist.power > 0 or self.consist.buy_menu_hint_wagons_add_power) \
                or self.consist._buy_menu_role_string is not None:
            pass
            # TODO callbacks.purchase_text = g.add_string(self.additional_text)

        if self.is_lead_unit_of_consist and len(self.consist.units) > 1:
            callbacks.articulated_part = grf.Switch(
                ranges={i + 1: unit.id for i, unit in enumerate(self.consist.units)},
                default=0x7fff,
                code='extra_callback_info1_byte',
            )

        # if self.sound_effects:
        #     callbacks.sound_effect = grf.Switch(
        #         ranges=self.sound_effects,
        #         default=layout,
        #         code='extra_callback_info1 & 255',
        #     )

        # Train name

        res = [
            grf.DefineStrings(
                feature=grf.TRAIN,
                offset=self.numeric_id,
                is_generic_offset=False,
                strings=[self.consist.name]
            ),
        ]

        # Define train

        extra_props = {}
        if self.consist.speed is not None:
            extra_props['max_speed'] = grf.Train.mph(self.consist.speed)
        # if len(self.consist.default_cargos) > 0:
        #     extra_props['default_cargo_type'] = self.consist.get_nml_expression_for_default_cargos()
        if self.consist.dual_headed:
            extra_props['dual_headed'] = True

        if callbacks.get_flags():
            extra_props['cb_flags'] = callbacks.get_flags()


        res.append(grf.Define(
            feature=grf.TRAIN,
            id=self.numeric_id,
            props={
                'climates_available': grf.ALL_CLIMATES if self.is_lead_unit_of_consist else grf.NO_CLIMATE,  # TODO expression
                'engine_class': getattr(grf.Train.EngineClass, self.engine_class[13:]),
                'introduction_date': date(self.consist.intro_date, 1 + self.consist.intro_date_days_offset, 1),
                'cargo_capacity': self.default_cargo_capacity,
                'sprite_id': 0xfd,  # magic value for newgrf sprites
                'power': grf.train_hpi(self.consist.power),
                'weight': grf.train_ton(self.consist.weight),
                'tractive_effort_coefficient': grf.nml_te(self.consist.tractive_effort_coefficient),
                'cost_factor': 0,  # use the CB to set this, the prop is capped to max 255, cb is 32k
                'running_cost_base': getattr(grf.Train.EngineClass, self.running_cost_base[13:]),
                'running_cost_factor': 0,  # use the CB to set this, the prop is capped to max 255, cb is 32k
                'refit_cost': 0,  # btw this needs to be 0 if we want autorefit without using cb
                'refittable_cargo_classes': self.grfpy_refittable_classes,
                'non_refittable_cargo_classes': grf.CargoClass.NONE,  # don't set non-refittable classes, increases likelihood of breaking cargo support
                # TODO
                'cargo_allow_refit': g.map_cargo_labels(self.label_refits_allowed),
                'cargo_disallow_refit': g.map_cargo_labels(self.label_refits_disallowed),
                'cargo_allow_refit': b'',
                'cargo_disallow_refit': b'',
                'misc_flags': self.grfpy_special_flags,
                'model_life': self.consist.model_life,
                'retire_early': self.consist.retire_early,
                'reliability_decay': 20,  # default value
                'vehicle_life': self.consist.vehicle_life,
                'shorten_by': 8 - self.vehicle_length,
                # TODO 'track_type': self.consist.track_type,
                # TODO 'effect_spawn_model_and_powered': EFFECT_SPAWN_MODEL_NONE; // default to none to suppress effects, set in cb as neede,

                **extra_props
            }
        ))

        # Vehicle graphics

        def tmpl_vehicle(reversed_variant, flipped, y, func):
            if self.symmetry_type == 'asymmetric':
                if reversed_variant == 'reversed':
                    bblist = global_constants.spritesheet_bounding_boxes_asymmetric_reversed
                else:
                    bblist = global_constants.spritesheet_bounding_boxes_asymmetric_unreversed
            else:
                bb_slice = slice(4 if self.vehicle_length == 8 else 0, 8)
                if reversed_variant == 'reversed':
                    bblist = global_constants.spritesheet_bounding_boxes_symmetric_reversed[bb_slice]
                else:
                    bblist = global_constants.spritesheet_bounding_boxes_symmetric_unreversed[bb_slice]
            res = []
            for i, bb in enumerate(bblist):
                xofs, yofs = utils.get_offsets(self.vehicle_length, flipped=flipped)[i]
                res.append(func(bb[0], y, bb[1], bb[2], xofs=xofs, yofs=yofs))
            return res

        png = grf.ImageFile(Path(global_constants.graphics_path) / f'{self.consist.id}.png')
        make_sprite = lambda *args, **kw: grf.FileSprite(png, *args, **kw)

        sprites = grf.VehicleSpriteTable(grf.TRAIN)
        variant_switches = []
        livery = self.consist.gestalt_graphics.all_liveries[0]
        livery_index = 0

        for reversed_variant in self.consist.reversed_variants:
            for flipped in (False, True):
                row_id = sprites.add_row(tmpl_vehicle(
                    reversed_variant,
                    flipped,
                    10 + (livery_index * 30) + self.spriterow_num * len(self.consist.gestalt_graphics.all_liveries) * 30,
                    make_sprite,
                ))
                layout = sprites.get_layout(row_id)
                if flipped:
                    ranges = {1: layout}
                else:
                    default = layout

            variant_switches.append(grf.Switch(
                ranges=ranges,
                default=default,
                code='vehicle_is_flipped'
            ))

        if len(variant_switches) == 1:
            graphics_switch = variant_switches[0]
        else:
            assert len(variant_switches) == 2, variant_switches
            graphics_switch = grf.RandomSwitch(
                scope='self',
                triggers=1,
                cmp_all=False,
                lowest_bit=0,
                groups=variant_switches,
            )

        # Purchase graphics

        def tmpl_vehicle_purchase(func):
            # TODO dual-head
            return func(
                self.consist.buy_menu_x_loc,
                10 + livery_index * 30,
                1 + self.consist.buy_menu_width,
                16,
                xofs=-1 * int(self.consist.buy_menu_width / 2),
                yofs=-11
            )
            # TODO cc2, pantograph

        row_id = sprites.add_purchase_graphics(tmpl_vehicle_purchase(make_sprite))
        purchase_graphics = sprites.get_layout(row_id)

        # Final touches
        res.append(sprites)

        default, maps = callbacks.make_switch(graphics_switch, purchase_graphics)
        res.append(grf.Action3(
            feature=grf.TRAIN,
            ids=[self.numeric_id],
            maps=maps,
            default=default,
        ))

        return res


class SteamEngineUnit(Train):
    """
    Unit for a steam engine, with smoke
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine_class = "ENGINE_CLASS_STEAM"
        self.effects = {"default": ["EFFECT_SPAWN_MODEL_STEAM", "EFFECT_SPRITE_STEAM"]}
        self.consist.str_name_suffix = "STR_NAME_SUFFIX_STEAM"
        self.default_effect_z_offset = 13  # optimised for Pony steam trains
        self._symmetry_type = "asymmetric"  # assume all steam engines are asymmetric

    @property
    def default_effect_offsets(self):
        # force steam engine smoke to front by default, can also over-ride per unit for more precise positioning
        return [(1 + int(math.floor(-0.5 * self.vehicle_length)), 0)]


from roster import Roster

def make_roster(disabled=False):
    roster = Roster(
        id="pony",
        numeric_id=1,
        # ELRL, ELNG is mapped to RAIL, NG etc
        # default intro dates per generation, can be over-ridden if needed by setting intro_date kw on consist
        intro_dates={
            "RAIL": [1860, 1900, 1930, 1960, 1990, 2020],
            "METRO": [1900, 1950, 2000],
            "NG": [1860, 1905, 1950, 2000],
        },
        # default speeds per generation, can be over-ridden if needed by setting speed kw arg on consist
        # speeds roughly same as RH trucks of same era + 5mph or so, and a bit higher at the top end (back and forth on this many times eh?),
        # NG is Corsican-style 1000mm, native brit NG is not a thing for gameplay
        speeds={
            "RAIL": {
                # gen 5 and 6 held down by design, really fast freight is imbalanced
                "standard": [
                    45,
                    45,
                    60,
                    75,
                    87,
                    87,
                ],
                # match standard, except gen 6
                "suburban": [45, 45, 60, 75, 87, 99],
                # smaller steps in gen 5 and 6, balances against faster HSTs
                "express": [
                    60,
                    75,
                    90,
                    105,
                    115,
                    125,
                ],
                "hst": [0, 0, 0, 112, 125, 125],
                "hst_on_lgv": [0, 0, 0, 112, 125, 140],
                "very_high_speed": [0, 0, 0, 0, 125, 125],
                "very_high_speed_on_lgv": [0, 0, 0, 0, 140, 186],
            },
            "METRO": {
                "standard": [45, 55, 65]
                # only standard for metro in Pony
            },
            "NG": {
                "standard": [
                    45,
                    45,
                    55,
                    65,
                ],
                # NG standard/suburban/express same in Pony, balanced against trams, RVs
                # suburban has to be provided as the mail railcar expects it, just copying it in is easiest solution
                "suburban": [45, 45, 55, 65],
                # suburban has to be provided as the coaches/mail vans etc expect it, just copying it in is easiest solution
                "express": [45, 45, 55, 65],
            },
        },
        # capacity factor per generation, will be multiplied by vehicle length
        freight_car_capacity_per_unit_length={
            "RAIL": [4, 4, 5, 5.5, 6, 6.5],
            "NG": [3, 3, 4, 4],
        },
        pax_car_capacity_per_unit_length={
            "RAIL": [3, 3.75, 4.5, 5.25, 6, 6],
            "NG": [3, 5, 5, 6],
        },
        pax_car_capacity_types={
            "default": {
                "multiplier": 1,
                "loading_speed_multiplier": 1,
            },
            "high_capacity": {
                "multiplier": 1.5,
                "loading_speed_multiplier": 1.75,
            },
            # very specifically tuned multiplier against a single pony vehicle
            "autocoach_combine": {
                "multiplier": 2.7,
                "loading_speed_multiplier": 1.75,
            },
            "restaurant": {
                "multiplier": 0.45,
                "loading_speed_multiplier": 1,
            },
        },
        # freight car weight factor varies slightly by gen, reflecting modern cars with lighter weight
        train_car_weight_factors=[0.5, 0.5, 0.5, 0.48, 0.44, 0.40],
        # caboose families (family names and caboose names are arbitrary strings)
        # caboose names map to labelled spriterows, as defined in the vehicle files
        caboose_families={
            "RAIL": {
                "caboose_car": {
                    "pony_caboose_car_default_1": ["caboose_1"],
                    "pony_caboose_car_default_2": ["caboose_2"],
                    "pony_caboose_car_default_3": ["caboose_3"],
                    "pony_caboose_car_default_4": ["caboose_4"],
                    "pony_caboose_car_default_5": ["caboose_5"],
                    "pony_caboose_car_default_6": ["caboose_6"],
                    "pony_gwr_1": ["caboose_1"],
                    #"pony_gwr_1": ["caboose_1", "gwr_1"],
                    "pony_railfreight_1": ["railfreight_1", "brown_1"],
                    "pony_railfreight_2": ["caboose_6"],
                    #"pony_railfreight_2": ["railfreight_2"],
                },
                "goods_caboose_car": {
                    "pony_goods_caboose_car_default_1": ["caboose_1"],
                    "pony_goods_caboose_car_default_2": ["caboose_2"],
                    "pony_goods_caboose_car_default_3": ["caboose_3"],
                    "pony_goods_caboose_car_default_4": ["caboose_4"],
                    "pony_goods_caboose_car_default_5": ["caboose_5"],
                    "pony_goods_caboose_car_default_6": ["caboose_6"],
                    "pony_railfreight_1": ["railfreight_1", "brown_1"],
                },
            },
            "NG": {
                "caboose_car": {
                    "pony_ng_caboose_car_1": ["ng_caboose_1"],
                    "pony_ng_caboose_car_2": ["ng_caboose_2"],
                    "pony_ng_caboose_car_3": ["ng_caboose_3"],
                },
            },
        },
        # lists of one default family name per generation, ascending
        caboose_default_family_by_generation={
            "RAIL": [
                {
                    "caboose_car": "pony_caboose_car_default_1",
                    "goods_caboose_car": "pony_goods_caboose_car_default_1",
                },
                {
                    "caboose_car": "pony_caboose_car_default_2",
                    "goods_caboose_car": "pony_goods_caboose_car_default_2",
                },
                {
                    "caboose_car": "pony_caboose_car_default_3",
                    "goods_caboose_car": "pony_goods_caboose_car_default_3",
                },
                {
                    "caboose_car": "pony_caboose_car_default_4",
                    "goods_caboose_car": "pony_goods_caboose_car_default_4",
                },
                {
                    "caboose_car": "pony_caboose_car_default_5",
                    "goods_caboose_car": "pony_goods_caboose_car_default_5",
                },
                {
                    "caboose_car": "pony_caboose_car_default_6",
                    "goods_caboose_car": "pony_goods_caboose_car_default_6",
                },
            ],
            "NG": [
                # ng caboose don't have much variation
                {"caboose_car": "pony_ng_caboose_car_1"},
                {"caboose_car": "pony_ng_caboose_car_1"},
                {"caboose_car": "pony_ng_caboose_car_2"},
                {"caboose_car": "pony_ng_caboose_car_3"},
            ],
        },
        # specify lists of cc2 colours, and an option to remap all the cc1 to a specific other cc (allowing multiple input colours to map to one result)
        livery_presets={
            "FREIGHTLINER_GBRF": {
                "cc2": [
                    "COLOUR_PALE_GREEN",
                    "COLOUR_GREEN",
                    "COLOUR_DARK_GREEN",
                    # includes GBRF
                    "COLOUR_MAUVE",
                ],
                # note the remap to yellow, allowing 1cc wagons to be whatever player chooses
                "remap_to_cc": "COLOUR_YELLOW",
                "docs_image_input_cc": [
                    ("COLOUR_YELLOW", "COLOUR_PALE_GREEN"),
                    ("COLOUR_ORANGE", "COLOUR_DARK_GREEN"),
                    ("COLOUR_ORANGE", "COLOUR_GREEN"),
                    ("COLOUR_CREAM", "COLOUR_MAUVE"),
                ],
            },
            "RAILFREIGHT_RED_STRIPE": {
                # don't match the stripe options to triple grey, it was tried and the blue just doesn't look good
                # green and purple were allowed as they're vivid and it's by player request
                "cc2": [
                    "COLOUR_RED",
                    "COLOUR_PINK",
                    "COLOUR_PURPLE",
                    "COLOUR_GREEN",
                ],
                "remap_to_cc": "COLOUR_GREY",
                "docs_image_input_cc": [
                    ("COLOUR_GREY", "COLOUR_RED"),
                    ("COLOUR_YELLOW", "COLOUR_PINK"),
                    ("COLOUR_GREY", "COLOUR_PURPLE"),
                    ("COLOUR_WHITE", "COLOUR_GREEN"),
                ],
            },
            "RAILFREIGHT_TRIPLE_GREY": {
                # green and purple were allowed as they're vivid and it's by player request
                # also used for Freightliner-style triple grey
                "cc2": [
                    "COLOUR_RED",
                    "COLOUR_PINK",
                    "COLOUR_BLUE",
                    "COLOUR_DARK_BLUE",
                    "COLOUR_LIGHT_BLUE",
                    "COLOUR_PURPLE",
                    "COLOUR_GREEN",
                ],
                # note the remap to white, to provide lightest of the triple greys as cc1
                "remap_to_cc": "COLOUR_WHITE",
                "docs_image_input_cc": [
                    ("COLOUR_GREY", "COLOUR_RED"),
                    ("COLOUR_YELLOW", "COLOUR_BLUE"),
                    ("COLOUR_BROWN", "COLOUR_DARK_BLUE"),
                    ("COLOUR_GREY", "COLOUR_PURPLE"),
                    ("COLOUR_WHITE", "COLOUR_GREEN"),
                ],
            },
            "YEOMAN": {
                "cc2": ["COLOUR_GREY", "COLOUR_WHITE"],
                "remap_to_cc": None,
                "docs_image_input_cc": [
                    ("COLOUR_BLUE", "COLOUR_GREY"),
                    ("COLOUR_DARK_BLUE", "COLOUR_WHITE"),
                    ("COLOUR_RED", "COLOUR_GREY"),
                    ("COLOUR_ORANGE", "COLOUR_WHITE"),
                ],
            },
        },
        # this list is manually maintained deliberately, even though it could be mostly automated using tech tree
        engines=[],
    )
    roster.register(disabled=disabled)


def make_lamia(roster_id):
    consist = EngineConsist(
        roster_id=roster_id,
        id="lamia",
        base_numeric_id=4880,
        name="0-6-0 Lamia",  # the name is the Basque mythical creature, not the Greek https://en.wikipedia.org/wiki/Lamia_(Basque_mythology)
        role="gronk!",
        role_child_branch_num=-2,
        # replacement_consist_id="chuggypig",  # this Joker ends with Gronk
        power=350,
        speed=35,
        # dibble TE up for game balance, assume low gearing or something
        tractive_effort_coefficient=0.375,
        fixed_run_cost_points=101,  # substantial cost bonus so it can make money
        random_reverse=True,
        gen=1,
        intro_date_offset=2,  # introduce later than gen epoch by design
        vehicle_life=60,  # extended vehicle life for all gronks eh
        sprites_complete=True,
    )

    consist.add_unit(type=SteamEngineUnit, weight=35, vehicle_length=4, spriterow_num=0)

    consist.description = """Nice little engine this one."""
    consist.foamer_facts = """Bagnall saddle tanks"""
    return consist

#  -----------   new code ------------

g = grf.NewGRF(
    grfid=b'CA\xff\xff',
    name='Iron Horsenstein',
    description='License: \x89GPL v2\r\x98',
)

# Bind all the used classes to current grf so they can be used declaratively
DefineStrings, Switch, RandomSwitch, ReplaceOldSprites, SetDescription, Action1, If, DefineMultiple, SpriteSet, ModifySprites, ComputeParameters, Action3, SetProperties, Define, GenericSpriteLayout = g.bind(grf.DefineStrings), g.bind(grf.Switch), g.bind(grf.RandomSwitch), g.bind(grf.ReplaceOldSprites), g.bind(grf.SetDescription), g.bind(grf.Action1), g.bind(grf.If), g.bind(grf.DefineMultiple), g.bind(grf.SpriteSet), g.bind(grf.ModifySprites), g.bind(grf.ComputeParameters), g.bind(grf.Action3), g.bind(grf.SetProperties), g.bind(grf.Define), g.bind(grf.GenericSpriteLayout)

# Train = g.bind(grf.Train)

# def tmpl_rv(x, y, func):
#     return [
#         func(      x, y, 10, 28, xofs= -4, yofs=-15),
#         func( x + 20, y, 26, 28, xofs=-18, yofs=-14),
#         func( x + 50, y, 36, 28, xofs=-18, yofs=-17),
#         func( x + 90, y, 26, 28, xofs=-10, yofs=-15),
#         func(x + 120, y, 10, 28, xofs= -4, yofs=-15),
#         func(x + 140, y, 26, 28, xofs=-16, yofs=-16),
#         func(x + 170, y, 36, 28, xofs=-18, yofs=-20),
#         func(x + 210, y, 26, 28, xofs= -6, yofs=-15),
#     ]

# rv_png = grf.ImageFile('sprites/32bpp_rv.png', colourkey=(0, 0, 255))
# sprites = tmpl_rv(0, 20, lambda *args, **kw: grf.FileSprite(rv_png, *args, **kw, bpp=24))

# diesel_effects = {
#     grf.SoundEvent.STOPPED: grf.RAWSound('sounds/modern_diesel_idle.wav'),
#     grf.SoundEvent.VISUAL_EFFECT: grf.RAWSound('sounds/modern_diesel_run.wav'),
#     grf.SoundEvent.RUNNING_16: grf.RAWSound('sounds/modern_diesel_coast.wav'),
#     grf.SoundEvent.START: grf.RAWSound('sounds/horn_4.wav'),
#     grf.SoundEvent.BREAKDOWN: grf.DefaultSound.BREAKDOWN_TRAIN_SHIP,
#     grf.SoundEvent.TUNNEL: grf.RAWSound('sounds/horn_4.wav'),  # sounds are cached by filename so horn_4 will only be added once
# }

# Train(
#     id=300,
#     name='Example train with sounds',
#     liveries=[{
#         'name': 'Default',
#         'sprites': sprites,
#     }],
#     sound_effects=diesel_effects,
#     engine_class=Train.EngineClass.DIESEL,
#     max_speed=Train.kmhishph(104),
#     power=255,
#     introduction_date=date(1900, 1, 1),
#     weight=20,
#     tractive_effort_coefficient=79,
#     vehicle_life=8,
#     model_life=144,
#     climates_available=grf.ALL_CLIMATES,
#     running_cost_factor=222,
#     cargo_capacity=90,
#     default_cargo_type=0,
#     cost_factor=1,
#     refittable_cargo_types=1,
# )

g.set_cargo_table(global_constants.cargo_labels)

DefineMultiple(
    feature=grf.GLOBAL_VAR,
    first_id=15,
    count=2,
    props={'basecost': [6, 9]}
)

DefineMultiple(
    feature=grf.GLOBAL_VAR,
    first_id=42,
    count=2,
    props={'basecost': [6, 4]}
)

# Disable default trains
g.add(grf.DisableDefault(grf.TRAIN, range(116)))

make_roster()
g.add(make_lamia("pony"))

g.write('iron_horse_grfpy_edition.grf')
