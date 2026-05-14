# SDevice Physics 块必须为每种材料单独定义

## 现象
4个 TB case 的 LBIC 结果与 baseline 完全一致，TB 区域没有表现出降低的迁移率和寿命。

## 根因
CMD 文件只定义了 `Physics (Material="YOUR_MATERIAL")`，没有为 `YOUR_MATERIAL_TB` 定义 Physics 块。
虽然 .par 文件中有 YOUR_MATERIAL_TB 的参数，但 SRH 复合和 PhuMob 迁移率模型不会自动启用——
必须在 CMD 中显式声明。

## 解决方案

```tcl
Physics (Material= "YOUR_MATERIAL"){
    Recombination(SRH)
    Mobility(PhuMob)
}

Physics (Material= "YOUR_MATERIAL_TB"){
    Recombination(SRH)
    Mobility(PhuMob)
}
```

**规则**: 每种出现在 mesh 中的半导体材料，都必须有对应的 `Physics (Material="xxx")` 块来启用物理模型。
.par 文件只提供参数值，不会自动激活模型。

## 验证方法
对比 baseline 和 TB case 在 TB 位置的光电流：
- 修复前: 所有 case 电流一致
- 修复后: TB case 在 TB 位置光电流下降（本项目中下降约 78%）

## 相关文件
- `swb/YOUR_PROJECT_NAME/SDevice/lbic_cmd/*.cmd`
- `swb/YOUR_PROJECT_NAME/SDevice/YOUR_MATERIAL_TB_LBIC.par`

## 日期
2026-04-21
