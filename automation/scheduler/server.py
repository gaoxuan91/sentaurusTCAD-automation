"""FastAPI server for TCAD batch simulation management.

Runs on VM (YOUR_VM_IP), port 8899.
Start: PYTHONPATH=YOUR_VM_PROJECT_PATH python -m uvicorn automation.scheduler.server:app --host 0.0.0.0 --port 8899
"""

import os
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from automation.scheduler.db import (
    init_db, get_conn, create_batch, add_tasks,
    get_batch_status, get_batch_results, mark_batch_failed,
)
from automation.scheduler.cmd_generator import (
    expand_experiment, generate_cmd_files, validate_config, generate_batch_script,
)
from automation.scheduler.worker import BatchWorker
from automation.scheduler.config import DEFAULT_MAX_WORKERS, DEFAULT_API_PORT
from automation.scheduler.config import SENTAURUS_BIN, SENTAURUS_SETUP

# VM-local defaults — all paths are Linux paths on the VM
VM_PROJECT_ROOT = Path("YOUR_VM_PROJECT_PATH")
VM_SWB = VM_PROJECT_ROOT / "swb" / "YOUR_PROJECT_NAME"
VM_SDE_DIR = VM_SWB / "SDE"
VM_SDEVICE_DIR = VM_SWB / "SDevice"
DEFAULT_PAR_FILE = str(VM_SDEVICE_DIR / "YOUR_MATERIAL_TB_LBIC_v4_He.par")
STATE_DB_DIR = VM_PROJECT_ROOT / "automation" / "state"

os.makedirs(STATE_DB_DIR, exist_ok=True)

app = FastAPI(title="TCAD Scheduler", version="1.0")

# Track active workers: {batch_id: {"thread": Thread, "worker": BatchWorker}}
_active_batches = {}  # type: Dict[str, Dict]


class BatchConfig(BaseModel):
    batch_name: str
    cases: Optional[List[str]] = None
    beam_config: Optional[Dict] = None
    interface: str = "no_effect"
    par_file: Optional[str] = None
    mesh_dir: Optional[str] = None
    output_dir: Optional[str] = None
    wavelength_nm: int = 450
    bias_V: float = 1.0
    n_rays: int = 100


def _fill_defaults(config: dict) -> dict:
    """Fill VM-local defaults for paths not specified by the client."""
    batch_name = config["batch_name"]

    if "mesh_dir" not in config or not config["mesh_dir"]:
        config["mesh_dir"] = str(VM_SDE_DIR)

    if "par_file" not in config or not config["par_file"]:
        # Auto-select PAR file based on interface
        interface = config.get("interface", "no_effect")
        if interface == "P1P2_mid":
            config["par_file"] = str(VM_SDEVICE_DIR / "YOUR_MATERIAL_TB_LBIC_v4_He_P1P2_mid.par")
        else:
            config["par_file"] = DEFAULT_PAR_FILE

    if "output_dir" not in config or not config["output_dir"]:
        config["output_dir"] = str(VM_SDEVICE_DIR / f"lbic_output_{batch_name}")

    if "cases" not in config or not config["cases"]:
        from automation.tools.sdevice import CASES
        config["cases"] = CASES

    if "beam_config" not in config or not config["beam_config"]:
        config["beam_config"] = {"start_nm": 50, "end_nm": 250, "step_nm": 5}

    return config


@app.on_event("startup")
def startup():
    """Initialize the global state DB on server start."""
    db_path = str(STATE_DB_DIR / "scheduler.db")
    init_db(db_path)


@app.get("/health")
def health():
    """VM resource status check."""
    try:
        import shutil
        disk = shutil.disk_usage("/")
        mem_info = {}
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        mem_info["total_kb"] = int(line.split()[1])
                    elif "MemAvailable" in line:
                        mem_info["available_kb"] = int(line.split()[1])
        except Exception:
            mem_info = {"error": "unavailable"}
        return {
            "status": "ok",
            "disk_gb_free": round(disk.free / (1024**3), 1),
            "memory": mem_info,
            "active_batches": list(_active_batches.keys()),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/batch/start")
def start_batch(config: BatchConfig):
    """Start a new batch simulation. Returns batch_id immediately."""
    cfg = _fill_defaults(config.dict())

    errors = validate_config(cfg)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Expand experiment
    expanded = expand_experiment(cfg)
    batch_id = expanded["batch_id"]

    # Check for duplicate batch
    db_path = str(STATE_DB_DIR / "scheduler.db")
    conn = get_conn(db_path)
    existing = conn.execute("SELECT batch_id FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail=f"Batch '{batch_id}' already exists")

    # Generate CMD files
    os.makedirs(cfg["output_dir"], exist_ok=True)
    n_cmds = generate_cmd_files(expanded)

    # Also generate manual fallback script
    generate_batch_script(
        expanded["tasks"], cfg["output_dir"],
        sentaurus_bin=SENTAURUS_BIN,
    )

    # Store in DB
    create_batch(conn, batch_id, json.dumps(cfg), n_cmds)
    add_tasks(conn, expanded["tasks"])
    conn.close()

    # Launch worker in background thread
    db_path_abs = os.path.abspath(db_path)
    worker = BatchWorker(db_path=db_path_abs, max_workers=DEFAULT_MAX_WORKERS,
                         sentaurus_bin=SENTAURUS_BIN, setup_script=SENTAURUS_SETUP)

    def _run():
        try:
            worker.run_batch(batch_id)
        finally:
            _active_batches.pop(batch_id, None)

    thread = threading.Thread(target=_run, name=f"batch-{batch_id}", daemon=True)
    _active_batches[batch_id] = {"thread": thread, "worker": worker}
    thread.start()

    return {"batch_id": batch_id, "task_count": n_cmds, "output_dir": cfg["output_dir"]}


@app.get("/batch/{batch_id}/status")
def batch_status(batch_id: str):
    """Get current progress of a batch."""
    db_path = str(STATE_DB_DIR / "scheduler.db")
    conn = get_conn(db_path)
    status = get_batch_status(conn, batch_id)
    conn.close()
    if not status:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return status


@app.get("/batch/{batch_id}/results")
def batch_results(batch_id: str, case: Optional[str] = None):
    """Get photocurrent results for a batch. Optionally filter by case name."""
    db_path = str(STATE_DB_DIR / "scheduler.db")
    conn = get_conn(db_path)
    results = get_batch_results(conn, batch_id, case)
    conn.close()
    return {"batch_id": batch_id, "count": len(results), "results": results}


@app.get("/batch")
def list_batches():
    """List all batches."""
    db_path = str(STATE_DB_DIR / "scheduler.db")
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT batch_id, status, task_total, task_done, task_failed, created_at FROM batches ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/batch/{batch_id}/cancel")
def cancel_batch(batch_id: str):
    """Cancel a running batch."""
    if batch_id not in _active_batches:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not running")
    entry = _active_batches[batch_id]
    entry["worker"].cancel()
    return {"status": "cancel_requested", "batch_id": batch_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=DEFAULT_API_PORT)
