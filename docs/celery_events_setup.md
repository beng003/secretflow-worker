# Celery Events 配置说明

## 问题背景

之前后端服务的 `EventReceiver` 无法监听到 Celery 任务状态，报错：
```
[Errno 111] Connection refused
```

**根本原因**：Worker 没有启用 Celery Events 广播功能。

## 解决方案

已完成以下修改，启用 Celery Events 广播：

### 1. 修改 `src/config/settings.py`

**修改内容**：将 `worker_send_task_events` 默认值从 `false` 改为 `true`

```python
# 修改前
self.worker_send_task_events = (
    os.getenv("WORKER_SEND_TASK_EVENTS", "false").lower() == "true"
)

# 修改后
self.worker_send_task_events = (
    os.getenv("WORKER_SEND_TASK_EVENTS", "true").lower() == "true"
)
```

**作用**：默认启用 Worker 事件广播。

---

### 2. 修改 `src/worker.py`

**修改内容**：移除 `--without-heartbeat` 参数

```python
# 修改前
sys.argv = [
    "worker",
    ...
    "--without-heartbeat",  # 禁用心跳，加速关闭
]

# 修改后
sys.argv = [
    "worker",
    ...
    # 启用事件广播，让后端的EventReceiver可以监听任务状态
    # 移除 --without-heartbeat，保持心跳和事件发送
]
```

**作用**：保持 Worker 心跳和事件发送功能。

---

### 3. 修改 `.env.secretflow`

**修改内容**：启用事件广播环境变量

```bash
# 修改前
WORKER_SEND_TASK_EVENTS=false

# 修改后
WORKER_SEND_TASK_EVENTS=true
```

**作用**：通过环境变量显式启用事件广播。

---

### 4. 优化 `scripts/entrypoint.sh`

**新增功能**：
- ✅ Redis 连接检查（最多重试 30 次）
- ✅ 详细的启动日志
- ✅ 显示 Worker 配置信息
- ✅ 明确标注事件广播已启用

**关键代码**：
```bash
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
```

---

## 架构说明

### ✅ 正确架构（修改后）

```
Backend (后端服务)
  ├─ send_task() → Redis Queue
  │                   ↓
  │           Celery Worker Process
  │              ↓           ↓
  │         消费任务    发送 Events
  │              ↓           ↓
  │      execute_task()   Redis Events Channel
  │              ↓           ↓
  │      SecretFlow 计算    EventReceiver
  │              ↓           ↓
  │      update_state()   监听状态变化
  │              ↓
  └─────────── Redis Result Backend
```

### 关键组件

1. **Celery Worker**：
   - 启动命令：`celery -A celery_app worker`
   - 监听队列：`secretflow_queue`
   - 发送事件：✅ 已启用

2. **EventReceiver（后端）**：
   - 连接到 Redis
   - 监听 Celery Events 通道
   - 接收任务状态变化

3. **update_state()**：
   - 在 `task_executor.py` 中调用
   - 更新任务状态到 Redis
   - 触发 Events 广播

---

## 验证方法

### 1. 检查 Worker 启动日志

启动 Worker 后，应该看到：

```
========================================
🚀 启动Celery Worker
========================================
📋 Worker配置:
   - 队列: secretflow_queue
   - 并发数: 2
   - 日志级别: INFO
   - 事件广播: 已启用 (WORKER_SEND_TASK_EVENTS=true)

[2026-02-01 17:00:00,000: INFO/MainProcess] Connected to redis://redis:6379/0
[2026-02-01 17:00:00,000: INFO/MainProcess] mingle: searching for neighbors
[2026-02-01 17:00:00,000: INFO/MainProcess] celery@node1 ready.
```

### 2. 检查后端 EventReceiver 日志

后端应该不再报 `Connection refused` 错误，而是：

```
[INFO] Celery Events 连接成功
[INFO] 开始监听任务状态变化...
```

### 3. 提交测试任务

```python
from celery_app import celery_app

# 提交任务
result = celery_app.send_task(
    'tasks.secretflow.execute_task',
    args=[task_params]
)

# 监听状态变化
while not result.ready():
    print(f"状态: {result.state}")
    print(f"信息: {result.info}")
    time.sleep(2)
```

应该能看到状态从 `PENDING` → `PROGRESS` → `SUCCESS` 的变化。

---

## 状态更新流程

### 任务执行过程中的状态更新

在 `task_executor.py` 中，任务执行过程会更新以下状态：

1. **task_started** (0%) - 任务开始
2. **cluster_init** (10%) - 集群初始化中
3. **cluster_init_completed** (20%) - 集群初始化完成
4. **device_init** (25%) - 设备初始化中
5. **device_init_completed** (30%) - 设备初始化完成
6. **algorithm_executing** (40%) - 算法执行中
7. **algorithm_completed** (90%) - 算法执行完成
8. **task_completed** (95%) - 任务完成

每个状态都会通过 `celery_task.update_state()` 发送到 Redis，并触发 Events 广播。

---

## 环境变量配置

确保以下环境变量正确配置：

```bash
# Redis 配置
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# Worker 配置
WORKER_SEND_TASK_EVENTS=true  # ← 关键：必须为 true
CELERY_WORKER_CONCURRENCY=2
CELERY_LOG_LEVEL=INFO

# 任务配置
TASK_TRACK_STARTED=true
TASK_ACKS_LATE=true
```

---

## 故障排查

### 问题 1：后端仍然报 Connection refused

**可能原因**：
- Redis 服务未启动
- Redis URL 配置错误
- Docker 网络配置问题

**解决方法**：
```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 测试 Redis 连接
docker exec -it backend-container redis-cli -h redis -p 6379 ping

# 检查网络连接
docker exec -it backend-container nc -zv redis 6379
```

### 问题 2：EventReceiver 连接成功但收不到事件

**可能原因**：
- Worker 未启用事件广播
- Worker 未正常启动

**解决方法**：
```bash
# 检查 Worker 日志
docker logs secretflow-worker | grep "WORKER_SEND_TASK_EVENTS"

# 应该看到：
# - 事件广播: 已启用 (WORKER_SEND_TASK_EVENTS=true)

# 检查 Worker 进程
docker exec -it secretflow-worker pgrep -f "celery worker"
```

### 问题 3：任务状态不更新

**可能原因**：
- `celery_task` 参数未传递
- `update_state()` 调用失败

**解决方法**：
检查 `celery_tasks.py` 是否传递了 `celery_task=self`：
```python
result = execute_secretflow_task(
    ...,
    celery_task=self,  # ← 必须传递
)
```

---

## 总结

✅ **已完成的修改**：
1. 启用 Worker 事件广播（`WORKER_SEND_TASK_EVENTS=true`）
2. 移除禁用心跳的参数（`--without-heartbeat`）
3. 添加 Redis 连接检查
4. 优化启动日志和错误处理

✅ **预期效果**：
- 后端 EventReceiver 可以正常连接
- 可以实时监听任务状态变化
- `update_state()` 的状态更新可以被后端接收
- 任务执行进度可以实时追踪（0% → 95%）

✅ **架构正确性**：
- SecretFlow Worker 是真正的 Celery Worker
- 任务通过 Redis 队列正确消费
- Events 通过 Redis 正确广播
- 后端可以监听到所有状态变化
