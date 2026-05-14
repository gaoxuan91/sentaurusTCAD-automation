# sde:build-mesh 不支持 -recRToSDDevice 参数

## 现象
SDE 脚本中使用 `(sde:build-mesh "-recRToSDDevice" ...)` 报错。

## 根因
Sentaurus W-2024.09-SP1 版本的 `sde:build-mesh` 不支持 `-recRToSDDevice` 标志。该标志在旧版本中用于将区域信息传递给 SDevice，但新版本已移除。

## 解决方案
调用 `sde:build-mesh` 时不加该参数：

```scheme
; 错误
(sde:build-mesh "-recRToSDDevice" "output_fps" "output_mesh")

; 正确
(sde:build-mesh "YOUR_PROJECT_NAME_CASE_fps")
```

## 验证方法
`sde:build-mesh` 正常执行，生成 `*_msh.tdr` 文件。

## 相关文件
- swb/YOUR_PROJECT_NAME/SDE/*.scs

## 日期
2026/04/16 发现并解决
