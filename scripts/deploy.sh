#!/bin/bash

set -e

# SecretFlow 隐私计算后端部署脚本
# 支持 Docker 和 Kubernetes 部署

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 默认配置
DEPLOYMENT_MODE="docker"
ENVIRONMENT="development"
NODE_COUNT=2
FORCE_REBUILD=false
SKIP_TESTS=false

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# 显示帮助信息
show_help() {
    cat << EOF
SecretFlow 隐私计算后端部署脚本

用法: $0 [选项]

选项:
    -m, --mode MODE         部署模式: docker|kubernetes (默认: docker)
    -e, --env ENVIRONMENT   环境: development|production (默认: development)
    -n, --nodes COUNT       节点数量 (默认: 2)
    -f, --force             强制重新构建镜像
    -s, --skip-tests        跳过测试
    -h, --help              显示此帮助信息

示例:
    $0 -m docker -e development -n 2
    $0 -m kubernetes -e production -n 4 --force
EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--mode)
                DEPLOYMENT_MODE="$2"
                shift 2
                ;;
            -e|--env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -n|--nodes)
                NODE_COUNT="$2"
                shift 2
                ;;
            -f|--force)
                FORCE_REBUILD=true
                shift
                ;;
            -s|--skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 验证环境
validate_environment() {
    log "验证部署环境..."
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose 未安装"
        exit 1
    fi
    
    # 检查 Python 环境
    if ! command -v python3 &> /dev/null; then
        error "Python 3 未安装"
        exit 1
    fi
    
    # 验证项目结构
    if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
        error "项目根目录未找到 pyproject.toml"
        exit 1
    fi
    
    if [[ ! -f "$PROJECT_ROOT/docker/docker-compose.yml" ]]; then
        error "Docker Compose 配置文件未找到"
        exit 1
    fi
    
    log "环境验证完成"
}

# 生成环境变量配置
generate_env_config() {
    log "生成环境变量配置..."
    
    local env_file="$PROJECT_ROOT/.env.${ENVIRONMENT}"
    
    cat > "$env_file" << EOF
# SecretFlow 隐私计算后端环境配置
# 环境: ${ENVIRONMENT}
# 生成时间: $(date)

# Redis 配置
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Celery 配置
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CELERY_TIMEZONE=Asia/Shanghai

# 安全配置
SECURITY_TOKEN=$(openssl rand -hex 32)

# 系统配置
DATA_PATH=/app/data
LOG_LEVEL=INFO
MAX_CONCURRENT_TASKS=4
TASK_TIMEOUT=3600

# 监控配置
FLOWER_BASIC_AUTH=admin:$(openssl rand -base64 12)
EOF

    if [[ "$ENVIRONMENT" == "production" ]]; then
        cat >> "$env_file" << EOF

# 生产环境安全配置
SSL_CERT_PATH=/app/certs/server.crt
SSL_KEY_PATH=/app/certs/server.key
REDIS_PASSWORD=$(openssl rand -base64 16)
EOF
    fi
    
    log "环境配置文件已生成: $env_file"
}

# 构建 Docker 镜像
build_docker_images() {
    log "构建 Docker 镜像..."
    
    cd "$PROJECT_ROOT"
    
    local build_args=""
    if [[ "$FORCE_REBUILD" == "true" ]]; then
        build_args="--no-cache"
    fi
    
    # 构建主应用镜像
    docker build $build_args -t secretflow-backend:latest -f Dockerfile .
    
    log "Docker 镜像构建完成"
}

# 部署到 Docker
deploy_docker() {
    log "部署到 Docker 环境..."
    
    cd "$PROJECT_ROOT/docker"
    
    # 停止现有服务
    docker-compose down || true
    
    # 清理旧数据（仅开发环境）
    if [[ "$ENVIRONMENT" == "development" ]]; then
        docker-compose down -v
    fi
    
    # 启动服务
    docker-compose --env-file="../.env.${ENVIRONMENT}" up -d
    
    # 等待服务启动
    log "等待服务启动..."
    sleep 30
    
    # 验证服务状态
    verify_deployment
    
    log "Docker 部署完成"
}

# 部署到 Kubernetes
deploy_kubernetes() {
    log "部署到 Kubernetes 环境..."
    
    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl 未安装"
        exit 1
    fi
    
    # 创建命名空间
    kubectl create namespace secretflow || true
    
    # 生成 Kubernetes 配置
    generate_k8s_config
    
    # 应用配置
    kubectl apply -f "$PROJECT_ROOT/k8s/"
    
    # 等待部署完成
    kubectl wait --for=condition=available --timeout=300s deployment/secretflow-backend -n secretflow
    
    log "Kubernetes 部署完成"
}

# 生成 Kubernetes 配置
generate_k8s_config() {
    local k8s_dir="$PROJECT_ROOT/k8s"
    mkdir -p "$k8s_dir"
    
    # Redis 部署
    cat > "$k8s_dir/redis.yaml" << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: secretflow
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command: ["redis-server", "--appendonly", "yes"]
        volumeMounts:
        - name: redis-data
          mountPath: /data
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: secretflow
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: secretflow
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF
    
    # SecretFlow 后端部署
    cat > "$k8s_dir/secretflow-backend.yaml" << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secretflow-backend
  namespace: secretflow
spec:
  replicas: ${NODE_COUNT}
  selector:
    matchLabels:
      app: secretflow-backend
  template:
    metadata:
      labels:
        app: secretflow-backend
    spec:
      containers:
      - name: worker
        image: secretflow-backend:latest
        env:
        - name: REDIS_HOST
          value: "redis"
        - name: CELERY_BROKER_URL
          value: "redis://redis:6379/0"
        - name: CELERY_RESULT_BACKEND
          value: "redis://redis:6379/0"
        - name: SECURITY_TOKEN
          valueFrom:
            secretKeyRef:
              name: secretflow-secrets
              key: security-token
        ports:
        - containerPort: 9394
        resources:
          limits:
            memory: "4Gi"
            cpu: "2"
          requests:
            memory: "2Gi"
            cpu: "1"
        volumeMounts:
        - name: data-storage
          mountPath: /app/data
      volumes:
      - name: data-storage
        persistentVolumeClaim:
          claimName: secretflow-data-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: secretflow-backend
  namespace: secretflow
spec:
  selector:
    app: secretflow-backend
  ports:
  - port: 9394
    targetPort: 9394
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: secretflow-data-pvc
  namespace: secretflow
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
EOF
}

# 验证部署状态
verify_deployment() {
    log "验证部署状态..."
    
    if [[ "$DEPLOYMENT_MODE" == "docker" ]]; then
        # 检查容器状态
        if ! docker-compose -f "$PROJECT_ROOT/docker/docker-compose.yml" ps | grep -q "Up"; then
            error "部分服务未正常启动"
            docker-compose -f "$PROJECT_ROOT/docker/docker-compose.yml" logs
            exit 1
        fi
        
        # 检查 Redis 连接
        if ! docker exec secretflow-redis redis-cli ping | grep -q "PONG"; then
            error "Redis 连接失败"
            exit 1
        fi
        
        log "Docker 部署验证通过"
        
        # 显示访问信息
        show_access_info_docker
        
    elif [[ "$DEPLOYMENT_MODE" == "kubernetes" ]]; then
        # 检查 Pod 状态
        if ! kubectl get pods -n secretflow | grep -q "Running"; then
            error "部分 Pod 未正常运行"
            kubectl describe pods -n secretflow
            exit 1
        fi
        
        log "Kubernetes 部署验证通过"
        show_access_info_k8s
    fi
}

# 显示 Docker 访问信息
show_access_info_docker() {
    log "部署完成! 访问信息:"
    echo ""
    echo "🚀 SecretFlow 隐私计算后端服务"
    echo "   Alice 节点: http://localhost:9394"
    echo "   Bob 节点:   http://localhost:9395"
    echo ""
    echo "📊 监控面板"
    echo "   Flower (Celery):     http://localhost:5555"
    echo "   Redis Commander:     http://localhost:8081"
    echo ""
    echo "🔑 默认认证信息"
    echo "   用户名: admin"
    echo "   密码: secretflow2024"
    echo ""
    echo "📝 查看日志: docker-compose -f docker/docker-compose.yml logs -f"
    echo "🛑 停止服务: docker-compose -f docker/docker-compose.yml down"
}

# 显示 Kubernetes 访问信息  
show_access_info_k8s() {
    log "部署完成! 访问信息:"
    echo ""
    echo "🚀 SecretFlow 隐私计算后端服务"
    echo "   命名空间: secretflow"
    echo ""
    echo "📝 查看状态: kubectl get pods -n secretflow"
    echo "📝 查看日志: kubectl logs -f deployment/secretflow-backend -n secretflow"
    echo "🛑 删除服务: kubectl delete namespace secretflow"
}

# 运行测试
run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log "跳过测试"
        return
    fi
    
    log "运行测试..."
    
    # 这里可以添加具体的测试逻辑
    # 例如：健康检查、API 测试等
    
    log "测试完成"
}

# 清理环境
cleanup() {
    log "清理部署环境..."
    
    if [[ "$DEPLOYMENT_MODE" == "docker" ]]; then
        cd "$PROJECT_ROOT/docker"
        docker-compose down -v
        docker system prune -f
    elif [[ "$DEPLOYMENT_MODE" == "kubernetes" ]]; then
        kubectl delete namespace secretflow || true
    fi
    
    log "环境清理完成"
}

# 主函数
main() {
    parse_args "$@"
    
    log "开始部署 SecretFlow 隐私计算后端"
    log "部署模式: $DEPLOYMENT_MODE"
    log "环境: $ENVIRONMENT"
    log "节点数量: $NODE_COUNT"
    
    validate_environment
    generate_env_config
    
    if [[ "$DEPLOYMENT_MODE" == "docker" ]]; then
        build_docker_images
        deploy_docker
    elif [[ "$DEPLOYMENT_MODE" == "kubernetes" ]]; then
        build_docker_images
        deploy_kubernetes
    else
        error "不支持的部署模式: $DEPLOYMENT_MODE"
        exit 1
    fi
    
    run_tests
    
    log "部署完成!"
}

# 错误处理
trap 'error "部署过程中发生错误，正在清理..."; cleanup; exit 1' ERR

# 运行主函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
