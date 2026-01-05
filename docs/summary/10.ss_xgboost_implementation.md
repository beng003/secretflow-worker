# SS-XGBoost 训练和预测功能实现总结

## 实现概述

**完成日期**: 2026-01-05  
**实现目标**: 实现基于SecretFlow的SS-XGBoost（Secret Sharing XGBoost）训练和预测功能

## 功能特性

### 1. SS-XGBoost训练
- ✅ 支持垂直分区数据的安全XGBoost训练
- ✅ 使用SPU（Secure Processing Unit）进行密态计算
- ✅ 支持字典格式的模型输出路径（每个参与方独立存储）
- ✅ 完整的参数配置支持

### 2. 模型保存和加载
- ✅ 安全保存模型（树结构和权重分片）
- ✅ 每个参与方只保存自己的模型分片
- ✅ 支持从分片重建完整模型
- ✅ 保存模型元数据（特征、参数等）

### 3. SS-XGBoost预测
- ✅ 使用保存的模型进行安全预测
- ✅ 预测结果只发送给指定接收方（使用`to_pyu`）
- ✅ 不泄露预测数据的统计信息
- ✅ 支持二分类和回归任务

## 实现细节

### 1. 核心函数

#### `_save_ss_xgb_model`
保存SS-XGBoost模型到各参与方。

**保存内容**:
- 模型元数据（JSON格式）
- 树结构（每个参与方的PYUObject）
- 树权重（SPUObject的密文分片）

**文件结构**:
```
/alice/models/
├── xgb_model.model.meta.json          # 元数据
├── xgb_model.model.tree_0.pkl         # 第0棵树的Alice分片
├── xgb_model.model.tree_1.pkl         # 第1棵树的Alice分片
├── xgb_model.model.weight_0.share     # 第0棵树权重的Alice分片
└── xgb_model.model.weight_1.share     # 第1棵树权重的Alice分片

/bob/models/
├── xgb_model.model.meta.json          # 元数据
├── xgb_model.model.tree_0.pkl         # 第0棵树的Bob分片
├── xgb_model.model.tree_1.pkl         # 第1棵树的Bob分片
├── xgb_model.model.weight_0.share     # 第0棵树权重的Bob分片
└── xgb_model.model.weight_1.share     # 第1棵树权重的Bob分片
```

#### `load_ss_xgb_model`
从各参与方的分片加载完整模型。

**加载过程**:
1. 读取元数据
2. 为每棵树加载各参与方的树结构分片
3. 使用`SPU.load`加载权重分片
4. 重建`XgbModel`对象

#### `execute_ss_xgboost`
执行SS-XGBoost训练任务。

**训练流程**:
```python
1. 验证配置
2. 读取垂直分区训练数据
3. 创建Xgb对象
4. 调用xgb.train()训练模型
5. 保存模型到各参与方
6. 返回训练结果
```

#### `execute_ss_xgb_predict`
执行SS-XGBoost预测任务。

**预测流程**:
```python
1. 验证配置
2. 加载模型
3. 读取预测数据
4. 使用model.predict(x_vdf, to_pyu=receiver_pyu)
5. 在接收方PYU上保存预测结果
6. 只返回预测数量（不泄露统计信息）
```

### 2. 训练参数

```python
xgb_params = {
    'num_boost_round': 10,        # 树的数量
    'max_depth': 5,               # 树的最大深度
    'learning_rate': 0.3,         # 学习率
    'objective': 'logistic',      # 目标函数 ('logistic' 或 'linear')
    'reg_lambda': 0.1,            # L2正则化系数
    'subsample': 1.0,             # 样本采样比例
    'colsample_by_tree': 1.0,     # 特征采样比例
    'base_score': 0.0,            # 初始预测分数
    'seed': 42                    # 随机种子
}
```

### 3. 模型元数据格式

```json
{
  "model_type": "ss_xgb",
  "version": "1.0.0",
  "objective": "RegType.Logistic",
  "base_score": 0.0,
  "features": ["f0", "f1", "f2"],
  "label": "y",
  "label_party": "alice",
  "parties": ["alice", "bob"],
  "num_trees": 3,
  "training_params": {
    "num_boost_round": 3,
    "max_depth": 3,
    "learning_rate": 0.3,
    "objective": "logistic",
    "reg_lambda": 0.1
  },
  "created_at": "2026-01-05T20:10:00",
  "secure_mode": true
}
```

## 使用示例

### 1. 训练模型

```python
from secretflow_task.task_dispatcher import TaskDispatcher

# 训练配置
train_config = {
    "train_data": {
        "alice": "/alice/data/train.csv",
        "bob": "/bob/data/train.csv"
    },
    "features": ["f0", "f1", "f2", "f6", "f7"],
    "label": "y",
    "label_party": "alice",
    "model_output": {
        "alice": "/alice/models/xgb_model.model",
        "bob": "/bob/models/xgb_model.model"
    },
    "params": {
        "num_boost_round": 10,
        "max_depth": 5,
        "learning_rate": 0.3,
        "objective": "logistic",
        "reg_lambda": 0.1
    }
}

# 执行训练
result = TaskDispatcher.dispatch('ss_xgb', devices, train_config)

# 返回结果
# {
#     "model_output": {...},
#     "num_trees": 10,
#     "secure_mode": True,
#     "training_params": {...}
# }
```

### 2. 模型预测

```python
# 预测配置
predict_config = {
    "model_path": {
        "alice": "/alice/models/xgb_model.model",
        "bob": "/bob/models/xgb_model.model"
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
result = TaskDispatcher.dispatch('ss_xgb_predict', devices, predict_config)

# 返回结果
# {
#     "output_path": {...},
#     "receiver_party": "alice",
#     "num_predictions": 1000,
#     "secure_mode": True
# }
```

### 3. 预测结果格式

预测结果CSV文件（只在接收方）:

```csv
probability,prediction
0.85,1
0.32,0
0.67,1
0.49,0
0.91,1
```

- `probability`: 预测为正类的概率（0到1之间）
- `prediction`: 根据阈值0.5判断的类别（0或1）

## 安全性特性

### 1. 模型保护

**树结构分片**:
- 每个参与方只保存自己特征对应的树分片
- 使用PYUObject保存，数据不离开参与方

**权重保护**:
- 使用SPU的`dump`机制保存密文分片
- 每个参与方只有权重的一部分密文
- 无法单独解密，需要所有参与方协作

### 2. 预测隐私保护

**数据流向**:
```
预测数据（各参与方）
  → SPU密态计算
  → 预测结果只发送给接收方（to_pyu）
  → 接收方本地保存
  → Driver只获取预测数量
```

**隐私保护措施**:
- ✅ 预测结果不经过driver
- ✅ 不返回统计信息（均值、标准差等）
- ✅ 只公开预测数量（非敏感信息）
- ✅ 其他参与方无法获取预测结果

### 3. 与SS-LR的一致性

SS-XGBoost的实现遵循与SS-LR相同的安全原则：
- 使用字典格式的路径（每个参与方独立存储）
- 使用`to_pyu`参数保护预测结果
- 不泄露统计信息
- 完整的单元测试覆盖

## 测试验证

### 测试用例

```python
class TestSSXGBoost:
    def test_ss_xgb_train(self, setup_devices):
        """测试SS-XGBoost训练"""
        # 训练模型并验证文件存在
        
    def test_ss_xgb_predict(self, setup_devices):
        """测试SS-XGBoost预测"""
        # 训练模型、执行预测、验证结果
```

### 测试结果

```bash
pytest tests/unit/test_ml_task.py::TestSSXGBoost -v
```

**结果**: ✅ 2/2 全部通过
- `test_ss_xgb_train` ✅ (30.39s)
- `test_ss_xgb_predict` ✅ (36.97s)

## 技术对比

### SS-XGBoost vs SS-LR

| 特性 | SS-LR | SS-XGBoost |
|-----|-------|-----------|
| 模型类型 | 线性模型 | 树模型 |
| 训练算法 | SGD | Boosting |
| 模型保存 | 权重分片 | 树结构+权重分片 |
| 预测方式 | 线性计算 | 树遍历+加权求和 |
| 安全机制 | SPU密态计算 | SPU密态计算 |
| 路径格式 | 字典格式 | 字典格式 |
| 隐私保护 | to_pyu | to_pyu |

### 优势

**SS-XGBoost的优势**:
- ✅ 更强的非线性拟合能力
- ✅ 自动特征选择
- ✅ 对异常值更鲁棒
- ✅ 支持分类和回归

**SS-LR的优势**:
- ✅ 训练速度更快
- ✅ 模型更简单
- ✅ 可解释性更强

## 性能考虑

### 训练性能

**影响因素**:
- 树的数量（`num_boost_round`）
- 树的深度（`max_depth`）
- 特征数量
- 样本数量
- SPU配置

**优化建议**:
- 减少树的数量和深度（在精度允许的情况下）
- 使用特征采样（`colsample_by_tree`）
- 使用样本采样（`subsample`）

### 预测性能

**预测时间** ∝ 树的数量 × 树的深度

**优化建议**:
- 使用较少的树
- 控制树的深度
- 批量预测

## 最佳实践

### 1. 参数选择

**二分类任务**:
```python
params = {
    'num_boost_round': 10,
    'max_depth': 5,
    'learning_rate': 0.3,
    'objective': 'logistic',
    'reg_lambda': 0.1
}
```

**回归任务**:
```python
params = {
    'num_boost_round': 10,
    'max_depth': 5,
    'learning_rate': 0.3,
    'objective': 'linear',
    'reg_lambda': 0.1
}
```

### 2. 模型调优

**过拟合**:
- 增加`reg_lambda`
- 减少`max_depth`
- 减少`num_boost_round`
- 使用`subsample`和`colsample_by_tree`

**欠拟合**:
- 增加`num_boost_round`
- 增加`max_depth`
- 增加`learning_rate`

### 3. 路径管理

**推荐的路径结构**:
```
/alice/
├── data/
│   ├── train.csv
│   └── test.csv
├── models/
│   └── xgb_model.model.*
└── results/
    └── predictions.csv

/bob/
├── data/
│   ├── train.csv
│   └── test.csv
└── models/
    └── xgb_model.model.*
```

## 常见问题

### Q1: 如何选择树的数量？

**A**: 
- 从较小的值开始（如10）
- 观察训练和验证性能
- 增加树的数量直到性能不再提升
- 考虑训练时间和模型大小

### Q2: 模型文件很大怎么办？

**A**:
- 减少树的数量
- 减少树的深度
- 使用特征采样
- 考虑模型压缩

### Q3: 预测速度慢怎么办？

**A**:
- 使用较少的树
- 减少树的深度
- 批量预测
- 考虑模型简化

### Q4: 如何处理不平衡数据？

**A**:
- 调整`base_score`
- 使用样本权重（如果支持）
- 调整分类阈值
- 使用重采样

## 与SecretFlow的集成

### API兼容性

本实现完全基于SecretFlow的官方API：
- `secretflow.ml.boost.ss_xgb_v.Xgb`
- `secretflow.ml.boost.ss_xgb_v.XgbModel`
- `secretflow.device.SPU`
- `secretflow.data.vertical.VDataFrame`

### 版本要求

- SecretFlow >= 1.12.0b0
- Python >= 3.10

## 未来改进

### 可能的增强功能

1. **模型评估**
   - 添加训练过程中的评估指标
   - 支持验证集
   - 早停机制

2. **特征重要性**
   - 计算特征重要性
   - 可视化支持

3. **模型压缩**
   - 树剪枝
   - 模型量化

4. **分布式优化**
   - 支持多SPU设备
   - 并行训练优化

## 总结

### 实现成果

1. ✅ **完整的SS-XGBoost训练功能**
   - 支持垂直分区数据
   - 完整的参数配置
   - 安全的模型保存

2. ✅ **安全的预测功能**
   - 使用`to_pyu`保护预测结果
   - 不泄露统计信息
   - 支持字典格式路径

3. ✅ **完善的测试覆盖**
   - 训练测试
   - 预测测试
   - 所有测试通过

4. ✅ **与SS-LR一致的设计**
   - 相同的路径格式
   - 相同的安全机制
   - 相同的API风格

### 适用场景

**推荐使用SS-XGBoost的场景**:
- ✅ 非线性关系明显的数据
- ✅ 需要自动特征选择
- ✅ 对异常值敏感的场景
- ✅ 需要更高预测精度

**推荐使用SS-LR的场景**:
- ✅ 线性关系明显的数据
- ✅ 需要快速训练
- ✅ 需要模型可解释性
- ✅ 数据量较大

**这是SecretFlow框架下完整的SS-XGBoost实现！** 🚀
