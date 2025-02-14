from train import EngineConsist, ElectricEngineUnit


def main(roster_id):
    consist = EngineConsist(
        roster_id=roster_id,
        id="stoat",
        base_numeric_id=3340,
        name="Stoat",
        role="branch_freight",
        role_child_branch_num=2,
        power=1050,
        speed=60,  # continues a long way into gen 3, so go faster
        random_reverse=True,
        pantograph_type="diamond-single",
        gen=2,
        intro_date_offset=3,  # introduce later than gen epoch by design
        fixed_run_cost_points=105,  # substantial cost bonus so it can make money
        sprites_complete=True,
    )

    consist.add_unit(
        type=ElectricEngineUnit, weight=54, vehicle_length=6, spriterow_num=0
    )

    consist.description = """Nippy little bugger."""
    consist.foamer_facts = """NER ES1, Metropolitan Railway camel-back and box-cab locomotives, Westoe Colliery electrics, generic steeple-cab locomotives"""

    return consist
