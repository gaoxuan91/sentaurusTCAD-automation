# TCAD 自动化调度系统

自研轻量级调度系统，纯 Python 实现。架构：Host 触发 + VM 自治执行（FastAPI + SQLite + N workers 并行）。

## 架构

```
Host (Windows/Linux)                    VM (Linux + Sentaurus TCAD)
┌──────────────────────┐   HTTP/SSH   ┌────────────────────────────┐
│ batch_client.py      │─────────────│  server.py (FastAPI :8899) │
│  · start_batch()     │  POST/GET   │  · POST /batch/start       │
│  · get_status()      │             │  · GET  /batch/{id}/status │
│  · get_results()     │             │  · GET  /batch/{id}/results│
├──────────────────────┤             │  · GET  /health            │
│ plot_batch.py        │             ├────────────────────────────┤
│  · L3 regression     │             │  worker.py (×N parallel)   │
│  · LBIC plots (PNG)  │             │  · ThreadPoolExecutor      │
└──────────────────────┘             │  · subprocess sdevice      │
                                     │  · PLT parse on completion │
                                     ├────────────────────────────┤
                                     │  db.py (SQLite)            │
                                     │  cmd_generator.py          │
                                     └────────────────────────────┘
```

## 组件

| 文件 | 位置 | 职责 |
|------|------|------|
| `automation/scheduler/db.py` | VM | SQLite schema + 原子任务认领 |
| `automation/scheduler/cmd_generator.py` | VM | JSON 配置 → CMD 文件批量生成 |
| `automation/scheduler/worker.py` | VM | N workers 并行执行 sdevice，失败重试 |
| `automation/scheduler/server.py` | VM | FastAPI HTTP API，常驻进程 |
| `automation/client/batch_client.py` | Host | urllib HTTP 客户端 |
| `automation/client/plot_batch.py` | Host | 回归验证 + Matplotlib 画图 |
| `automation/agent/tcad_agent.py` | Host | LLM Agent 工具接口 |
| `automation/utils/plt_parser.py` | Both | PLT 文件解析器 |
| `automation/utils/validation.py` | VM | 批次结果验证 |
| `automation/utils/vm_config_loader.py` | Both | VM 配置加载 |

## 快速启动

```bash
# 1. VM 端 — 启动调度器
ssh your_user@YOUR_VM_IP
cd YOUR_VM_PROJECT_PATH
source /path/to/sentaurus/setup.sh
PYTHONPATH=. python -m uvicorn automation.scheduler.server:app --host 0.0.0.0 --port 8899

# 2. Host 端 — 提交实验
python -c "
from automation.client.batch_client import TCADSchedulerClient
c = TCADSchedulerClient()
result = c.start_batch({
    'batch_name': 'test',
    'cases': ['baseline'],
    'beam_config': {'start_nm': 50, 'end_nm': 250, 'step_nm': 5},
})
print(f'Batch ID: {result[\"batch_id\"]}, Tasks: {result[\"task_count\"]}')
"

# 3. Host 端 — 画图 + L3 验证
python -m automation.client.plot_batch <batch_id>
```

## 实验配置 JSON

提交至 `/batch/start` 的完整配置：

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

## 任务状态机

```
pending → running → done     (成功，数据已解析)
                  → failed   (失败，重试后)
pending → (cancelled)        (手动中止)

单任务 retry: failed → reset → pending → retry (最多 N 次)
```

## 三层验证

| 层 | 位置 | 内容 |
|----|------|------|
| L1 | VM worker | 单文件 PLT 解析 + sanity check |
| L2 | VM worker | 批量物理一致性检查 |
| L3 | Host | 回归对比 vs reference, tolerance 可配置 |

## 故障处理

1. sdevice 返回非零 RC → 自动 retry
2. sdevice 超时 → retry
3. 全部 retry 耗尽 → 标记 failed，批次继续
4. Worker 线程崩溃 → 隔离到单任务，不影响其他 worker
5. 批次级失败 → 检查 `/health` 端点，手动介入

## 不自动化范围

- SDE 网格生成（手动，需 Xvfb）
- 材料参数物理决策
- 论文撰写
