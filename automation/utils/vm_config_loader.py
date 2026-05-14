import json
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "vm_config.json"


def get_vm_config():
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    conn = cfg["vm_connection"]
    conn["ip"] = os.environ.get("TCAD_VM_IP", conn["ip"])
    conn["username"] = os.environ.get("TCAD_VM_USER", conn["username"])
    conn["password"] = os.environ.get("TCAD_VM_PASS", conn["password"])
    return cfg


def get_ssh_client(timeout=10):
    import paramiko
    cfg = get_vm_config()["vm_connection"]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        cfg["ip"],
        port=cfg.get("port", 22),
        username=cfg["username"],
        password=cfg["password"],
        timeout=timeout,
    )
    return ssh


def get_sftp_client(timeout=10):
    ssh = get_ssh_client(timeout)
    return ssh, ssh.open_sftp()


def get_vm_paths():
    cfg = get_vm_config()
    return cfg["paths"]


def get_sentaurus_config():
    cfg = get_vm_config()
    return cfg["sentaurus"]
