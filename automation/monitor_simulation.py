#!/usr/bin/env python3
"""
监控正在运行的 SDevice 仿真
"""

import paramiko
import time
import sys

VM_IP = "YOUR_VM_IP"
VM_USER = "tcad"
VM_PASSWORD = "123"
LOG_FILE = "YOUR_VM_PROJECT_PATH/swb/YOUR_PROJECT_NAME/SDevice/test_vertical_246k_conservative.log"

def monitor():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASSWORD)

    print("监控 SDevice 仿真进度...")
    print("=" * 70)

    last_size = 0
    no_change_count = 0

    try:
        while True:
            # 检查日志文件大小
            stdin, stdout, stderr = ssh.exec_command(f"wc -l {LOG_FILE} 2>/dev/null || echo '0'")
            line_count = stdout.read().decode().strip().split()[0]

            # 检查内存
            stdin, stdout, stderr = ssh.exec_command("free -h | grep Mem")
            mem_info = stdout.read().decode().strip()

            # 检查进程
            stdin, stdout, stderr = ssh.exec_command("pgrep -f sdevice | wc -l")
            process_count = stdout.read().decode().strip()

            # 读取最后几行
            stdin, stdout, stderr = ssh.exec_command(f"tail -n 3 {LOG_FILE} 2>/dev/null || echo 'Log not found'")
            last_lines = stdout.read().decode().strip()

            print(f"\r进程: {process_count} | 日志行数: {line_count} | 内存: {mem_info}", end='')

            # 检查是否有变化
            if line_count == str(last_size):
                no_change_count += 1
            else:
                no_change_count = 0
                last_size = int(line_count) if line_count.isdigit() else 0

            # 如果日志不再增长且没有进程，可能已完成
            if no_change_count > 6 and process_count == '0':
                print("\n\n仿真似乎已完成或停止")
                print("\n最后几行日志:")
                print("-" * 70)
                print(last_lines)
                print("-" * 70)
                break

            # 每10秒显示一次详细信息
            if int(time.time()) % 10 == 0:
                print("\n" + "-" * 70)
                print("最新日志:")
                print(last_lines)
                print("-" * 70)

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\n监控已停止")
    finally:
        ssh.close()

if __name__ == '__main__':
    monitor()
