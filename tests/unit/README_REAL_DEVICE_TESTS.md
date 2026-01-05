# 真实设备测试说明

## 概述

`test_psi_task_real.py` 使用真实的SecretFlow设备进行集成测试，而不是Mock对象。这更接近实际运行环境。

## 测试文件

- **test_psi_task.py**: 使用Mock对象的单元测试（快速，不需要SecretFlow环境）
- **test_psi_task_real.py**: 使用真实SecretFlow设备的集成测试（需要SecretFlow环境）

## 运行要求

### 1. 环境要求

需要安装SecretFlow及其依赖：

```bash
# 使用uv安装（推荐）
uv sync

# 或使用pip安装
pip install secretflow==1.12.0b0
```

### 2. 运行真实设备测试

```bash
# 运行真实设备测试
pytest tests/unit/test_psi_task_real.py -v -s

# 运行特定测试
pytest tests/unit/test_psi_task_real.py::TestPSIWithRealDevices::test_psi_single_column -v -s
```

### 3. 运行Mock测试（不需要SecretFlow）

```bash
# 运行Mock测试
pytest tests/unit/test_psi_task.py -v
```

## 测试对比

### Mock测试 (test_psi_task.py)

**优点**:
- ✅ 快速执行（0.07秒）
- ✅ 不需要SecretFlow环境
- ✅ 适合CI/CD流水线
- ✅ 测试覆盖率高

**缺点**:
- ❌ 不测试真实的PSI执行
- ❌ 可能遗漏实际运行时的问题

**测试内容**:
- 配置验证逻辑
- 参数检查
- 错误处理
- 边界条件

### 真实设备测试 (test_psi_task_real.py)

**优点**:
- ✅ 测试真实的PSI执行
- ✅ 验证与SecretFlow的集成
- ✅ 发现实际运行时的问题
- ✅ 端到端验证

**缺点**:
- ❌ 执行较慢
- ❌ 需要SecretFlow环境
- ❌ 可能受环境影响

**测试内容**:
- 单列PSI执行
- 多列PSI执行
- 通过TaskDispatcher调用
- 实际文件读写

## 测试数据

### 数据准备

测试使用Iris数据集，自动生成测试数据：

```python
# 在setup_secretflow fixture中自动准备
data, target = load_iris(return_X_y=True, as_frame=True)
data['uid'] = np.arange(len(data)).astype('str')
data['month'] = ['Jan'] * 75 + ['Feb'] * 75

# 创建alice和bob的数据
da = data.sample(frac=0.9)  # alice: 90%的数据
db = data.sample(frac=0.8)  # bob: 80%的数据
```

### 数据文件

- `tests/data/alice.csv` - Alice的输入数据
- `tests/data/bob.csv` - Bob的输入数据
- `tests/data/alice_psi_*.csv` - PSI输出结果
- `tests/data/bob_psi_*.csv` - PSI输出结果

## 测试用例

### 1. test_psi_single_column

测试单列PSI求交：

```python
task_config = {
    "keys": {"alice": ["uid"], "bob": ["uid"]},
    "protocol": "KKRT_PSI_2PC"
}
```

### 2. test_psi_multi_column

测试多列PSI求交：

```python
task_config = {
    "keys": {"alice": ["uid", "month"], "bob": ["uid", "month"]}
}
```

### 3. test_psi_via_dispatcher

测试通过TaskDispatcher调用PSI。

## 设备初始化

参考 `local_test.py` 的方式：

```python
# 初始化SecretFlow
sf.init(parties=['alice', 'bob'], address="local")

# 创建设备
alice = sf.PYU('alice')
bob = sf.PYU('bob')
spu = sf.SPU(sf.utils.testing.cluster_def(['alice', 'bob']))

devices = {
    'alice': alice,
    'bob': bob,
    'spu': spu
}
```

## 清理

测试完成后自动清理：

```python
# 在fixture的teardown中
sf.shutdown()
```

## 建议的测试策略

### 开发阶段

1. 先运行Mock测试验证逻辑正确性
2. 再运行真实设备测试验证集成

```bash
# 快速验证
pytest tests/unit/test_psi_task.py -v

# 完整验证
pytest tests/unit/test_psi_task_real.py -v -s
```

### CI/CD流水线

- 使用Mock测试（快速反馈）
- 定期运行真实设备测试（夜间构建）

### 生产部署前

- 必须运行真实设备测试
- 验证所有测试用例通过

## 故障排查

### 问题1: ModuleNotFoundError: No module named 'secretflow'

**解决方案**:
```bash
uv sync
# 或
pip install secretflow==1.12.0b0
```

### 问题2: 测试数据目录不存在

**解决方案**:
测试会自动创建 `tests/data/` 目录并生成测试数据。

### 问题3: PSI执行失败

**检查**:
- SecretFlow版本是否正确
- 设备初始化是否成功
- 输入文件是否存在

## 总结

- **Mock测试**: 日常开发使用，快速验证逻辑
- **真实设备测试**: 集成验证，确保实际可用

两种测试互补，共同保证代码质量。
