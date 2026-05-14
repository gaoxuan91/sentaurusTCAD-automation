"""TCAD Agent Tools — LLM-callable functions for autonomous experiment management.

These tools are designed to be called by Claude Code to:
1. Submit experiments to the VM scheduler
2. Monitor batch progress
3. Analyze results with validation
4. Diagnose failures using the knowledge base
5. Compare with historical batches

All functions return structured dicts with a "summary" key for LLM consumption.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.client.batch_client import SSHSchedulerClient, TCADSchedulerError

# ---------------------------------------------------------------------------
# Knowledge base paths (Host side)
# ---------------------------------------------------------------------------
KB_PATHS = {
    "claude_md": PROJECT_ROOT / "CLAUDE.md",
    "handover": PROJECT_ROOT / "HANDOVER.md",
    "agents_md": PROJECT_ROOT / "AGENTS.md",
    "project_status": PROJECT_ROOT / "docs" / "PROJECT_STATUS.md",
    "workflow": PROJECT_ROOT / "docs" / "WORKFLOW.md",
    "troubleshooting_dir": PROJECT_ROOT / "docs" / "troubleshooting",
    "simulation_inventory": PROJECT_ROOT / "docs" / "SIMULATION_INVENTORY.md",
}

# ---------------------------------------------------------------------------
# Known parameters (mirrors CLAUDE.md for quick LLM reference without file reads)
# ---------------------------------------------------------------------------
KNOWN_CASES = [
    "baseline", "tb_vertical_single", "tb_parallel_single",
    "tb_double", "tb_parallel_multi", "tb_wide", "tb_dense",
]

INTERFACE_PRESETS = {
    "no_effect": "geometry only, no TB physics (reference)",
    "P1P2_mid": "Charge=+-1e12 cm^-2, Chi0_TB=3.30 eV (full TB model)",
}

PAR_PRESETS = {
    "v4_He": "多晶参数: mu=(10,20), chi=3.40, tau=100us",
    "v5_sc": "单晶参数: mu=(1000,1000), chi=3.60, tau_e=10us, tau_h=400us",
}

BEAM_PRESETS = {
    "full": {"start_nm": 50, "end_nm": 250, "step_nm": 5},    # 41 positions
    "coarse": {"start_nm": 50, "end_nm": 250, "step_nm": 10},  # 21 positions
    "quick": {"start_nm": 50, "end_nm": 250, "step_nm": 20},   # 11 positions
    "single": {"start_nm": 150, "end_nm": 150, "step_nm": 10}, # 1 position
}

# ---------------------------------------------------------------------------
# Core Agent Tools
# ---------------------------------------------------------------------------

def submit_experiment(
    batch_name: str,
    cases: Optional[List[str]] = None,
    interface: str = "no_effect",
    par_preset: str = "v5_sc",
    beam_preset: str = "full",
    wavelength_nm: int = 450,
    n_rays: int = 100,
    vm_host: str = "YOUR_VM_IP",
    vm_port: int = 8899,
    dry_run: bool = False,
) -> Dict:
    """Submit an LBIC experiment to the VM scheduler.

    Parameters:
        batch_name: Unique name for this batch (e.g., 'v6_full_7case')
        cases: List of case names. None = all 7 cases.
               Available: baseline, tb_vertical_single, tb_parallel_single,
                         tb_double, tb_parallel_multi, tb_wide, tb_dense
        interface: 'no_effect' (geometry only) or 'P1P2_mid' (full TB model)
        par_preset: 'v4_He' (polycrystal) or 'v5_sc' (single crystal)
        beam_preset: 'full' (41pos), 'coarse' (21pos), 'quick' (11pos), or 'single' (1pos)
        dry_run: If True, return the config JSON without submitting

    Returns:
        dict with batch_id, task_count, output_dir, and config used
    """
    if cases is None:
        cases = KNOWN_CASES

    beam_config = BEAM_PRESETS.get(beam_preset, BEAM_PRESETS["full"])

    config = {
        "batch_name": batch_name,
        "cases": cases,
        "beam_config": beam_config,
        "interface": interface,
        "wavelength_nm": wavelength_nm,
        "n_rays": n_rays,
    }

    if dry_run:
        n_pos = len(list(range(beam_config["start_nm"], beam_config["end_nm"] + 1, beam_config["step_nm"])))
        n_tasks = len(cases) * n_pos
        est_min = round(n_tasks / 3 * 0.2, 1)  # ~12s/sim, 3 workers
        return {
            "dry_run": True,
            "config": config,
            "estimated_tasks": n_tasks,
            "estimated_time_min": est_min,
            "summary": (
                f"[DRY RUN] Would submit '{batch_name}': {len(cases)} cases x {n_pos} positions = "
                f"{n_tasks} tasks, ~{est_min} min. Interface: {interface}, PAR: {par_preset}."
            ),
        }

    client = SSHSchedulerClient(vm_host=vm_host, port=vm_port)
    try:
        result = client.start_batch(config)
        return {
            **result,
            "config": config,
            "summary": (
                f"Batch '{batch_name}' submitted: {result['task_count']} tasks "
                f"({len(cases)} cases x {len(list(range(beam_config['start_nm'], beam_config['end_nm'] + 1, beam_config['step_nm'])))} positions). "
                f"Interface: {interface}, PAR: {par_preset}. "
                f"Output: {result.get('output_dir', 'N/A')}"
            ),
        }
    except TCADSchedulerError as e:
        return {"error": True, "code": e.code, "detail": str(e.detail),
                "summary": f"Failed to submit batch: [{e.code}] {e.detail}"}


def check_batch(batch_id: str, vm_host: str = "YOUR_VM_IP", vm_port: int = 8899) -> Dict:
    """Check the progress of a running or completed batch.

    Returns dict with status, task_done, task_total, task_failed, running, pending.
    """
    client = SSHSchedulerClient(vm_host=vm_host, port=vm_port)
    try:
        status = client.get_status(batch_id)
        pct = (status.get("task_done", 0) / max(status.get("task_total", 1), 1)) * 100
        status["summary"] = (
            f"Batch '{batch_id}': {status.get('status', '?')}. "
            f"{status.get('task_done', 0)}/{status.get('task_total', 0)} done ({pct:.0f}%), "
            f"{status.get('task_failed', 0)} failed, {status.get('running', 0)} running."
        )
        return status
    except TCADSchedulerError as e:
        return {"error": True, "summary": f"Failed to check batch: {e}"}


def get_results(batch_id: str, case: Optional[str] = None,
                vm_host: str = "YOUR_VM_IP", vm_port: int = 8899) -> Dict:
    """Fetch photocurrent results for a completed batch.

    Returns structured results with per-case photocurrent data.
    """
    client = SSHSchedulerClient(vm_host=vm_host, port=vm_port)
    try:
        data = client.get_results(batch_id, case=case)
        results = data.get("results", [])

        # Group by case for easy analysis
        by_case = {}
        for r in results:
            c = r["case_name"]
            if c not in by_case:
                by_case[c] = []
            by_case[c].append(r)

        # Summary per case
        case_summaries = {}
        for c, items in by_case.items():
            currents = [it["photocurrent"] for it in items
                       if it["photocurrent"] is not None and abs(it["photocurrent"]) > 1e-15]
            failed = [it for it in items if it["status"] == "failed"]
            case_summaries[c] = {
                "n_total": len(items),
                "n_done": len(items) - len(failed),
                "n_failed": len(failed),
                "peak_current": max(currents) if currents else None,
                "mean_current": sum(currents) / len(currents) if currents else None,
            }

        return {
            "batch_id": batch_id,
            "by_case": by_case,
            "case_summaries": case_summaries,
            "raw": results,
            "summary": _build_results_summary(case_summaries),
        }
    except TCADSchedulerError as e:
        return {"error": True, "summary": f"Failed to get results: {e}"}


def diagnose_failure(batch_id: str, vm_host: str = "YOUR_VM_IP", vm_port: int = 8899) -> Dict:
    """Diagnose failed tasks in a batch by analyzing error messages.

    Returns categorized failure analysis and suggested fixes.
    """
    client = SSHSchedulerClient(vm_host=vm_host, port=vm_port)
    try:
        data = client.get_results(batch_id)
        results = data.get("results", [])

        failed = [r for r in results if r["status"] == "failed"]
        if not failed:
            return {"summary": f"No failed tasks in batch '{batch_id}'.", "failed_count": 0}

        # Categorize errors
        categories = {}
        for f in failed:
            msg = f.get("error_msg", "")
            if "convergence" in msg.lower() or "residual" in msg.lower():
                cat = "convergence"
            elif "license" in msg.lower():
                cat = "license"
            elif "mesh" in msg.lower() or "grid" in msg.lower():
                cat = "mesh"
            elif "memory" in msg.lower() or "allocation" in msg.lower():
                cat = "memory"
            elif "optics" in msg.lower() or "ray" in msg.lower():
                cat = "optics"
            elif "syntax" in msg.lower() or "unrecognized" in msg.lower():
                cat = "syntax"
            else:
                cat = "other"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(f)

        suggestions = []
        if "convergence" in categories:
            suggestions.append("收敛失败: 尝试减小 Quasistationary MaxStep 或增加 Iterations")
        if "license" in categories:
            suggestions.append("License 问题: 检查 LM_LICENSE_FILE 是否指向 27020@localhost")
        if "mesh" in categories:
            suggestions.append("网格问题: 检查 mesh 文件路径是否存在，TB 区域网格是否需要细化")
        if "memory" in categories:
            suggestions.append("内存不足: 减少并行 worker 数或使用更粗网格")
        if "optics" in categories:
            suggestions.append("光学配置问题: 检查 Window 坐标、RayTracing 配置、wavelength")
        if "syntax" in categories:
            suggestions.append("语法错误: 检查 CMD 文件语法，对照 CLAUDE.md 已验证语法规则")

        return {
            "batch_id": batch_id,
            "failed_count": len(failed),
            "categories": {k: len(v) for k, v in categories.items()},
            "sample_errors": [(f["case_name"], f["bx_nm"], (f.get("error_msg", "") or "")[:200])
                            for f in failed[:5]],
            "suggestions": suggestions,
            "summary": (
                f"Batch '{batch_id}': {len(failed)} failed tasks. "
                f"Categories: {dict((k, len(v)) for k, v in categories.items())}. "
                f"Suggestions: {'; '.join(suggestions[:3])}"
            ),
        }
    except TCADSchedulerError as e:
        return {"error": True, "summary": f"Failed to diagnose: {e}"}


def wait_and_report(batch_id: str, poll_interval: int = 30,
                    vm_host: str = "YOUR_VM_IP", vm_port: int = 8899) -> Dict:
    """Wait for a batch to complete, reporting progress at each interval.

    This is a blocking call. Use for batches that take minutes to hours.
    """
    client = SSHSchedulerClient(vm_host=vm_host, port=vm_port)
    return client.wait_for_completion(batch_id, poll_interval=poll_interval)


def list_batches(vm_host: str = "YOUR_VM_IP", vm_port: int = 8899) -> Dict:
    """List all batches in the scheduler database."""
    client = SSHSchedulerClient(vm_host=vm_host, port=vm_port)
    try:
        batches = client.list_batches()
        return {
            "batches": batches,
            "count": len(batches),
            "summary": f"{len(batches)} batches found: " +
                       ", ".join(f"{b['batch_id']}({b['status']})" for b in batches[:10]),
        }
    except TCADSchedulerError as e:
        return {"error": True, "summary": f"Failed to list batches: {e}"}


def cancel_batch(batch_id: str, vm_host: str = "YOUR_VM_IP", vm_port: int = 8899) -> Dict:
    """Cancel a running batch."""
    client = SSHSchedulerClient(vm_host=vm_host, port=vm_port)
    try:
        result = client.cancel_batch(batch_id)
        return {**result, "summary": f"Cancellation requested for batch '{batch_id}'."}
    except TCADSchedulerError as e:
        return {"error": True, "summary": f"Failed to cancel: {e}"}


def check_health(vm_host: str = "YOUR_VM_IP", vm_port: int = 8899) -> Dict:
    """Check VM scheduler health and resource availability."""
    client = SSHSchedulerClient(vm_host=vm_host, port=vm_port)
    try:
        h = client.health()
        mem = h.get("memory", {})
        summary = (
            f"VM healthy. Disk: {h.get('disk_gb_free', '?')}GB free. "
            f"Memory: {mem.get('available_kb', 0) // 1024}MB available / "
            f"{mem.get('total_kb', 0) // 1024}MB total. "
            f"Active batches: {h.get('active_batches', [])}"
        )
        return {**h, "summary": summary}
    except TCADSchedulerError as e:
        return {"error": True, "summary": f"VM unreachable: {e}"}


# ---------------------------------------------------------------------------
# Knowledge base tools (for LLM to read without raw file access)
# ---------------------------------------------------------------------------

def query_knowledge(topic: str) -> Dict:
    """Search the project knowledge base for relevant information.

    Topics: 'cases', 'parameters', 'interfaces', 'syntax', 'troubleshooting',
            'workflow', 'current_state', 'past_results'
    """
    topic_lower = topic.lower()

    if topic_lower in ("cases", "case"):
        return {
            "topic": "Simulation Cases",
            "content": {c: f"Case {i+1}/7" for i, c in enumerate(KNOWN_CASES)},
            "summary": f"7 cases available: {', '.join(KNOWN_CASES)}",
        }
    elif topic_lower in ("parameters", "params", "par"):
        return {"topic": "Material Parameter Presets", "content": PAR_PRESETS,
                "summary": "; ".join(f"{k}: {v}" for k, v in PAR_PRESETS.items())}
    elif topic_lower in ("interfaces", "interface"):
        return {"topic": "Interface Presets", "content": INTERFACE_PRESETS,
                "summary": "; ".join(f"{k}: {v}" for k, v in INTERFACE_PRESETS.items())}
    elif topic_lower in ("syntax", "grammar"):
        return {
            "topic": "Verified Syntax Rules",
            "content": {
                "SDE": "Coordinates in um, position needs 3 args, use sdegeo:set-contact",
                "Optics": "2D uses RayTracing, Window Origin=(x,y) Line(x1= x2=)",
                "Physics": "Each material needs its own Physics block",
                "CMD": "No Define @VAR@, no TMM for 2D, Polarization=0.5 required",
                "PLT": "Do NOT include Plot line in File block (causes binary output)",
            },
            "summary": "Key syntax rules retrieved. See CLAUDE.md for full reference.",
        }
    elif topic_lower in ("troubleshooting", "errors", "debug"):
        ts_dir = KB_PATHS["troubleshooting_dir"]
        if ts_dir.exists():
            files = sorted(ts_dir.glob("*.md"))
            return {
                "topic": "Troubleshooting Knowledge Base",
                "file_count": len(files),
                "files": [f.name for f in files],
                "summary": f"{len(files)} troubleshooting records available in docs/troubleshooting/.",
            }
        return {"summary": "Troubleshooting directory not found."}
    elif topic_lower in ("workflow", "process"):
        return {
            "topic": "Workflow",
            "content": {
                "steps": [
                    "1. Generate mesh (SDE, manual, requires Xvfb)",
                    "2. Submit experiment via agent (POST /batch/start)",
                    "3. Scheduler auto-generates CMDs, runs sdevice with 3 workers",
                    "4. PLT parsed on VM, results stored in SQLite",
                    "5. Pull results via agent, run L3 validation on Host",
                    "6. Generate plots",
                ],
                "automation_boundary": "SDE mesh generation is manual. Everything after is automated.",
            },
            "summary": "Workflow: SDE(manual) → Submit(API) → SDevice(auto) → Parse(VM) → Validate(Host)",
        }
    elif topic_lower in ("current_state", "status", "state"):
        return {
            "topic": "Current Project State",
            "summary": "See HANDOVER.md for latest. Key: v5_sc active, Scheduler v1.0 deployed, 3D paused.",
        }
    elif topic_lower in ("past_results", "history", "batches"):
        return {
            "topic": "Past Results",
            "summary": "See docs/SIMULATION_INVENTORY.md for full catalog. 4700+ simulations total.",
        }
    else:
        return {
            "topic": topic,
            "summary": f"No specific knowledge for '{topic}'. Try: cases, parameters, interfaces, syntax, troubleshooting, workflow, current_state, past_results.",
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_results_summary(case_summaries: Dict) -> str:
    lines = []
    for case, s in case_summaries.items():
        peak = f"{s['peak_current']:.2e}A" if s['peak_current'] else "N/A"
        lines.append(f"{case}: {s['n_done']}/{s['n_total']} done, peak={peak}")
    return " | ".join(lines)
