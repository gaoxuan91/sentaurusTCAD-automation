"""
SDevice CMD/PAR generation and simulation execution tools.

Extracted from analysis/run_complete_lbic.py — data definitions and generation
functions are identical to the original. The original script now imports from here.
"""
from pathlib import Path

from automation.utils.vm_config_loader import get_vm_config

# ---------------------------------------------------------------------------
# Case & interface definitions
# ---------------------------------------------------------------------------

CASES = [
    "baseline",
    "tb_vertical_single",
    "tb_parallel_single",
    "tb_double",
    "tb_parallel_multi",
    "tb_wide",
    "tb_dense",
]

INTERFACES = {
    "no_effect": {
        "charge": None,
        "chi0_tb": 3.4,
        "description": "No TB effect (geometry only)",
    },
    "P1P2_mid": {
        "charge": 1e12,
        "chi0_tb": 3.30,
        "description": "Complete TB model (Charge + Band Offset)",
    },
}

BEAM_POSITIONS_NM = list(range(50, 451, 10))

GRID_FILES = {
    "baseline": "../SDE/YOUR_PROJECT_NAME_baseline_fps_msh.tdr",
    "tb_vertical_single": "../SDE/YOUR_PROJECT_NAME_tb_vertical_single_fps_msh.tdr",
    "tb_parallel_single": "../SDE/YOUR_PROJECT_NAME_tb_parallel_single_fps_msh.tdr",
    "tb_double": "../SDE/YOUR_PROJECT_NAME_tb_double_fps_msh.tdr",
    "tb_parallel_multi": "../SDE/YOUR_PROJECT_NAME_tb_parallel_multi_fps_msh.tdr",
    "tb_wide": "../SDE/YOUR_PROJECT_NAME_tb_wide_fps_msh.tdr",
    "tb_dense": "../SDE/YOUR_PROJECT_NAME_tb_dense_fps_msh.tdr",
}

# PLACEHOLDER_INTERFACE_BLOCKS

INTERFACE_BLOCKS = {
    "baseline": "",
    "tb_vertical_single": """
Physics (RegionInterface = "bulk_L/tb_v1") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v1/bulk_R") {{ Charge (Conc={neg_charge:.2e}) }}
""",
    "tb_parallel_single": """
Physics (RegionInterface = "bulk_B/tb_h1") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_h1/bulk_T") {{ Charge (Conc={neg_charge:.2e}) }}
""",
    "tb_double": """
Physics (RegionInterface = "bulk_L/tb_v1") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v1/bulk_M") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M/tb_v2") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v2/bulk_R") {{ Charge (Conc={neg_charge:.2e}) }}
""",
    "tb_parallel_multi": """
Physics (RegionInterface = "bulk_1/tb_h1") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_h1/bulk_2") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_2/tb_h2") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_h2/bulk_3") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_3/tb_h3") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_h3/bulk_4") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_4/tb_h4") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_h4/bulk_5") {{ Charge (Conc={neg_charge:.2e}) }}
""",
    "tb_wide": """
Physics (RegionInterface = "bulk_L/tb_v1") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v1/bulk_R") {{ Charge (Conc={neg_charge:.2e}) }}
""",
    "tb_dense": """
Physics (RegionInterface = "bulk_L/tb_v1") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v1/bulk_M1") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M1/tb_v2") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v2/bulk_M2") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M2/tb_v3") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v3/bulk_M3") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M3/tb_v4") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v4/bulk_M4") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M4/tb_v5") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v5/bulk_M5") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M5/tb_v6") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v6/bulk_M6") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M6/tb_v7") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v7/bulk_M7") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M7/tb_v8") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v8/bulk_M8") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M8/tb_v9") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v9/bulk_M9") {{ Charge (Conc={neg_charge:.2e}) }}
Physics (RegionInterface = "bulk_M9/tb_v10") {{ Charge (Conc={charge:.2e}) }}
Physics (RegionInterface = "tb_v10/bulk_R") {{ Charge (Conc={neg_charge:.2e}) }}
""",
}

# PLACEHOLDER_CMD_TEMPLATE

CMD_TEMPLATE = """File {{
    Grid      = "{grid_file}"
    Current   = "{plt_path}"
    Output    = "{log_path}"
    Parameter = "{par_path}"
}}

Electrode {{
    {{ Name="Anode"   Voltage=0.0 }}
    {{ Name="Cathode" Voltage=0.0 }}
}}

Physics (Material= "YOUR_MATERIAL"){{
    Recombination(SRH)
    Mobility(PhuMob)
}}

{tb_physics}

{interface_charge}

Physics {{
    Optics (
        ComplexRefractiveIndex (WavelengthDep(Real Imag))
        OpticalGeneration (
            QuantumYield (StepFunction(EffectiveBandgap))
            ComputeFromMonochromaticSource
        )
        Excitation (
            Wavelength = 0.450
            Intensity  = 1.0
            Polarization = 0.5
            Window (
                Origin = (-0.001, {beam_x_um})
                Line (x1=0.0 x2=0.2)
            )
        )
        OpticalSolver (
            RayTracing (
                RayDistribution (
                    Mode = AutoPopulate
                    NumberOfRays = 100
                )
                MinIntensity = 1e-5
                DepthLimit = 100
            )
        )
    )
}}

Math {{
    -CheckUndefinedModels
    Extrapolate
    Iterations = 15
    NotDamped  = 50
}}

Solve {{
    Poisson
    Coupled {{ Poisson Electron Hole }}
    Quasistationary (
        InitialStep=0.01 Increment=1.5
        MinStep=1e-5 MaxStep=0.1
        Goal {{ Name="Anode" Voltage=1.0 }}
    ) {{ Coupled {{ Poisson Electron Hole }} }}
}}
"""

TB_PHYSICS_BLOCK = """Physics (Material= "YOUR_MATERIAL_TB"){
    Recombination(SRH)
    Mobility(PhuMob)
}"""

LOCAL_PAR_BASE = Path(__file__).parent.parent.parent / "swb" / "YOUR_PROJECT_NAME" / "SDevice" / "YOUR_MATERIAL_TB_LBIC.par"


# ---------------------------------------------------------------------------
# Generation functions
# ---------------------------------------------------------------------------

def generate_par_file(interface_name, chi0_tb):
    with open(LOCAL_PAR_BASE, "r") as f:
        content = f.read()

    lines = content.split("\n")
    new_lines = []
    in_tb_material = False
    in_bandgap = False

    for line in lines:
        if 'Material = "YOUR_MATERIAL_TB"' in line:
            in_tb_material = True
        elif in_tb_material and "Bandgap" in line:
            in_bandgap = True
        elif in_tb_material and in_bandgap and "Chi0" in line:
            new_lines.append(f"        Chi0 = {chi0_tb}")
            continue
        elif in_tb_material and line.strip().startswith("}"):
            if in_bandgap:
                in_bandgap = False
            else:
                in_tb_material = False

        new_lines.append(line)

    return "\n".join(new_lines)


def generate_interface_charge_block(case, charge):
    if case == "baseline" or charge is None:
        return ""
    template = INTERFACE_BLOCKS.get(case, "")
    if template:
        return template.format(charge=charge, neg_charge=-charge)
    return ""


def generate_cmd(case, interface_name, interface_config, bx_nm, grid_file=None,
                 plt_path=None, log_path=None, par_path=None):
    beam_x_um = f"{bx_nm / 1000.0:.4f}"
    tb_physics = "" if case == "baseline" else TB_PHYSICS_BLOCK
    interface_charge = generate_interface_charge_block(case, interface_config["charge"])
    if grid_file is None:
        grid_file = GRID_FILES[case]
    if plt_path is None:
        plt_path = f"./output/{case}_{interface_name}_bx{bx_nm}_des.plt"
    if log_path is None:
        log_path = f"./logs/{case}_{interface_name}_bx{bx_nm}.log"
    if par_path is None:
        par_path = f"./{interface_name}.par"

    return CMD_TEMPLATE.format(
        grid_file=grid_file,
        case=case,
        interface=interface_name,
        bx_nm=bx_nm,
        beam_x_um=beam_x_um,
        tb_physics=tb_physics,
        interface_charge=interface_charge,
        plt_path=plt_path,
        log_path=log_path,
        par_path=par_path,
    )


def generate_cmd_batch(cases=None, interfaces=None, positions=None):
    cases = cases or CASES
    interfaces = interfaces or INTERFACES
    positions = positions or BEAM_POSITIONS_NM
    result = {}
    for case in cases:
        for iface_name, iface_config in interfaces.items():
            for bx_nm in positions:
                key = f"{case}_{iface_name}_bx{bx_nm}"
                result[key] = generate_cmd(case, iface_name, iface_config, bx_nm)
    return result
