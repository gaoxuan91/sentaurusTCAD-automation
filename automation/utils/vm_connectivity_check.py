# ============================================================
# YOUR_MATERIAL Sentaurus Project
# VM 连接性检查脚本 (第二阶段备用)
# 第一阶段用途: 手动运行，验证 SSH/SFTP 连通性
# ============================================================
# 使用方式:
#   python vm_connectivity_check.py --ip <VM_IP> --user <username>
# ============================================================

import argparse
import socket
import sys

def check_ssh(ip, port=22, timeout=5):
    """检查 SSH 端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception as e:
        return False

def ping_host(ip, count=1, timeout=5):
    """检查 ICMP 连通性"""
    import subprocess
    try:
        result = subprocess.run(
            ['ping', '-n', str(count), '-w', str(timeout*1000), ip],
            capture_output=True, text=True, timeout=timeout+1
        )
        return result.returncode == 0
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description='VM 连接性检查')
    parser.add_argument('--ip', default='YOUR_VM_IP', help='VM IP 地址')
    parser.add_argument('--user', default='tcad', help='用户名')
    parser.add_argument('--port', type=int, default=22, help='SSH 端口')
    args = parser.parse_args()

    print(f"检查 VM 连通性: {args.ip}")
    print("-" * 40)

    # Ping 检查
    print(f"[1] Ping 检查... ", end='')
    if ping_host(args.ip):
        print("✓ 成功")
    else:
        print("✗ 失败")
        print("  提示: 请确认 VM IP 地址正确，且网络可达")

    # SSH 端口检查
    print(f"[2] SSH 端口({args.port})检查... ", end='')
    if check_ssh(args.ip, args.port):
        print("✓ 端口开放")
    else:
        print("✗ 端口未开放或被阻断")
        print("  提示: 请确认 VM 的 SSH 服务已启动，且端口未被防火墙阻断")

    print("-" * 40)
    print("检查完成")
    print("如需完整 SSH/SFTP 功能，请填写 env/centos_info.md")

if __name__ == '__main__':
    main()