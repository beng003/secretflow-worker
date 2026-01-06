#!/bin/bash
set -e

echo "🚀 启动Ray工作节点..."

# 检查必要的环境变量
if [ -z "$RAY_HEAD_ADDRESS" ]; then
    echo "❌ 错误：RAY_HEAD_ADDRESS环境变量未设置"
    exit 1
fi

if [ -z "$RAY_NODE_IP" ]; then
    echo "❌ 错误：RAY_NODE_IP环境变量未设置"
    exit 1
fi

# 等待头节点就绪
echo "⏳ 等待Ray头节点就绪..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if ray health-check --address=${RAY_HEAD_ADDRESS} 2>/dev/null; then
        echo "✅ Ray头节点已就绪"
        break
    fi
    retry_count=$((retry_count + 1))
    echo "等待中... ($retry_count/$max_retries)"
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "❌ 错误：无法连接到Ray头节点 ${RAY_HEAD_ADDRESS}"
    exit 1
fi

# 启动Ray工作节点
ray start \
    --address=${RAY_HEAD_ADDRESS} \
    --node-ip-address=${RAY_NODE_IP} \
    --num-cpus=${RAY_NUM_CPUS:-0} \
    --object-store-memory=${RAY_OBJECT_STORE_MEMORY:-2000000000} \
    --block

echo "✅ Ray工作节点启动成功"
