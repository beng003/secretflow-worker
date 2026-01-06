#!/bin/bash
set -e

echo "🚀 启动Ray头节点..."

# 检查必要的环境变量
if [ -z "$RAY_NODE_IP" ]; then
    echo "❌ 错误：RAY_NODE_IP环境变量未设置"
    exit 1
fi

# 启动Ray头节点
ray start \
    --head \
    --port=${RAY_PORT:-61379} \
    --node-ip-address=${RAY_NODE_IP} \
    --num-cpus=${RAY_NUM_CPUS:-0} \
    --object-store-memory=${RAY_OBJECT_STORE_MEMORY:-2000000000} \
    --include-dashboard=false \
    --block

echo "✅ Ray头节点启动成功"
