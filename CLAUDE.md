# Sentaurus TCAD 自动化 — Claude Code 指令

## 项目概述

基于 Sentaurus TCAD 的仿真自动化框架，集成 Claude Code LLM Agent。
支持 Host-VM 分布式架构：Host 端提交/分析，VM 端执行仿真。

## 环境配置

| 项目 | 配置方式 |
|------|----------|
| VM IP | `.env` 中 `TCAD_VM_IP` 或 `automation/config/vm_config.json` |
| SSH 凭据 | `.env` 中 `TCAD_VM_USER` / `TCAD_VM_PASSWORD` |
| Sentaurus 路径 | `vm_config.json` 中 `sentaurus.bin_path` |
| VM 项目路径 | `.env` 中 `TCAD_VM_PROJECT_PATH` |

## 工作流

### 完整仿真流程
```
SDE (Scheme脚本) → Mesh (.tdr) → SDevice (.cmd+.par) → .plt/.tdr 输出 → Python 提取绘图
```

### 批量仿真流程
```
1. SDE 生成 mesh → 上传到 VM
2. Python 生成 CMD 文件（根据案例 × 光束位置展开）
3. VM 批量执行 sdevice
4. 下载 .plt 结果到 Host
5. Python 提取光电流 + 绘图对比
```

## 已验证的 Sentaurus 语法规则 (W-2024.09-SP1)

> **遇到 Sentaurus 语法问题时，必须先查阅 `docs/troubleshooting/` 目录**

### SDE (Scheme)
- **坐标单位是 um**！500nm 器件写 `(position 0 0 0) (position 0.5 0.2 0)`，不是 500/200
- `position` 需要 3 个参数: `(position x y z)` — 不是 2 个
- 接触定义用 `sdegeo:set-contact` — 不是 `define-contact`（后者不导出到 mesh）
- `sde:build-mesh` 不加 `-recRToSDDevice` 参数（2024版不支持）
- 注释用 `;` 不是 `#`
- 前缀: 几何=`sdegeo:`, 网格细化=`sdedr:`, 保存=`sde:`
- 禁止 `Define @VAR@` 语法，直接写数值
- 运行需要 Xvfb: `Xvfb :99 -screen 0 1024x768x24 &` + `export DISPLAY=:99`

### SDE 命令行
```bash
# ⚠️ 关键顺序：必须先 export DISPLAY，再 source setup.sh
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &
source /path/to/sentaurus/setup.sh
sde -e -l script.scs  # 执行 Scheme 脚本生成 mesh
```

### SDevice Optics（LBIC 仿真）
- **2D 器件必须用 RayTracing**，不能用 TMM（TMM 只适用于 1D 层状结构）
- **3D 器件 optics 语法**: 使用 `Theta + Window + Rectangle/Polygon` 风格
  - ❌ 错误: `Window ( Origin=(x,y,z) Line(x1 x2 x3) )` — 3D 不支持 `Line`
  - ✅ 正确: `Excitation ( Theta=180 Window( Origin=(x,y,z) Rectangle(dx=a dy=b) ) )`
- Window 语法: `Window ( Origin=(x,y) Line(x1=a x2=b) )` — **不支持命名字符串**
- **必须指定 Polarization**: `Polarization = 0.5`（非偏振光）
- Wavelength 单位是 um: `Wavelength = 0.450`（= 450nm）
- ComplexRefractiveIndex 必须指定 `Formula = 0`
- 参数名: `n_0`, `k_0`, `Cn_lambda`, `Dn_lambda` — **不是** `lambda0`

**⚠️ LBIC 坐标系关键**:
Sentaurus 使用 `3d_sprocess` 坐标系，SDE x ↔ SDevice y，SDE y ↔ SDevice x。
- **正确的顶部照明 LBIC**（沿 SDE x 横向扫描）:
  ```tcl
  Origin = (-0.001, {beam_sde_x_um})   ← SDevice x=-0.001（顶面以上）
  Line (x1=0.0 x2=0.2)                 ← 覆盖全深度 SDE y=0-0.2μm
  ```

### SDevice Physics 块
- **每种半导体材料必须有独立的 Physics 块**来启用物理模型
- .par 文件只提供参数值，不会自动激活 SRH/Mobility 等模型
- 示例:
```tcl
Physics (Material="YourMaterial")    { Recombination(SRH) Mobility(PhuMob) }
Physics (Material="YourMaterial_TB") { Recombination(SRH) Mobility(PhuMob) }
```

### PAR vs CMD
- `.par` = 材料参数 (BandGap, Permittivity, Nc, Nv, ComplexRefractiveIndex...)
- `.cmd` = 仿真控制 (File{}, Electrode{}, Physics{}, Solve{})
- .par 中定义参数，.cmd 中启用模型 — 两者缺一不可

### SDevice 命令行
```bash
# 单个仿真
sdevice cmd_file.cmd

# 批量运行（在 VM 上）
export PATH=/path/to/sentaurus/bin:$PATH
export LM_LICENSE_FILE=27020@localhost
sdevice ./your_cmd_dir/case1.cmd
```

### 3D 网格生成经验
- SDE 可生成的网格规模 > SDevice 可求解的规模
- 246k 顶点（1.4M 四面体）：SDevice 可加载，但在 Quasistationary 求解时内存不足
- 808k 顶点（4.7M 四面体）：SDevice 在 `Computing edges...` 阶段即内存溢出
- 建议 3D 网格目标：100k-150k 顶点范围

### 文件上传到 VM（Paramiko）
- paramiko sftp 可以正常传输文本文件
- **后台任务启动方式**（重要！`exec_command` + nohup 会挂起）:
```python
transport = ssh.get_transport()
channel = transport.open_session()
channel.exec_command('cd /path && nohup bash script.sh > log 2>&1 &')
channel.close()
```

## TCAD 自动化调度系统

自研轻量级调度系统。架构：Host 触发 + VM 自治执行（FastAPI + SQLite + N workers 并行）。

**快速命令**:
```bash
# VM 端 — 启动调度服务器
ssh your_user@YOUR_VM_IP
cd YOUR_VM_PROJECT_PATH
source /path/to/sentaurus/setup.sh
PYTHONPATH=. nohup python3 -m uvicorn automation.scheduler.server:app --host 0.0.0.0 --port 8899 > /tmp/scheduler.log 2>&1 &

# Host 端 — 提交批次
python -c "
from automation.client.batch_client import TCADSchedulerClient
c = TCADSchedulerClient()
result = c.start_batch({'batch_name': 'test', 'cases': ['baseline'], 'beam_config': {'start_nm': 50, 'end_nm': 250, 'step_nm': 5}})
print(result)
"

# Host 端 — 画图 + 回归验证
python -m automation.client.plot_batch <batch_id>
```

## LLM 自主操作规范

你是 TCAD 自动化 Agent。面对仿真请求时，**自主完成全流程**，只在关键节点向用户确认。

### 可用工具

所有工具通过 `automation/agent/tcad_agent.py` 调用：

```python
from automation.agent.tcad_agent import *

submit_experiment(batch_name, cases, interface, par_preset, beam_preset, dry_run=False)
check_batch(batch_id)
get_results(batch_id, case=None)
diagnose_failure(batch_id)
wait_and_report(batch_id, poll_interval=30)
list_batches()
check_health()
query_knowledge(topic)  # topics: cases, parameters, interfaces, syntax, troubleshooting, workflow
```

### 标准操作流程 (SOP)

#### 收到仿真请求时：

1. **理解意图** — 解析用户请求中的：case 范围、参数集、界面类型、光束精度
2. **确认 VM 在线** — `check_health()`。若不在线，告知用户启动调度器
3. **Dry-run 验证** — `submit_experiment(..., dry_run=True)` 展示预计规模和时间
4. **提交执行** — `submit_experiment(...)` 提交到 VM
5. **等待完成** — `wait_and_report(batch_id)` 或间歇 `check_batch()`
6. **结果分析** — `get_results(batch_id)` 返回结构化数据
7. **出现失败时** — `diagnose_failure(batch_id)` → 查 `docs/troubleshooting/` → 修复 → 重新提交
8. **画图** — `python -m automation.client.plot_batch <batch_id>`
9. **总结报告** — 关键数值、效应对比、与历史对比、建议下一步

### 自主决策边界

**直接执行（不询问）**:
- 标准批次提交（合理规模）
- 进度查询、结果获取
- 失败诊断和知识库检索
- 画图和回归验证

**确认后执行**:
- 修改 .par 材料参数文件
- 超过 500 仿真的大批次
- 删除已有批次数据
- 修改 CMD 模板

**禁止执行**:
- SDE 网格生成（需 Xvfb，手动操作）
- 修改 VM 上 Sentaurus 安装

### 失败处理决策树

```
仿真失败 → diagnose_failure(batch_id)
  ├── convergence 类 → 查 docs/troubleshooting/ 收敛相关条目
  │   → 自动修复: 减小 MaxStep, 增加 Iterations → 重新生成 CMD → 重新提交
  ├── syntax 类 → 查本文件已验证语法 → 修复 CMD 模板 → 重新提交
  ├── license 类 → 提示用户检查 license 服务器
  ├── memory 类 → 减少 worker 数或使用 coarse mesh → 重新提交
  ├── mesh 类 → 提示用户重新生成 mesh
  └── other → 读取完整 error_msg → 查知识库 → 尝试修复 → 若 3 次失败则升级到人工
```

## 开发规则

### 必须遵守
1. **修改前先读** — 不要凭记忆修改文件，先 Read 当前内容
2. **查知识库** — 遇到报错先查 `docs/troubleshooting/`，不要从零开始 debug
3. **记录解决方案** — 每解决一个新问题，在 `docs/troubleshooting/` 创建记录
4. **单一职责** — 一次只改一个东西，改完验证再改下一个

### 禁止事项
- 不要用 TMM 光学求解器（2D 器件只能用 RayTracing）
- 不要在 SDE 脚本中使用 nm 数值（必须转换为 um）
- 不要跳过 troubleshooting 知识库直接 debug

## 关键文档索引

| 文档 | 用途 |
|------|------|
| [docs/troubleshooting/](docs/troubleshooting/) | Sentaurus 问题排查知识库 |
| [docs/SVisual_Data_Extraction_Summary.md](docs/SVisual_Data_Extraction_Summary.md) | SVisual Tcl 命令参考 |
| [docs/VM_Hardware_Optimization.md](docs/VM_Hardware_Optimization.md) | VM 性能优化 |
| [params/](params/) | 材料参数 YAML 模板 |
| [AGENTS.md](AGENTS.md) | 系统架构文档 |
| [HANDOVER.md](HANDOVER.md) | 跨会话交接模板 |
