#!/bin/bash
set -e

echo "🚀 启动SecretFlow Worker容器..."

# 根据节点类型启动Ray
if [ "$RAY_NODE_TYPE" = "head" ]; then
    echo "📋 节点类型：Ray头节点"
    /app/scripts/start_ray_head.sh &
elif [ "$RAY_NODE_TYPE" = "worker" ]; then
    echo "📋 节点类型：Ray工作节点"
    /app/scripts/start_ray_worker.sh &
else
    echo "❌ 错误：未知的RAY_NODE_TYPE: $RAY_NODE_TYPE"
    exit 1
fi

RAY_PID=$!

# 等待Ray启动完成
sleep 5

# 验证Ray是否运行
if ! ps -p $RAY_PID > /dev/null; then
    echo "❌ Ray启动失败"
    exit 1
fi

echo "✅ Ray启动成功"

# 启动Celery Worker
echo "🚀 启动Celery Worker..."
exec python src/worker.py
