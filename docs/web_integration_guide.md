# Web 容器与 Worker 容器对接指南

## 概述

本文档说明 Web 容器（FastAPI + Celery）如何与 SecretFlow Worker 容器对接，实现完整的隐私计算任务调度和状态管理。

## 核心对接要点

### 设计原则

1. **职责分离**
   - Web 容器：业务逻辑、任务编排、数据库访问、API 接口
   - Worker 容器：纯计算任务执行、结果返回

2. **通信方式**
   - 任务下发：Web → Redis 队列 → Worker
   - 状态通知：Worker → Redis 发布订阅 → Web
   - 结果返回：Worker → Redis Backend → Web

3. **数据传递**
   - 所有数据通过任务参数传递
   - Worker 不访问 Web 容器的数据库
   - 文件路径使用容器内绝对路径

## 一、任务提交对接

### 1.1 Web 端任务提交服务

Web 容器需要实现任务提交服务，构建符合 Worker API 规范的任务参数。

**推荐实现位置**：`web/src/services/secretflow_task_service.py`

```python
from celery import Celery
from typing import Dict, Any
import uuid

class SecretFlowTaskService:
    """SecretFlow 任务提交服务"""
    
    def __init__(self, redis_url: str):
        self.celery_app = Celery(
            'web_task_submitter',
            broker=redis_url,
            backend=redis_url
        )
    
    def submit_psi_task(
        self,
        parties: list,
        keys: Dict[str, list],
        input_paths: Dict[str, str],
        output_paths: Dict[str, str],
        receiver: str,
        protocol: str = "KKRT_PSI_2PC"
    ) -> str:
        """
        提交 PSI 任务
        
        Returns:
            task_id: Celery 任务 ID
        """
        task_request_id = f"psi-{uuid.uuid4().hex[:8]}"
        
        task_params = {
            "sf_init_config": {
                "parties": parties,
                "address": "local"  # 生产环境使用集群模式
            },
            "spu_config": {
                "cluster_def": {
                    "nodes": [
                        {"party": party, "address": f"127.0.0.1:{12345+i}"}
                        for i, party in enumerate(parties)
                    ],
                    "runtime_config": {
                        "protocol": "SEMI2K",
                        "field": "FM128"
                    }
                }
            },
            "task_config": {
                "task_type": "psi",
                "keys": keys,
                "input_paths": input_paths,
                "output_paths": output_paths,
                "receiver": receiver,
                "protocol": protocol,
                "sort": True
            }
        }
        
        # 发送任务到 Worker
        result = self.celery_app.send_task(
            "tasks.secretflow.execute_task",
            args=[task_request_id, task_params],
            queue="secretflow_queue"
        )
        
        return result.id
```

### 1.2 FastAPI 接口实现

**推荐实现位置**：`web/src/api/v1/secretflow.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List

router = APIRouter(prefix="/api/v1/secretflow", tags=["SecretFlow"])

class PSITaskRequest(BaseModel):
    """PSI 任务请求"""
    parties: List[str]
    keys: Dict[str, List[str]]
    input_paths: Dict[str, str]
    output_paths: Dict[str, str]
    receiver: str
    protocol: str = "KKRT_PSI_2PC"

@router.post("/tasks/psi")
async def submit_psi_task(
    request: PSITaskRequest,
    task_service: SecretFlowTaskService = Depends(get_task_service)
):
    """提交 PSI 任务"""
    try:
        # 1. 参数验证（业务层面）
        validate_psi_request(request)
        
        # 2. 提交任务
        task_id = task_service.submit_psi_task(
            parties=request.parties,
            keys=request.keys,
            input_paths=request.input_paths,
            output_paths=request.output_paths,
            receiver=request.receiver,
            protocol=request.protocol
        )
        
        # 3. 保存任务记录到数据库
        await save_task_record(task_id, request)
        
        # 4. 返回任务 ID
        return {
            "task_id": task_id,
            "status": "PENDING",
            "message": "任务已提交"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 1.3 任务参数构建规范

**关键要点**：

1. **文件路径**：使用容器内绝对路径（如 `/app/data/xxx.csv`）
2. **参与方名称**：保持一致（alice, bob 等）
3. **集群配置**：
   - 开发/测试：使用本地模式 `"address": "local"`
   - 生产环境：使用集群模式，配置各参与方地址

**完整任务参数示例**：参见 `docs/worker-api/00.worker-api.md`

## 二、任务状态监听对接

### 2.1 状态监听服务实现

Worker 容器会通过 Redis 发布任务状态事件，Web 容器需要实现监听服务接收这些事件。

**推荐实现位置**：`web/src/services/task_status_listener.py`

```python
import asyncio
import aioredis
import json
from typing import Dict, Any

class TaskStatusListener:
    """任务状态监听服务"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None
        self.running = False
    
    async def start_listening(self):
        """启动状态监听"""
        self.redis = await aioredis.from_url(self.redis_url)
        self.running = True
        
        # 并行监听发布订阅和队列
        await asyncio.gather(
            self._listen_pubsub(),
            self._process_status_queue()
        )
    
    async def _listen_pubsub(self):
        """监听 Redis 发布订阅频道"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("task_status_events")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    await self._handle_status_event(event)
                except Exception as e:
                    logger.error(f"处理发布订阅消息失败: {e}")
    
    async def _process_status_queue(self):
        """处理状态队列（防丢失）"""
        while self.running:
            try:
                message = await self.redis.brpop("task_status_queue", timeout=5)
                if message:
                    event = json.loads(message[1])
                    await self._handle_status_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理状态队列失败: {e}")
    
    async def _handle_status_event(self, event: Dict[str, Any]):
        """处理任务状态事件"""
        task_request_id = event["task_request_id"]
        status = event["status"]
        data = event["data"]
        
        # 调用数据库服务更新任务状态
        await update_task_status(
            task_request_id=task_request_id,
            status=status,
            result_data=data,
            updated_at=datetime.now()
        )
```

### 2.2 状态事件格式

Worker 发布的状态事件格式：

```json
{
    "task_request_id": "psi-abc123",
    "status": "RUNNING|SUCCESS|FAILURE|RETRY",
    "timestamp": "2026-01-07T00:00:00.000000Z",
    "data": {
        "started_at": "timestamp",
        "result": {},
        "error": "error_message"
    },
    "worker_container": "secretflow-worker",
    "task_name": "tasks.secretflow.execute_task"
}
```

### 2.3 应用启动时集成监听器

**推荐实现位置**：`web/src/core/init_app.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

# 全局监听器实例
task_status_listener = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global task_status_listener
    
    # 启动时
    task_status_listener = TaskStatusListener(settings.redis_url)
    asyncio.create_task(task_status_listener.start_listening())
    logger.info("任务状态监听器已启动")
    
    yield
    
    # 关闭时
    if task_status_listener:
        await task_status_listener.stop_listening()
        logger.info("任务状态监听器已关闭")

# 创建 FastAPI 应用
app = FastAPI(lifespan=lifespan)
```

## 三、任务结果获取对接

### 3.1 轮询方式获取结果

```python
from celery.result import AsyncResult

async def get_task_result(task_id: str, timeout: int = 300):
    """获取任务结果"""
    result = AsyncResult(task_id, app=celery_app)
    
    # 等待任务完成
    celery_response = result.get(timeout=timeout)
    
    # 提取任务输出数据
    task_output = celery_response["result"]["result"]["result"]
    
    return {
        "status": celery_response["status"],
        "result": task_output,
        "performance": celery_response["result"]["result"]["performance_metrics"]
    }
```

### 3.2 结果提取路径

Celery 完整响应结构：

```python
celery_response["result"]["result"]["result"]  # 任务的具体输出数据
celery_response["result"]["result"]["performance_metrics"]  # 性能指标
celery_response["result"]["result"]["task_metadata"]  # 任务元数据
```

详见：`docs/worker-api/00.worker-api.md` 返回结果章节

## 四、任务链对接（可选）

### 4.1 任务链在 Web 端实现

基于 `docs/chain.md` 的设计，任务链编排在 Web 端实现，使用 Celery 的任务编排原语。

**推荐实现位置**：`web/src/services/task_chain_service.py`

```python
from celery import chain, group, chord

class TaskChainService:
    """任务链编排服务"""
    
    def create_ml_workflow(
        self,
        preprocess_params,
        train_params,
        eval_params
    ):
        """创建机器学习工作流"""
        
        # 1. 数据预处理任务
        preprocess_task = self.celery_app.signature(
            "tasks.secretflow.execute_task",
            args=["preprocess-001", preprocess_params],
            queue="secretflow_queue"
        )
        
        # 2. 模型训练任务
        train_task = self.celery_app.signature(
            "tasks.secretflow.execute_task",
            args=["train-001", train_params],
            queue="secretflow_queue"
        )
        
        # 3. 模型评估任务
        eval_task = self.celery_app.signature(
            "tasks.secretflow.execute_task",
            args=["eval-001", eval_params],
            queue="secretflow_queue"
        )
        
        # 创建任务链：预处理 → 训练 → 评估
        workflow = chain(preprocess_task, train_task, eval_task)
        
        # 执行任务链
        result = workflow.apply_async()
        
        return result.id
```

### 4.2 并行任务支持

```python
def create_parallel_psi_workflow(self, psi_tasks_params):
    """创建并行 PSI 任务"""
    
    # 创建多个并行 PSI 任务
    psi_tasks = [
        self.celery_app.signature(
            "tasks.secretflow.execute_task",
            args=[f"psi-{i}", params],
            queue="secretflow_queue"
        )
        for i, params in enumerate(psi_tasks_params)
    ]
    
    # 并行执行
    job = group(psi_tasks)
    result = job.apply_async()
    
    return result.id
```

## 五、数据库设计建议

### 5.1 任务记录表

```sql
CREATE TABLE secretflow_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(100) UNIQUE NOT NULL,  -- Celery 任务 ID
    task_request_id VARCHAR(100),           -- 业务任务 ID
    task_type VARCHAR(50) NOT NULL,         -- 任务类型（psi, ss_lr等）
    status VARCHAR(20) NOT NULL,            -- 任务状态
    params JSONB,                           -- 任务参数
    result JSONB,                           -- 任务结果
    error_message TEXT,                     -- 错误信息
    performance_metrics JSONB,              -- 性能指标
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_task_id ON secretflow_tasks(task_id);
CREATE INDEX idx_status ON secretflow_tasks(status);
CREATE INDEX idx_created_at ON secretflow_tasks(created_at);
```

### 5.2 任务状态日志表

```sql
CREATE TABLE task_status_logs (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_task_log_task_id ON task_status_logs(task_id);
```

## 六、环境配置对接

### 6.1 Docker Compose 配置

确保 Web 容器和 Worker 容器使用相同的 Redis 实例：

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  web:
    build: ./web
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0
      - ENABLE_TASK_STATUS_LISTENER=true
  
  secretflow-worker:
    build: ./worker
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0
      - WORKER_CONTAINER_ID=secretflow-worker
```

### 6.2 环境变量对齐

**Web 容器需要的环境变量**：

```bash
# Redis 配置（与 Worker 相同）
REDIS_URL=redis://redis:6379/0

# 任务状态监听配置
ENABLE_TASK_STATUS_LISTENER=true
TASK_STATUS_CHANNEL=task_status_events
TASK_STATUS_QUEUE=task_status_queue

# Celery 配置
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

## 七、错误处理对接

### 7.1 捕获 Worker 返回的错误

```python
async def handle_task_result(task_id: str):
    """处理任务结果，包含错误处理"""
    try:
        result = AsyncResult(task_id, app=celery_app)
        celery_response = result.get(timeout=300)
        
        # 检查任务状态
        if celery_response["status"] == "SUCCESS":
            task_result = celery_response["result"]["result"]
            
            if task_result["status"] == "success":
                # 任务成功
                return {"success": True, "data": task_result["result"]}
            else:
                # 任务执行失败
                return {
                    "success": False,
                    "error": task_result.get("error", "Unknown error")
                }
        else:
            # Celery 任务失败
            return {
                "success": False,
                "error": celery_response.get("traceback", "Task failed")
            }
    
    except TimeoutError:
        return {"success": False, "error": "任务执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### 7.2 任务重试策略

Web 端可以实现自动重试逻辑：

```python
async def submit_task_with_retry(
    task_params,
    max_retries: int = 3,
    retry_delay: int = 60
):
    """带重试的任务提交"""
    for attempt in range(max_retries):
        try:
            task_id = await submit_task(task_params)
            result = await wait_for_task(task_id)
            
            if result["success"]:
                return result
            
            # 任务失败，检查是否需要重试
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            else:
                return result
        
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            else:
                raise
```

## 八、测试和验证

### 8.1 集成测试

```python
async def test_psi_task_integration():
    """测试 PSI 任务端到端流程"""
    
    # 1. 提交任务
    task_id = await submit_psi_task({...})
    assert task_id is not None
    
    # 2. 等待任务完成
    await asyncio.sleep(10)
    
    # 3. 查询任务状态（从数据库）
    task = await get_task_from_db(task_id)
    assert task.status == "SUCCESS"
    
    # 4. 验证结果
    result = task.result
    assert result["intersection_count"] > 0
    assert "output_paths" in result
```

### 8.2 监听器测试

```python
async def test_status_listener():
    """测试状态监听器"""
    
    # 模拟 Worker 发布状态事件
    await redis.publish("task_status_events", json.dumps({
        "task_request_id": "test-001",
        "status": "SUCCESS",
        "data": {"result": {...}}
    }))
    
    # 等待监听器处理
    await asyncio.sleep(1)
    
    # 验证数据库已更新
    task = await get_task_from_db("test-001")
    assert task.status == "SUCCESS"
```

## 九、性能优化建议

### 9.1 连接池管理

```python
# Redis 连接池
redis_pool = aioredis.ConnectionPool.from_url(
    redis_url,
    max_connections=10,
    decode_responses=True
)

# Celery 应用配置
celery_app.conf.update(
    broker_pool_limit=10,
    broker_connection_retry_on_startup=True
)
```

### 9.2 异步任务提交

使用异步方式提交任务，避免阻塞：

```python
async def submit_task_async(task_params):
    """异步提交任务"""
    result = await asyncio.to_thread(
        celery_app.send_task,
        "tasks.secretflow.execute_task",
        args=[task_id, task_params],
        queue="secretflow_queue"
    )
    return result.id
```

## 十、检查清单

### Web 端需要实现的功能

- [ ] **任务提交服务**
  - [ ] 构建符合 Worker API 规范的任务参数
  - [ ] 通过 Celery 发送任务到 Worker
  - [ ] 保存任务记录到数据库

- [ ] **任务状态监听**
  - [ ] 实现 TaskStatusListener 服务
  - [ ] 监听 Redis 发布订阅频道
  - [ ] 处理状态队列消息
  - [ ] 更新数据库任务状态

- [ ] **任务结果获取**
  - [ ] 通过 Celery AsyncResult 获取结果
  - [ ] 正确提取任务输出数据
  - [ ] 保存结果到数据库

- [ ] **FastAPI 接口**
  - [ ] 任务提交接口
  - [ ] 任务状态查询接口
  - [ ] 任务结果查询接口
  - [ ] 任务取消接口（可选）

- [ ] **数据库设计**
  - [ ] 任务记录表
  - [ ] 任务状态日志表
  - [ ] 索引优化

- [ ] **错误处理**
  - [ ] 任务失败重试逻辑
  - [ ] 超时处理
  - [ ] 错误日志记录

- [ ] **配置管理**
  - [ ] 环境变量配置
  - [ ] Redis 连接配置
  - [ ] Celery 应用配置

## 总结

Web 容器与 Worker 容器的对接关键点：

1. **任务提交**：构建符合 Worker API 规范的参数，通过 Celery 发送
2. **状态监听**：实现 Redis 发布订阅监听，实时更新任务状态
3. **结果获取**：通过 Celery AsyncResult 或数据库查询获取结果
4. **职责分离**：Web 负责业务编排，Worker 负责计算执行
5. **配置对齐**：确保两个容器使用相同的 Redis 和消息格式

参考文档：
- [Worker API 文档](worker-api/00.worker-api.md) - 完整的任务参数规范
- [任务状态监听设计](04.task_status_listener.md) - 状态同步机制详细设计
- [任务链设计](chain.md) - 任务编排方案（Web 端实现）
