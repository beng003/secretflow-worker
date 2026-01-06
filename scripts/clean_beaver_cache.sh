#!/bin/bash
# 清理SPU BeaverCache缓存目录

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "正在清理BeaverCache目录..."

# 统计目录数量
CACHE_COUNT=$(find . -maxdepth 1 -name "BeaverCache.*" -type d | wc -l)

if [ $CACHE_COUNT -eq 0 ]; then
    echo "没有找到BeaverCache目录"
    exit 0
fi

echo "找到 $CACHE_COUNT 个BeaverCache目录"

# 显示目录大小
echo "总大小: $(du -sh BeaverCache.* 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo '0')"

# 删除目录
rm -rf BeaverCache.*

echo "清理完成！已删除 $CACHE_COUNT 个目录"
