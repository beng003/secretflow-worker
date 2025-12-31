# SecretFlow 隐私计算后端 Makefile
# 简化常用开发和部署操作

.PHONY: help install build start stop restart logs clean deploy test lint format

# 默认目标
help:
	@echo "SecretFlow 隐私计算后端 - 可用命令:"
	@echo ""
	@echo "开发环境:"
	@echo "  install     安装项目依赖"
	@echo "  build       构建 Docker 镜像"
	@echo "  start       启动开发环境"
	@echo "  stop        停止所有服务"
	@echo "  restart     重启服务"
	@echo "  logs        查看服务日志"
	@echo ""
	@echo "部署相关:"
	@echo "  deploy-dev  部署开发环境"
	@echo "  deploy-prod 部署生产环境"
	@echo "  status      查看服务状态"
	@echo ""
	@echo "工具命令:"
	@echo "  test        运行测试"
	@echo "  lint        代码检查"
	@echo "  format      代码格式化"
	@echo "  clean       清理环境"
	@echo "  shell       进入容器 shell"
	@echo ""
	@echo "Ray 集群:"
	@echo "  ray-start   启动 Ray 集群"
	@echo "  ray-stop    停止 Ray 集群"
	@echo "  ray-status  查看 Ray 状态"

# =================================================================
# 开发环境
# =================================================================

install:
	@echo "📦 安装项目依赖..."
	pip install -e .
	@echo "✅ 依赖安装完成"

build:
	@echo "🔨 构建 Docker 镜像..."
	docker build -t secretflow-backend:latest .
	@echo "✅ 镜像构建完成"

start: build
	@echo "🚀 启动开发环境..."
	cp -n .env.example .env || true
	cd docker && docker-compose up -d
	@echo "✅ 开发环境已启动"
	@echo ""
	@echo "📊 访问监控面板:"
	@echo "   Flower:          http://localhost:5555"
	@echo "   Redis Commander: http://localhost:8081"

stop:
	@echo "🛑 停止所有服务..."
	cd docker && docker-compose down
	@echo "✅ 服务已停止"

restart: stop start
	@echo "🔄 服务重启完成"

logs:
	@echo "📝 查看服务日志..."
	cd docker && docker-compose logs -f

status:
	@echo "📊 服务状态:"
	cd docker && docker-compose ps

# =================================================================
# 部署相关
# =================================================================

deploy-dev:
	@echo "🚀 部署开发环境..."
	./scripts/deploy.sh -m docker -e development -n 2
	@echo "✅ 开发环境部署完成"

deploy-prod:
	@echo "🚀 部署生产环境..."
	./scripts/deploy.sh -m docker -e production -n 3 --force
	@echo "✅ 生产环境部署完成"

deploy-k8s:
	@echo "☸️ 部署到 Kubernetes..."
	./scripts/deploy.sh -m kubernetes -e production -n 4
	@echo "✅ Kubernetes 部署完成"

# =================================================================
# 工具命令
# =================================================================

test:
	@echo "🧪 运行测试..."
	python -m pytest tests/ -v
	@echo "✅ 测试完成"

lint:
	@echo "🔍 代码检查..."
	flake8 src/ --max-line-length=88 --exclude=__pycache__
	black --check src/
	isort --check-only src/
	@echo "✅ 代码检查完成"

format:
	@echo "🎨 代码格式化..."
	black src/
	isort src/
	@echo "✅ 代码格式化完成"

shell:
	@echo "🐚 进入 Alice 节点容器..."
	docker exec -it secretflow-worker-alice /bin/bash

shell-bob:
	@echo "🐚 进入 Bob 节点容器..."
	docker exec -it secretflow-worker-bob /bin/bash

shell-redis:
	@echo "🐚 进入 Redis 容器..."
	docker exec -it secretflow-redis /bin/sh

# =================================================================
# Ray 集群管理
# =================================================================

ray-start:
	@echo "⚡ 启动 Ray 集群..."
	./scripts/ray_cluster.sh --type head --node-ip 127.0.0.1 start
	@echo "✅ Ray 集群已启动"

ray-stop:
	@echo "⚡ 停止 Ray 集群..."
	./scripts/ray_cluster.sh stop
	@echo "✅ Ray 集群已停止"

ray-status:
	@echo "⚡ Ray 集群状态:"
	./scripts/ray_cluster.sh status

ray-cleanup:
	@echo "🧹 清理 Ray 环境..."
	./scripts/ray_cluster.sh cleanup
	@echo "✅ Ray 环境清理完成"

# =================================================================
# 环境清理
# =================================================================

clean:
	@echo "🧹 清理开发环境..."
	cd docker && docker-compose down -v || true
	docker system prune -f
	docker volume prune -f
	rm -rf __pycache__/ .pytest_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ 环境清理完成"

clean-all: clean
	@echo "🧹 深度清理..."
	docker rmi secretflow-backend:latest || true
	docker rmi secretflow/secretflow-anolis8:1.12.0b0 || true
	@echo "✅ 深度清理完成"

# =================================================================
# 健康检查和诊断
# =================================================================

health:
	@echo "🩺 执行健康检查..."
	@echo "检查 Docker 服务..."
	docker version > /dev/null && echo "✅ Docker 正常" || echo "❌ Docker 异常"
	@echo "检查 Docker Compose..."
	docker-compose version > /dev/null && echo "✅ Docker Compose 正常" || echo "❌ Docker Compose 异常"
	@echo "检查服务状态..."
	cd docker && docker-compose ps
	@echo "检查网络连通性..."
	@if docker ps --format "table {{.Names}}" | grep -q secretflow; then \
		docker exec secretflow-worker-alice ping -c 1 redis > /dev/null 2>&1 && echo "✅ Alice -> Redis 连通" || echo "❌ Alice -> Redis 连接失败"; \
		docker exec secretflow-worker-bob ping -c 1 redis > /dev/null 2>&1 && echo "✅ Bob -> Redis 连通" || echo "❌ Bob -> Redis 连接失败"; \
	else \
		echo "⚠️ 容器未运行"; \
	fi

monitor:
	@echo "📊 打开监控面板..."
	@echo "Flower (Celery): http://localhost:5555"
	@echo "Redis Commander: http://localhost:8081"
	@if command -v xdg-open > /dev/null; then \
		xdg-open http://localhost:5555 2>/dev/null & \
		xdg-open http://localhost:8081 2>/dev/null & \
	elif command -v open > /dev/null; then \
		open http://localhost:5555 2>/dev/null & \
		open http://localhost:8081 2>/dev/null & \
	else \
		echo "请手动访问上述 URL"; \
	fi

# =================================================================
# 开发工具
# =================================================================

dev-setup:
	@echo "⚙️ 设置开发环境..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ 创建 .env 文件"; \
	fi
	@if [ ! -f .gitignore ]; then \
		echo "*.pyc\n__pycache__/\n.env\n.pytest_cache/\nnode_modules/\n*.log" > .gitignore; \
		echo "✅ 创建 .gitignore 文件"; \
	fi
	chmod +x scripts/*.sh
	@echo "✅ 开发环境设置完成"

backup:
	@echo "💾 备份数据..."
	mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	cd docker && docker-compose exec redis redis-cli --rdb /data/dump.rdb
	docker cp secretflow-redis:/data/dump.rdb backups/$(shell date +%Y%m%d_%H%M%S)/
	@echo "✅ 数据备份完成"

# =================================================================
# 示例任务
# =================================================================

demo-psi:
	@echo "🎯 运行 PSI 示例..."
	python -c "
from celery import Celery
app = Celery('secretflow_backend', broker='redis://localhost:6379/0')
config = {
    'task_id': 'demo_psi_001',
    'parties': ['alice', 'bob'],
    'data_config': {'protocol': 'ECDH_PSI_2PC'},
    'output_config': {'output_path': '/tmp/psi_output'}
}
result = app.send_task('tasks.privacy_computing.psi_intersection', args=[config])
print(f'任务已提交: {result.id}')
print('请访问 http://localhost:5555 查看任务状态')
"

demo-health:
	@echo "🏥 运行健康检查示例..."
	python -c "
from celery import Celery
app = Celery('secretflow_backend', broker='redis://localhost:6379/0')
result = app.send_task('tasks.health_check.node_health_check')
print(f'健康检查任务: {result.id}')
print(f'执行结果: {result.get(timeout=30)}')
"

# =================================================================
# 文档和帮助
# =================================================================

docs:
	@echo "📚 生成文档..."
	@echo "项目文档位于: README.md"
	@echo "配置示例: .env.example"
	@echo "部署脚本: scripts/deploy.sh"

version:
	@echo "📋 版本信息:"
	@grep "version" pyproject.toml | head -1
	@echo "Docker 镜像: secretflow-backend:latest"
	@echo "基础镜像: secretflow/secretflow-anolis8:1.12.0b0"
