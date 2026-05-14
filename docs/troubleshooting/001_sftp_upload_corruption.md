# SFTP 上传文本文件损坏

## 现象
SDE 脚本通过 SFTP 上传到 VM 后，`sde:build-mesh` 等命令中的字符串被损坏，导致 SDE 解析失败。

## 根因
SFTP 传输过程中对文本文件的字符串处理存在问题，特殊字符或引号在传输时被修改。

## 解决方案
不使用 SFTP 传输文本文件。改用 SSH heredoc 方式在 VM 上直接创建脚本：

```bash
ssh -i /tmp/vm_key tcad@YOUR_VM_IP << 'HEREDOC'
cat > YOUR_VM_PROJECT_PATH/swb/YOUR_PROJECT_NAME/SDE/baseline_fps_sdev.scs << 'EOF'
; SDE 脚本内容...
EOF
HEREDOC
```

关键：heredoc 的定界符必须用单引号包裹（`'EOF'`），防止 shell 变量展开。

## 验证方法
上传后在 VM 上用 `hexdump -C` 检查文件内容，确认双引号等特殊字符完整。

## 相关文件
- swb/YOUR_PROJECT_NAME/SDE/*.scs

## 日期
2026/04/16 发现并解决
