# SDevice 报 Inputfile doesn't exist

## 现象
运行 SDevice 时报错：
```
Inputfile doesn't exist or without read permission !
```
即使文件存在且权限正常。

## 根因
**待确认。** 可能原因：
1. Mesh TDR 文件尚未生成（SDE 未成功运行）— **最可能的原因**
2. `.par` 文件中引用的 mesh 路径与实际路径不匹配
3. SELinux/AppArmor 限制
4. Sentaurus 许可证问题
5. SSH 环境变量未正确传递（`source setup.sh` 未执行）

## 解决方案
**当前阻塞 — 需先完成 SDE mesh 生成。**

排查步骤：
1. 确认 `Mesh/` 目录下存在 `*_msh.tdr` 文件
2. 检查 `.par` 或 `.cmd` 中 `File { Grid = "..." }` 路径是否正确
3. 在 VM 终端直接运行（非 SSH），观察完整错误
4. 检查 `lmstat -a` 确认许可证状态

## 验证方法
SDevice 运行后生成非零字节的 `.plt` 和 `.tdr` 输出文件。

## 相关文件
- swb/YOUR_PROJECT_NAME/SDevice/*.cmd
- swb/YOUR_PROJECT_NAME/SDevice/*.par
- output/baseline/logs/sdevice_baseline.log

## 日期
2026/04/17 发现，待诊断
