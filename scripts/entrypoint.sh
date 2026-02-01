#!/bin/bash
set -e

echo "========================================"
echo "🚀 启动SecretFlow Worker容器"
echo "========================================"
echo "📋 节点ID: ${NODE_ID}"
echo "📋 节点IP: ${NODE_IP}"
echo "📋 Redis URL: ${REDIS_URL}"
echo "📋 Celery Broker: ${CELERY_BROKER_URL:-$REDIS_URL}"
echo ""

# 检查Redis连接
echo "🔍 检查Redis连接..."
MAX_RETRIES=30
RETRY_COUNT=0
REDIS_HOST=$(echo $REDIS_URL | sed -n 's/.*\/\/\([^:]*\).*/\1/p')
REDIS_PORT=$(echo $REDIS_URL | sed -n 's/.*:\([0-9]*\).*/\1/p')

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if timeout 2 bash -c "echo > /dev/tcp/${REDIS_HOST}/${REDIS_PORT}" 2>/dev/null; then
        echo "✅ Redis连接成功 (${REDIS_HOST}:${REDIS_PORT})"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "⏳ 等待Redis启动... (${RETRY_COUNT}/${MAX_RETRIES})"
        sleep 2
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Redis连接失败，无法启动Worker"
    exit 1
fi

echo ""

# 启动Ray集群
echo "========================================"
echo "🚀 启动Ray集群"
echo "========================================"
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

# 等待Ray初始化
echo "⏳ 等待Ray初始化..."
sleep 5

# 验证Ray状态
echo "📊 检查Ray状态..."
ray status || echo "⚠️  ray status命令失败，但Ray可能已正常启动"

echo "✅ Ray启动成功"
echo ""

# 启动Celery Worker
echo "========================================"
echo "🚀 启动Celery Worker"
echo "========================================"
echo "📋 Worker配置:"
echo "   - 队列: ${CELERY_QUEUES:-secretflow_queue}"
echo "   - 并发数: ${CELERY_WORKER_CONCURRENCY:-2}"
echo "   - 日志级别: ${CELERY_LOG_LEVEL:-INFO}"
echo "   - 事件广播: 已启用 (WORKER_SEND_TASK_EVENTS=true)"
echo ""

# 使用exec确保Celery Worker接收信号
exec python src/worker.py
