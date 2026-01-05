# Pytest环境配置修复总结

## 问题描述

**现象**: VS Code测试插件运行pytest时报错，但命令行运行正常

**错误信息**:
```
RuntimeError: PSI任务执行失败: ray::pyu_fn()
ModuleNotFoundError: No module named 'secretflow_task'
```

**原因分析**:
- 命令行运行pytest时，工作目录是项目根目录，`src/`自动在Python路径中
- VS Code测试插件运行时，Ray worker进程的`sys.path`不包含`src/`目录
- 导致Ray worker无法导入`secretflow_task`模块

## 解决方案

通过**三层配置**确保pytest能够正确找到`src`目录：

### 1. pyproject.toml配置 ✅

**文件**: `pyproject.toml`

**添加配置**:
```toml
[tool.pytest.ini_options]
pythonpath = ["src"]  # ← 关键配置
```

**作用**: pytest自动将`src`目录添加到`sys.path`

### 2. conftest.py配置 ✅

**文件**: `conftest.py`（项目根目录）

**内容**:
```python
import sys
from pathlib import Path

# 将src目录添加到Python路径
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
```

**作用**: pytest启动时立即将`src`添加到Python路径

### 3. VS Code settings.json配置 ✅

**文件**: `.vscode/settings.json`

**添加配置**:
```json
{
    "python.testing.cwd": "${workspaceFolder}",
    "python.testing.pytestPath": "${workspaceFolder}/.venv/bin/pytest"
}
```

**作用**: 
- 设置pytest工作目录为项目根目录
- 使用虚拟环境中的pytest

## 配置文件变更

### 修改的文件

1. **pyproject.toml**
   - 添加: `pythonpath = ["src"]`

2. **.vscode/settings.json**
   - 添加: `python.testing.cwd`
   - 添加: `python.testing.pytestPath`

3. **conftest.py** (新建)
   - 在pytest启动时添加`src`到Python路径

### 新建的文档

1. **docs/pytest_configuration.md**
   - 详细的配置说明
   - 问题排查指南
   - 最佳实践

2. **docs/summary/pytest_env_fix.md**
   - 本文档

## 验证结果

### 测试结果

```bash
pytest tests/unit/test_psi_task.py -v
```

**结果**: ✅ 19/19 全部通过

**测试覆盖**:
- PSI配置验证测试 ✅
- CSV行数统计测试 ✅
- PSI执行测试 ✅
- 多列PSI测试 ✅
- 任务分发器集成测试 ✅

### 环境兼容性

- ✅ 命令行运行pytest
- ✅ VS Code测试插件运行
- ✅ Ray worker能够导入模块
- ✅ IDE代码补全和分析正常

## 技术细节

### Python路径解析顺序

1. **conftest.py执行** (最先)
   ```python
   sys.path.insert(0, str(src_path))
   ```

2. **pytest读取配置**
   ```toml
   pythonpath = ["src"]
   ```

3. **VS Code设置工作目录**
   ```json
   "python.testing.cwd": "${workspaceFolder}"
   ```

### Ray Worker环境继承

当pytest运行涉及Ray的测试时：

```python
# 这个函数会在Ray worker中执行
intersection_count = reveal(devices[receiver](_count_csv_lines)(receiver_output_path))
```

**工作流程**:
1. 主进程的`sys.path`包含`src/`目录
2. Ray worker继承主进程的环境变量和Python路径
3. Worker能够成功导入`secretflow_task`模块
4. 函数正常执行

## 最佳实践

### 1. 项目结构

```
secretflow_test/
├── src/
│   └── secretflow_task/    # 源代码
├── tests/                   # 测试代码
├── conftest.py             # pytest配置
├── pyproject.toml          # 项目配置
└── .vscode/
    └── settings.json       # IDE配置
```

### 2. 导入规范

**推荐**:
```python
from secretflow_task.jobs.psi_task import execute_psi
from secretflow_task.task_dispatcher import TaskDispatcher
```

**不推荐**:
```python
from jobs.psi_task import execute_psi  # ❌ 相对导入
```

### 3. 测试路径

**推荐**:
```python
TEST_DATA_DIR = Path(__file__).parent.parent / "data"
```

**不推荐**:
```python
TEST_DATA_DIR = "tests/data"  # ❌ 依赖工作目录
```

## 问题排查

### 如果测试插件仍然报错

**步骤**:
1. 重启VS Code
2. 清除pytest缓存: `rm -rf .pytest_cache`
3. 在测试面板点击"刷新测试"
4. 检查虚拟环境是否激活

### 验证配置是否生效

**方法1**: 查看pytest输出
```bash
pytest --collect-only
```

**方法2**: 在测试中打印路径
```python
import sys
print("Python路径:", sys.path)
```

## 相关文档

- `docs/pytest_configuration.md` - 详细配置指南
- `.vscode/README.md` - VS Code配置说明
- `conftest.py` - pytest配置文件

## 总结

### 修复成果

1. ✅ **命令行运行正常**
   - pytest能够找到`src`目录
   - 所有测试通过

2. ✅ **测试插件运行正常**
   - VS Code测试面板能够发现和运行测试
   - 不再出现模块导入错误

3. ✅ **Ray worker正常**
   - worker进程能够导入模块
   - 分布式计算功能正常

4. ✅ **IDE功能正常**
   - 代码补全和跳转正常
   - 类型检查和分析正常

### 核心原则

**确保`src`目录在Python路径中，无论从哪里运行测试**

通过三层配置（pyproject.toml + conftest.py + VS Code settings），我们实现了：
- 开发环境一致性
- 测试环境可靠性
- 分布式计算兼容性

**问题彻底解决！** 🎉
