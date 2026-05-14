# SDE 坐标系统与 LBIC 仿真成功路径

## 现象
SDE 脚本使用 nm 数值（如 `position 500 200 0`），生成的器件尺寸为 500um×200um 而非预期的 500nm×200nm。导致：
1. 载流子扩散长度（~4um）远小于器件尺寸（500um），光生载流子无法到达电极
2. LBIC 仿真光电流为零

## 根因
Sentaurus SDE 内部坐标单位固定为 **微米(um)**。写 `(position 500 200 0)` 意味着 500um×200um。

## 解决方案
所有 SDE 坐标必须除以 1000：
- 器件: `(position 0 0 0) (position 0.5 0.2 0)` → 500nm × 200nm
- 电极: 宽度 0.01um = 10nm
- TB: 宽度 0.003um = 3nm
- 网格细化窗口也必须用 um 坐标

## 验证方法
```bash
sde -e -l script.scs  # 生成 mesh
# 检查 mesh 文件大小合理（不应过大）
# SDevice 仿真应产生合理电流（~1e-10 A 量级）
```

## 正确的 SDE 脚本模板（um 坐标）
```scheme
; 500nm x 200nm device
(sdegeo:create-rectangle (position 0 0 0) (position 0.5 0.2 0) "YOUR_MATERIAL" "bulk")
(sdegeo:create-rectangle (position 0 0 0) (position 0.01 0.2 0) "Metal" "anode")
(sdegeo:create-rectangle (position 0.49 0 0) (position 0.5 0.2 0) "Metal" "cathode")
; TB (3nm wide) at center
(sdegeo:create-rectangle (position 0.2485 0 0) (position 0.2515 0.2 0) "YOUR_MATERIAL_TB" "tb_vertical")

(sdegeo:set-contact (find-region-id "anode") "Anode")
(sdegeo:set-contact (find-region-id "cathode") "Cathode")

; Mesh refinement
(sdedr:define-refeval-window "RefWin_TB" "Rectangle" (position 0.2485 -0.01 0) (position 0.2515 0.21 0))
(sdedr:define-refinement-size "RefDef_TB" 0.0005 0.01 0.0 0.0001 0.005 0.0)
(sdedr:define-refinement-placement "RefPlace_TB" "RefDef_TB" "RefWin_TB")

(sdedr:define-refeval-window "RefWin_Bulk" "Rectangle" (position -0.01 -0.01 0) (position 0.51 0.21 0))
(sdedr:define-refinement-size "RefDef_Bulk" 0.01 0.01 0.0 0.005 0.005 0.0)
(sdedr:define-refinement-placement "RefPlace_Bulk" "RefDef_Bulk" "RefWin_Bulk")

(sde:save-model "output_name")
(sde:build-mesh "output_name")
```

## 相关文件
- `analysis/run_sde_um.py` — 正确的 SDE 脚本生成与上传
- `swb/YOUR_PROJECT_NAME/SDE/` — VM 上的 SDE 文件

## 日期
2026-04-21
