#!/bin/bash
set -e

# SecretFlow生产环境部署脚本 (Host网络模式)

echo "=========================================="
echo "SecretFlow Worker 生产环境部署"
echo "=========================================="

# 检查环境变量文件
if [ ! -f ".env.production" ]; then
    echo "❌ 错误：未找到 .env.production 文件"
    echo "请先从模板创建配置文件："
    echo "  cp config/production.env.template .env.production"
    echo "  vim .env.production  # 编辑配置"
    exit 1
fi

# 加载环境变量
source .env.production

echo ""
echo "📋 部署配置："
echo "  节点ID: ${NODE_ID}"
echo "  节点IP: ${NODE_IP}"
echo "  Ray类型: ${RAY_NODE_TYPE}"
echo "  Redis端口: ${REDIS_PORT}"
echo "  Ray端口: ${RAY_PORT}"
echo "  SecretFlow端口: ${SF_PORT_RANGE_START}-${SF_PORT_RANGE_END}"
echo ""

# 检查端口占用
echo "🔍 检查端口占用..."
check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":${port} "; then
        echo "⚠️  警告：端口 ${port} 已被占用"
        return 1
    fi
    return 0
}

# 检查关键端口
if ! check_port ${REDIS_PORT}; then
    echo "❌ Redis端口 ${REDIS_PORT} 已被占用，请修改配置或停止占用进程"
    exit 1
fi

if [ "${RAY_NODE_TYPE}" = "head" ]; then
    if ! check_port ${RAY_PORT}; then
        echo "❌ Ray端口 ${RAY_PORT} 已被占用，请修改配置或停止占用进程"
        exit 1
    fi
fi

echo "✅ 端口检查通过"
echo ""

# 停止现有容器
echo "🛑 停止现有容器..."
docker compose -f docker/docker-compose.production.yml --env-file .env.production down 2>/dev/null || true
echo ""

# 构建镜像
echo "🔨 构建Docker镜像..."
docker build -f docker/Dockerfile -t secretflow-worker:latest .
if [ $? -ne 0 ]; then
    echo "❌ 镜像构建失败"
    exit 1
fi
echo "✅ 镜像构建成功"
echo ""

# 启动服务
echo "🚀 启动服务..."
docker compose -f docker/docker-compose.production.yml --env-file .env.production up -d
if [ $? -ne 0 ]; then
    echo "❌ 服务启动失败"
    exit 1
fi
echo ""

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查容器状态
echo ""
echo "📊 容器状态："
docker ps --filter "name=${NODE_ID}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 显示日志
echo "📋 Worker日志（最后20行）："
echo "----------------------------------------"
docker logs ${NODE_ID}-worker --tail 20
echo "----------------------------------------"
echo ""

# 验证Ray集群
if [ "${RAY_NODE_TYPE}" = "head" ]; then
    echo "🔍 验证Ray集群状态..."
    sleep 5
    docker exec ${NODE_ID}-worker ray status 2>/dev/null || echo "⚠️  Ray集群状态检查失败（可能还在启动中）"
    echo ""
fi

echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "📋 后续操作："
echo "  查看日志: docker logs -f ${NODE_ID}-worker"
echo "  进入容器: docker exec -it ${NODE_ID}-worker bash"
echo "  停止服务: docker compose -f docker/docker-compose.production.yml --env-file .env.production down"
echo "  重启服务: docker compose -f docker/docker-compose.production.yml --env-file .env.production restart"
echo ""

if [ "${RAY_NODE_TYPE}" = "head" ]; then
    echo "📋 Ray集群管理："
    echo "  查看状态: docker exec ${NODE_ID}-worker ray status"
    echo "  查看节点: docker exec ${NODE_ID}-worker ray list nodes"
    echo ""
fi

echo "=========================================="
