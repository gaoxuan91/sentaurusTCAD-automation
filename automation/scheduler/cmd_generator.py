"""CMD file generator — expand experiment config into SDevice CMD files.

Uses automation.tools.sdevice for CMD template and case definitions.
"""

import os
import json
import shutil
from datetime import datetime
from typing import Dict, List

from automation.tools.sdevice import (
    CASES, INTERFACES, GRID_FILES, generate_cmd, generate_par_file, LOCAL_PAR_BASE,
)


DEFAULT_BEAM_CONFIG = {"start_nm": 50, "end_nm": 250, "step_nm": 5}


def expand_beam_positions(beam_config: Dict) -> List[int]:
    return list(range(
        beam_config.get("start_nm", 50),
        beam_config.get("end_nm", 250) + 1,
        beam_config.get("step_nm", 5),
    ))


def validate_config(config: Dict) -> List[str]:
    """Validate experiment config. Returns list of error messages (empty = valid)."""
    errors = []
    required = ["batch_name", "output_dir", "mesh_dir"]
    for key in required:
        if key not in config:
            errors.append(f"Missing required field: '{key}'")

    if "cases" in config and config["cases"]:
        for c in config["cases"]:
            if c not in CASES:
                errors.append(f"Unknown case: '{c}'. Known: {CASES}")

    interface = config.get("interface", "no_effect")
    if interface not in INTERFACES:
        errors.append(f"Unknown interface: '{interface}'. Known: {list(INTERFACES.keys())}")

    return errors


def expand_experiment(config: Dict) -> Dict:
    """Expand experiment config into task list and batch metadata.

    Returns: {"batch_id": str, "tasks": list[dict], "config": dict}
    """
    batch_name = config["batch_name"]
    cases = config.get("cases") or CASES
    interface_name = config.get("interface", "no_effect")
    interface_config = INTERFACES[interface_name]
    beam_config = config.get("beam_config", DEFAULT_BEAM_CONFIG)
    output_dir = config["output_dir"]
    cmd_dir = os.path.join(output_dir, "cmds")
    log_dir = os.path.join(output_dir, "logs")
    mesh_dir = config["mesh_dir"]

    positions = expand_beam_positions(beam_config)
    tasks = []

    for case in cases:
        # Build absolute grid file path from mesh_dir + basename of GRID_FILES entry
        grid_rel = GRID_FILES.get(case, f"{case}_msh.tdr")
        grid_abs = os.path.join(mesh_dir, os.path.basename(grid_rel))

        for bx_nm in positions:
            task_id = f"{batch_name}-{case}_{interface_name}_bx{bx_nm}"
            cmd_path = os.path.join(cmd_dir, f"{task_id}.cmd")
            plt_path = os.path.join(output_dir, f"{task_id}_des.plt")
            log_path = os.path.join(log_dir, f"{task_id}.log")

            tasks.append({
                "task_id": task_id,
                "batch_id": batch_name,
                "case_name": case,
                "interface": interface_name,
                "bx_nm": bx_nm,
                "cmd_path": cmd_path,
                "plt_path": plt_path,
                "log_path": log_path,
                "_grid_file": grid_abs,
                "_chi0_tb": interface_config.get("chi0_tb", 3.4),
                "_charge": interface_config.get("charge"),
            })

    return {
        "batch_id": batch_name,
        "tasks": tasks,
        "config": config,
    }


def generate_cmd_files(expanded: Dict) -> int:
    """Generate all CMD files and PAR files. Returns count of CMD files written."""
    tasks = expanded["tasks"]
    interface_name = tasks[0]["interface"]
    interface_config = INTERFACES[interface_name]
    chi0_tb = interface_config.get("chi0_tb", 3.4)
    cmd_dir = os.path.dirname(tasks[0]["cmd_path"])

    # Generate/copy PAR file to cmd_dir (CMD template references ./{interface}.par)
    par_dst = os.path.join(cmd_dir, f"{interface_name}.par")
    os.makedirs(cmd_dir, exist_ok=True)

    if interface_name != "no_effect" and chi0_tb != 3.4:
        par_content = generate_par_file(interface_name, chi0_tb)
        with open(par_dst, "w", encoding="utf-8") as f:
            f.write(par_content)
    else:
        shutil.copy(str(LOCAL_PAR_BASE), par_dst)

    written = 0
    for t in tasks:
        os.makedirs(os.path.dirname(t["cmd_path"]), exist_ok=True)
        cmd_content = generate_cmd(
            case=t["case_name"],
            interface_name=t["interface"],
            interface_config={"charge": t["_charge"], "chi0_tb": t["_chi0_tb"]},
            bx_nm=t["bx_nm"],
            grid_file=t["_grid_file"],
            plt_path=t["plt_path"],
            log_path=t["log_path"],
            par_path=os.path.join(cmd_dir, f"{interface_name}.par"),
        )
        with open(t["cmd_path"], "w", encoding="utf-8") as f:
            f.write(cmd_content)
        written += 1

    return written


def generate_batch_script(tasks: List[Dict], output_dir: str,
                          sentaurus_bin: str, license_port: int = 27020) -> str:
    """Generate a bash fallback script that runs all tasks sequentially.
    Useful for manual execution or debugging outside the scheduler.
    """
    script_lines = [
        "#!/bin/bash",
        f"export PATH={sentaurus_bin}:$PATH",
        f"export LM_LICENSE_FILE={license_port}@localhost",
        "",
        f"TOTAL={len(tasks)}",
        "COUNT=0",
        "PASS=0",
        "FAIL=0",
        f'LOG="{os.path.join(output_dir, "batch_manual.log")}"',
        'echo "=== Manual batch: $TOTAL sims ===" >> "$LOG"',
        'echo "Start: $(date)" >> "$LOG"',
        "",
    ]

    for t in tasks:
        script_lines.append(f'echo "[$((COUNT+1))/$TOTAL] {t["task_id"]} $(date +%H:%M:%S)" >> "$LOG"')
        script_lines.append(f'if sdevice "{t["cmd_path"]}" >> "$LOG" 2>&1; then')
        script_lines.append(f'    PASS=$((PASS + 1))')
        script_lines.append(f'else')
        script_lines.append(f'    FAIL=$((FAIL + 1))')
        script_lines.append(f'    echo "  FAILED: {t["task_id"]}" >> "$LOG"')
        script_lines.append(f'fi')

    script_lines.extend([
        "",
        'echo "=== FINISHED: $(date) ===" >> "$LOG"',
        'echo "Pass: $PASS  Fail: $FAIL  Total: $TOTAL" >> "$LOG"',
    ])

    script_path = os.path.join(output_dir, "run_manual.sh")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("\n".join(script_lines))
    os.chmod(script_path, 0o755)
    return script_path
