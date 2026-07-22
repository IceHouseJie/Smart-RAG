#!/bin/sh

# 安装 Git hooks 到 .git/hooks/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔄 安装 Git hooks..."

# 为每个 hook 创建符号链接
for hook in "$PROJECT_DIR/.githooks/"*; do
  hook_name=$(basename "$hook")
  ln -sf "$hook" "$PROJECT_DIR/.git/hooks/$hook_name"
  echo "  ✅ $hook_name 已安装"
done

echo "🎉 Git hooks 安装完成！"
