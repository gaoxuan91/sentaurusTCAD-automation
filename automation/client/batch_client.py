"""Host-side client for the TCAD VM scheduler API.

Supports two transports:
  - HTTP direct (when VM port 8899 is reachable from Host)
  - SSH tunnel (when only SSH is available; runs curl via paramiko exec_command)
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional


class TCADSchedulerClient:
    """Communicates with the TCAD scheduler on the VM using direct HTTP."""

    def __init__(self, vm_host: str = "YOUR_VM_IP", port: int = 8899,
                 timeout: int = 10):
        self.base_url = f"http://{vm_host}:{port}"
        self.timeout = timeout

    def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            try:
                detail = json.loads(error_body)
            except json.JSONDecodeError:
                detail = error_body
            raise TCADSchedulerError(e.code, detail, path) from e
        except urllib.error.URLError as e:
            raise TCADSchedulerError(0, str(e.reason), path) from e

    def health(self) -> Dict:
        return self._request("GET", "/health")

    def start_batch(self, config: Dict) -> Dict:
        return self._request("POST", "/batch/start", config)

    def get_status(self, batch_id: str) -> Dict:
        return self._request("GET", f"/batch/{batch_id}/status")

    def get_results(self, batch_id: str, case: Optional[str] = None) -> Dict:
        path = f"/batch/{batch_id}/results"
        if case:
            path += f"?case={case}"
        return self._request("GET", path)

    def list_batches(self) -> List[Dict]:
        return self._request("GET", "/batch")

    def cancel_batch(self, batch_id: str) -> Dict:
        return self._request("POST", f"/batch/{batch_id}/cancel")

    def wait_for_completion(self, batch_id: str, poll_interval: int = 30,
                            show_progress: bool = True) -> Dict:
        while True:
            status = self.get_status(batch_id)
            if show_progress:
                done = status.get("task_done", 0)
                failed = status.get("task_failed", 0)
                total = status.get("task_total", 0)
                running = status.get("running", 0)
                pct = (done / total * 100) if total > 0 else 0
                bar = "=" * int(pct / 5) + "-" * (20 - int(pct / 5))
                print(f"\r  [{bar}] {done}/{total} done, {running} running, {failed} failed  ", end="", flush=True)
            if status.get("status") in ("done", "failed"):
                if show_progress:
                    print()
                return status
            time.sleep(poll_interval)


class SSHSchedulerClient(TCADSchedulerClient):
    """Communicates with the TCAD scheduler via SSH tunnel (curl on VM).

    Use this when the Host cannot directly reach VM port 8899.
    Requires paramiko on the Host.
    """

    def __init__(self, vm_host: str = "YOUR_VM_IP", port: int = 8899,
                 vm_user: str = "tcad", vm_password: str = os.environ.get("TCAD_VM_PASSWORD", ""),
                 ssh_port: int = 22, timeout: int = 15):
        super().__init__(vm_host, port, timeout)
        self.vm_user = vm_user
        self.vm_password = vm_password
        self.ssh_port = ssh_port
        self._ssh = None

    def _get_ssh(self):
        if self._ssh is None:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.base_url.split("//")[1].split(":")[0],
                       port=self.ssh_port, username=self.vm_user,
                       password=self.vm_password, timeout=self.timeout)
            self._ssh = ssh
        return self._ssh

    def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{path}"
        if body:
            data_str = json.dumps(body)
            cmd = f"curl -s -X {method} '{url}' -H 'Content-Type: application/json' -d '{data_str}'"
        else:
            cmd = f"curl -s -X {method} '{url}'"
        try:
            ssh = self._get_ssh()
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=self.timeout)
            out = stdout.read().decode("utf-8", errors="ignore")
            err = stderr.read().decode("utf-8", errors="ignore")
            if not out.strip():
                raise TCADSchedulerError(0, f"Empty response (stderr: {err[:200]})", path)
            try:
                result = json.loads(out)
            except json.JSONDecodeError:
                raise TCADSchedulerError(0, f"Invalid JSON: {out[:200]}", path)
            if "detail" in result and isinstance(result.get("detail"), list):
                raise TCADSchedulerError(400, result["detail"], path)
            return result
        except TCADSchedulerError:
            raise
        except Exception as e:
            raise TCADSchedulerError(0, str(e), path) from e

    def close(self):
        if self._ssh:
            self._ssh.close()
            self._ssh = None


class TCADSchedulerError(Exception):
    def __init__(self, code: int, detail, path: str):
        self.code = code
        self.detail = detail
        self.path = path
        super().__init__(f"[{code}] {path}: {detail}")


def get_client(vm_host: str = "YOUR_VM_IP", port: int = 8899,
               prefer_ssh: bool = True) -> TCADSchedulerClient:
    """Factory: return the best available client (SSH if Host can't reach VM directly)."""
    if prefer_ssh:
        try:
            client = SSHSchedulerClient(vm_host=vm_host, port=port)
            client.health()
            return client
        except Exception:
            pass
    try:
        client = TCADSchedulerClient(vm_host=vm_host, port=port)
        client.health()
        return client
    except Exception:
        return SSHSchedulerClient(vm_host=vm_host, port=port)
