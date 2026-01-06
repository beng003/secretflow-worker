# SecretFlow任务集成方案（直接API调用版）

## 一、背景与目标

### 1.1 设计背景

经过Component System方案的实践，发现该方案存在以下问题：
- **复杂度高**：需要构造复杂的DistData、Context、Output等对象
- **调试困难**：错误信息不直观，问题定位成本高
- **文档不足**：Component API文档和示例较少
- **维护成本**：API变更时适配工作量大

### 1.2 新方案目标

**核心理念**：回归简单，直接调用SecretFlow原生API

**设计目标**：
1. **简单直接**：类似`local_test.py`的调用方式，易于理解和维护
2. **灵活高效**：直接使用SecretFlow的PYU/SPU设备和算法API
3. **易于扩展**：新增任务只需添加对应的执行函数
4. **保持兼容**：与现有Celery + Worker架构无缝集成

---

## 二、SecretFlow直接API分析

### 2.1 核心调用模式

SecretFlow的直接API遵循以下模式：

```python
import secretflow as sf

# 1. 初始化集群
sf.init(parties=['alice', 'bob'], address='local')

# 2. 创建设备
alice = sf.PYU('alice')
bob = sf.PYU('bob')
spu = sf.SPU(sf.utils.testing.cluster_def(['alice', 'bob']))

# 3. 准备数据（使用VDataFrame或FedNdarray）
vdf = sf.data.vertical.read_csv({
    alice: 'alice.csv',
    bob: 'bob.csv'
})

# 4. 调用算法
from secretflow.ml.linear.ss_sgd import SSRegression
model = SSRegression(spu)
model.fit(vdf[['f1', 'f2']], vdf['label'], epochs=10, learning_rate=0.1)

# 5. 获取结果
predictions = model.predict(vdf[['f1', 'f2']])

# 6. 清理
sf.shutdown()
```

### 2.2 主要任务类型的直接API

#### 2.2.1 隐私计算类

**PSI（隐私集合求交）**
```python
# 使用SPU设备直接调用
spu = sf.SPU(sf.utils.testing.cluster_def(['alice', 'bob']))
spu.psi(
    keys={alice.party: ['uid'], bob.party: ['uid']},
    input_path={alice.party: 'alice.csv', bob.party: 'bob.csv'},
    output_path={alice.party: 'alice_psi.csv', bob.party: 'bob_psi.csv'},
    receiver='alice',
    broadcast_result={alice.party: True, bob.party: True}
)
```

#### 2.2.2 数据预处理类

**StandardScaler（标准化）**
```python
from secretflow.preprocessing import StandardScaler

scaler = StandardScaler()
scaled_vdf = scaler.fit_transform(vdf, cols=['age', 'income'])
```

**LabelEncoder（标签编码）**
```python
from secretflow.preprocessing import LabelEncoder

encoder = LabelEncoder()
encoded_vdf = encoder.fit_transform(vdf, cols=['category'])
```

**数据分箱**
```python
from secretflow.preprocessing.binning import VertBinning

binning = VertBinning(spu)
binned_vdf = binning.fit_transform(vdf, binning_method='quantile', bin_num=10)
```

#### 2.2.3 机器学习类

**逻辑回归（SS-SGD）**
```python
from secretflow.ml.linear.ss_sgd import SSRegression

model = SSRegression(spu)
model.fit(
    x=vdf[['f1', 'f2', 'f3']],
    y=vdf['label'],
    epochs=10,
    learning_rate=0.01,
    batch_size=128,
    sig_type='t1',
    reg_type='logistic',
    penalty='l2',
    l2_norm=0.1
)
```

**XGBoost（SecureBoost）**
```python
from secretflow.ml.boost.ss_xgb_v import Xgb

params = {
    'num_boost_round': 10,
    'max_depth': 5,
    'learning_rate': 0.1,
    'objective': 'binary:logistic',
    'reg_lambda': 0.1,
    'subsample': 1.0,
    'colsample_by_tree': 1.0,
    'sketch_eps': 0.1,
    'base_score': 0.5
}

model = Xgb(spu)
model.train(vdf, vdf['label'], params)
```

**联邦学习神经网络**
```python
from secretflow.ml.nn import FLModel
from secretflow.ml.nn.applications.sl_dnn import DNN

# 定义模型
model_alice = DNN(input_dim=10, output_dim=1, hidden_sizes=[64, 32])
model_bob = DNN(input_dim=8, output_dim=1, hidden_sizes=[64, 32])

# 创建FL模型
fl_model = FLModel(
    device_y=alice,
    model_dict={alice: model_alice, bob: model_bob},
    aggregator=aggregator
)

# 训练
history = fl_model.fit(
    x=vdf[['f1', 'f2', ...]],
    y=vdf['label'],
    epochs=10,
    batch_size=128
)
```

#### 2.2.4 统计分析类

**表统计**
```python
from secretflow.stats import table_statistics

stats = table_statistics(vdf, ['age', 'income', 'score'])
# 返回：count, mean, std, min, max, quartiles等
```

**相关性分析**
```python
from secretflow.stats import pearson_r

corr_matrix = pearson_r(vdf, ['f1', 'f2', 'f3'])
```

**VIF（方差膨胀因子）**
```python
from secretflow.stats import vif

vif_values = vif(vdf, ['f1', 'f2', 'f3'])
```

#### 2.2.5 模型评估类

**二分类评估**
```python
from secretflow.ml.linear.ss_sgd import SSRegression

# 预测
predictions = model.predict(vdf[features])

# 评估
from secretflow.stats import binary_classification_eval

metrics = binary_classification_eval(
    y_true=vdf['label'],
    y_pred=predictions,
    bucket_size=10
)
# 返回：AUC, accuracy, precision, recall, F1等
```

---

## 三、简化架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                  Web容器 (FastAPI + Celery)                  │
│  ┌────────────────────────────────────────────────────┐     │
│  │  TaskChainService / TaskService                     │     │
│  │  - 接收Web请求并提交到Celery队列                     │     │
│  └────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │ Celery Queue
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                Worker容器 (SecretFlow Worker)                │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Celery任务接收层                                   │     │
│  │  - execute_secretflow_celery_task                  │     │
│  └────────────────────────────────────────────────────┘     │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │  任务执行协调器                                     │     │
│  │  - TaskExecutor                                    │     │
│  │  - 集群初始化                                       │     │
│  │  - 设备管理（PYU/SPU/HEU）                          │     │
│  │  - 资源清理                                         │     │
│  └────────────────────────────────────────────────────┘     │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │  任务分发器（新增简化版）                            │     │
│  │  - TaskDispatcher                                  │     │
│  │  - 根据task_type调用对应的执行函数                   │     │
│  └────────────────────────────────────────────────────┘     │
│                         │                                    │
│       ┌─────────────────┼─────────────────┐                 │
│       │                 │                 │                 │
│       ▼                 ▼                 ▼                 │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐              │
│  │  PSI    │    │   ML     │    │  Stats   │              │
│  │ 执行函数 │    │ 执行函数  │    │ 执行函数  │              │
│  └─────────┘    └──────────┘    └──────────┘              │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │  SecretFlow原生API                                  │     │
│  │  - sf.PYU / sf.SPU / sf.HEU                        │     │
│  │  - spu.psi()                                       │     │
│  │  - SSRegression, Xgb, StandardScaler等             │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件

#### 3.2.1 任务分发器（TaskDispatcher）

```python
"""
任务分发器 - 简化版
位置: src/secretflow_task/task_dispatcher.py
"""

from typing import Dict, Any, Callable
from utils.log import logger


class TaskDispatcher:
    """
    任务分发器：根据task_type路由到对应的执行函数
    
    设计理念：
    - 每个任务类型对应一个执行函数
    - 执行函数接收标准化的参数：devices, task_config
    - 执行函数返回标准化的结果字典
    """
    
    # 任务类型到执行函数的映射
    TASK_REGISTRY: Dict[str, Callable] = {}
    
    @classmethod
    def register_task(cls, task_type: str):
        """任务注册装饰器"""
        def decorator(func: Callable):
            cls.TASK_REGISTRY[task_type] = func
            logger.info(f"注册任务类型: {task_type} -> {func.__name__}")
            return func
        return decorator
    
    @classmethod
    def dispatch(
        cls,
        task_type: str,
        devices: Dict[str, Any],
        task_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分发任务到对应的执行函数
        
        Args:
            task_type: 任务类型
            devices: 设备字典 {'pyus': {...}, 'spu': ..., 'heu': ...}
            task_config: 任务配置
            
        Returns:
            Dict[str, Any]: 执行结果
            
        Raises:
            ValueError: 不支持的任务类型
        """
        executor_func = cls.TASK_REGISTRY.get(task_type)
        
        if not executor_func:
            raise ValueError(
                f"不支持的任务类型: {task_type}. "
                f"支持的类型: {list(cls.TASK_REGISTRY.keys())}"
            )
        
        logger.info(f"分发任务: {task_type} -> {executor_func.__name__}")
        
        try:
            result = executor_func(devices=devices, task_config=task_config)
            return {
                'status': 'success',
                'task_type': task_type,
                'result': result
            }
        except Exception as e:
            logger.error(f"任务执行失败: {task_type}", exc_info=True)
            return {
                'status': 'failed',
                'task_type': task_type,
                'error': str(e)
            }
    
    @classmethod
    def list_supported_tasks(cls) -> list:
        """获取所有支持的任务类型"""
        return list(cls.TASK_REGISTRY.keys())
```

#### 3.2.2 任务执行函数示例

**PSI任务**
```python
"""
PSI任务执行函数
位置: src/secretflow_task/jobs/psi_task.py
"""

from secretflow_task.task_dispatcher import TaskDispatcher
from utils.log import logger


@TaskDispatcher.register_task('psi')
def execute_psi(devices: dict, task_config: dict) -> dict:
    """
    执行PSI隐私集合求交
    
    Args:
        devices: {'pyus': {'alice': PYU, 'bob': PYU}, 'spu': SPU}
        task_config: {
            'keys': {'alice': ['uid'], 'bob': ['uid']},
            'input_paths': {'alice': 'alice.csv', 'bob': 'bob.csv'},
            'output_paths': {'alice': 'alice_psi.csv', 'bob': 'bob_psi.csv'},
            'receiver': 'alice',
            'protocol': 'ECDH_PSI_2PC'  # optional
        }
    
    Returns:
        Dict: {'intersection_count': int, 'output_paths': {...}}
    """
    spu = devices['spu']
    pyus = devices['pyus']
    
    keys = task_config['keys']
    input_paths = task_config['input_paths']
    output_paths = task_config['output_paths']
    receiver = task_config.get('receiver', list(pyus.keys())[0])
    
    logger.info(f"执行PSI: keys={keys}, receiver={receiver}")
    
    # 调用SPU的PSI接口
    psi_result = spu.psi(
        keys=keys,
        input_path=input_paths,
        output_path=output_paths,
        receiver=receiver,
        broadcast_result={party: True for party in pyus.keys()},
        disable_alignment=task_config.get('disable_alignment', True)
    )
    
    # 读取输出文件统计交集数量
    import pandas as pd
    intersection_count = len(pd.read_csv(output_paths[receiver]))
    
    return {
        'intersection_count': intersection_count,
        'output_paths': output_paths,
        'psi_protocol': task_config.get('protocol', 'KKRT')
    }
```

**标准化任务**
```python
"""
数据标准化任务
位置: src/secretflow_task/jobs/preprocessing_task.py
"""

import secretflow as sf
from secretflow.preprocessing import StandardScaler
from secretflow_task.task_dispatcher import TaskDispatcher
from utils.log import logger


@TaskDispatcher.register_task('standard_scaler')
def execute_standard_scaler(devices: dict, task_config: dict) -> dict:
    """
    执行数据标准化
    
    Args:
        devices: {'pyus': {'alice': PYU, 'bob': PYU}}
        task_config: {
            'input_data': {'alice': 'alice.csv', 'bob': 'bob.csv'},
            'output_data': {'alice': 'alice_scaled.csv', 'bob': 'bob_scaled.csv'},
            'columns': ['age', 'income', 'score'],
            'with_mean': True,
            'with_std': True
        }
    
    Returns:
        Dict: {'output_paths': {...}, 'scale_params': {...}}
    """
    pyus = devices['pyus']
    
    input_data = task_config['input_data']
    output_data = task_config['output_data']
    columns = task_config.get('columns')
    
    logger.info(f"执行StandardScaler: columns={columns}")
    
    # 读取数据为VDataFrame
    vdf = sf.data.vertical.read_csv(
        {pyus[party]: path for party, path in input_data.items()}
    )
    
    # 创建并执行StandardScaler
    scaler = StandardScaler(
        with_mean=task_config.get('with_mean', True),
        with_std=task_config.get('with_std', True)
    )
    
    scaled_vdf = scaler.fit_transform(vdf, cols=columns)
    
    # 保存结果
    for party, path in output_data.items():
        scaled_vdf.partitions[pyus[party]].to_csv(path)
    
    return {
        'output_paths': output_data,
        'columns_scaled': columns,
        'scale_params': {
            'mean': scaler.mean_ if hasattr(scaler, 'mean_') else None,
            'std': scaler.scale_ if hasattr(scaler, 'scale_') else None
        }
    }
```

**逻辑回归任务**
```python
"""
逻辑回归训练任务
位置: src/secretflow_task/jobs/ml_task.py
"""

import secretflow as sf
from secretflow.ml.linear.ss_sgd import SSRegression
from secretflow_task.task_dispatcher import TaskDispatcher
from utils.log import logger


@TaskDispatcher.register_task('ss_lr')
def execute_ss_logistic_regression(devices: dict, task_config: dict) -> dict:
    """
    执行安全逻辑回归训练
    
    Args:
        devices: {'pyus': {...}, 'spu': SPU}
        task_config: {
            'train_data': {'alice': 'alice_train.csv', 'bob': 'bob_train.csv'},
            'features': ['f1', 'f2', 'f3'],
            'label': 'y',
            'label_party': 'alice',
            'model_output': '/path/to/model',
            'params': {
                'epochs': 10,
                'learning_rate': 0.01,
                'batch_size': 128,
                'penalty': 'l2',
                'l2_norm': 0.1
            }
        }
    
    Returns:
        Dict: {'model_path': str, 'metrics': {...}}
    """
    spu = devices['spu']
    pyus = devices['pyus']
    
    train_data = task_config['train_data']
    features = task_config['features']
    label = task_config['label']
    params = task_config.get('params', {})
    
    logger.info(f"执行SS-LR训练: features={features}, label={label}")
    
    # 读取训练数据
    vdf = sf.data.vertical.read_csv(
        {pyus[party]: path for party, path in train_data.items()}
    )
    
    # 创建模型
    model = SSRegression(spu)
    
    # 训练
    model.fit(
        x=vdf[features],
        y=vdf[label],
        epochs=params.get('epochs', 10),
        learning_rate=params.get('learning_rate', 0.01),
        batch_size=params.get('batch_size', 128),
        sig_type=params.get('sig_type', 't1'),
        reg_type='logistic',
        penalty=params.get('penalty', 'l2'),
        l2_norm=params.get('l2_norm', 0.1)
    )
    
    # 保存模型
    model_path = task_config.get('model_output', '/tmp/ss_lr_model')
    model.save_model(model_path)
    
    return {
        'model_path': model_path,
        'epochs_trained': params.get('epochs', 10),
        'learning_rate': params.get('learning_rate', 0.01)
    }
```

**XGBoost任务**
```python
@TaskDispatcher.register_task('ss_xgb')
def execute_ss_xgboost(devices: dict, task_config: dict) -> dict:
    """
    执行SecureBoost XGBoost训练
    
    Args:
        devices: {'pyus': {...}, 'spu': SPU}
        task_config: {
            'train_data': {...},
            'features': [...],
            'label': 'y',
            'model_output': '/path/to/model',
            'params': {
                'num_boost_round': 10,
                'max_depth': 5,
                'learning_rate': 0.1,
                'objective': 'binary:logistic',
                ...
            }
        }
    """
    from secretflow.ml.boost.ss_xgb_v import Xgb
    
    spu = devices['spu']
    pyus = devices['pyus']
    
    # 读取数据
    vdf = sf.data.vertical.read_csv(
        {pyus[party]: path for party, path in task_config['train_data'].items()}
    )
    
    # 创建并训练模型
    model = Xgb(spu)
    model.train(
        dtrain=vdf[task_config['features']],
        label=vdf[task_config['label']],
        params=task_config.get('params', {})
    )
    
    # 保存模型
    model_path = task_config.get('model_output', '/tmp/ss_xgb_model')
    model.save_model(model_path)
    
    return {
        'model_path': model_path,
        'num_boost_round': task_config['params'].get('num_boost_round', 10)
    }
```

**统计分析任务**
```python
@TaskDispatcher.register_task('table_statistics')
def execute_table_statistics(devices: dict, task_config: dict) -> dict:
    """
    执行表统计分析
    
    Args:
        devices: {'pyus': {...}}
        task_config: {
            'input_data': {'alice': 'alice.csv'},
            'columns': ['age', 'income', 'education'],
            'output_report': '/path/to/report.json'
        }
    """
    from secretflow.stats import table_statistics
    
    pyus = devices['pyus']
    
    # 读取数据
    vdf = sf.data.vertical.read_csv(
        {pyus[party]: path for party, path in task_config['input_data'].items()}
    )
    
    # 计算统计信息
    stats = table_statistics(vdf, task_config['columns'])
    
    # 保存报告
    import json
    with open(task_config.get('output_report', '/tmp/stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)
    
    return {
        'statistics': stats,
        'report_path': task_config.get('output_report')
    }
```

#### 3.2.3 修改任务执行器（task_executor.py）

```python
"""
修改现有的任务执行器，集成任务分发器
位置: src/secretflow_task/task_executor.py（修改）
"""

import secretflow as sf
from secretflow_task.task_dispatcher import TaskDispatcher
from utils.log import logger


def execute_secretflow_task(
    task_request_id: str,
    sf_init_config: dict,
    spu_config: dict,
    heu_config: dict,
    task_config: dict
) -> dict:
    """
    SecretFlow任务执行主函数（简化版）
    
    Args:
        task_request_id: 任务请求ID
        sf_init_config: SecretFlow初始化配置
        spu_config: SPU配置
        heu_config: HEU配置
        task_config: 任务配置
    
    Returns:
        Dict: 执行结果
    """
    logger.info(f"开始执行任务: {task_request_id}")
    
    try:
        # ========================================
        # 第1步：初始化SecretFlow集群
        # ========================================
        logger.info("[1/4] 初始化SecretFlow集群...")
        parties = sf_init_config.get('parties', ['alice', 'bob'])
        address = sf_init_config.get('address', 'local')
        
        sf.init(parties=parties, address=address)
        logger.info(f"  SecretFlow集群初始化完成: parties={parties}")
        
        # ========================================
        # 第2步：创建设备
        # ========================================
        logger.info("[2/4] 创建计算设备...")
        
        # 创建PYU设备
        pyus = {party: sf.PYU(party) for party in parties}
        logger.info(f"  PYU设备创建完成: {list(pyus.keys())}")
        
        # 创建SPU设备（如果需要）
        spu = None
        if spu_config:
            spu = sf.SPU(spu_config.get('cluster_def', 
                         sf.utils.testing.cluster_def(parties)))
            logger.info("  SPU设备创建完成")
        
        # 创建HEU设备（如果需要）
        heu = None
        if heu_config:
            # HEU创建逻辑
            pass
        
        devices = {
            'pyus': pyus,
            'spu': spu,
            'heu': heu
        }
        
        # ========================================
        # 第3步：执行任务（使用任务分发器）
        # ========================================
        logger.info("[3/4] 执行任务...")
        
        task_type = task_config.get('task_type')
        if not task_type:
            raise ValueError("任务配置中缺少task_type字段")
        
        logger.info(f"  任务类型: {task_type}")
        
        # 调用任务分发器
        result = TaskDispatcher.dispatch(
            task_type=task_type,
            devices=devices,
            task_config=task_config
        )
        
        logger.info(f"  任务执行完成: status={result['status']}")
        
        # ========================================
        # 第4步：清理资源
        # ========================================
        logger.info("[4/4] 清理资源...")
        sf.shutdown()
        logger.info("  SecretFlow集群已关闭")
        
        return {
            'task_request_id': task_request_id,
            'status': 'success',
            'task_type': task_type,
            'result': result
        }
        
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        
        # 确保清理资源
        try:
            sf.shutdown()
        except:
            pass
        
        return {
            'task_request_id': task_request_id,
            'status': 'failed',
            'error': str(e)
        }
```

---

## 四、任务配置格式

### 4.1 统一配置格式

```json
{
  "task_request_id": "task-uuid-001",
  "sf_init_config": {
    "parties": ["alice", "bob"],
    "address": "local"
  },
  "spu_config": {
    "cluster_def": {
      "nodes": [
        {"party": "alice", "address": "127.0.0.1:12345"},
        {"party": "bob", "address": "127.0.0.1:12346"}
      ],
      "runtime_config": {
        "protocol": "SEMI2K",
        "field": "FM128"
      }
    }
  },
  "heu_config": null,
  "task_config": {
    "task_type": "ss_lr",
    "train_data": {
      "alice": "/data/alice_train.csv",
      "bob": "/data/bob_train.csv"
    },
    "features": ["f1", "f2", "f3"],
    "label": "y",
    "label_party": "alice",
    "model_output": "/models/lr_model",
    "params": {
      "epochs": 10,
      "learning_rate": 0.01,
      "batch_size": 128,
      "penalty": "l2",
      "l2_norm": 0.1
    }
  }
}
```

### 4.2 各类任务配置示例

#### PSI任务
```json
{
  "task_type": "psi",
  "keys": {
    "alice": ["uid"],
    "bob": ["uid"]
  },
  "input_paths": {
    "alice": "/data/alice.csv",
    "bob": "/data/bob.csv"
  },
  "output_paths": {
    "alice": "/data/alice_psi.csv",
    "bob": "/data/bob_psi.csv"
  },
  "receiver": "alice",
  "protocol": "ECDH_PSI_2PC"
}
```

#### 标准化任务
```json
{
  "task_type": "standard_scaler",
  "input_data": {
    "alice": "/data/alice.csv",
    "bob": "/data/bob.csv"
  },
  "output_data": {
    "alice": "/data/alice_scaled.csv",
    "bob": "/data/bob_scaled.csv"
  },
  "columns": ["age", "income", "score"],
  "with_mean": true,
  "with_std": true
}
```

#### XGBoost任务
```json
{
  "task_type": "ss_xgb",
  "train_data": {
    "alice": "/data/alice_train.csv",
    "bob": "/data/bob_train.csv"
  },
  "features": ["f1", "f2", "f3", "f4"],
  "label": "y",
  "model_output": "/models/xgb_model",
  "params": {
    "num_boost_round": 10,
    "max_depth": 5,
    "learning_rate": 0.1,
    "objective": "binary:logistic",
    "reg_lambda": 0.1
  }
}
```

---

## 五、支持的任务类型清单

### 5.1 已实现任务（优先级高）

| 任务类型 | 任务名称 | 执行函数 | API路径 |
|---------|---------|---------|---------|
| psi | 隐私集合求交 | execute_psi | spu.psi() |
| standard_scaler | 标准化 | execute_standard_scaler | StandardScaler |
| ss_lr | 逻辑回归 | execute_ss_logistic_regression | SSRegression |
| ss_xgb | XGBoost | execute_ss_xgboost | Xgb |
| table_statistics | 表统计 | execute_table_statistics | table_statistics |

### 5.2 待实现任务（按优先级）

**数据预处理类**
- min_max_scaler - 最小最大归一化
- label_encoder - 标签编码
- onehot_encoder - One-Hot编码
- binning - 数据分箱
- fillna - 缺失值填充

**机器学习类**
- ss_glm - 广义线性模型
- sgb - Secure Gradient Boosting
- ss_kmeans - K-Means聚类

**统计分析类**
- pearson_correlation - Pearson相关性
- vif - 方差膨胀因子
- woe_iv - WOE/IV计算

**模型评估类**
- biclassification_eval - 二分类评估
- regression_eval - 回归评估

---

## 六、实施计划

### 6.1 Phase 1: 核心框架（2天）

**任务清单**：
- [x] 创建 `TaskDispatcher` 任务分发器
- [x] 实现任务注册机制
- [x] 修改 `task_executor.py` 集成分发器
- [x] 编写单元测试

**交付物**：
- 完整的任务分发框架
- 单元测试覆盖率 > 80%

### 6.2 Phase 2: 核心任务实现（3天）

**任务清单**：
- [ ] 实现PSI任务（已有参考）
- [ ] 实现StandardScaler任务
- [ ] 实现SS-LR任务
- [ ] 实现SS-XGBoost任务
- [ ] 实现表统计任务

**交付物**：
- 5个核心任务的执行函数
- 每个任务的单元测试和集成测试

### 6.3 Phase 3: 扩展任务实现（5天）

**任务清单**：
- [ ] 实现其他预处理任务（MinMaxScaler、LabelEncoder等）
- [ ] 实现其他ML任务（GLM、SGB、KMeans等）
- [ ] 实现统计分析任务
- [ ] 实现模型评估任务

**交付物**：
- 15+个任务的完整实现
- 配置示例和使用文档

### 6.4 Phase 4: 测试与优化（3天）

**任务清单**：
- [ ] 端到端集成测试
- [ ] 性能基准测试
- [ ] 错误处理和日志优化
- [ ] 文档完善

**交付物**：
- 完整的测试报告
- 性能优化建议
- 部署文档

### 6.5 Phase 5: 部署与监控（2天）

**任务清单**：
- [ ] 生产环境部署
- [ ] 监控指标配置
- [ ] 告警规则设置
- [ ] 运维文档编写

**交付物**：
- 生产环境运行的系统
- 监控仪表板
- 运维手册

**总计工期**：约15个工作日

---

## 七、优势对比

### 7.1 新方案 vs Component System方案

| 对比项 | Component System方案 | 直接API方案（新） |
|-------|---------------------|-----------------|
| **代码复杂度** | 高（需要构造DistData、Context等） | 低（直接调用API） |
| **学习曲线** | 陡峭 | 平缓 |
| **调试难度** | 困难（错误信息复杂） | 简单（直观明了） |
| **文档支持** | 较少 | 丰富（官方API文档） |
| **代码行数** | ~1000行（核心） | ~500行（核心） |
| **维护成本** | 高 | 低 |
| **扩展性** | 中等 | 高（新增任务只需一个函数） |
| **性能** | 相同 | 相同 |
| **兼容性** | API变更影响大 | 直接跟随SecretFlow版本 |

### 7.2 核心优势

1. **极简设计**：
   - 每个任务一个执行函数
   - 标准化的参数和返回值
   - 无需复杂的适配层

2. **易于理解**：
   - 代码逻辑清晰
   - 类似local_test.py的风格
   - 新人上手快

3. **灵活扩展**：
   - 注册机制简单
   - 新增任务无需修改框架
   - 支持自定义任务

4. **便于调试**：
   - 错误定位准确
   - 日志输出直观
   - 支持单步调试

5. **维护友好**：
   - 代码量少
   - 依赖简单
   - 升级成本低

---

## 八、风险评估与应对

### 8.1 风险点

| 风险 | 等级 | 影响 | 应对措施 |
|-----|------|------|---------|
| SecretFlow API变更 | 中 | 需要更新执行函数 | 1. 锁定SecretFlow版本<br>2. 建立API变更监控<br>3. 编写适配层 |
| 性能问题 | 低 | 某些任务执行慢 | 1. 性能基准测试<br>2. 优化数据传输<br>3. 使用异步执行 |
| 错误处理不足 | 中 | 任务失败难定位 | 1. 完善异常捕获<br>2. 增强日志输出<br>3. 添加重试机制 |
| 兼容性问题 | 低 | 旧任务迁移困难 | 1. 提供迁移工具<br>2. 支持Legacy模式<br>3. 灰度发布 |

### 8.2 降级方案

如果新方案遇到问题，可以：
1. 保留原有PSI等任务的执行器
2. 新任务使用新方案，老任务保持不变
3. 逐步迁移，确保平滑过渡

---

## 九、总结

### 9.1 核心设计理念

**简单就是美**：
- 放弃复杂的Component System
- 直接使用SecretFlow原生API
- 用装饰器实现任务注册
- 标准化参数和返回值

### 9.2 关键特性

✅ **极简架构**：任务分发器 + 执行函数  
✅ **易于扩展**：注册机制，新增任务只需一个函数  
✅ **直观调试**：清晰的错误信息和日志  
✅ **零学习成本**：类似local_test.py的风格  
✅ **高度灵活**：支持任意SecretFlow API调用  

### 9.3 预期效果

- **开发效率提升50%**：代码量减半，逻辑更清晰
- **维护成本降低60%**：简单的代码结构，易于理解
- **调试时间缩短70%**：直观的错误信息
- **新人上手时间缩短80%**：符合直觉的设计

### 9.4 下一步行动

1. Review本设计方案，确认技术细节
2. 搭建核心框架（TaskDispatcher）
3. 实现5个核心任务
4. 编写单元测试和集成测试
5. 逐步扩展其他任务类型

---

**设计完成时间**：2026-01-04  
**设计版本**：v1.0  
**设计原则**：简单、直接、高效
