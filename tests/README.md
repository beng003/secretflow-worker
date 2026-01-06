# Tests目录说明

## 目录结构

```
tests/
├── README.md                    # 本文件
├── conftest.py                  # Pytest配置和共享fixtures
├── data/                        # 测试数据目录
│   └── integration/             # 集成测试数据
├── models/                      # 测试模型目录
│   └── integration/             # 集成测试模型
├── unit/                        # 单元测试
│   ├── test_task_dispatcher.py  # 任务分发器测试
│   └── jobs/                    # Jobs任务测试
│       ├── test_psi_task.py     # PSI任务测试
│       ├── linear/              # Linear模型测试
│       │   └── test_ss_lr_task.py
│       ├── boost/               # Boost模型测试
│       │   └── test_ss_xgb_task.py
│       ├── preprocessing/       # 预处理任务测试
│       │   ├── test_scaler_tasks.py
│       │   └── test_encoder_tasks.py
│       ├── stats/               # 统计分析任务测试
│       │   ├── test_table_statistics_task.py
│       │   ├── test_pearson_correlation_task.py
│       │   └── test_vif_task.py
│       └── evaluation/          # 模型评估任务测试
│           ├── test_biclassification_eval_task.py
│           └── test_regression_eval_task.py
├── integration/                 # 集成测试
│   └── test_ml_workflow.py      # 完整ML工作流测试
└── no_pytest/                   # 非pytest测试（保留）
```

## 测试组织原则

### 1. 模块化组织

测试目录结构与源代码目录结构一一对应：

| 源代码 | 测试代码 |
|-------|---------|
| `src/secretflow_task/jobs/psi_task.py` | `tests/unit/jobs/test_psi_task.py` |
| `src/secretflow_task/jobs/linear/ss_lr_task.py` | `tests/unit/jobs/linear/test_ss_lr_task.py` |
| `src/secretflow_task/jobs/boost/ss_xgb_task.py` | `tests/unit/jobs/boost/test_ss_xgb_task.py` |
| `src/secretflow_task/jobs/preprocessing/scaler/` | `tests/unit/jobs/preprocessing/test_scaler_tasks.py` |
| `src/secretflow_task/jobs/stats/` | `tests/unit/jobs/stats/` |
| `src/secretflow_task/jobs/evaluation/` | `tests/unit/jobs/evaluation/` |

### 2. 测试类型

- **单元测试** (`unit/`): 测试单个任务的功能
- **集成测试** (`integration/`): 测试多个任务的端到端工作流

### 3. 测试数据管理

- 测试数据统一存放在 `tests/data/` 目录
- 测试模型统一存放在 `tests/models/` 目录
- 使用相对路径引用测试数据

## 运行测试

### 运行所有测试

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 运行所有集成测试
pytest tests/integration/ -v

# 运行所有测试
pytest tests/ -v
```

### 运行特定模块测试

```bash
# 运行Linear模型测试
pytest tests/unit/jobs/linear/ -v

# 运行Preprocessing测试
pytest tests/unit/jobs/preprocessing/ -v

# 运行Stats测试
pytest tests/unit/jobs/stats/ -v

# 运行Evaluation测试
pytest tests/unit/jobs/evaluation/ -v
```

### 运行特定测试文件

```bash
# 运行SS-LR测试
pytest tests/unit/jobs/linear/test_ss_lr_task.py -v

# 运行表统计测试
pytest tests/unit/jobs/stats/test_table_statistics_task.py -v

# 运行完整工作流测试
pytest tests/integration/test_ml_workflow.py -v
```

### 运行特定测试函数

```bash
# 运行SS-LR训练测试
pytest tests/unit/jobs/linear/test_ss_lr_task.py::test_ss_lr_train -v

# 运行完整工作流测试
pytest tests/integration/test_ml_workflow.py::test_complete_ml_workflow -v -s
```

### 测试选项

```bash
# 显示详细输出
pytest tests/ -v

# 显示print输出
pytest tests/ -s

# 显示测试覆盖率
pytest tests/ --cov=src/secretflow_task

# 并行运行测试
pytest tests/ -n auto

# 只运行失败的测试
pytest tests/ --lf

# 运行到第一个失败就停止
pytest tests/ -x
```

## 编写测试

### 测试文件命名

- 测试文件以 `test_` 开头
- 文件名与被测试的源文件对应
- 例如：`ss_lr_task.py` → `test_ss_lr_task.py`

### 测试函数命名

- 测试函数以 `test_` 开头
- 使用描述性的函数名
- 例如：`test_ss_lr_train`, `test_table_statistics`

### Fixture使用

```python
@pytest.fixture(scope="module")
def setup_secretflow():
    """初始化SecretFlow环境"""
    sf.init(parties=["alice", "bob"], address="local")
    yield
    sf.shutdown()

@pytest.fixture(scope="module")
def setup_devices(setup_secretflow):
    """创建SecretFlow设备"""
    alice = sf.PYU("alice")
    bob = sf.PYU("bob")
    spu = sf.SPU(sf.utils.testing.cluster_def(["alice", "bob"]))
    
    return {"alice": alice, "bob": bob, "spu": spu}
```

### 测试示例

```python
def test_standard_scaler(setup_devices, prepare_test_data):
    """测试StandardScaler任务"""
    devices = setup_devices
    data_paths = prepare_test_data
    
    task_config = {
        "input_data": data_paths,
        "output_data": {...},
        "columns": ["age", "income"],
        "with_mean": True,
        "with_std": True,
    }
    
    result = TaskDispatcher.dispatch("standard_scaler", devices, task_config)
    
    assert result is not None
    assert "output_paths" in result
    assert os.path.exists(task_config["output_data"]["alice"])
```

## 测试最佳实践

### 1. 测试隔离

- 每个测试函数独立运行
- 使用fixture准备和清理测试环境
- 避免测试之间的依赖

### 2. 测试数据

- 使用小规模测试数据（100-1000条）
- 测试数据应该可重现（固定随机种子）
- 避免使用真实敏感数据

### 3. 断言清晰

- 使用明确的断言语句
- 提供有意义的错误信息
- 测试关键功能点

### 4. 测试覆盖

- 测试正常流程
- 测试异常情况
- 测试边界条件

### 5. 性能考虑

- 单元测试应该快速执行（秒级）
- 集成测试可以较慢（分钟级）
- 使用合适的scope避免重复初始化

## 常见问题

### Q: 测试失败怎么办？

A: 查看详细错误信息，检查：
1. SecretFlow环境是否正确初始化
2. 测试数据是否正确生成
3. 任务配置是否正确
4. 设备配置是否正确

### Q: 如何调试测试？

A: 使用以下方法：
1. 添加 `-s` 参数查看print输出
2. 使用 `pytest --pdb` 在失败时进入调试器
3. 在测试中添加日志输出
4. 检查生成的测试数据和模型文件

### Q: 测试运行很慢怎么办？

A: 优化方法：
1. 减少测试数据量
2. 使用 `scope="module"` 共享fixture
3. 使用 `-n auto` 并行运行测试
4. 只运行需要的测试

## 贡献指南

### 添加新测试

1. 在对应的测试目录下创建测试文件
2. 遵循现有的测试结构和命名规范
3. 使用共享的fixture
4. 添加清晰的测试文档字符串

### 更新测试

1. 保持测试与源代码同步
2. 更新测试时同步更新文档
3. 确保所有测试通过

## 参考资料

- [Pytest文档](https://docs.pytest.org/)
- [SecretFlow文档](https://www.secretflow.org.cn/)
- [项目文档](../docs/)
