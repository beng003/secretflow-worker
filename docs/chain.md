# 任务链（Task Chain）功能设计方案

## 一、架构决策

### 1.1 设计位置选择：**Web端（FastAPI + Celery）**

#### 决策依据

**✅ 在Web端设计的理由：**

1. **职责分离原则**
   - Worker端专注于**纯计算任务**执行
   - Web端负责**业务编排和调度逻辑**
   - 任务链属于业务编排，应在Web端实现

2. **Celery原生支持**
   - Celery提供完善的任务编排原语（chain, group, chord, chunks）
   - Web端的Celery应用可直接使用这些功能
   - 无需重复造轮子

3. **状态管理便利**
   - Web端可访问数据库，便于持久化任务链状态
   - 可实现任务链的可视化监控和管理
   - 便于实现任务链的暂停、恢复、取消等操作

4. **API集成自然**
   - FastAPI直接暴露任务链提交接口
   - 统一的错误处理和响应格式
   - 便于前端集成和调用

**❌ 不在Worker端设计的理由：**

1. Worker端不应包含业务逻辑和编排逻辑
2. Worker端不应直接访问数据库（已在文档中明确）
3. Worker端专注于SecretFlow计算任务，保持单一职责
4. 任务链涉及多任务协调，不适合在单个Worker中实现

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web容器 (FastAPI + Celery)               │
│                                                                  │
│  ┌────────────────┐         ┌─────────────────────────────┐    │
│  │  FastAPI接口   │ ──────→ │  任务链编排服务              │    │
│  │  /api/v1/chain │         │  TaskChainService            │    │
│  └────────────────┘         └─────────────────────────────┘    │
│                                        │                         │
│                                        ▼                         │
│                             ┌──────────────────────┐            │
│                             │  Celery任务编排      │            │
│                             │  - chain()           │            │
│                             │  - group()           │            │
│                             │  - chord()           │            │
│                             └──────────────────────┘            │
│                                        │                         │
│                                        ▼                         │
│                             ┌──────────────────────┐            │
│                             │  Redis消息队列       │            │
│                             └──────────────────────┘            │
│                                        │                         │
└────────────────────────────────────────┼─────────────────────────┘
                                         │
                                         │ 任务分发
                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Worker容器 (SecretFlow Worker)               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Celery Worker                                            │  │
│  │  - 接收任务                                                │  │
│  │  - 执行SecretFlow计算                                      │  │
│  │  - 发布状态到Redis                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                        │                         │
└────────────────────────────────────────┼─────────────────────────┘
                                         │
                                         │ 状态通知
                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Web容器 (状态监听)                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  TaskStatusListener                                       │  │
│  │  - 监听任务状态变更                                         │  │
│  │  - 更新数据库                                              │  │
│  │  - 触发任务链下一步（如需要）                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### Web端组件

| 组件名称 | 职责 | 位置 |
|---------|------|------|
| `TaskChainAPI` | 接收任务链提交请求 | `src/api/v1/task_chain.py` |
| `TaskChainService` | 任务链编排和管理 | `src/services/task_chain_service.py` |
| `TaskChainRepository` | 任务链数据持久化 | `src/repositories/task_chain_repository.py` |
| `ChainExecutor` | Celery任务链执行器 | `src/executors/chain_executor.py` |
| `ChainStatusMonitor` | 任务链状态监控 | `src/monitors/chain_status_monitor.py` |

#### Worker端组件

| 组件名称 | 职责 | 位置 |
|---------|------|------|
| `SecretFlowTask` | 执行单个SecretFlow任务 | `src/secretflow_task/celery_tasks.py` |
| `StatusNotifier` | 发布任务状态到Redis | `src/utils/status_notifier.py` |

---

## 三、任务链类型设计

### 3.1 Celery任务编排原语

#### 3.1.1 Chain（顺序链）

**适用场景**：任务必须**顺序执行**，后续任务依赖前置任务的结果

```python
from celery import chain

# 示例：PSI -> 数据分析 -> 结果加密
task_chain = chain(
    execute_psi.s(task_request_id_1, psi_params),
    analyze_data.s(task_request_id_2, analysis_params),
    encrypt_result.s(task_request_id_3, encrypt_params)
)
result = task_chain.apply_async()
```

**特点**：
- 串行执行，顺序严格
- 前一个任务的输出作为后一个任务的输入
- 任何一步失败，整个链终止

#### 3.1.2 Group（并行组）

**适用场景**：多个任务可以**并行执行**，互不依赖

```python
from celery import group

# 示例：同时对多方数据进行预处理
parallel_tasks = group(
    preprocess_alice_data.s(task_request_id_1, alice_params),
    preprocess_bob_data.s(task_request_id_2, bob_params),
    preprocess_carol_data.s(task_request_id_3, carol_params)
)
result = parallel_tasks.apply_async()
```

**特点**：
- 并行执行，提高效率
- 所有任务独立运行
- 返回所有任务的结果列表

#### 3.1.3 Chord（先并行后汇总）

**适用场景**：先并行执行多个任务，然后将所有结果汇总到一个回调任务

```python
from celery import chord

# 示例：多方数据验证 -> 汇总验证报告
validation_chord = chord(
    [
        validate_alice_data.s(task_request_id_1, alice_params),
        validate_bob_data.s(task_request_id_2, bob_params),
        validate_carol_data.s(task_request_id_3, carol_params)
    ]
)(generate_validation_report.s(task_request_id_4, report_params))

result = validation_chord.apply_async()
```

**特点**：
- 前置任务并行执行
- 回调任务等待所有前置任务完成
- 回调任务接收所有前置任务的结果

#### 3.1.4 复合编排（Chain + Group + Chord）

**适用场景**：复杂的任务依赖关系

```python
from celery import chain, group, chord

# 示例：数据准备 -> 并行训练 -> 模型融合 -> 结果验证
complex_workflow = chain(
    # 步骤1：数据准备
    prepare_data.s(task_request_id_1, prepare_params),
    
    # 步骤2：并行训练多个模型
    chord([
        train_model_a.s(task_request_id_2, model_a_params),
        train_model_b.s(task_request_id_3, model_b_params),
        train_model_c.s(task_request_id_4, model_c_params)
    ])(
        # 步骤3：模型融合
        merge_models.s(task_request_id_5, merge_params)
    ),
    
    # 步骤4：结果验证
    validate_result.s(task_request_id_6, validate_params)
)

result = complex_workflow.apply_async()
```

### 3.2 任务链配置数据结构

```json
{
  "chain_id": "chain-uuid-001",
  "chain_name": "联邦学习训练流程",
  "chain_type": "complex",
  "created_by": "user-001",
  "description": "数据准备 -> 并行训练 -> 模型聚合 -> 验证",
  
  "tasks": [
    {
      "task_id": "task-001",
      "task_name": "数据预处理",
      "task_type": "psi",
      "execution_mode": "sequential",
      "depends_on": [],
      "task_params": {
        "sf_init_config": {...},
        "spu_config": {...},
        "task_config": {...}
      }
    },
    {
      "task_id": "task-002",
      "task_name": "模型训练-Alice",
      "task_type": "train",
      "execution_mode": "parallel",
      "depends_on": ["task-001"],
      "task_params": {...}
    },
    {
      "task_id": "task-003",
      "task_name": "模型训练-Bob",
      "task_type": "train",
      "execution_mode": "parallel",
      "depends_on": ["task-001"],
      "task_params": {...}
    },
    {
      "task_id": "task-004",
      "task_name": "模型聚合",
      "task_type": "aggregate",
      "execution_mode": "sequential",
      "depends_on": ["task-002", "task-003"],
      "callback_for": ["task-002", "task-003"],
      "task_params": {...}
    }
  ],
  
  "options": {
    "retry_policy": {
      "max_retries": 3,
      "retry_on_failure": true
    },
    "timeout": 7200,
    "priority": "high",
    "stop_on_error": true
  }
}
```

---

## 四、数据模型设计

### 4.1 任务链表（task_chains）

```sql
CREATE TABLE task_chains (
    id BIGSERIAL PRIMARY KEY,
    chain_id VARCHAR(64) UNIQUE NOT NULL,
    chain_name VARCHAR(255) NOT NULL,
    chain_type VARCHAR(50) NOT NULL,  -- 'sequential', 'parallel', 'chord', 'complex'
    description TEXT,
    
    -- 任务配置
    chain_config JSONB NOT NULL,  -- 完整的任务链配置
    
    -- 状态信息
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',  -- PENDING, RUNNING, SUCCESS, FAILURE, CANCELLED
    celery_chain_id VARCHAR(255),  -- Celery任务链ID
    
    -- 执行统计
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    
    -- 时间信息
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 用户信息
    created_by VARCHAR(64),
    
    -- 元数据
    metadata JSONB,
    
    -- 索引
    INDEX idx_chain_id (chain_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_created_by (created_by)
);
```

### 4.2 任务链节点表（chain_tasks）

```sql
CREATE TABLE chain_tasks (
    id BIGSERIAL PRIMARY KEY,
    chain_id VARCHAR(64) NOT NULL,
    task_id VARCHAR(64) NOT NULL,
    task_request_id VARCHAR(64) UNIQUE NOT NULL,  -- 对应task_requests表
    
    -- 任务信息
    task_name VARCHAR(255) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    execution_mode VARCHAR(50),  -- 'sequential', 'parallel'
    
    -- 依赖关系
    depends_on JSONB,  -- 依赖的task_id数组
    is_callback BOOLEAN DEFAULT FALSE,
    
    -- 执行信息
    celery_task_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    
    -- 顺序和优先级
    execution_order INTEGER,
    priority INTEGER DEFAULT 5,
    
    -- 时间信息
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 结果和错误
    result JSONB,
    error JSONB,
    
    -- 外键
    FOREIGN KEY (chain_id) REFERENCES task_chains(chain_id) ON DELETE CASCADE,
    FOREIGN KEY (task_request_id) REFERENCES task_requests(task_request_id) ON DELETE CASCADE,
    
    -- 索引
    INDEX idx_chain_id (chain_id),
    INDEX idx_task_request_id (task_request_id),
    INDEX idx_status (status),
    INDEX idx_execution_order (execution_order)
);
```

### 4.3 任务链依赖关系表（chain_dependencies）

```sql
CREATE TABLE chain_dependencies (
    id BIGSERIAL PRIMARY KEY,
    chain_id VARCHAR(64) NOT NULL,
    from_task_id VARCHAR(64) NOT NULL,  -- 被依赖的任务
    to_task_id VARCHAR(64) NOT NULL,    -- 依赖方任务
    
    dependency_type VARCHAR(50) DEFAULT 'sequential',  -- 'sequential', 'data', 'condition'
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键
    FOREIGN KEY (chain_id) REFERENCES task_chains(chain_id) ON DELETE CASCADE,
    
    -- 唯一约束
    UNIQUE(chain_id, from_task_id, to_task_id),
    
    -- 索引
    INDEX idx_chain_id (chain_id),
    INDEX idx_from_task (from_task_id),
    INDEX idx_to_task (to_task_id)
);
```

---

## 五、核心实现

### 5.1 任务链服务（TaskChainService）

```python
"""
任务链服务
位置: src/services/task_chain_service.py
"""

from typing import Dict, Any, List, Optional
from celery import chain, group, chord
from datetime import datetime
import uuid

from repositories.task_chain_repository import TaskChainRepository
from repositories.task_request_repository import TaskRequestRepository
from executors.chain_executor import ChainExecutor
from utils.log import logger


class TaskChainService:
    """任务链管理服务"""
    
    def __init__(self):
        self.chain_repo = TaskChainRepository()
        self.task_request_repo = TaskRequestRepository()
        self.chain_executor = ChainExecutor()
    
    async def create_chain(
        self,
        chain_name: str,
        chain_config: Dict[str, Any],
        created_by: str = None,
        description: str = None
    ) -> Dict[str, Any]:
        """创建任务链
        
        Args:
            chain_name: 任务链名称
            chain_config: 任务链配置（包含tasks数组和options）
            created_by: 创建者
            description: 描述
            
        Returns:
            Dict[str, Any]: 创建的任务链信息
        """
        # 1. 生成chain_id
        chain_id = f"chain-{uuid.uuid4()}"
        
        # 2. 解析任务链类型
        chain_type = self._detect_chain_type(chain_config)
        
        # 3. 验证任务链配置
        self._validate_chain_config(chain_config)
        
        # 4. 为每个任务创建task_request
        tasks = chain_config.get('tasks', [])
        total_tasks = len(tasks)
        
        task_request_ids = []
        for task in tasks:
            task_request_id = await self._create_task_request(
                chain_id=chain_id,
                task_config=task
            )
            task_request_ids.append(task_request_id)
            task['task_request_id'] = task_request_id
        
        # 5. 保存任务链到数据库
        chain_data = {
            'chain_id': chain_id,
            'chain_name': chain_name,
            'chain_type': chain_type,
            'description': description,
            'chain_config': chain_config,
            'status': 'PENDING',
            'total_tasks': total_tasks,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'created_by': created_by,
            'metadata': {
                'task_request_ids': task_request_ids
            }
        }
        
        await self.chain_repo.create(chain_data)
        
        logger.info(f"任务链创建成功: chain_id={chain_id}, tasks={total_tasks}")
        
        return {
            'chain_id': chain_id,
            'chain_name': chain_name,
            'chain_type': chain_type,
            'total_tasks': total_tasks,
            'status': 'PENDING',
            'created_at': datetime.now().isoformat()
        }
    
    async def execute_chain(self, chain_id: str) -> Dict[str, Any]:
        """执行任务链
        
        Args:
            chain_id: 任务链ID
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        # 1. 获取任务链配置
        chain = await self.chain_repo.get_by_chain_id(chain_id)
        if not chain:
            raise ValueError(f"任务链不存在: {chain_id}")
        
        if chain['status'] != 'PENDING':
            raise ValueError(f"任务链状态不允许执行: {chain['status']}")
        
        chain_config = chain['chain_config']
        chain_type = chain['chain_type']
        
        # 2. 构建Celery任务链
        celery_chain = self.chain_executor.build_celery_chain(
            chain_type=chain_type,
            chain_config=chain_config
        )
        
        # 3. 提交任务链执行
        async_result = celery_chain.apply_async()
        celery_chain_id = async_result.id
        
        # 4. 更新任务链状态
        await self.chain_repo.update(chain_id, {
            'status': 'RUNNING',
            'celery_chain_id': celery_chain_id,
            'started_at': datetime.now()
        })
        
        logger.info(
            f"任务链开始执行: chain_id={chain_id}, "
            f"celery_chain_id={celery_chain_id}"
        )
        
        return {
            'chain_id': chain_id,
            'celery_chain_id': celery_chain_id,
            'status': 'RUNNING',
            'started_at': datetime.now().isoformat()
        }
    
    async def get_chain_status(self, chain_id: str) -> Dict[str, Any]:
        """获取任务链状态
        
        Args:
            chain_id: 任务链ID
            
        Returns:
            Dict[str, Any]: 任务链状态信息
        """
        chain = await self.chain_repo.get_by_chain_id(chain_id)
        if not chain:
            raise ValueError(f"任务链不存在: {chain_id}")
        
        # 获取所有子任务状态
        chain_tasks = await self.chain_repo.get_chain_tasks(chain_id)
        
        return {
            'chain_id': chain_id,
            'chain_name': chain['chain_name'],
            'status': chain['status'],
            'total_tasks': chain['total_tasks'],
            'completed_tasks': chain['completed_tasks'],
            'failed_tasks': chain['failed_tasks'],
            'progress': (chain['completed_tasks'] / chain['total_tasks'] * 100) 
                        if chain['total_tasks'] > 0 else 0,
            'tasks': chain_tasks,
            'started_at': chain.get('started_at'),
            'completed_at': chain.get('completed_at')
        }
    
    async def cancel_chain(self, chain_id: str) -> Dict[str, Any]:
        """取消任务链
        
        Args:
            chain_id: 任务链ID
            
        Returns:
            Dict[str, Any]: 取消结果
        """
        chain = await self.chain_repo.get_by_chain_id(chain_id)
        if not chain:
            raise ValueError(f"任务链不存在: {chain_id}")
        
        if chain['status'] in ['SUCCESS', 'FAILURE', 'CANCELLED']:
            raise ValueError(f"任务链已结束，无法取消: {chain['status']}")
        
        # 撤销Celery任务链
        celery_chain_id = chain.get('celery_chain_id')
        if celery_chain_id:
            from celery.result import AsyncResult
            from celery_app import celery_app
            
            async_result = AsyncResult(celery_chain_id, app=celery_app)
            async_result.revoke(terminate=True, signal='SIGKILL')
        
        # 更新状态
        await self.chain_repo.update(chain_id, {
            'status': 'CANCELLED',
            'completed_at': datetime.now()
        })
        
        logger.info(f"任务链已取消: chain_id={chain_id}")
        
        return {
            'chain_id': chain_id,
            'status': 'CANCELLED',
            'cancelled_at': datetime.now().isoformat()
        }
    
    def _detect_chain_type(self, chain_config: Dict[str, Any]) -> str:
        """检测任务链类型"""
        tasks = chain_config.get('tasks', [])
        
        # 检查是否有并行任务
        has_parallel = any(
            task.get('execution_mode') == 'parallel' 
            for task in tasks
        )
        
        # 检查是否有回调任务
        has_callback = any(
            task.get('is_callback', False) 
            for task in tasks
        )
        
        if has_parallel and has_callback:
            return 'complex'  # 复合编排
        elif has_callback:
            return 'chord'    # 先并行后汇总
        elif has_parallel:
            return 'parallel' # 纯并行
        else:
            return 'sequential'  # 纯顺序
    
    def _validate_chain_config(self, chain_config: Dict[str, Any]) -> None:
        """验证任务链配置"""
        tasks = chain_config.get('tasks')
        if not tasks or len(tasks) == 0:
            raise ValueError("任务链至少需要一个任务")
        
        # 验证依赖关系
        task_ids = {task['task_id'] for task in tasks}
        for task in tasks:
            depends_on = task.get('depends_on', [])
            for dep_id in depends_on:
                if dep_id not in task_ids:
                    raise ValueError(
                        f"任务 {task['task_id']} 依赖的任务 {dep_id} 不存在"
                    )
        
        # 检测循环依赖
        if self._has_circular_dependency(tasks):
            raise ValueError("任务链存在循环依赖")
    
    def _has_circular_dependency(self, tasks: List[Dict]) -> bool:
        """检测循环依赖（使用拓扑排序）"""
        from collections import defaultdict, deque
        
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        # 构建依赖图
        for task in tasks:
            task_id = task['task_id']
            depends_on = task.get('depends_on', [])
            
            for dep_id in depends_on:
                graph[dep_id].append(task_id)
                in_degree[task_id] += 1
        
        # 拓扑排序
        queue = deque([
            task['task_id'] 
            for task in tasks 
            if in_degree[task['task_id']] == 0
        ])
        
        sorted_count = 0
        while queue:
            node = queue.popleft()
            sorted_count += 1
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 如果排序数量少于任务数量，说明有循环依赖
        return sorted_count < len(tasks)
    
    async def _create_task_request(
        self, 
        chain_id: str, 
        task_config: Dict[str, Any]
    ) -> str:
        """为任务链中的单个任务创建task_request记录"""
        task_request_id = f"task-{uuid.uuid4()}"
        
        task_request_data = {
            'task_request_id': task_request_id,
            'task_type': task_config['task_type'],
            'task_name': task_config['task_name'],
            'status': 'PENDING',
            'params': task_config.get('task_params', {}),
            'metadata': {
                'chain_id': chain_id,
                'task_id': task_config['task_id'],
                'execution_mode': task_config.get('execution_mode'),
                'depends_on': task_config.get('depends_on', [])
            }
        }
        
        await self.task_request_repo.create(task_request_data)
        
        return task_request_id
```

### 5.2 任务链执行器（ChainExecutor）

```python
"""
Celery任务链执行器
位置: src/executors/chain_executor.py
"""

from typing import Dict, Any, List
from celery import chain, group, chord

from secretflow_task.celery_tasks import execute_secretflow_celery_task
from utils.log import logger


class ChainExecutor:
    """Celery任务链构建和执行器"""
    
    def build_celery_chain(
        self,
        chain_type: str,
        chain_config: Dict[str, Any]
    ):
        """构建Celery任务链
        
        Args:
            chain_type: 任务链类型
            chain_config: 任务链配置
            
        Returns:
            Celery chain/group/chord对象
        """
        tasks = chain_config['tasks']
        
        if chain_type == 'sequential':
            return self._build_sequential_chain(tasks)
        elif chain_type == 'parallel':
            return self._build_parallel_group(tasks)
        elif chain_type == 'chord':
            return self._build_chord_chain(tasks)
        elif chain_type == 'complex':
            return self._build_complex_chain(tasks)
        else:
            raise ValueError(f"不支持的任务链类型: {chain_type}")
    
    def _build_sequential_chain(self, tasks: List[Dict]) -> chain:
        """构建顺序任务链"""
        celery_tasks = []
        
        for task in tasks:
            task_request_id = task['task_request_id']
            task_params = task['task_params']
            
            # 使用.s()创建任务签名（signature）
            task_sig = execute_secretflow_celery_task.s(
                task_request_id,
                task_params
            )
            celery_tasks.append(task_sig)
        
        # 创建任务链
        return chain(*celery_tasks)
    
    def _build_parallel_group(self, tasks: List[Dict]) -> group:
        """构建并行任务组"""
        celery_tasks = []
        
        for task in tasks:
            task_request_id = task['task_request_id']
            task_params = task['task_params']
            
            task_sig = execute_secretflow_celery_task.s(
                task_request_id,
                task_params
            )
            celery_tasks.append(task_sig)
        
        # 创建并行组
        return group(*celery_tasks)
    
    def _build_chord_chain(self, tasks: List[Dict]) -> chord:
        """构建chord任务链（并行+回调）"""
        # 分离并行任务和回调任务
        parallel_tasks = [t for t in tasks if not t.get('is_callback', False)]
        callback_tasks = [t for t in tasks if t.get('is_callback', False)]
        
        if len(callback_tasks) != 1:
            raise ValueError("Chord模式需要恰好一个回调任务")
        
        # 构建并行任务组
        parallel_sigs = []
        for task in parallel_tasks:
            task_sig = execute_secretflow_celery_task.s(
                task['task_request_id'],
                task['task_params']
            )
            parallel_sigs.append(task_sig)
        
        # 构建回调任务
        callback_task = callback_tasks[0]
        callback_sig = execute_secretflow_celery_task.s(
            callback_task['task_request_id'],
            callback_task['task_params']
        )
        
        # 创建chord
        return chord(parallel_sigs)(callback_sig)
    
    def _build_complex_chain(self, tasks: List[Dict]):
        """构建复杂任务链（组合chain/group/chord）"""
        # 按依赖关系分组任务
        task_groups = self._group_tasks_by_dependency(tasks)
        
        # 构建复合任务链
        chain_elements = []
        
        for group_tasks in task_groups:
            # 检查该组是否有并行任务
            if len(group_tasks) > 1:
                # 并行执行
                group_sigs = []
                for task in group_tasks:
                    task_sig = execute_secretflow_celery_task.s(
                        task['task_request_id'],
                        task['task_params']
                    )
                    group_sigs.append(task_sig)
                chain_elements.append(group(*group_sigs))
            else:
                # 单个任务
                task = group_tasks[0]
                task_sig = execute_secretflow_celery_task.s(
                    task['task_request_id'],
                    task['task_params']
                )
                chain_elements.append(task_sig)
        
        # 创建整体任务链
        return chain(*chain_elements)
    
    def _group_tasks_by_dependency(
        self, 
        tasks: List[Dict]
    ) -> List[List[Dict]]:
        """按依赖关系对任务分组（拓扑排序）"""
        from collections import defaultdict, deque
        
        # 构建依赖图
        graph = defaultdict(list)
        in_degree = {task['task_id']: 0 for task in tasks}
        task_map = {task['task_id']: task for task in tasks}
        
        for task in tasks:
            task_id = task['task_id']
            depends_on = task.get('depends_on', [])
            
            for dep_id in depends_on:
                graph[dep_id].append(task_id)
                in_degree[task_id] += 1
        
        # 拓扑排序并分组
        task_groups = []
        current_level = deque([
            task_id 
            for task_id, degree in in_degree.items() 
            if degree == 0
        ])
        
        while current_level:
            # 当前层级的所有任务（可并行）
            level_tasks = [task_map[task_id] for task_id in current_level]
            task_groups.append(level_tasks)
            
            # 准备下一层级
            next_level = set()
            for task_id in current_level:
                for neighbor in graph[task_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_level.add(neighbor)
            
            current_level = deque(sorted(next_level))
        
        return task_groups
```

### 5.3 FastAPI接口

```python
"""
任务链API接口
位置: src/api/v1/task_chain.py
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from services.task_chain_service import TaskChainService


router = APIRouter(prefix="/api/v1/chains", tags=["任务链"])


class TaskConfig(BaseModel):
    """单个任务配置"""
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    task_type: str = Field(..., description="任务类型（psi/train等）")
    execution_mode: str = Field("sequential", description="执行模式（sequential/parallel）")
    depends_on: List[str] = Field(default_factory=list, description="依赖的任务ID列表")
    is_callback: bool = Field(False, description="是否为回调任务")
    task_params: Dict[str, Any] = Field(..., description="任务参数")


class ChainOptions(BaseModel):
    """任务链选项"""
    retry_policy: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = Field(7200, description="超时时间（秒）")
    priority: Optional[str] = Field("normal", description="优先级")
    stop_on_error: bool = Field(True, description="遇到错误时停止")


class CreateChainRequest(BaseModel):
    """创建任务链请求"""
    chain_name: str = Field(..., description="任务链名称")
    description: Optional[str] = Field(None, description="描述")
    tasks: List[TaskConfig] = Field(..., min_items=1, description="任务列表")
    options: Optional[ChainOptions] = Field(default_factory=ChainOptions)


class CreateChainResponse(BaseModel):
    """创建任务链响应"""
    chain_id: str
    chain_name: str
    chain_type: str
    total_tasks: int
    status: str
    created_at: str


class ExecuteChainResponse(BaseModel):
    """执行任务链响应"""
    chain_id: str
    celery_chain_id: str
    status: str
    started_at: str


class ChainStatusResponse(BaseModel):
    """任务链状态响应"""
    chain_id: str
    chain_name: str
    status: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    progress: float
    tasks: List[Dict[str, Any]]
    started_at: Optional[str]
    completed_at: Optional[str]


@router.post("/", response_model=CreateChainResponse)
async def create_chain(
    request: CreateChainRequest,
    chain_service: TaskChainService = Depends()
):
    """创建任务链
    
    支持的任务链类型：
    - 顺序链（Sequential Chain）：任务按顺序执行
    - 并行组（Parallel Group）：任务并行执行
    - Chord链：先并行执行，再汇总
    - 复合链（Complex Chain）：混合编排
    """
    try:
        chain_config = {
            'tasks': [task.dict() for task in request.tasks],
            'options': request.options.dict() if request.options else {}
        }
        
        result = await chain_service.create_chain(
            chain_name=request.chain_name,
            chain_config=chain_config,
            description=request.description
        )
        
        return CreateChainResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建任务链失败: {str(e)}")


@router.post("/{chain_id}/execute", response_model=ExecuteChainResponse)
async def execute_chain(
    chain_id: str,
    chain_service: TaskChainService = Depends()
):
    """执行任务链"""
    try:
        result = await chain_service.execute_chain(chain_id)
        return ExecuteChainResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行任务链失败: {str(e)}")


@router.get("/{chain_id}", response_model=ChainStatusResponse)
async def get_chain_status(
    chain_id: str,
    chain_service: TaskChainService = Depends()
):
    """获取任务链状态"""
    try:
        result = await chain_service.get_chain_status(chain_id)
        return ChainStatusResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务链状态失败: {str(e)}")


@router.delete("/{chain_id}")
async def cancel_chain(
    chain_id: str,
    chain_service: TaskChainService = Depends()
):
    """取消任务链"""
    try:
        result = await chain_service.cancel_chain(chain_id)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务链失败: {str(e)}")


@router.get("/")
async def list_chains(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    chain_service: TaskChainService = Depends()
):
    """查询任务链列表"""
    try:
        result = await chain_service.list_chains(
            status=status,
            page=page,
            page_size=page_size
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务链列表失败: {str(e)}")
```

---

## 六、状态管理与监控

### 6.1 任务链状态监听器

```python
"""
任务链状态监听器扩展
位置: src/services/task_status_listener.py（扩展现有代码）
"""

async def _handle_status_event(self, event: Dict[str, Any]):
    """处理任务状态事件（扩展支持任务链）"""
    try:
        task_request_id = event["task_request_id"]
        status = event["status"]
        data = event["data"]
        
        # 1. 更新任务状态
        await self.task_status_service.update_task_status(
            task_request_id=task_request_id,
            status=status,
            result_data=data,
            updated_at=datetime.now()
        )
        
        # 2. 检查是否属于任务链
        task_request = await self.task_request_repo.get_by_id(task_request_id)
        metadata = task_request.get('metadata', {})
        chain_id = metadata.get('chain_id')
        
        if chain_id:
            # 3. 更新任务链状态
            await self._update_chain_status(chain_id, task_request_id, status)
        
        logger.info(f"任务状态已更新: {task_request_id} -> {status}")
        
    except Exception as e:
        logger.error(f"处理任务状态事件失败: {e}", extra={"event": event})


async def _update_chain_status(
    self,
    chain_id: str,
    task_request_id: str,
    task_status: str
):
    """更新任务链状态
    
    当任务链中的单个任务状态变更时：
    1. 更新chain_tasks表中的任务状态
    2. 统计任务链整体完成情况
    3. 如果所有任务完成，更新任务链状态
    """
    from repositories.task_chain_repository import TaskChainRepository
    
    chain_repo = TaskChainRepository()
    
    # 1. 更新单个任务状态
    await chain_repo.update_chain_task_status(
        task_request_id=task_request_id,
        status=task_status
    )
    
    # 2. 统计任务链状态
    chain_tasks = await chain_repo.get_chain_tasks(chain_id)
    
    total = len(chain_tasks)
    completed = sum(1 for t in chain_tasks if t['status'] == 'SUCCESS')
    failed = sum(1 for t in chain_tasks if t['status'] == 'FAILURE')
    
    # 3. 更新任务链状态
    chain_status = None
    if failed > 0:
        chain_status = 'FAILURE'
    elif completed == total:
        chain_status = 'SUCCESS'
    
    if chain_status:
        await chain_repo.update(chain_id, {
            'status': chain_status,
            'completed_tasks': completed,
            'failed_tasks': failed,
            'completed_at': datetime.now()
        })
        
        logger.info(
            f"任务链状态更新: chain_id={chain_id}, "
            f"status={chain_status}, "
            f"progress={completed}/{total}"
        )
    else:
        # 只更新进度
        await chain_repo.update(chain_id, {
            'completed_tasks': completed,
            'failed_tasks': failed
        })
```

### 6.2 监控指标

| 指标名称 | 说明 | 数据源 |
|---------|------|-------|
| `chain_total_count` | 总任务链数量 | `task_chains` |
| `chain_running_count` | 运行中任务链数量 | `task_chains.status='RUNNING'` |
| `chain_success_rate` | 任务链成功率 | 成功数/总数 |
| `chain_avg_execution_time` | 平均执行时间 | `completed_at - started_at` |
| `chain_task_distribution` | 任务数量分布 | `total_tasks`统计 |
| `chain_failure_reasons` | 失败原因分析 | 聚合失败任务的错误信息 |

---

## 七、使用示例

### 7.1 顺序任务链示例

```json
{
  "chain_name": "PSI数据处理流程",
  "description": "数据预处理 -> PSI求交 -> 结果分析",
  "tasks": [
    {
      "task_id": "task-001",
      "task_name": "数据预处理",
      "task_type": "preprocessing",
      "execution_mode": "sequential",
      "depends_on": [],
      "task_params": {
        "sf_init_config": {...},
        "task_config": {...}
      }
    },
    {
      "task_id": "task-002",
      "task_name": "PSI求交",
      "task_type": "psi",
      "execution_mode": "sequential",
      "depends_on": ["task-001"],
      "task_params": {...}
    },
    {
      "task_id": "task-003",
      "task_name": "结果分析",
      "task_type": "analysis",
      "execution_mode": "sequential",
      "depends_on": ["task-002"],
      "task_params": {...}
    }
  ],
  "options": {
    "timeout": 3600,
    "stop_on_error": true
  }
}
```

### 7.2 并行任务链示例

```json
{
  "chain_name": "多方数据验证",
  "description": "并行验证Alice、Bob、Carol的数据",
  "tasks": [
    {
      "task_id": "task-001",
      "task_name": "验证Alice数据",
      "task_type": "validation",
      "execution_mode": "parallel",
      "depends_on": [],
      "task_params": {...}
    },
    {
      "task_id": "task-002",
      "task_name": "验证Bob数据",
      "task_type": "validation",
      "execution_mode": "parallel",
      "depends_on": [],
      "task_params": {...}
    },
    {
      "task_id": "task-003",
      "task_name": "验证Carol数据",
      "task_type": "validation",
      "execution_mode": "parallel",
      "depends_on": [],
      "task_params": {...}
    }
  ]
}
```

### 7.3 Chord任务链示例

```json
{
  "chain_name": "联邦模型训练",
  "description": "并行训练 -> 模型聚合",
  "tasks": [
    {
      "task_id": "task-001",
      "task_name": "Alice模型训练",
      "task_type": "train",
      "execution_mode": "parallel",
      "depends_on": [],
      "task_params": {...}
    },
    {
      "task_id": "task-002",
      "task_name": "Bob模型训练",
      "task_type": "train",
      "execution_mode": "parallel",
      "depends_on": [],
      "task_params": {...}
    },
    {
      "task_id": "task-003",
      "task_name": "模型聚合",
      "task_type": "aggregate",
      "execution_mode": "sequential",
      "depends_on": ["task-001", "task-002"],
      "is_callback": true,
      "task_params": {...}
    }
  ]
}
```

### 7.4 复杂任务链示例

```json
{
  "chain_name": "端到端隐私计算流程",
  "description": "数据准备 -> 并行训练 -> 模型融合 -> 验证评估",
  "tasks": [
    {
      "task_id": "task-001",
      "task_name": "数据预处理",
      "task_type": "preprocessing",
      "execution_mode": "sequential",
      "depends_on": [],
      "task_params": {...}
    },
    {
      "task_id": "task-002",
      "task_name": "Alice特征工程",
      "task_type": "feature_engineering",
      "execution_mode": "parallel",
      "depends_on": ["task-001"],
      "task_params": {...}
    },
    {
      "task_id": "task-003",
      "task_name": "Bob特征工程",
      "task_type": "feature_engineering",
      "execution_mode": "parallel",
      "depends_on": ["task-001"],
      "task_params": {...}
    },
    {
      "task_id": "task-004",
      "task_name": "联邦模型训练",
      "task_type": "federated_training",
      "execution_mode": "sequential",
      "depends_on": ["task-002", "task-003"],
      "task_params": {...}
    },
    {
      "task_id": "task-005",
      "task_name": "模型评估",
      "task_type": "evaluation",
      "execution_mode": "sequential",
      "depends_on": ["task-004"],
      "task_params": {...}
    }
  ]
}
```

---

## 八、实施计划

### Phase 1: 数据库设计 (1天)

- [ ] 创建 `task_chains` 表
- [ ] 创建 `chain_tasks` 表
- [ ] 创建 `chain_dependencies` 表
- [ ] 编写数据库迁移脚本
- [ ] 添加索引和外键约束

### Phase 2: 核心服务实现 (3天)

- [ ] 实现 `TaskChainRepository`
- [ ] 实现 `ChainExecutor`
- [ ] 实现 `TaskChainService`
- [ ] 编写单元测试

### Phase 3: API接口开发 (2天)

- [ ] 实现任务链创建接口
- [ ] 实现任务链执行接口
- [ ] 实现任务链状态查询接口
- [ ] 实现任务链取消接口
- [ ] 实现任务链列表接口
- [ ] 编写API文档

### Phase 4: 状态监听集成 (2天)

- [ ] 扩展 `TaskStatusListener` 支持任务链
- [ ] 实现任务链状态自动更新
- [ ] 实现任务链完成通知
- [ ] 编写集成测试

### Phase 5: 测试与优化 (2天)

- [ ] 端到端测试（顺序/并行/chord/复杂）
- [ ] 性能测试（大规模任务链）
- [ ] 错误处理测试
- [ ] 并发安全测试
- [ ] 代码优化和重构

### Phase 6: 文档与部署 (1天)

- [ ] 编写用户文档
- [ ] 编写开发文档
- [ ] 准备示例代码
- [ ] 部署到测试环境
- [ ] 验收测试

**预计总工期**: 11个工作日

---

## 九、技术风险与应对

### 9.1 技术风险

| 风险项 | 影响 | 概率 | 应对措施 |
|-------|------|------|---------|
| Celery任务链执行失败 | 高 | 中 | 完善错误处理、重试机制、失败通知 |
| 任务链状态不一致 | 高 | 中 | 事务处理、状态校验、定期同步 |
| 大规模任务链性能瓶颈 | 中 | 低 | 分批处理、异步执行、性能监控 |
| 循环依赖检测失效 | 中 | 低 | 完善拓扑排序算法、增加验证 |
| Redis性能压力 | 中 | 中 | 连接池优化、消息批处理 |

### 9.2 业务风险

| 风险项 | 影响 | 概率 | 应对措施 |
|-------|------|------|---------|
| 任务链设计过于复杂 | 中 | 高 | 提供可视化设计工具、模板 |
| 用户误用导致资源浪费 | 中 | 中 | 添加配额限制、资源监控 |
| 任务链中断难以恢复 | 高 | 低 | 实现断点续传、任务链暂停恢复 |

---

## 十、优化方向

### 10.1 短期优化（3个月内）

1. **可视化设计界面**
   - 拖拽式任务链设计器
   - 实时依赖关系图展示
   - 执行进度可视化

2. **任务链模板**
   - 预定义常用任务链模板
   - 模板市场和分享
   - 参数化模板

3. **智能调度**
   - 基于资源使用情况的动态调度
   - 任务优先级自动调整
   - 负载均衡优化

### 10.2 长期优化（6-12个月）

1. **任务链版本管理**
   - 任务链配置版本控制
   - 回滚到历史版本
   - 差异对比

2. **条件分支支持**
   - 基于任务结果的条件跳转
   - 动态任务生成
   - 循环执行支持

3. **跨集群任务链**
   - 支持跨多个Worker集群
   - 异地容灾
   - 分布式事务

4. **AI辅助优化**
   - 基于历史数据的任务链优化建议
   - 自动资源分配
   - 执行时间预测

---

## 十一、总结

### 11.1 核心结论

**任务链功能应在Web端（FastAPI + Celery）设计**

### 11.2 关键优势

1. **架构清晰**：Web端负责编排，Worker端负责计算，职责分离
2. **技术成熟**：利用Celery原生任务链功能，稳定可靠
3. **易于扩展**：基于数据库的状态管理，便于功能扩展
4. **监控完善**：统一的状态追踪和错误处理机制

### 11.3 实施建议

1. **分阶段实施**：先支持简单链，再逐步支持复杂编排
2. **充分测试**：重点测试错误处理、并发安全、性能压力
3. **文档先行**：提供详细的API文档和使用示例
4. **监控优先**：从第一版就集成完善的监控和日志

### 11.4 成功指标

- [ ] 支持4种任务链类型（顺序/并行/chord/复合）
- [ ] 任务链执行成功率 > 99%
- [ ] 支持100+任务的大规模任务链
- [ ] 状态同步延迟 < 2秒
- [ ] API响应时间 < 500ms
