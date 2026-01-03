# SecretFlow Worker端参数设计理念

## 设计概述

本文档阐述SecretFlow Worker端函数参数格式的设计理念与架构思想。基于对SecretFlow框架的深入分析，我们制定了标准化的参数格式，确保Worker端任务执行的可扩展性、可维护性和高可靠性。

## 核心设计原则

### 1. 分层解耦原则

**设计理念**: 将SecretFlow任务执行参数按照功能职责分为四个独立层次：

```
┌─────────────────────────────────────┐
│         task_config                 │  ← 任务特定参数层
├─────────────────────────────────────┤
│     heu_config (可选)               │  ← HEU设备配置层  
├─────────────────────────────────────┤
│     spu_config (可选)               │  ← SPU设备配置层
├─────────────────────────────────────┤
│         sf_init_config              │  ← 基础集群层
└─────────────────────────────────────┘
```

**优势分析**:
- **独立性**: 每层配置职责单一，互不干扰
- **复用性**: 基础配置层可在多种任务间共享
- **可测试性**: 各层可独立进行单元测试
- **可扩展性**: 新增设备类型无需修改现有结构

### 2. 条件可选原则

**设计理念**: 基于"基本所有任务都需要sf.init，极少部分不需要spu.init或heu.init"的需求，采用条件可选设计：

```yaml
spu_config:
  enable_spu: true/false  # 控制是否启用
  # 当enable_spu为true时，其他配置必须提供

heu_config:
  enable_heu: true/false  # 控制是否启用  
  # 当enable_heu为true时，其他配置必须提供
```

**实现策略**:
- **默认启用**: spu和heu设备默认启用，覆盖大多数使用场景
- **显式禁用**: 通过`enable_*`标志明确禁用特定设备
- **验证机制**: 启用时强制验证必需参数完整性
- **性能优化**: 禁用设备可避免不必要的初始化开销

### 3. 任务类型驱动原则

**设计理念**: `task_config`中的`algorithm_params`根据`task_type`动态调整结构：

```yaml
algorithm_params:
  # PSI任务特有参数
  psi_params:
    input_keys: {...}
    protocol: "PROTOCOL_RR22"
    join_type: "inner_join"
    
  # 机器学习任务特有参数  
  ml_params:
    features: [...]
    model_type: "logistic_regression"
    training_params: {...}
```

**架构优势**:
- **类型安全**: 编译时可确定参数类型和结构
- **可维护性**: 新任务类型只需扩展对应参数结构
- **文档清晰**: 每种任务类型的参数含义明确
- **验证简化**: 基于task_type进行针对性参数验证

## 状态监听系统集成设计

### 集成架构

基于现有的Redis状态监听系统(`@/disc/home/beng003/work/secretflow_test/docs/04.task_status_listener.md`)，Worker端采用以下集成策略：

```
┌─────────────────────────┐    Redis消息    ┌─────────────────────────┐
│   SecretFlow Worker     │ ────────────→   │   FastAPI Web容器       │
│   容器                  │    发布状态     │                         │
│                         │                 │                         │
│ ┌─────────────────────┐ │                 │ ┌─────────────────────┐ │
│ │ execute_secretflow_ │ │                 │ │  TaskStatusListener │ │
│ │ task()             │ │                 │ │                     │ │
│ │                     │ │                 │ │ _handle_status_event│ │
│ │ _publish_task_event │ │                 │ │                     │ │ 
│ └─────────────────────┘ │                 │ └─────────────────────┘ │
└─────────────────────────┘                 └─────────────────────────┘
```

### 状态通信标准

**任务生命周期状态**:
1. **RUNNING** - 任务开始执行、各阶段进度更新
2. **SUCCESS** - 任务成功完成，包含结果信息
3. **FAILURE** - 任务执行失败，包含错误详情
4. **RETRY** - 任务重试状态(网络异常等场景)

**状态消息格式**:
```json
{
  "task_request_id": "uuid-string",
  "status": "RUNNING|SUCCESS|FAILURE|RETRY", 
  "timestamp": "2026-01-04T00:38:00.000Z",
  "data": {
    "stage": "sf_init|spu_init|heu_init|task_execution|cleanup",
    "parties_connected": ["alice", "bob"],
    "computation_progress": 0.65,
    "error": "error_message_if_any",
    "result": {}
  },
  "worker_container": "secretflow-worker-1",
  "task_name": "secretflow.execute_psi_task"
}
```

## 函数签名标准化

### 标准函数签名

```python
def execute_secretflow_task(
    task_request_id: str,
    sf_init_config: Dict[str, Any],
    spu_config: Dict[str, Any], 
    heu_config: Dict[str, Any],
    task_config: Dict[str, Any]
) -> Dict[str, Any]:
    """SecretFlow任务执行标准函数 - 同步版本
    
    注意: SecretFlow框架的用户API主要是同步的，因此主执行流程采用同步模式
    
    Args:
        task_request_id: 任务请求唯一标识符
        sf_init_config: SecretFlow集群初始化配置
        spu_config: SPU设备配置(含enable_spu标志)
        heu_config: HEU设备配置(含enable_heu标志) 
        task_config: 任务特定执行配置
        
    Returns:
        Dict[str, Any]: 任务执行结果
        {
            "status": "success|failure",
            "execution_time": float,
            "output_paths": List[str],
            "result_metadata": Dict[str, Any]
        }
    """
```

### 执行流程标准化

```python
def execute_secretflow_task(task_request_id, sf_init_config, spu_config, heu_config, task_config):
    """SecretFlow任务执行主函数 - 同步实现
    
    基于SecretFlow同步API的实际特性设计的执行流程
    """
    import secretflow as sf
    import time
    from log import logger  # 假设项目有统一的日志模块
    
    start_time = time.time()
    
    try:
        # 1. 同步发布任务开始状态
        _publish_status(task_request_id, "RUNNING", {"stage": "task_started"})
        
        # 2. 同步初始化SecretFlow集群
        sf.init(
            parties=sf_init_config["parties"],
            address=sf_init_config.get("address", "auto"),
            cross_silo_comm_backend=sf_init_config.get("cross_silo_comm_backend", "brpc_link")
        )
        _publish_status(task_request_id, "RUNNING", {"stage": "sf_cluster_ready"})
        
        # 3. 同步初始化设备(按需)
        devices = _initialize_devices(spu_config, heu_config)
        _publish_status(task_request_id, "RUNNING", {
            "stage": "devices_ready",
            "devices_initialized": list(devices.keys())
        })
        
        # 4. 同步执行具体任务
        result = _execute_task_by_type(task_config, devices)
        execution_time = time.time() - start_time
        
        # 5. 发布成功状态
        _publish_status(task_request_id, "SUCCESS", {
            "result": result,
            "execution_time": execution_time
        })
        
        return result
        
    except Exception as e:
        execution_time = time.time() - start_time
        _publish_status(task_request_id, "FAILURE", {
            "error": str(e),
            "error_type": type(e).__name__,
            "execution_time": execution_time
        })
        raise
    finally:
        # 清理SecretFlow资源
        try:
            sf.shutdown()
        except Exception as cleanup_error:
            logger.warning(f"资源清理警告: {cleanup_error}")
```

## 参数验证与安全设计

### 多层验证策略

**1. 结构验证**
- 必需字段存在性检查
- 数据类型一致性验证
- 字段值范围和格式验证

**2. 逻辑验证** 
- 参与方一致性检查(sf_init_config.parties与task_config.data_sources一致)
- 协议兼容性验证(SEMI2K适用2方，ABY3适用3方)
- 设备依赖关系检查

**3. 安全验证**
- 敏感参数脱敏处理
- 通信配置安全性检查
- 密钥长度安全性验证

### 错误处理与重试机制

**分类错误处理**:
```python
class SecretFlowTaskError(Exception):
    pass

class ClusterInitError(SecretFlowTaskError):
    """集群初始化失败"""
    pass

class DeviceConfigError(SecretFlowTaskError):
    """设备配置错误"""
    pass
    
class NetworkError(SecretFlowTaskError):
    """网络通信错误，可重试"""
    pass

class AlgorithmError(SecretFlowTaskError):
    """算法执行错误"""
    pass
```

**重试策略**:
- **网络错误**: 指数退避重试，最多3次
- **临时资源不足**: 延迟重试，最多5次
- **配置错误**: 不重试，立即失败
- **算法错误**: 不重试，记录详细错误信息

## 可扩展性设计

### 新任务类型扩展

**1. 定义新任务类型**:
```yaml
task_config:
  task_type: "new_algorithm"  # 新算法类型
  domain: "custom"
  algorithm_params:
    # 新算法特定参数
    custom_param1: "value1"
    custom_param2: 123
```

**2. 实现对应执行器**:
```python
class NewAlgorithmExecutor(BaseTaskExecutor):
    def validate_params(self, algorithm_params):
        # 新算法参数验证
        pass
        
    def execute_algorithm(self, algorithm_params):
        # 新算法执行逻辑
        pass
```

**3. 注册到任务工厂**:
```python
TASK_EXECUTOR_REGISTRY = {
    "psi": PSITaskExecutor,
    "lr": LogisticRegressionExecutor, 
    "new_algorithm": NewAlgorithmExecutor,  # 新增
}
```

### 新设备类型扩展

未来如需支持新的计算设备(如GPU设备、专用AI芯片等)：

```yaml
# 新设备配置格式
gpu_config:
  enable_gpu: true
  gpu_type: "nvidia_v100"
  memory_limit: "8GB"
  cuda_version: "11.2"
```

**实现策略**:
1. 在函数签名中增加对应设备配置参数
2. 实现新设备的初始化和管理逻辑
3. 更新验证规则和错误处理
4. 保持向后兼容性

## 性能优化考虑

### 初始化优化

**按需初始化**: 基于SecretFlow同步API的特性，采用按需顺序初始化策略：

```python
def _initialize_devices(spu_config, heu_config):
    """按需初始化SecretFlow计算设备
    
    SecretFlow的设备API是同步的，因此采用顺序初始化
    优化策略主要是避免不必要的设备初始化
    """
    devices = {}
    
    # 按需初始化SPU设备
    if spu_config.get("enable_spu", True):
        logger.info("初始化SPU设备...")
        start_time = time.time()
        
        cluster_def = sf.utils.testing.cluster_def(spu_config["parties"])
        spu_device = sf.SPU(
            cluster_def=cluster_def,
            link_desc=spu_config["link_desc"]
        )
        devices["spu"] = spu_device
        
        init_time = time.time() - start_time
        logger.info(f"SPU设备初始化完成，耗时: {init_time:.2f}秒")
        
    # 按需初始化HEU设备
    if heu_config.get("enable_heu", True):
        logger.info("初始化HEU设备...")
        start_time = time.time()
        
        heu_device = sf.HEU(
            config=heu_config,
            server_party=spu_config["parties"][0]  # 使用第一个参与方作为服务器
        )
        devices["heu"] = heu_device
        
        init_time = time.time() - start_time
        logger.info(f"HEU设备初始化完成，耗时: {init_time:.2f}秒")
    
    return devices
```

**配置缓存**: 相同配置的设备实例可复用，避免重复初始化开销。
**同步状态上报**: 基于SecretFlow长时间运行任务的特性，采用简洁可靠的同步状态上报：

```python
def _publish_status(task_request_id: str, status: str, data: dict):
    """同步状态上报 - 简洁可靠的实现
    
    优势:
    - 代码简洁，易于维护
    - 状态更新可靠，错误容易追踪
    - 资源占用小，无需额外线程
    - Redis本地操作延迟可忽略(<1ms)
    """
    try:
        from utils.status_notifier import _publish_task_event
        _publish_task_event(task_request_id, status, data, "task.secretflow")
        logger.debug(f"状态已上报: {task_request_id} -> {status}")
        
    except Exception as e:
        # 使用warning级别，不影响主任务执行
        logger.warning(f"状态上报失败，但不影响任务执行: {e}")
        # 注意：不抛出异常，确保状态上报失败不会中断SecretFlow计算
```

### 内存管理优化

**资源清理策略**:
- 任务完成后及时释放计算设备资源
- 大数据集分块处理，控制内存峰值
- 异常情况下确保资源清理执行

### 通信优化

**状态上报优化**:
- 批量状态更新减少Redis通信频次
- 关键状态变更实时上报，进度状态可适当延迟
- 异步状态发布避免阻塞主计算流程

## 部署与运维考虑

### 配置管理

**环境隔离**: 不同环境(开发/测试/生产)使用独立的配置文件：

```yaml
# config/dev.yaml - 开发环境
sf_init_config:
  address: "ray://localhost:10001"
  
# config/prod.yaml - 生产环境  
sf_init_config:
  address: "ray://ray-cluster:10001"
```

**配置验证**: 部署前自动验证配置文件完整性和正确性。

### 监控与诊断

**关键指标监控**:
- 任务执行成功率和平均耗时
- 设备初始化成功率和耗时
- 网络通信延迟和错误率
- 系统资源使用情况

**诊断信息收集**:
- 详细的执行日志记录
- 任务参数和执行环境快照
- 错误堆栈和上下文信息