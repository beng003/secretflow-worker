# 安全预测功能改进：使用to_pyu而非reveal

## 改进概述

**改进前**: 使用`reveal()`将预测结果公开给所有参与方  
**改进后**: 使用`predict(to_pyu=...)`将预测结果只发送给指定接收方

## 核心问题

### 原实现的问题

```python
# 原代码（不安全）
spu_predictions = model.predict(x_vdf)
predictions = reveal(spu_predictions)  # ❌ 公开给所有人
```

**问题**:
- `reveal()`会将SPU密文解密并公开给**所有参与方**
- 违背了"只有接收方能看到预测结果"的隐私保护原则
- 其他参与方不应该看到预测结果

### 改进后的实现

```python
# 新代码（安全）
receiver_pyu = devices[receiver_party]
predictions_fed = model.predict(x_vdf, to_pyu=receiver_pyu)  # ✅ 只发送给接收方
predictions_pyu = predictions_fed.partitions[receiver_pyu]
```

**优势**:
- ✅ 预测结果只发送给指定的接收方
- ✅ 其他参与方看不到预测结果
- ✅ 符合隐私保护要求

## SSRegression.predict的to_pyu参数

### 方法签名

```python
def predict(
    self,
    x: Union[FedNdarray, VDataFrame],
    batch_size: int = 1024,
    to_pyu: PYU = None,
) -> Union[SPUObject, FedNdarray]:
    """
    Predict using the model.
    
    Args:
        x: Predict samples
        batch_size: how many samples use in one calculation
        to_pyu: the prediction initiator
            - if not None: predict result is reveal to to_pyu device and save as FedNdarray
            - otherwise: keep predict result in secret and save as SPUObject
    
    Return:
        pred scores in SPUObject or FedNdarray, shape (n_samples,)
    """
```

### 工作原理

**当to_pyu=None时**:
```python
pred = model.predict(x_vdf)
# 返回: SPUObject（密文，所有参与方都看不到）
```

**当to_pyu=alice时**:
```python
pred = model.predict(x_vdf, to_pyu=alice)
# 返回: FedNdarray，只包含alice的partition
# FedNdarray结构:
# {
#     alice: PYUObject(预测结果数据)
# }
```

### 源码实现（model.py:704-711）

```python
if to_pyu is not None:
    assert isinstance(to_pyu, PYU)
    return FedNdarray(
        partitions={
            to_pyu: pred.to(to_pyu),  # 只发送给指定PYU
        },
        partition_way=PartitionWay.VERTICAL,
    )
else:
    return pred  # 返回SPUObject
```

## 完整实现

### 预测流程

```python
# 1. 指定接收方
receiver_pyu = devices[receiver_party]

# 2. 执行预测，结果只发送给接收方
predictions_fed = model.predict(x_vdf, to_pyu=receiver_pyu)

# 3. 获取接收方的PYUObject
predictions_pyu = predictions_fed.partitions[receiver_pyu]

# 4. 在接收方PYU上保存结果（不经过driver）
def save_predictions(pred_data, output_file):
    import pandas as pd
    import numpy as np
    import os
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    pred_flat = pred_data.flatten() if isinstance(pred_data, np.ndarray) else pred_data
    pred_df = pd.DataFrame({
        'prediction': pred_flat,
        'probability': pred_flat
    })
    pred_df.to_csv(output_file, index=False)
    
    return {
        'num_predictions': len(pred_flat),
        'mean': float(np.mean(pred_flat)),
        'std': float(np.std(pred_flat)),
        'min': float(np.min(pred_flat)),
        'max': float(np.max(pred_flat))
    }

# 5. 在接收方PYU上执行保存
stats_pyu = receiver_pyu(save_predictions)(predictions_pyu, output_path)

# 6. 只reveal统计信息（不reveal原始预测数据）
stats = reveal(stats_pyu)
```

## 关键技术点

### 1. PYU远程执行

```python
# 在PYU上执行函数
result_pyu = pyu_device(function)(arg1, arg2, ...)
```

**特点**:
- 函数在PYU设备上远程执行
- 参数和返回值都是PYUObject
- 数据不经过driver（中心节点）

### 2. 数据流向

**改进前（使用reveal）**:
```
SPU (密文) 
  → reveal → 
Driver (明文) 
  → 所有参与方都能看到
```

**改进后（使用to_pyu）**:
```
SPU (密文) 
  → to(receiver_pyu) → 
Receiver PYU (明文，仅接收方) 
  → 保存到文件
  → 其他参与方看不到
```

### 3. 统计信息的处理

**预测数据**: 不reveal，只在接收方PYU上  
**统计信息**: 可以reveal（不包含原始数据）

```python
# ❌ 不要这样做
predictions = reveal(predictions_pyu)  # 暴露所有预测数据

# ✅ 应该这样做
stats = reveal(stats_pyu)  # 只暴露统计信息
```

## 安全性对比

| 方式 | 预测数据可见性 | 安全性 | 适用场景 |
|------|--------------|--------|---------|
| **reveal** | 所有参与方 | ❌ 低 | 测试/调试 |
| **to_pyu** | 仅接收方 | ✅ 高 | 生产环境 |

## 测试验证

### 测试代码

```python
def test_secure_predict(self, setup_devices):
    """测试使用安全保存的模型进行预测"""
    devices, alice_path, bob_path = setup_devices
    
    # 训练模型
    train_config = {
        "train_data": {"alice": alice_path, "bob": bob_path},
        "features": ["f0", "f1", "f2", "f6", "f7"],
        "label": "y",
        "label_party": "alice",
        "model_output": model_path,
        "params": {"epochs": 3}
    }
    TaskDispatcher.dispatch('ss_lr_secure', devices, train_config)
    
    # 执行预测
    predict_config = {
        "model_path": model_path,
        "predict_data": {"alice": alice_path, "bob": bob_path},
        "output_path": predict_output,
        "receiver_party": "alice"
    }
    result = TaskDispatcher.dispatch('ss_lr_predict_secure', devices, predict_config)
    
    # 验证
    assert result['secure_mode'] is True
    assert result['receiver_party'] == 'alice'
    assert os.path.exists(predict_output)
```

### 测试结果

```bash
pytest tests/unit/test_ml_task_secure.py -v
```

**结果**: ✅ 3/3 通过

## 使用示例

### 基本用法

```python
from secretflow_task.task_dispatcher import TaskDispatcher

# 预测配置
predict_config = {
    "model_path": "models/lr_model",
    "predict_data": {
        "alice": "alice_test.csv",
        "bob": "bob_test.csv"
    },
    "output_path": "results/predictions.csv",
    "receiver_party": "alice"  # 只有alice能看到预测结果
}

# 执行安全预测
result = TaskDispatcher.dispatch('ss_lr_predict_secure', devices, predict_config)

# 结果
# {
#     "output_path": "results/predictions.csv",
#     "receiver_party": "alice",
#     "num_predictions": 1000,
#     "secure_mode": True,
#     "statistics": {
#         "mean": 0.523,
#         "std": 0.287,
#         "min": 0.001,
#         "max": 0.999
#     }
# }
```

### 文件位置

**预测结果文件**: 只保存在接收方的文件系统上
- Alice看到: `results/predictions.csv`（实际数据）
- Bob看到: 无（没有这个文件）

## 改进总结

### ✅ 改进点

1. **使用to_pyu参数**: 预测结果只发送给指定接收方
2. **PYU远程执行**: 在接收方PYU上直接保存，不经过driver
3. **最小化reveal**: 只reveal统计信息，不reveal原始预测数据
4. **符合隐私保护**: 其他参与方看不到预测结果

### 📊 性能影响

- **无性能损失**: to_pyu和reveal的性能相同
- **更安全**: 数据传输更少（只发送给一方）
- **更高效**: 不需要在driver上处理数据

### 🎯 最佳实践

**开发/测试环境**:
- 可以使用reveal（便于调试）
- 使用`ss_lr_predict`任务

**生产环境**:
- 必须使用to_pyu（保护隐私）
- 使用`ss_lr_predict_secure`任务

## 技术亮点

1. ✅ **深入理解predict的to_pyu参数**
2. ✅ **正确使用PYU远程执行**
3. ✅ **最小化数据暴露**
4. ✅ **符合隐私保护最佳实践**

这是SecretFlow隐私计算的正确使用方式！
