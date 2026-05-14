#!/bin/bash
# ============================================================
# YOUR_MATERIAL Sentaurus Project
# VM 通信链路验证脚本
# 第一阶段使用：手动执行，验证环境连通性
# ============================================================
# 用法: 在 CentOS VM 终端中运行此脚本
# ============================================================

echo "========================================"
echo "YOUR_MATERIAL Project - VM 环境检查脚本"
echo "========================================"
echo ""

# 1. 系统信息
echo "[1/6] 系统信息"
echo "----------------------------"
cat /etc/centos-release 2>/dev/null || echo "CentOS 版本未知"
uname -r
echo ""

# 2. 用户信息
echo "[2/6] 用户信息"
echo "----------------------------"
whoami
echo "Home: $HOME"
echo ""

# 3. CPU/内存
echo "[3/6] 硬件资源"
echo "----------------------------"
nproc 2>/dev/null && echo "CPU 核心数: $(nproc)"
free -h 2>/dev/null || echo "内存信息未知"
echo ""

# 4. Sentaurus 命令检查
echo "[4/6] Sentaurus 命令检查"
echo "----------------------------"
commands="swb sde sdevice svisual"
for cmd in $commands; do
    path=$(which $cmd 2>/dev/null)
    if [ -n "$path" ]; then
        echo "✓ $cmd: $path"
    else
        echo "✗ $cmd: 未找到"
    fi
done
echo ""

# 5. 环境变量
echo "[5/6] Sentaurus 环境变量"
echo "----------------------------"
echo "STROOT: ${STROOT:-未设置}"
echo "PATH (前3项): $(echo $PATH | tr ':' '\n' | head -3 | tr '\n' ' ')"
echo ""

# 6. 共享文件夹检查
echo "[6/6] 共享文件夹 / 文件系统"
echo "----------------------------"
df -h | grep -E "mount|shared|vmware" || echo "未找到特定挂载信息"
ls /mnt/ 2>/dev/null || echo "/mnt/ 为空"
ls /home/ 2>/dev/null | head -5
echo ""

echo "========================================"
echo "检查完成"
echo "========================================"
echo "请将上述结果复制到 Host 端 env/ 目录下的文档中"
echo "如有任何 ✗ 项，请先解决该问题再继续"
echo ""