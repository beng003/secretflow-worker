#!/bin/bash

set -e

# SecretFlow Ray 集群管理脚本
# 用于生产模式下的 Ray 集群启动和管理

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 默认配置
ACTION="start"
NODE_TYPE="head"
HEAD_IP="127.0.0.1"
HEAD_PORT="10001"
NODE_IP="127.0.0.1"
WORKER_PORT="10002"
DASHBOARD_PORT="8265"
OBJECT_MANAGER_PORT="8076"
MIN_WORKER_PORT="10100"
MAX_WORKER_PORT="10200"
MEMORY_LIMIT="4GB"
CPU_COUNT="2"

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
SecretFlow Ray 集群管理脚本

用法: $0 [选项] [动作]

动作:
    start       启动 Ray 节点
    stop        停止 Ray 节点
    status      查看集群状态
    restart     重启 Ray 节点
    cleanup     清理 Ray 进程和缓存

选项:
    --type TYPE         节点类型: head|worker (默认: head)
    --head-ip IP        头节点IP地址 (默认: 127.0.0.1)
    --head-port PORT    头节点端口 (默认: 10001)
    --node-ip IP        当前节点IP地址 (默认: 127.0.0.1)
    --memory LIMIT      内存限制 (默认: 4GB)
    --cpu COUNT         CPU核心数 (默认: 2)
    -h, --help          显示此帮助信息

环境变量:
    RAY_HEAD_IP         头节点IP地址
    RAY_HEAD_PORT       头节点端口
    NODE_IP             当前节点IP地址
    MEMORY_LIMIT        内存限制
    CPU_COUNT           CPU核心数

示例:
    # 启动头节点
    $0 --type head --head-ip 192.168.1.100 start

    # 启动工作节点
    $0 --type worker --head-ip 192.168.1.100 --node-ip 192.168.1.101 start

    # 查看集群状态
    $0 status

    # 停止并清理
    $0 stop
    $0 cleanup
EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --type)
                NODE_TYPE="$2"
                shift 2
                ;;
            --head-ip)
                HEAD_IP="$2"
                shift 2
                ;;
            --head-port)
                HEAD_PORT="$2"
                shift 2
                ;;
            --node-ip)
                NODE_IP="$2"
                shift 2
                ;;
            --memory)
                MEMORY_LIMIT="$2"
                shift 2
                ;;
            --cpu)
                CPU_COUNT="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            start|stop|status|restart|cleanup)
                ACTION="$1"
                shift
                ;;
            *)
                error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 读取环境变量
load_env_vars() {
    # 从环境变量覆盖默认值
    HEAD_IP=${RAY_HEAD_IP:-$HEAD_IP}
    HEAD_PORT=${RAY_HEAD_PORT:-$HEAD_PORT}
    NODE_IP=${NODE_IP:-$NODE_IP}
    MEMORY_LIMIT=${MEMORY_LIMIT:-$MEMORY_LIMIT}
    CPU_COUNT=${CPU_COUNT:-$CPU_COUNT}
    
    log "配置信息:"
    log "  节点类型: $NODE_TYPE"
    log "  头节点地址: $HEAD_IP:$HEAD_PORT"
    log "  当前节点IP: $NODE_IP"
    log "  内存限制: $MEMORY_LIMIT"
    log "  CPU核心数: $CPU_COUNT"
}

# 验证环境
validate_environment() {
    # 检查网络连通性
    if [[ "$NODE_TYPE" == "worker" && "$HEAD_IP" != "$NODE_IP" ]]; then
        if ! ping -c 1 -W 5 "$HEAD_IP" &> /dev/null; then
            error "无法连接到头节点: $HEAD_IP"
            exit 1
        fi
    fi
    
    # 检查端口可用性
    if [[ "$NODE_TYPE" == "head" ]]; then
        if netstat -tuln 2>/dev/null | grep -q ":$HEAD_PORT "; then
            error "端口 $HEAD_PORT 已被占用"
            exit 1
        fi
    fi
    
    log "环境验证通过"
}

# 启动头节点
start_head_node() {
    log "启动 Ray 头节点..."
    
    ray start \
        --head \
        --node-ip-address="$NODE_IP" \
        --port="$HEAD_PORT" \
        --dashboard-host="0.0.0.0" \
        --dashboard-port="$DASHBOARD_PORT" \
        --object-manager-port="$OBJECT_MANAGER_PORT" \
        --min-worker-port="$MIN_WORKER_PORT" \
        --max-worker-port="$MAX_WORKER_PORT" \
        --memory="$MEMORY_LIMIT" \
        --num-cpus="$CPU_COUNT" \
        --include-dashboard=False \
        --disable-usage-stats \
        --verbose \
        --log-to-driver
    
    log "Ray 头节点启动完成"
    log "Dashboard: http://$NODE_IP:$DASHBOARD_PORT (如果启用)"
}

# 启动工作节点
start_worker_node() {
    log "启动 Ray 工作节点..."
    
    # 等待头节点就绪
    local retry_count=0
    local max_retries=30
    
    while ! ray status --address="$HEAD_IP:$HEAD_PORT" &> /dev/null; do
        if [[ $retry_count -ge $max_retries ]]; then
            error "头节点连接超时: $HEAD_IP:$HEAD_PORT"
            exit 1
        fi
        
        log "等待头节点就绪... (尝试 $((retry_count + 1))/$max_retries)"
        sleep 5
        ((retry_count++))
    done
    
    ray start \
        --address="$HEAD_IP:$HEAD_PORT" \
        --node-ip-address="$NODE_IP" \
        --object-manager-port="$OBJECT_MANAGER_PORT" \
        --min-worker-port="$MIN_WORKER_PORT" \
        --max-worker-port="$MAX_WORKER_PORT" \
        --memory="$MEMORY_LIMIT" \
        --num-cpus="$CPU_COUNT" \
        --disable-usage-stats \
        --verbose \
        --log-to-driver
    
    log "Ray 工作节点启动完成，已连接到: $HEAD_IP:$HEAD_PORT"
}

# 停止 Ray 节点
stop_ray() {
    log "停止 Ray 节点..."
    
    ray stop --force || true
    
    # 强制终止残留进程
    pkill -f "ray::" || true
    pkill -f "raylet" || true
    pkill -f "gcs_server" || true
    
    log "Ray 节点已停止"
}

# 查看集群状态
show_status() {
    log "查看 Ray 集群状态..."
    
    if [[ "$NODE_TYPE" == "head" ]]; then
        ray status --address="$HEAD_IP:$HEAD_PORT" || {
            log "无法连接到 Ray 集群"
            return 1
        }
    else
        # 工作节点查看本地状态
        if pgrep -f "ray::" > /dev/null; then
            log "Ray 工作进程正在运行"
            ray status --address="$HEAD_IP:$HEAD_PORT" || log "无法获取集群状态"
        else
            log "Ray 工作进程未运行"
        fi
    fi
    
    # 显示本地进程信息
    log "本地 Ray 进程:"
    pgrep -f "ray::" | while read -r pid; do
        ps -p "$pid" -o pid,cmd --no-headers || true
    done
}

# 清理 Ray 环境
cleanup_ray() {
    log "清理 Ray 环境..."
    
    # 停止 Ray 进程
    stop_ray
    
    # 清理临时文件和日志
    rm -rf /tmp/ray/* 2>/dev/null || true
    rm -rf ~/ray_results/* 2>/dev/null || true
    
    # 清理共享内存
    if command -v ipcs &> /dev/null; then
        ipcs -m | awk '/ray/ {print $2}' | xargs -r ipcrm -m || true
    fi
    
    log "Ray 环境清理完成"
}

# 健康检查
health_check() {
    log "执行健康检查..."
    
    local health_status="healthy"
    
    # 检查进程状态
    if ! pgrep -f "ray::" > /dev/null; then
        log "警告: Ray 进程未运行"
        health_status="unhealthy"
    fi
    
    # 检查网络连接
    if [[ "$NODE_TYPE" == "worker" ]]; then
        if ! ray status --address="$HEAD_IP:$HEAD_PORT" &> /dev/null; then
            log "警告: 无法连接到头节点"
            health_status="unhealthy"
        fi
    fi
    
    # 检查资源使用
    local memory_usage
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    log "内存使用率: ${memory_usage}%"
    
    if (( $(echo "$memory_usage > 90" | bc -l) )); then
        log "警告: 内存使用率过高"
        health_status="warning"
    fi
    
    log "健康状态: $health_status"
    
    if [[ "$health_status" == "unhealthy" ]]; then
        return 1
    fi
}

# 主函数
main() {
    parse_args "$@"
    load_env_vars
    
    case $ACTION in
        start)
            validate_environment
            if [[ "$NODE_TYPE" == "head" ]]; then
                start_head_node
            elif [[ "$NODE_TYPE" == "worker" ]]; then
                start_worker_node
            else
                error "无效的节点类型: $NODE_TYPE"
                exit 1
            fi
            ;;
        stop)
            stop_ray
            ;;
        status)
            show_status
            ;;
        restart)
            stop_ray
            sleep 5
            if [[ "$NODE_TYPE" == "head" ]]; then
                start_head_node
            else
                start_worker_node
            fi
            ;;
        cleanup)
            cleanup_ray
            ;;
        *)
            error "无效的动作: $ACTION"
            show_help
            exit 1
            ;;
    esac
}

# 错误处理
trap 'error "脚本执行过程中发生错误"; exit 1' ERR

# 运行主函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
