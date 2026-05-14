# sdegeo:define-contact 不导出接触到 Mesh

## 现象
SDE 脚本中使用 `sdegeo:define-contact` 定义接触后，生成的 mesh 文件中不包含接触信息。SDevice 运行时找不到电极。

## 根因
在 W-2024.09-SP1 版本中，`sdegeo:define-contact` 只在 SDE 内部定义接触，不会将接触信息写入导出的 mesh TDR 文件。

## 解决方案
使用 `sdegeo:set-contact` 替代 `sdegeo:define-contact`：

```scheme
; 错误 — 接触不会导出到 mesh
(sdegeo:define-contact (list "anode") "Anode")

; 正确 — 接触会导出到 mesh
(sdegeo:set-contact (find-region-id "anode") "Anode")
```

## 验证方法
生成 mesh 后，在 SDevice 中检查是否能识别 Anode/Cathode 电极。

## 相关文件
- swb/YOUR_PROJECT_NAME/SDE/*.scs

## 日期
2026/04/16 发现并解决
