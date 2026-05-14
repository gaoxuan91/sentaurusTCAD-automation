# TCAD Sentaurus Autopilot

Sentaurus TCAD 仿真自动化框架，集成 Claude Code LLM Agent，支持 Host-VM 分布式批量仿真调度。希望能抛砖引玉，欢迎大家来看看


## 架构

```
Host (Windows/Linux)                    VM (Linux + Sentaurus TCAD)
┌──────────────────────┐   HTTP/SSH   ┌────────────────────────────┐
│ batch_client.py      │─────────────│  server.py (FastAPI :8899) │
│  · start_batch()     │  POST/GET   │  · POST /batch/start       │
│  · get_status()      │             │  · GET  /batch/{id}/status │
│  · get_results()     │             │  · GET  /batch/{id}/results│
├──────────────────────┤             │  · GET  /health            │
│ tcad_agent.py        │             ├────────────────────────────┤
│  · LLM 自主操作       │             │  worker.py (×3 parallel)   │
│  · submit/diagnose   │             │  · sdevice subprocess      │
│  · query_knowledge   │             │  · PLT parse + validation  │
└──────────────────────┘             ├────────────────────────────┤
                                     │  db.py (SQLite)            │
                                     │  cmd_generator.py          │
                                     └────────────────────────────┘
```

## 核心模块

| 模块 | 职责 |
|------|------|
| `automation/scheduler/server.py` | FastAPI HTTP API，接收实验配置，调度执行 |
| `automation/scheduler/worker.py` | 线程池并行执行 sdevice，失败重试 |
| `automation/scheduler/db.py` | SQLite 批次/任务状态管理 |
| `automation/scheduler/cmd_generator.py` | JSON 配置 → CMD 文件批量生成 |
| `automation/client/batch_client.py` | Host 端 HTTP/SSH 客户端 |
| `automation/client/plot_batch.py` | 结果绘图 + 回归验证 |
| `automation/agent/tcad_agent.py` | LLM Agent 工具接口（submit/check/diagnose） |
| `automation/utils/plt_parser.py` | Sentaurus PLT 文件解析器 |
| `automation/utils/validation.py` | 批次结果验证（物理一致性 + 回归） |
| `automation/utils/vm_config_loader.py` | VM 配置加载（支持环境变量覆盖） |
| `automation/tools/sdevice.py` | SDevice CMD/PAR 模板定义 |

## 快速开始

### 1. 环境准备

**Host 端（你的电脑）**:
```bash
pip install fastapi uvicorn jinja2 paramiko matplotlib
```

**VM 端（Sentaurus 服务器）**:
```bash
pip install fastapi uvicorn
# 确保 Sentaurus 已安装并可执行
which sdevice
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 VM IP、SSH 凭据、Sentaurus 路径
```

编辑 `automation/config/vm_config.json`，配置 VM 连接信息和路径。

### 3. 启动 VM 端调度器

```bash
# SSH 到 VM
ssh your_user@YOUR_VM_IP

# 启动调度器
cd YOUR_VM_PROJECT_PATH
source /path/to/sentaurus/setup.sh
python -m uvicorn automation.scheduler.server:app --host 0.0.0.0 --port 8899
```

### 4. Host 端提交实验

```python
from automation.client.batch_client import TCADSchedulerClient

client = TCADSchedulerClient(vm_ip="YOUR_VM_IP")

# 提交批次
result = client.start_batch({
    "batch_name": "test_run",
    "cases": ["your_case_1", "your_case_2"],
    "beam_config": {"start_nm": 50, "end_nm": 250, "step_nm": 5},
    "interface": "no_effect",
})
print(f"Batch ID: {result['batch_id']}, Tasks: {result['task_count']}")

# 等待完成
client.wait_for_completion(result["batch_id"])
```

### 5. 使用 LLM Agent

```python
from automation.agent.tcad_agent import *

# 检查 VM 状态
check_health()

# 提交实验（dry-run）
submit_experiment("test_batch", cases=["baseline"], dry_run=True)

# 查询进度
check_batch("batch_id")

# 获取结果
get_results("batch_id")
```

## 为你的项目配置

### 1. 定义案例和接口

编辑 `automation/tools/sdevice.py`，定义你的：
- `CASES`: 仿真案例列表
- `INTERFACES`: 界面物理配置
- `CMD_TEMPLATE`: SDevice CMD 模板
- `GRID_FILES`: 网格文件映射

### 2. 准备参数文件

在 `params/` 目录下创建你的材料参数模板（参考已有的 YAML 模板）。

### 3. 生成网格

使用 SDE 脚本生成 mesh 文件，放到 VM 的 `swb/` 目录下。

### 4. 运行仿真

通过 API 或 Agent 提交批量仿真任务。

## API 端点

| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/batch/start` | 提交实验配置 JSON，启动批次 |
| GET | `/batch/{id}/status` | 查询进度 |
| GET | `/batch/{id}/results` | 获取光电流数据 |
| GET | `/health` | VM 资源状态 |

## 实验配置 JSON

```json
{
  "batch_name": "my_experiment",
  "cases": ["case1", "case2"],
  "beam_config": {"start_nm": 50, "end_nm": 250, "step_nm": 5},
  "interface": "no_effect",
  "par_file": null,
  "mesh_dir": null,
  "output_dir": null,
  "wavelength_nm": 450,
  "bias_V": 1.0,
  "n_rays": 100
}
```

`null` 字段由服务器自动填充。

## 文档

- [docs/troubleshooting/](docs/troubleshooting/) — Sentaurus 常见问题排查
- [docs/SVisual_Data_Extraction_Summary.md](docs/SVisual_Data_Extraction_Summary.md) — SVisual 数据提取指南
- [docs/VM_Hardware_Optimization.md](docs/VM_Hardware_Optimization.md) — VM 性能优化
- [params/](params/) — 材料参数 YAML 模板

## 许可证

MIT License
