# SDE Headless 模式 position 函数报错

## 现象
使用 `sde -e -l script.scs` 运行 SDE 脚本时，`position` 函数报错：
```
position: wrong number of arguments
```

尝试过的变体均失败：
- `(position 0 0)` → wrong number of arguments
- `(position 0 0 0)` → wrong number of arguments (headless 模式下)
- `(list 0 0)` → expected position (got list)
- `(sdegeo:position 0 0 0)` → unbound variable

## 根因
Sentaurus W-2024.09-SP1 的 SDE 在 headless 模式（`-e -l`）下，Scheme 解释器对 `position` 函数的绑定与 GUI 模式不同。即使配合 `QT_QPA_PLATFORM=offscreen` 绕过了 HOOPS 图形初始化，核心几何函数仍无法正常工作。

这是 Sentaurus 版本特定的限制，不是脚本语法问题。

## 解决方案
**无法在 headless 模式下解决。** 必须使用以下方式之一：
1. VNC 连接 VM，在图形桌面中打开 SDE GUI 运行脚本
2. MobaXterm + X11 Forwarding 远程运行 SDE
3. 在 SWB GUI 中运行完整工作流

## 验证方法
在 GUI 环境中运行 `sde -e -l script.scs`，检查是否生成 `*_msh.tdr` 文件。

## 相关文件
- swb/YOUR_PROJECT_NAME/SDE/*.scs
- automation/VM_MANUAL_OPERATION.md

## 日期
2026/04/16 发现，确认为版本限制
