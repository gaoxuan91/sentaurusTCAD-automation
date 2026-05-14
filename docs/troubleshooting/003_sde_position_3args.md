# SDE position 函数需要 3 个参数

## 现象
SDE 脚本中使用 `(position x y)` 报错：
```
position: wrong number of arguments
```

## 根因
Sentaurus W-2024.09-SP1 版本的 `position` 函数要求 3 个参数（x, y, z），即使是 2D 仿真也必须提供 z 坐标。

旧版本或某些文档中使用 2 个参数的写法在此版本不适用。

## 解决方案
所有 `position` 调用改为 3 参数形式，z 坐标设为 0：

```scheme
; 错误
(sdegeo:create-rectangle (position 0 0) (position 500 200) "YOUR_MATERIAL" "bulk")

; 正确
(sdegeo:create-rectangle (position 0 0 0) (position 500 200 0) "YOUR_MATERIAL" "bulk")
```

## 验证方法
SDE 脚本运行不再报 `position: wrong number of arguments`。

## 相关文件
- swb/YOUR_PROJECT_NAME/SDE/*.scs

## 日期
2026/04/16 发现并解决
