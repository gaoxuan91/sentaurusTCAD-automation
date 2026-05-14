# VM Hardware Optimization for 3D TCAD Simulation

## 本机硬件配置

- **CPU**: AMD Ryzen 7 4800H (8 cores, 16 threads)
- **内存**: 估计 16-32 GB（需确认）
- **架构**: Zen 2, 7nm, 基础频率 2.9 GHz, 最大 4.2 GHz

## 当前VM配置（需确认）

通过SSH检查当前配置：
```bash
ssh tcad@YOUR_VM_IP
cat /proc/cpuinfo | grep processor | wc -l  # CPU核心数
free -h                                      # 内存
```

## 推荐VM配置（3D仿真优化）

### 方案A：平衡配置（推荐）
```
CPU: 12 vCPUs (6 cores × 2 threads)
内存: 20 GB
硬盘: 100 GB (thin provisioning)
```

**理由**：
- 保留4个线程给宿主机（Windows + 其他应用）
- 3D TCAD仿真是内存密集型，20GB足够150k节点网格
- 允许宿主机流畅运行

### 方案B：最大性能（仅3D仿真时）
```
CPU: 14 vCPUs (7 cores × 2 threads)
内存: 24 GB
硬盘: 100 GB
```

**理由**：
- 最大化VM性能
- 仅在专注仿真时使用
- 宿主机可能略卡顿

### 方案C：保守配置（当前可能配置）
```
CPU: 8 vCPUs (4 cores × 2 threads)
内存: 16 GB
硬盘: 80 GB
```

**问题**：
- 3D仿真可能较慢
- 内存可能不足（150k节点需要~18GB）

## 配置检查清单

### 1. CPU配置
```bash
# 在VM中检查
lscpu | grep -E "CPU\(s\)|Thread|Core"
```

**优化建议**：
- 启用所有CPU特性（VT-x/AMD-V, IOMMU）
- 在VMware/VirtualBox中设置"处理器数量"
- 启用"虚拟化CPU性能计数器"

### 2. 内存配置
```bash
# 在VM中检查
free -h
cat /proc/meminfo | grep MemTotal
```

**3D仿真内存需求估算**：
```
网格节点数: 150,000
每节点内存: ~100-120 KB
总需求: 150k × 120KB ≈ 18 GB

推荐配置: 20-24 GB（留20%余量）
```

### 3. 硬盘I/O优化
```bash
# 检查硬盘类型
df -Th
lsblk
```

**优化**：
- 使用SSD（如果可能）
- 启用"预分配磁盘空间"（VMware）
- 禁用"压缩磁盘"

### 4. 网络配置
```bash
# 检查网络延迟
ping -c 5 192.168.190.1
```

**优化**：
- 使用"桥接模式"或"NAT"（避免"仅主机"）
- 禁用不必要的网络服务

## 性能测试

### 测试1：CPU性能
```bash
# 在VM中运行
time dd if=/dev/zero of=/tmp/test bs=1M count=1024
# 应该 < 2秒
```

### 测试2：内存带宽
```bash
# 安装sysbench
sudo apt install sysbench
sysbench memory --memory-total-size=10G run
# 应该 > 5000 MB/s
```

### 测试3：单点LBIC时间
```bash
# 运行baseline 3D单点
time sdevice baseline_3d_single_point.cmd
# 目标: < 10分钟/点
```

## 3D仿真时间估算

### 当前配置（假设8 vCPUs, 16GB）
```
单点时间: 10-15 分钟
粗扫描 (441 points): 441 × 12 min = 5,292 min ≈ 88 hours ≈ 3.7 days
细扫描 (1681 points): 1681 × 12 min = 20,172 min ≈ 336 hours ≈ 14 days
```

### 优化后配置（12 vCPUs, 20GB）
```
单点时间: 6-8 分钟
粗扫描 (441 points): 441 × 7 min = 3,087 min ≈ 51 hours ≈ 2.1 days
细扫描 (1681 points): 1681 × 7 min = 11,767 min ≈ 196 hours ≈ 8.2 days
```

### 最优配置（14 vCPUs, 24GB）
```
单点时间: 5-6 分钟
粗扫描 (441 points): 441 × 5.5 min = 2,426 min ≈ 40 hours ≈ 1.7 days
细扫描 (1681 points): 1681 × 5.5 min = 9,246 min ≈ 154 hours ≈ 6.4 days
```

## 实施步骤

### Step 1: 检查当前配置
```bash
ssh tcad@YOUR_VM_IP
echo "=== CPU ==="
lscpu | grep -E "CPU\(s\)|Thread|Core"
echo "=== Memory ==="
free -h
echo "=== Disk ==="
df -h /home/tcad
```

### Step 2: 调整VM设置（VMware示例）
1. 关闭VM
2. 编辑虚拟机设置
3. 处理器：
   - 处理器数量：6（或7）
   - 每个处理器的核心数：2
4. 内存：20 GB（或24 GB）
5. 硬盘：确保有100GB可用空间
6. 启动VM

### Step 3: 验证配置
```bash
ssh tcad@YOUR_VM_IP
# 应该看到12（或14）个CPU
lscpu | grep "CPU(s):"
# 应该看到20GB（或24GB）内存
free -h | grep Mem
```

### Step 4: 运行性能测试
```bash
# 测试单点LBIC
cd YOUR_VM_PROJECT_PATH/swb/YOUR_PROJECT_NAME/SDevice
time sdevice baseline_3d_single_point.cmd
```

## 风险与权衡

### 风险1：宿主机性能下降
- **症状**：Windows卡顿，浏览器慢
- **解决**：降低VM CPU到10 vCPUs

### 风险2：内存不足
- **症状**：VM频繁swap，仿真极慢
- **解决**：减小网格密度，或增加宿主机内存

### 风险3：过热
- **症状**：CPU温度>90°C，降频
- **解决**：清理散热器，降低VM CPU

## 推荐配置总结

**对于你的硬件（Ryzen 7 4800H）**：

✅ **推荐配置**：
- CPU: 12 vCPUs (6 cores × 2 threads)
- 内存: 20 GB
- 预期单点时间: 6-8 分钟
- 粗扫描时间: ~2 days

⚠️ **最小配置**：
- CPU: 8 vCPUs
- 内存: 16 GB
- 预期单点时间: 10-12 分钟
- 粗扫描时间: ~3.5 days

🚀 **最大配置**（仅专注仿真时）：
- CPU: 14 vCPUs
- 内存: 24 GB
- 预期单点时间: 5-6 分钟
- 粗扫描时间: ~1.7 days

## 下一步

1. 检查当前VM配置
2. 根据需求调整
3. 运行单点测试验证
4. 开始3D仿真
