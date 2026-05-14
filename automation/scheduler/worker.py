"""Worker pool for parallel SDevice simulation execution on VM."""

import os
import time
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from automation.scheduler.db import (
    get_conn, claim_next_task, mark_task_done, mark_task_failed,
    reset_task_for_retry, batch_has_pending, mark_batch_done, mark_batch_failed,
    mark_batch_running,
)
from automation.utils.plt_parser import extract_photocurrent, sanity_check
from automation.utils.validation import validate_batch
from automation.scheduler.config import (
    DEFAULT_MAX_WORKERS, DEFAULT_MAX_RETRIES,
    SENTAURUS_BIN, SENTAURUS_SETUP, DARK_CURRENT_THRESHOLD,
)


class BatchWorker:
    """Manages parallel execution of SDevice tasks with a thread pool."""

    def __init__(self, db_path: str, max_workers: int = DEFAULT_MAX_WORKERS,
                 sentaurus_bin: str = SENTAURUS_BIN,
                 setup_script: str = SENTAURUS_SETUP,
                 license_port: int = 27020):
        self.db_path = db_path
        self.max_workers = max_workers
        self.sentaurus_bin = sentaurus_bin
        self.setup_script = setup_script
        self.license_port = license_port
        self._cancel_event = threading.Event()
        self._env = self._build_env()

    def _build_env(self) -> dict:
        env = os.environ.copy()
        env["PATH"] = f"{self.sentaurus_bin}:{env.get('PATH', '')}"
        env["LM_LICENSE_FILE"] = f"{self.license_port}@localhost"
        env["STDB"] = "/dev/null"
        return env

    def run_batch(self, batch_id: str) -> dict:
        """Execute all pending tasks for a batch. Blocks until done or cancelled."""
        self._cancel_event.clear()
        conn = get_conn(self.db_path)
        mark_batch_running(conn, batch_id)
        conn.close()

        submitted = 0
        completed = 0
        failed = 0
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            # Submit initial batch of tasks
            for _ in range(self.max_workers):
                conn = get_conn(self.db_path)
                task = claim_next_task(conn, batch_id)
                conn.close()
                if task:
                    f = executor.submit(self._run_one, task)
                    futures[f] = task
                    submitted += 1

            # As tasks complete, claim and submit more
            while futures and not self._cancel_event.is_set():
                done_futures = []
                for f in as_completed(futures):
                    task_result = f.result()
                    if task_result["status"] == "done":
                        completed += 1
                    else:
                        failed += 1
                    results.append(task_result)
                    done_futures.append(f)

                for f in done_futures:
                    del futures[f]

                # Claim new tasks to keep pool full
                while len(futures) < self.max_workers and not self._cancel_event.is_set():
                    conn = get_conn(self.db_path)
                    task = claim_next_task(conn, batch_id)
                    conn.close()
                    if task:
                        f = executor.submit(self._run_one, task)
                        futures[f] = task
                        submitted += 1
                    else:
                        break  # No more pending tasks

            # Cancel remaining if requested
            if self._cancel_event.is_set():
                for f in futures:
                    f.cancel()

        # Finalize batch status
        conn = get_conn(self.db_path)
        if self._cancel_event.is_set():
            mark_batch_failed(conn, batch_id)
        else:
            n_failed = sum(1 for r in results if r["status"] == "failed")
            if n_failed > 0:
                mark_batch_done(conn, batch_id)  # done with partial failures
            else:
                mark_batch_done(conn, batch_id)

            # Run L2 validation
            batch_results = self._collect_validation_data(conn, batch_id)
            l2_report = validate_batch(batch_results)
        conn.close()

        return {
            "batch_id": batch_id,
            "submitted": submitted,
            "completed": completed,
            "failed": failed,
            "cancelled": self._cancel_event.is_set(),
            "l2_validation": l2_report if not self._cancel_event.is_set() else None,
        }

    def _run_one(self, task: dict) -> dict:
        """Execute one SDevice simulation with retry logic."""
        task_id = task["task_id"]
        cmd_path = task["cmd_path"]
        max_retries = DEFAULT_MAX_RETRIES

        for attempt in range(max_retries):
            if self._cancel_event.is_set():
                return {"task_id": task_id, "status": "cancelled"}

            start = time.time()
            try:
                result = subprocess.run(
                    ["sdevice", cmd_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True,
                    timeout=600,
                    env=self._env,
                )
                duration = time.time() - start

                if result.returncode != 0:
                    stderr_tail = result.stderr[-500:] if result.stderr else "no stderr"
                    if attempt < max_retries - 1:
                        conn = get_conn(self.db_path)
                        mark_task_failed(conn, task_id, f"rc={result.returncode}: {stderr_tail}")
                        reset_task_for_retry(conn, task_id)
                        conn.close()
                        continue
                    else:
                        conn = get_conn(self.db_path)
                        mark_task_failed(conn, task_id, f"Exhausted {max_retries} retries: {stderr_tail}")
                        conn.close()
                        return {"task_id": task_id, "status": "failed",
                                "error": f"rc={result.returncode}"}

                # Parse PLT output
                photocurrent = None
                convergence = True
                plt_path = task.get("plt_path", "")
                if plt_path and os.path.exists(plt_path):
                    with open(plt_path, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    photocurrent = extract_photocurrent(content)
                    check = sanity_check(content, label=task_id)
                    if check["status"] == "WARN":
                        convergence = False
                else:
                    convergence = False

                conn = get_conn(self.db_path)
                mark_task_done(
                    conn, task_id,
                    photocurrent=photocurrent or 0.0,
                    convergence=convergence,
                    duration_s=duration,
                )
                conn.close()
                return {"task_id": task_id, "status": "done",
                        "photocurrent": photocurrent, "duration_s": duration}

            except subprocess.TimeoutExpired:
                if attempt < max_retries - 1:
                    conn = get_conn(self.db_path)
                    mark_task_failed(conn, task_id, "timeout")
                    reset_task_for_retry(conn, task_id)
                    conn.close()
                else:
                    conn = get_conn(self.db_path)
                    mark_task_failed(conn, task_id, f"timeout after {max_retries} retries")
                    conn.close()
                    return {"task_id": task_id, "status": "failed", "error": "timeout"}

            except FileNotFoundError:
                conn = get_conn(self.db_path)
                mark_task_failed(conn, task_id, "sdevice not found in PATH")
                conn.close()
                return {"task_id": task_id, "status": "failed", "error": "sdevice not found"}

            except Exception as e:
                conn = get_conn(self.db_path)
                mark_task_failed(conn, task_id, f"unexpected error: {type(e).__name__}: {e}")
                conn.close()
                return {"task_id": task_id, "status": "failed",
                        "error": f"{type(e).__name__}: {e}"}

        return {"task_id": task_id, "status": "failed", "error": "exhausted retries"}

    def _collect_validation_data(self, conn, batch_id: str) -> dict:
        """Collect photocurrent data in the format validation.py expects."""
        rows = conn.execute(
            "SELECT case_name, bx_nm, photocurrent FROM tasks WHERE batch_id=? AND status='done'",
            (batch_id,),
        ).fetchall()
        results = {}
        for r in rows:
            if r["case_name"] not in results:
                results[r["case_name"]] = {}
            results[r["case_name"]][r["bx_nm"]] = r["photocurrent"]
        return results

    def cancel(self):
        self._cancel_event.set()
