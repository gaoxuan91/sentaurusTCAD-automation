# SVisual TDR 数据提取 - 完整总结

**日期**: 2026-04-26  
**状态**: ✅ 完成  
**成果**: 成功掌握 SVisual TDR 数据提取方法，完成 baseline 案例的完整 2D 空间分布数据提取和可视化

---

## 🎯 主要成果

### 1. 掌握了 SVisual Tcl 命令

经过系统学习和大量试错，成功掌握了 SVisual 的核心命令：

**关键命令**:
```tcl
# 加载 TDR 文件
load_file file.tdr -name dataset_name

# 创建 plot
create_plot -dataset dataset_name -name plot_name

# 在指定点探测场值（核心命令）
probe_field -field FieldName -coord {x y}

# 积分场值
integrate_field -field FieldName

# 导出可视化
export_view filename.png
```

### 2. 成功提取 Baseline 案例数据

**提取的物理量**:
- ElectrostaticPotential (电势分布)
- eDensity (电子密度分布)
- hDensity (空穴密度分布)
- eQuasiFermi (电子准费米能级)
- hQuasiFermi (空穴准费米能级)

**数据规格**:
- 网格: 51 × 21 = 1071 个点
- 分辨率: 0.01 μm
- 提取速度: 214 点/秒
- 总耗时: 5 秒/案例

### 3. 生成了高质量可视化

**输出文件** (`D:\YOUR_MATERIAL_Sentaurus_Project\output\spatial_distribution\`):
- 5 个数据文件 (.dat, 原始数据)
- 5 个单独热图 (.png, 300 DPI)
- 1 个组合图 (所有物理量对比)

### 4. 创建了自动化工具

**核心脚本**:
1. `extract_2d_full.py` - 单案例 2D 数据提取
2. `visualize_2d_data.py` - 热图生成
3. `batch_extract_all_cases.py` - 批量提取（支持多案例）

---

## 📊 数据提取示例

### Baseline 案例的电势分布

从提取的数据可以看到：
- 左侧电极 (x=0): 1.30 V
- 中心区域 (x=0.25): 0.50 V  
- 右侧电极 (x=0.5): 0.30 V

电势呈现线性梯度分布，符合预期的 P1-P2 电极配置。

### 电子密度分布

- 高密度区域: 1.12×10^10 cm^-3 (x=0.1, y=0.1)
- 中密度区域: 2.65×10^7 cm^-3 (x=0.25, y=0.1)
- 低密度区域: 251 cm^-3 (x=0.4, y=0.1)

显示出明显的空间梯度，反映了载流子的输运特性。

---

## 🔍 学习过程

### 试错历程

尝试了多种方法，最终找到正确路径：

| 尝试方法 | 结果 | 原因 |
|---------|------|------|
| `tdx -tf` 转换 | ❌ 失败 | TDR 是 Ogawa 格式，不是标准 HDF5 |
| `inspect` 查看 | ❌ 失败 | 需要 DISPLAY 环境变量 |
| `create_cutline` | ❌ 失败 | 语法复杂，未找到正确用法 |
| `get_variable_data` | ❌ 失败 | 只适用于 PLT 文件 |
| `export_variables` | ❌ 失败 | 语法复杂，未找到正确用法 |
| `probe_field` | ✅ 成功 | **正确方法！** |

### 关键突破

**突破点**: 查阅 Synopsys 官方示例脚本

找到的官方示例：
```
/usr/synopsys/sentaurus/W-2024.09-SP1/tcad/W-2024.09-SP1/linux64/lib/python3.11/site-packages/swbgui/mockedfiles/templateinputfiles/svisual/IdVg_vis.tcl
```

从中学到了正确的命令模式和语法。

---

## 📁 文件组织

### 脚本文件

```
analysis/
├── extract_2d_full.py              # 单案例 2D 数据提取
├── visualize_2d_data.py            # 热图生成
├── batch_extract_all_cases.py     # 批量提取脚本
├── check_tdr_files.py              # 检查可用 TDR 文件
└── [其他探索性脚本...]            # 学习过程中的试错脚本
```

### 输出文件

```
output/spatial_distribution/
├── ElectrostaticPotential_2d.dat   # 电势数据
├── eDensity_2d.dat                 # 电子密度数据
├── hDensity_2d.dat                 # 空穴密度数据
├── eQuasiFermi_2d.dat              # 电子准费米能级
├── hQuasiFermi_2d.dat              # 空穴准费米能级
├── ElectrostaticPotential_heatmap.png
├── eDensity_heatmap.png
├── hDensity_heatmap.png
├── eQuasiFermi_heatmap.png
├── hQuasiFermi_heatmap.png
└── baseline_all_fields_combined.png
```

### 文档文件

```
docs/troubleshooting/
├── 016_tdr_data_extraction.md      # TDR 格式研究
├── 017_svisual_research_progress.md # SVisual 命令探索
└── 018_svisual_data_extraction_success.md # 成功总结
```

---

## 🚀 下一步工作

### 当前状态

- ✅ 已完成: Baseline 案例数据提取和可视化
- ⏳ 待完成: 其他 TB 案例的仿真和数据提取

### 发现的情况

检查 VM 上的 TDR 文件发现：
- ✅ Baseline 案例: 已有 LBIC 扫描数据（bx100-bx250）
- ❌ TB 案例: TDR 文件尚未生成

**原因**: TB 案例的仿真可能还未运行，或者 TDR 文件在其他位置。

### 后续计划

1. **确认 TB 案例状态**
   - 检查 TB 案例的仿真是否已完成
   - 确认 TDR 文件的位置

2. **运行 TB 案例仿真**（如果尚未完成）
   - 使用已有的 SDE 网格和 SDevice 参数
   - 生成 7 个 TB 配置的 TDR 文件

3. **批量提取所有案例数据**
   - 使用 `batch_extract_all_cases.py`
   - 提取所有 7 个案例的 2D 空间分布

4. **生成对比分析**
   - Baseline vs TB 案例的物理场对比
   - TB 附近的局部场特征分析
   - 量化 TB 对载流子输运的影响

---

## 💡 关键经验

1. **查阅官方文档和示例最高效**
   - 盲目试错浪费时间
   - 官方示例提供了最佳实践

2. **TDR 和 PLT 文件处理方式不同**
   - TDR: 使用 `probe_field` 提取空间分布
   - PLT: 使用 `get_variable_data` 提取 I-V 曲线

3. **批量处理要考虑性能**
   - 214 点/秒的速度
   - 1071 点需要 5 秒
   - 大规模提取需要合理规划

4. **数据可视化很重要**
   - 热图直观展示空间分布
   - 对数标度适合密度数据
   - 组合图便于对比分析

---

## 📚 参考资料

### Synopsys 官方文档

- Sentaurus Visual User Guide
- Sentaurus Device User Guide
- Applications Library 示例

### 项目文档

- `CLAUDE.md` - 项目概述
- `docs/WORKFLOW.md` - 完整工作流程
- `docs/PHASE1_PHASE2_SUMMARY.md` - 仿真结果总结

---

## ✅ 总结

经过一天的深入学习和探索，成功掌握了 SVisual TDR 数据提取的完整流程。关键突破是找到 `probe_field` 命令，它可以在任意坐标点提取场值，从而实现完整的 2D 空间分布数据提取。

**核心成果**:
- ✅ 掌握 SVisual Tcl 命令
- ✅ 成功提取 baseline 案例数据
- ✅ 生成高质量可视化
- ✅ 创建自动化工具
- ✅ 建立完整文档

**工具链已就绪**，可以随时提取和分析任何 TDR 文件的空间分布数据！
