from datetime import date
import time

import grf

from polar_fox import git_info

import iron_horse
import global_constants


def main():
    start = time.time()
    iron_horse.main()
    print(iron_horse.vacant_numeric_ids_formatted())

    g = grf.NewGRF(
        grfid=b'CA\xff\xff',
        name=f'Iron Horsenstein {git_info.get_version()}',
        description='License: {SILVER}GPL v2{}{BLACK}',
    )

    g.strings.import_lang_dir('src/lang', 'english.lng')

    g.strings.add('{STRING} ({STRING})', 'NAME_CONSIST_PARENTHESES')

    g.set_cargo_table(global_constants.cargo_labels)

    g.add(grf.BaseCosts({
        grf.BaseCosts.BUILD_VEHICLE_TRAIN: global_constants.PR_BUILD_VEHICLE_TRAIN + 8,
        grf.BaseCosts.BUILD_VEHICLE_WAGON: global_constants.PR_BUILD_VEHICLE_WAGON + 8,
        grf.BaseCosts.RUNNING_TRAIN_STEAM: global_constants.PR_RUNNING_TRAIN_STEAM + 8,
        grf.BaseCosts.RUNNING_TRAIN_DIESEL: global_constants.PR_RUNNING_TRAIN_DIESEL + 8,
        # electric running cost not used, don't define base cost multiplier
    }))

    # Disable default trains
    g.add(grf.DisableDefault(grf.TRAIN, range(116)))

    # TODO sort order

    consists = iron_horse.ActiveRosters().consists_in_buy_menu_order
    g.add(*consists)

    g.write('iron_horse_grfpy_edition.grf')

if __name__ == "__main__":
    main()
