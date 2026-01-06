.PHONY: help lint format check fix test clean docker-build docker-up docker-down docker-logs docker-restart dev dev-redis redis-start redis-stop redis-logs

# 默认目标
.DEFAULT_GOAL := help

# 颜色定义
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# 项目配置
PROJECT_NAME := secretflow-worker
PYTHON := python3
VENV := .venv
DOCKER_COMPOSE := docker compose
DOCKER_COMPOSE_FILE := docker/docker-compose.production.yml
DOCKER_COMPOSE_DEV := docker/docker-compose.dev.yml
ENV_FILE := .env.production
ENV_DEV := .env.development

##@ 帮助

help: ## 显示帮助信息
	@echo "$(BLUE)SecretFlow Worker - Makefile命令$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "使用方法: make $(GREEN)<target>$(NC)\n\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BLUE)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ 代码质量

lint: ## 运行ruff检查代码
	@echo "$(BLUE)🔍 运行代码检查...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && ruff check src/ tests/; \
	else \
		ruff check src/ tests/; \
	fi

format: ## 使用ruff格式化代码
	@echo "$(BLUE)✨ 格式化代码...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && ruff format src/ tests/; \
	else \
		ruff format src/ tests/; \
	fi

check: ## 检查代码格式（不修改文件）
	@echo "$(BLUE)🔍 检查代码格式...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && ruff format --check src/ tests/; \
	else \
		ruff format --check src/ tests/; \
	fi

fix: ## 自动修复代码问题（ruff check + format）
	@echo "$(BLUE)🔧 自动修复代码问题...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && ruff check --fix src/ tests/ && ruff format src/ tests/; \
	else \
		ruff check --fix src/ tests/ && ruff format src/ tests/; \
	fi
	@echo "$(GREEN)✅ 代码修复完成$(NC)"

##@ Docker相关

docker-build: ## 构建Docker镜像
	@echo "$(BLUE)🐳 构建Docker镜像...$(NC)"
	docker build -f docker/Dockerfile -t $(PROJECT_NAME):latest .
	@echo "$(GREEN)✅ 镜像构建完成$(NC)"

docker-up: ## 启动生产环境容器
	@echo "$(BLUE)🚀 启动生产环境容器...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) up -d
	@echo "$(GREEN)✅ 容器启动完成$(NC)"
	@echo "$(YELLOW)💡 查看日志: make docker-logs$(NC)"

docker-down: ## 停止并删除容器
	@echo "$(BLUE)🛑 停止容器...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) down
	@echo "$(GREEN)✅ 容器已停止$(NC)"

docker-restart: docker-down docker-build docker-up ## 重启容器（重新构建）

docker-logs: ## 查看容器日志
	@echo "$(BLUE)📋 查看容器日志...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) logs -f

docker-logs-worker: ## 查看Worker容器日志
	@echo "$(BLUE)📋 查看Worker日志...$(NC)"
	docker logs -f node1-worker

docker-logs-redis: ## 查看Redis容器日志
	@echo "$(BLUE)📋 查看Redis日志...$(NC)"
	docker logs -f node1-redis

docker-ps: ## 查看运行中的容器
	@echo "$(BLUE)📊 运行中的容器:$(NC)"
	docker ps --filter name=node1

docker-exec: ## 进入Worker容器（交互式shell）
	@echo "$(BLUE)🔧 进入Worker容器...$(NC)"
	docker exec -it node1-worker /bin/bash

docker-ray-status: ## 查看Ray集群状态
	@echo "$(BLUE)📊 Ray集群状态:$(NC)"
	docker exec node1-worker ray status

docker-clean: ## 清理Docker资源（容器、卷、网络）
	@echo "$(YELLOW)⚠️  清理Docker资源...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) --env-file $(ENV_FILE) down -v
	@echo "$(GREEN)✅ 清理完成$(NC)"

docker-clean-all: docker-clean ## 清理所有Docker资源（包括镜像）
	@echo "$(YELLOW)⚠️  删除镜像...$(NC)"
	docker rmi $(PROJECT_NAME):latest || true
	@echo "$(GREEN)✅ 完全清理完成$(NC)"

##@ 开发环境

dev: ## 启动开发环境（本地Python + 本地Ray + 本地Redis）
	@echo "$(BLUE)🚀 启动开发环境...$(NC)"
	@echo "$(YELLOW)💡 确保已启动Redis: make redis-start$(NC)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(RED)❌ 虚拟环境不存在，请先运行: python -m venv .venv && source .venv/bin/activate && pip install -e .$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ 启动Celery Worker...$(NC)"
	@. $(VENV)/bin/activate && python src/worker.py

dev-ray: ## 启动本地Ray集群（开发用）
	@echo "$(BLUE)🚀 启动本地Ray集群...$(NC)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(RED)❌ 虚拟环境不存在$(NC)"; \
		exit 1; \
	fi
	@. $(VENV)/bin/activate && ray start --head \
		--port=6379 \
		--num-cpus=0 \
		--object-store-memory=2000000000 \
		--include-dashboard=True \
		--dashboard-host=0.0.0.0 \
		--dashboard-port=8265
	@echo "$(GREEN)✅ Ray集群已启动$(NC)"
	@echo "$(YELLOW)💡 Dashboard: http://localhost:8265$(NC)"
	@echo "$(YELLOW)💡 停止Ray: make dev-ray-stop$(NC)"

dev-ray-stop: ## 停止本地Ray集群
	@echo "$(BLUE)🛑 停止Ray集群...$(NC)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(RED)❌ 虚拟环境不存在$(NC)"; \
		exit 1; \
	fi
	@. $(VENV)/bin/activate && ray stop
	@echo "$(GREEN)✅ Ray集群已停止$(NC)"

dev-ray-status: ## 查看本地Ray集群状态
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(RED)❌ 虚拟环境不存在$(NC)"; \
		exit 1; \
	fi
	@. $(VENV)/bin/activate && ray status

##@ Redis开发环境

redis-start: ## 启动Redis容器（开发用）
	@echo "$(BLUE)🚀 启动Redis容器...$(NC)"
	@if [ ! -f "$(DOCKER_COMPOSE_DEV)" ]; then \
		echo "$(YELLOW)⚠️  开发环境配置文件不存在，创建中...$(NC)"; \
		$(MAKE) _create-dev-compose; \
	fi
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_DEV) up -d redis
	@echo "$(GREEN)✅ Redis已启动$(NC)"
	@echo "$(YELLOW)💡 连接地址: redis://localhost:6379/0$(NC)"
	@echo "$(YELLOW)💡 查看日志: make redis-logs$(NC)"

redis-stop: ## 停止Redis容器
	@echo "$(BLUE)🛑 停止Redis容器...$(NC)"
	@if [ -f "$(DOCKER_COMPOSE_DEV)" ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_DEV) down; \
	fi
	@echo "$(GREEN)✅ Redis已停止$(NC)"

redis-logs: ## 查看Redis日志
	@echo "$(BLUE)📋 Redis日志:$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_DEV) logs -f redis

redis-cli: ## 连接到Redis CLI
	@echo "$(BLUE)🔧 连接到Redis...$(NC)"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_DEV) exec redis redis-cli

redis-restart: redis-stop redis-start ## 重启Redis容器

##@ 任务管理

task-hello: ## 发送hello测试任务到队列
	@echo "$(BLUE)📤 发送hello任务...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && python scripts/send_task.py hello; \
	else \
		python scripts/send_task.py hello; \
	fi

task-health: ## 发送健康检查任务到队列
	@echo "$(BLUE)📤 发送健康检查任务...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && python scripts/send_task.py health; \
	else \
		python scripts/send_task.py health; \
	fi

task-psi: ## 发送PSI测试任务到队列
	@echo "$(BLUE)📤 发送PSI任务...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && python scripts/send_task.py psi; \
	else \
		python scripts/send_task.py psi; \
	fi

task-send: ## 使用Python交互式发送自定义任务
	@echo "$(BLUE)📤 启动Python交互式环境...$(NC)"
	@echo "$(YELLOW)示例代码:$(NC)"
	@echo "  from src.celery_app import app"
	@echo "  result = app.send_task('tasks.secretflow.hello.hello_task', queue='secretflow_queue')"
	@echo "  print(f'Task ID: {result.id}')"
	@echo "  result.get(timeout=60)"
	@echo ""
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && python -i -c "from src.celery_app import app; print('✅ Celery app已加载，可以使用app.send_task()发送任务')"; \
	else \
		python -i -c "from src.celery_app import app; print('✅ Celery app已加载，可以使用app.send_task()发送任务')"; \
	fi

##@ 测试

test: ## 运行测试
	@echo "$(BLUE)🧪 运行测试...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && pytest tests/ -v; \
	else \
		pytest tests/ -v; \
	fi

test-cov: ## 运行测试并生成覆盖率报告
	@echo "$(BLUE)🧪 运行测试（含覆盖率）...$(NC)"
	@if [ -d "$(VENV)" ]; then \
		. $(VENV)/bin/activate && pytest tests/ -v --cov=src --cov-report=html --cov-report=term; \
	else \
		pytest tests/ -v --cov=src --cov-report=html --cov-report=term; \
	fi
	@echo "$(GREEN)✅ 覆盖率报告: htmlcov/index.html$(NC)"

##@ 清理

clean: ## 清理Python缓存文件
	@echo "$(BLUE)🧹 清理缓存文件...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true
	@echo "$(GREEN)✅ 清理完成$(NC)"

clean-all: clean docker-clean-all ## 清理所有（Python缓存 + Docker资源）

##@ 内部目标（不要直接调用）

_create-dev-compose: ## 创建开发环境Docker Compose配置
	@mkdir -p docker
	@echo "version: '3.8'" > $(DOCKER_COMPOSE_DEV)
	@echo "" >> $(DOCKER_COMPOSE_DEV)
	@echo "services:" >> $(DOCKER_COMPOSE_DEV)
	@echo "  redis:" >> $(DOCKER_COMPOSE_DEV)
	@echo "    image: redis:7-alpine" >> $(DOCKER_COMPOSE_DEV)
	@echo "    container_name: dev-redis" >> $(DOCKER_COMPOSE_DEV)
	@echo "    ports:" >> $(DOCKER_COMPOSE_DEV)
	@echo "      - \"6379:6379\"" >> $(DOCKER_COMPOSE_DEV)
	@echo "    command:" >> $(DOCKER_COMPOSE_DEV)
	@echo "      - redis-server" >> $(DOCKER_COMPOSE_DEV)
	@echo "      - --maxmemory" >> $(DOCKER_COMPOSE_DEV)
	@echo "      - \"2gb\"" >> $(DOCKER_COMPOSE_DEV)
	@echo "      - --maxmemory-policy" >> $(DOCKER_COMPOSE_DEV)
	@echo "      - allkeys-lru" >> $(DOCKER_COMPOSE_DEV)
	@echo "    healthcheck:" >> $(DOCKER_COMPOSE_DEV)
	@echo "      test: [\"CMD\", \"redis-cli\", \"ping\"]" >> $(DOCKER_COMPOSE_DEV)
	@echo "      interval: 5s" >> $(DOCKER_COMPOSE_DEV)
	@echo "      timeout: 3s" >> $(DOCKER_COMPOSE_DEV)
	@echo "      retries: 5" >> $(DOCKER_COMPOSE_DEV)
	@echo "    volumes:" >> $(DOCKER_COMPOSE_DEV)
	@echo "      - redis_dev_data:/data" >> $(DOCKER_COMPOSE_DEV)
	@echo "" >> $(DOCKER_COMPOSE_DEV)
	@echo "volumes:" >> $(DOCKER_COMPOSE_DEV)
	@echo "  redis_dev_data:" >> $(DOCKER_COMPOSE_DEV)
	@echo "$(GREEN)✅ 开发环境配置已创建: $(DOCKER_COMPOSE_DEV)$(NC)"
