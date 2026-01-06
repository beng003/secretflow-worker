#!/bin/bash
set -e

echo "🚀 启动SecretFlow Worker容器..."
echo "📋 节点ID: ${NODE_ID}"
echo "📋 节点IP: ${NODE_IP}"

# 使用ray start命令启动独立的Ray集群
# 每个节点都启动自己的头节点
echo "🚀 启动Ray集群..."
ray start --head \
    --node-ip-address="${NODE_IP}" \
    --port="${RAY_PORT:-61379}" \
    --num-cpus="${RAY_NUM_CPUS:-0}" \
    --object-store-memory="${RAY_OBJECT_STORE_MEMORY:-2000000000}" \
    --include-dashboard=False \
    --disable-usage-stats

if [ $? -ne 0 ]; then
    echo "❌ Ray启动失败"
    exit 1
fi

# 等待Ray启动完成
echo "⏳ 等待Ray初始化..."
sleep 5

# 验证Ray状态
echo "📊 检查Ray状态..."
ray status || echo "⚠️  ray status命令失败，但Ray可能已正常启动"

echo "✅ Ray启动成功"

# 启动Celery Worker
echo "🚀 启动Celery Worker..."
exec python src/worker.py
