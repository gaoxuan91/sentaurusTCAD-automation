# SDevice CMD 文件 Material Block 语法错误

## 现象
SDevice 运行 baseline.cmd 时报错：
```
Error in baseline.cmd at line 18, offending input: Material
syntax error
```
错误出现在 `Physics (Material= "YOUR_MATERIAL")` 块。

## 根因
**待确认。** 可能原因：
1. `Material=` 后面的引号格式问题（中文引号 vs 英文引号）
2. Material 名称与 mesh 中定义的材料名不匹配
3. Physics block 的嵌套语法错误

## 解决方案
**待修复。** 排查步骤：
1. 用 `hexdump` 检查 .cmd 文件中的引号字符是否为 ASCII 双引号 (0x22)
2. 检查 mesh TDR 中的材料名称是否与 .cmd 中一致
3. 参考 nMOS_dvs_full.cmd 中的 Physics block 写法
4. 简化 Physics block，逐步添加内容定位具体出错行

## 验证方法
SDevice 运行不再报 syntax error，正常进入求解阶段。

## 相关文件
- swb/YOUR_PROJECT_NAME/SDevice/baseline.cmd
- baseline_sdevice_fixed.cmd（根目录修复版）
- nMOS_dvs_full.cmd（参考示例）

## 日期
2026/04/17 发现，待修复
