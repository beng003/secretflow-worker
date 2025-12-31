#!/bin/bash
"""
PSI 隐私计算启动脚本
用于启动完整的 SecretFlow PSI 演示环境
"""

set -e

echo "=========================================="
echo "SecretFlow PSI 隐私计算演示环境"
echo "=========================================="

# 检查 Docker 和 Docker Compose
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose 未安装"
    exit 1
fi

# 进入项目目录
cd "$(dirname "$0")/.."

echo "清理之前的容器..."
docker-compose down --volumes --remove-orphans

echo "构建 Docker 镜像..."
docker-compose build --no-cache

echo "创建数据目录..."
mkdir -p data/alice data/bob

echo "启动 PSI 计算环境..."
docker-compose up -d

echo ""
echo "等待容器启动..."
sleep 10

echo ""
echo "检查容器状态..."
docker-compose ps

echo ""
echo "=========================================="
echo "PSI 环境启动完成!"
echo "=========================================="
echo "Alice 容器: sf_alice (172.20.0.10)"
echo "Bob 容器:   sf_bob   (172.20.0.20)"
echo ""
echo "监控日志:"
echo "  Alice: docker-compose logs -f alice"
echo "  Bob:   docker-compose logs -f bob"
echo ""
echo "查看结果:"
echo "  docker-compose exec alice ls -la /data/alice/"
echo "  docker-compose exec bob ls -la /data/bob/"
echo "=========================================="
