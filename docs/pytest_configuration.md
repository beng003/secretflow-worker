# Pytest环境配置说明

## 问题背景

在使用VS Code的pytest测试插件运行测试时，可能会遇到以下错误：

```
ModuleNotFoundError: No module named 'secretflow_task'
```

这是因为Ray worker进程无法找到项目的`src`目录，导致无法导入`secretflow_task`模块。

**为什么命令行运行成功，测试插件运行失败？**

- **命令行运行**: 工作目录是项目根目录，`src/`在Python路径中
- **测试插件运行**: 可能从不同目录启动，Ray worker的`sys.path`不包含`src/`

## 解决方案

我们通过以下三层配置确保pytest能够正确找到`src`目录：

### 1. pyproject.toml配置

在`pyproject.toml`中添加`pythonpath`配置：

```toml
[tool.pytest.ini_options]
addopts = "--ignore=tests/no_pytest"
testpaths = ["tests"]
norecursedirs = ["tests/no_pytest"]
pythonpath = ["src"]  # ← 关键配置
filterwarnings = [
    "ignore:os.fork\\(\\) was called:RuntimeWarning"
]
```

**作用**: pytest会自动将`src`目录添加到`sys.path`

### 2. conftest.py配置

在项目根目录创建`conftest.py`：

```python
"""
Pytest配置文件

配置pytest测试环境，确保src目录在Python路径中
"""

import sys
from pathlib import Path

# 将src目录添加到Python路径
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
```

**作用**: 在pytest启动时立即将`src`添加到Python路径

### 3. VS Code settings.json配置

在`.vscode/settings.json`中配置：

```json
{
    "python.analysis.extraPaths": [
        "${workspaceFolder}/src"
    ],
    "python.autoComplete.extraPaths": [
        "${workspaceFolder}/src"
    ],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ],
    "python.testing.unittestEnabled": false,
    "python.testing.cwd": "${workspaceFolder}",
    "python.testing.pytestPath": "${workspaceFolder}/.venv/bin/pytest"
}
```

**关键配置说明**:
- `python.testing.cwd`: 设置pytest工作目录为项目根目录
- `python.testing.pytestPath`: 使用虚拟环境中的pytest
- `python.analysis.extraPaths`: IDE代码分析时能找到模块

### 4. 环境变量配置（可选）

`.env`文件：

```bash
# Python路径配置
PYTHONPATH=${PYTHONPATH}:${PWD}/src
```

## 配置验证

### 命令行测试

```bash
# 运行单个测试
pytest tests/unit/test_psi_task.py::TestExecutePSI::test_execute_psi_success -v

# 运行所有测试
pytest tests/unit/ -v
```

### VS Code测试插件

1. 打开测试面板（Testing视图）
2. 点击刷新按钮重新发现测试
3. 运行任意测试
4. 应该能够成功运行，不再出现模块导入错误

## 工作原理

### 配置生效顺序

1. **conftest.py**: pytest启动时首先执行，将`src`添加到`sys.path`
2. **pyproject.toml**: pytest读取配置，进一步确认`pythonpath`设置
3. **VS Code settings**: IDE层面确保工作目录和pytest路径正确

### Ray Worker环境

当pytest运行涉及Ray的测试时：

```python
# 在PYU上执行的函数
intersection_count = reveal(devices[receiver](_count_csv_lines)(receiver_output_path))
```

Ray worker进程会：
1. 继承主进程的`sys.path`
2. 能够找到`secretflow_task`模块
3. 成功导入并执行函数

## 常见问题

### Q1: 测试插件仍然报错怎么办？

**解决方法**:
1. 重启VS Code
2. 清除pytest缓存: `rm -rf .pytest_cache`
3. 在测试面板点击"刷新测试"按钮

### Q2: 命令行运行正常，插件运行失败？

**检查**:
- VS Code是否从项目根目录打开
- `.vscode/settings.json`中的`python.testing.cwd`是否正确
- 虚拟环境是否激活

### Q3: 如何验证配置是否生效？

**验证方法**:
```python
# 在测试文件开头添加
import sys
print("Python路径:", sys.path)
```

运行测试，检查输出中是否包含`/path/to/project/src`

## 最佳实践

### 1. 保持配置一致

确保以下配置文件同步：
- `pyproject.toml`
- `conftest.py`
- `.vscode/settings.json`

### 2. 使用相对导入

在`src`目录内的模块中使用相对导入：

```python
# 推荐
from secretflow_task.jobs.psi_task import execute_psi

# 不推荐
from jobs.psi_task import execute_psi
```

### 3. 测试隔离

确保测试不依赖特定的工作目录：

```python
# 使用绝对路径
TEST_DATA_DIR = Path(__file__).parent.parent / "data"

# 不要使用相对路径
# TEST_DATA_DIR = "tests/data"  # ❌
```

## 参考资料

- [Pytest Configuration](https://docs.pytest.org/en/stable/reference/customize.html)
- [VS Code Python Testing](https://code.visualstudio.com/docs/python/testing)
- [Ray Documentation](https://docs.ray.io/)

## 总结

通过三层配置（pyproject.toml + conftest.py + VS Code settings），我们确保了：

✅ 命令行运行pytest正常  
✅ VS Code测试插件运行正常  
✅ Ray worker能够找到模块  
✅ IDE代码补全和分析正常  

**核心原则**: 确保`src`目录在Python路径中，无论从哪里运行测试。
