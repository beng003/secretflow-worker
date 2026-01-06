# 路径格式改进：支持字典格式的参与方路径

## 改进概述

**改进日期**: 2026-01-05  
**改进目标**: 将模型保存路径`model_output`和预测输出路径`output_path`改为字典格式，每个参与方有自己的路径

## 改进动机

### 原实现的问题

**原格式**（单一路径）:
```python
# 训练配置
task_config = {
    "model_output": "/models/lr_model",  # ❌ 所有参与方共享基础路径
    ...
}

# 保存的文件
# /models/lr_model.meta.json
# /models/lr_model.alice.share
# /models/lr_model.bob.share
# /models/lr_model.alice.json
# /models/lr_model.bob.json
```

**问题**:
- ❌ 所有文件保存在同一目录
- ❌ 无法让每个参与方将文件保存到各自的位置
- ❌ 不符合分布式场景下各参与方独立存储的需求

### 改进后的格式

**新格式**（字典格式）:
```python
# 训练配置
task_config = {
    "model_output": {
        "alice": "/alice/models/lr_model.share",  # ✅ Alice的路径
        "bob": "/bob/models/lr_model.share"       # ✅ Bob的路径
    },
    ...
}

# 保存的文件
# Alice端:
#   /alice/models/lr_model.share          (密文分片)
#   /alice/models/lr_model.share.meta.json (元数据)
# Bob端:
#   /bob/models/lr_model.share            (密文分片)
#   /bob/models/lr_model.share.meta.json   (元数据)
```

**优势**:
- ✅ 每个参与方的文件保存在各自的目录
- ✅ 支持分布式场景下的独立存储
- ✅ 更符合实际部署需求
- ✅ 路径更灵活，可以指定不同的存储位置

## 实现细节

### 1. 模型保存函数修改

#### 函数签名变更

```python
# 旧签名
def _save_ss_lr_model(
    model: SSRegression,
    ...,
    model_output: str,  # ❌ 字符串类型
    spu_device: SPU
) -> None:

# 新签名
def _save_ss_lr_model(
    model: SSRegression,
    ...,
    model_output: Dict[str, str],  # ✅ 字典类型 {party: path}
    spu_device: SPU
) -> None:
```

#### 保存逻辑变更

```python
# 为每个参与方保存密文分片和元数据
share_paths = []
for party in parties:
    if party not in model_output:
        raise ValueError(f"model_output中缺少参与方'{party}'的路径")
    
    party_path = model_output[party]
    
    # 确保目录存在
    party_dir = os.path.dirname(party_path)
    if party_dir:
        os.makedirs(party_dir, exist_ok=True)
    
    # 密文分片路径
    share_path = party_path
    share_paths.append(share_path)
    
    # 为每个参与方保存元数据文件
    party_meta = {
        "party": party,
        "model_type": "ss_sgd_secure",
        "share_path": share_path,
        "parties": parties,
        "features": features,
        "label": label,
        "label_party": label_party,
        "reg_type": str(linear_model.reg_type),
        "sig_type": str(linear_model.sig_type),
        "training_params": model_meta["training_params"],
        "secure_mode": True,
        "created_at": datetime.now().isoformat()
    }
    
    meta_path = f"{party_path}.meta.json"
    with open(meta_path, 'w') as f:
        json.dump(party_meta, f, indent=2)
    logger.info(f"参与方 {party} 的元数据已保存到: {meta_path}")

# 使用SPU.dump保存密文分片
logger.info(f"保存密文分片到: {share_paths}")
spu_device.dump(linear_model.weights, share_paths)
```

### 2. 模型加载函数修改

#### 函数签名变更

```python
# 旧签名
def load_ss_lr_model(
    model_output: str,  # ❌ 字符串类型
    spu_device: SPU,
    parties: List[str]
) -> Dict:

# 新签名
def load_ss_lr_model(
    model_output: Dict[str, str],  # ✅ 字典类型 {party: path}
    spu_device: SPU,
    parties: List[str]
) -> Dict:
```

#### 加载逻辑变更

```python
# 验证所有参与方的路径都存在
for party in parties:
    if party not in model_output:
        raise ValueError(f"model_output中缺少参与方'{party}'的路径")

# 从第一个参与方的元数据文件读取模型信息
first_party = parties[0]
first_party_path = model_output[first_party]
meta_path = f"{first_party_path}.meta.json"

if not os.path.exists(meta_path):
    raise FileNotFoundError(f"模型元数据文件不存在: {meta_path}")

# 读取模型元数据
with open(meta_path, 'r') as f:
    model_meta = json.load(f)

# 构建密文分片路径
share_paths = []
for party in parties:
    share_path = model_output[party]
    if not os.path.exists(share_path):
        raise FileNotFoundError(f"参与方 {party} 的密文分片不存在: {share_path}")
    share_paths.append(share_path)

# 使用SPU.load从密文分片重建SPUObject
spu_weights = spu_device.load(share_paths)
```

### 3. 预测函数修改

#### 文档和验证更新

```python
@TaskDispatcher.register_task('ss_lr_predict')
def execute_ss_lr_predict(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行SS-LR模型预测任务（安全模式）
    
    Args:
        devices: 设备字典
        task_config: 任务配置，包含以下字段：
            - model_path: Dict[str, str] - 模型文件路径字典 {party: path}
            - predict_data: Dict[str, str] - 预测数据路径字典
            - output_path: Dict[str, str] - 预测结果输出路径字典 {party: path}
            - receiver_party: str - 接收预测结果的参与方（可选）
    """
    # 验证路径格式
    if not isinstance(model_path, dict):
        raise ValueError("model_path必须是字典格式 {party: path}")
    if not isinstance(output_path, dict):
        raise ValueError("output_path必须是字典格式 {party: path}")
```

#### 预测保存逻辑

```python
# 验证接收方在output_path中有对应路径
if receiver_party not in output_path:
    raise ValueError(f"output_path中缺少接收方'{receiver_party}'的路径")

receiver_output_path = output_path[receiver_party]

# 在接收方PYU上保存预测结果
num_predictions_pyu = receiver_pyu(save_predictions)(predictions_pyu, receiver_output_path)
```

### 4. 配置验证函数修改

```python
def _validate_ss_lr_config(task_config: Dict) -> None:
    """验证SS-LR任务配置"""
    
    # 验证model_output格式
    model_output = task_config['model_output']
    if not isinstance(model_output, dict):
        raise ValueError("model_output必须是字典类型 {party: path}")
    
    if not model_output:
        raise ValueError("model_output不能为空")
    
    for party, path in model_output.items():
        if not isinstance(path, str) or not path:
            raise ValueError(f"参与方'{party}'的model_output路径必须是非空字符串")
```

## 使用示例

### 1. 模型训练

```python
from secretflow_task.task_dispatcher import TaskDispatcher

# 训练配置（使用字典格式的路径）
train_config = {
    "train_data": {
        "alice": "/alice/data/train.csv",
        "bob": "/bob/data/train.csv"
    },
    "features": ["f0", "f1", "f2"],
    "label": "y",
    "label_party": "alice",
    "model_output": {
        "alice": "/alice/models/lr_model.share",
        "bob": "/bob/models/lr_model.share"
    },
    "params": {
        "epochs": 10,
        "learning_rate": 0.1
    }
}

# 执行训练
result = TaskDispatcher.dispatch('ss_lr', devices, train_config)

# 保存的文件
# Alice端:
#   /alice/models/lr_model.share          (密文分片)
#   /alice/models/lr_model.share.meta.json (元数据)
# Bob端:
#   /bob/models/lr_model.share            (密文分片)
#   /bob/models/lr_model.share.meta.json   (元数据)
```

### 2. 模型预测

```python
# 预测配置（使用字典格式的路径）
predict_config = {
    "model_path": {
        "alice": "/alice/models/lr_model.share",
        "bob": "/bob/models/lr_model.share"
    },
    "predict_data": {
        "alice": "/alice/data/test.csv",
        "bob": "/bob/data/test.csv"
    },
    "output_path": {
        "alice": "/alice/results/predictions.csv",
        "bob": "/bob/results/predictions.csv"
    },
    "receiver_party": "alice"
}

# 执行预测
result = TaskDispatcher.dispatch('ss_lr_predict', devices, predict_config)

# 保存的文件（只有接收方）
# Alice端:
#   /alice/results/predictions.csv  (预测结果)
# Bob端:
#   无预测结果文件（Bob不是接收方）
```

## 文件结构对比

### 改进前（单一路径）

```
/models/
├── lr_model.meta.json          # 主元数据（已删除）
├── lr_model.alice.share        # Alice的密文分片
├── lr_model.alice.json         # Alice的引用文件
├── lr_model.bob.share          # Bob的密文分片
└── lr_model.bob.json           # Bob的引用文件
```

**问题**: 所有文件在同一目录，不适合分布式部署

### 改进后（字典格式）

```
/alice/
└── models/
    ├── lr_model.share          # Alice的密文分片
    └── lr_model.share.meta.json # Alice的元数据

/bob/
└── models/
    ├── lr_model.share          # Bob的密文分片
    └── lr_model.share.meta.json # Bob的元数据
```

**优势**: 每个参与方的文件独立存储，适合分布式部署

## 测试更新

### 测试用例修改

```python
def test_secure_save_and_load(self, setup_devices):
    """测试安全模式保存和加载（不解密）"""
    devices, alice_path, bob_path = setup_devices
    
    # 使用字典格式的模型路径
    model_output = {
        "alice": f"{TEST_MODELS_DIR}/alice/lr_model_secure.share",
        "bob": f"{TEST_MODELS_DIR}/bob/lr_model_secure.share"
    }
    
    # 训练并保存模型
    task_config = {
        "train_data": {"alice": alice_path, "bob": bob_path},
        "features": ["f0", "f1", "f2", "f6", "f7"],
        "label": "y",
        "label_party": "alice",
        "model_output": model_output,
        "params": {"epochs": 3}
    }
    
    result = TaskDispatcher.dispatch('ss_lr', devices, task_config)
    
    # 验证文件存在
    assert os.path.exists(f"{model_output['alice']}.meta.json")
    assert os.path.exists(model_output['alice'])
    assert os.path.exists(f"{model_output['bob']}.meta.json")
    assert os.path.exists(model_output['bob'])
    
    # 加载模型
    model_info = load_ss_lr_model(model_output, spu_device, parties)
    assert model_info is not None
```

### 测试结果

```bash
pytest tests/unit/test_ml_task.py -v
```

**结果**: ✅ 3/3 全部通过
- `test_secure_save_and_load` ✅
- `test_secure_predict` ✅
- `test_share_files_are_different` ✅

## 向后兼容性

### 不兼容变更

**旧格式**（不再支持）:
```python
task_config = {
    "model_output": "/models/lr_model"  # ❌ 字符串格式
}
```

**新格式**（必须使用）:
```python
task_config = {
    "model_output": {                    # ✅ 字典格式
        "alice": "/alice/models/lr_model.share",
        "bob": "/bob/models/lr_model.share"
    }
}
```

### 迁移指南

如果有代码使用旧的字符串格式，需要更新为字典格式：

```python
# 旧代码
model_output = "/models/lr_model"

# 新代码
model_output = {
    "alice": "/alice/models/lr_model.share",
    "bob": "/bob/models/lr_model.share"
}
```

## 改进收益

### 1. 分布式部署支持

**改进前**: 所有文件在同一目录，不适合分布式场景  
**改进后**: 每个参与方独立存储，完全支持分布式部署

### 2. 路径灵活性

**改进前**: 只能指定基础路径，文件名由系统生成  
**改进后**: 可以为每个参与方指定完整路径，包括目录和文件名

### 3. 存储隔离

**改进前**: 所有参与方的文件混在一起  
**改进后**: 每个参与方的文件完全隔离

### 4. 实际部署场景

**场景**: Alice和Bob在不同的服务器上

**改进前**:
```
# 无法实现，因为只有一个路径
model_output = "/models/lr_model"
```

**改进后**:
```python
# 可以实现，每个参与方指定各自服务器的路径
model_output = {
    "alice": "/alice_server/models/lr_model.share",
    "bob": "/bob_server/models/lr_model.share"
}
```

## 技术亮点

1. ✅ **字典格式路径**: 每个参与方有独立的路径
2. ✅ **自动创建目录**: 保存时自动创建所需目录
3. ✅ **独立元数据**: 每个参与方有自己的元数据文件
4. ✅ **完整验证**: 验证所有参与方的路径都存在
5. ✅ **向后不兼容**: 强制使用新格式，避免混淆
6. ✅ **测试覆盖**: 所有测试都已更新并通过

## 总结

本次改进将模型保存和预测的路径格式从单一字符串改为字典格式，使得：

- ✅ 每个参与方可以将文件保存到各自的位置
- ✅ 完全支持分布式部署场景
- ✅ 路径更灵活，可以自定义目录结构
- ✅ 文件存储更隔离，更安全
- ✅ 符合实际生产环境的需求

**这是面向分布式部署的重要改进！** 🚀
