# 创建新的 TCAD 自动化项目

本指南帮助你基于此框架搭建自己的 Sentaurus TCAD 自动化仿真项目。

## 步骤

### 1. 配置 VM 连接

```bash
cp .env.example .env
# 编辑 .env，填入你的 VM 信息
```

编辑 `automation/config/vm_config.json`：
- `vm_connection.ip`: 你的 VM IP
- `vm_connection.username`: SSH 用户名
- `vm_connection.password`: SSH 密码
- `sentaurus.bin_path`: Sentaurus 安装路径
- `paths.vm_project_root`: VM 上的项目路径

### 2. 定义仿真案例

编辑 `automation/tools/sdevice.py`：

```python
# 定义你的案例
CASES = [
    "baseline",
    "your_case_1",
    "your_case_2",
]

# 定义界面配置
INTERFACES = {
    "no_effect": {"description": "无界面物理"},
    "your_interface": {"description": "你的界面模型", "charge": 1e12},
}

# 定义网格文件映射
GRID_FILES = {
    "baseline": "path/to/baseline_mesh.tdr",
    "your_case_1": "path/to/case1_mesh.tdr",
}

# 定义 CMD 模板
CMD_TEMPLATE = """File {{
    Grid      = "{{grid_file}}"
    Current   = "{{plt_path}}"
    Output    = "{{log_path}}"
    Parameter = "{{par_path}}"
}}

Electrode {{
    {{electrodes}}
}}

Physics (Material="YourMaterial") {{
    Recombination(SRH)
    Mobility(PhuMob)
}}

Solve {{
    Poisson
    Coupled {{ Poisson Electron Hole }}
}}
"""
```

### 3. 准备材料参数

在 `params/` 目录创建你的 `.par` 文件，或使用已有的 YAML 模板作为参考。

### 4. 生成网格

使用 SDE 脚本生成 mesh 文件：

```bash
# 在 VM 上
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &
source /path/to/sentaurus/setup.sh
sde -e -l your_script.scs
```

### 5. 启动调度器并运行

```bash
# VM 端
cd YOUR_VM_PROJECT_PATH
source /path/to/sentaurus/setup.sh
PYTHONPATH=. python -m uvicorn automation.scheduler.server:app --host 0.0.0.0 --port 8899

# Host 端
from automation.client.batch_client import TCADSchedulerClient
client = TCADSchedulerClient()
result = client.start_batch({
    "batch_name": "my_first_batch",
    "cases": ["baseline", "your_case_1"],
})
```

## 自定义验证规则

编辑 `automation/utils/validation.py` 中的阈值，匹配你的器件预期：

```python
EXPECTED_CURRENT_MIN = 1e-15  # 你的器件最小预期电流
EXPECTED_CURRENT_MAX = 1e-6   # 你的器件最大预期电流
```

## 更多参考

- [docs/troubleshooting/](../../docs/troubleshooting/) — Sentaurus 常见问题
- [CLAUDE.md](../../CLAUDE.md) — Claude Code 集成指南
- [AGENTS.md](../../AGENTS.md) — 系统架构文档
