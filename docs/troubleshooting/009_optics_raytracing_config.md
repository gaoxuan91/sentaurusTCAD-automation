# SDevice Optics RayTracing 配置成功路径

## 现象
多种光学求解器配置失败：
1. TMM (Transfer Matrix Method) 报 "empty LayerStack" — 无法从 2D 非层状结构提取层
2. Window 命名语法 `Window ("beam") (` 报错
3. 缺少 Polarization 参数报错
4. LayerStackExtraction(WindowName="beam") 引用不存在的窗口

## 根因
- TMM 只适用于严格的 1D 层状结构，2D 器件必须用 RayTracing
- Sentaurus W-2024.09-SP1 的 Window 不支持命名字符串
- RayTracing 必须指定 Polarization 或 PolarizationAngle

## 解决方案 — 完整可用的 Optics 配置

```tcl
Physics {
    Optics (
        ComplexRefractiveIndex (WavelengthDep(Real Imag))
        OpticalGeneration (
            QuantumYield (StepFunction(EffectiveBandgap))
            ComputeFromMonochromaticSource
        )
        Excitation (
            Wavelength = 0.450          * um (= 450nm)
            Intensity  = 1.0            * W/cm^2
            Polarization = 0.5          * 必须！非偏振光
            Window (
                Origin = (0.250, -0.001)  * um坐标，y略高于器件顶面
                Line (x1=0.225 x2=0.275)  * 光束宽度 = 2*sigma = 50nm
            )
        )
        OpticalSolver (
            RayTracing (
                RayDistribution (
                    Mode = AutoPopulate
                    NumberOfRays = 100
                )
                MinIntensity = 1e-5
                DepthLimit = 100
            )
        )
    )
}
```

## 关键要点

| 参数 | 正确值 | 说明 |
|------|--------|------|
| Wavelength | 0.450 | 单位 um，不是 nm |
| Polarization | 0.5 | 非偏振光，必须指定 |
| Window Origin | (x, -0.001) | y 略高于器件顶面(y=0) |
| Window Line | x1, x2 | 光束宽度范围，单位 um |
| OpticalSolver | RayTracing | 2D 器件不能用 TMM |
| NumberOfRays | 100 | 足够精度，不会太慢 |

## PAR 文件 ComplexRefractiveIndex 配置

```
ComplexRefractiveIndex
{ 
    Formula = 0        * 必须指定！否则报错
    n_0    = 2.0       * YOUR_MATERIAL at 450nm
    k_0    = 0.5       * α ≈ 1.4×10^5 cm^-1
    Cn_lambda = 0
    Dn_lambda = 0
    Ck_lambda = 0
    Dk_lambda = 0
}
```

**禁止使用**: `lambda0`（不是有效参数名）

## 验证方法
检查 .plt 输出中：
- `RaytracePhoton AbsorbedBulk` > 0（光子被吸收）
- `Anode TotalCurrent` >> 暗电流（~8e-24 A）
- 典型光电流: ~1e-10 A（1V偏压，1 W/cm² 照射）

## 相关文件
- `swb/YOUR_PROJECT_NAME/SDevice/YOUR_MATERIAL_TB_LBIC.par`
- `swb/YOUR_PROJECT_NAME/SDevice/lbic_cmd/*.cmd`

## 日期
2026-04-21
