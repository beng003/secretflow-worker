"""
TableStatistics表统计任务测试
"""

import pytest
import os
from pathlib import Path
import secretflow as sf

from secretflow_task.task_dispatcher import TaskDispatcher

# 测试数据路径
TEST_DATA_DIR = str(Path(__file__).parent.parent.parent.parent / "data")


@pytest.fixture(scope="module")
def setup_secretflow():
    """初始化SecretFlow环境"""
    sf.init(parties=["alice", "bob"], address="local")
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    yield
    sf.shutdown()


@pytest.fixture(scope="module")
def setup_devices(setup_secretflow):
    """创建SecretFlow设备"""
    alice = sf.PYU("alice")
    bob = sf.PYU("bob")
    
    devices = {
        "alice": alice,
        "bob": bob,
    }
    return devices


@pytest.fixture(scope="module")
def prepare_test_data():
    """准备测试数据"""
    import pandas as pd
    import numpy as np
    
    np.random.seed(42)
    
    alice_data = pd.DataFrame({
        "age": np.random.randint(20, 60, 100),
        "income": np.random.randint(30000, 150000, 100),
    })
    
    bob_data = pd.DataFrame({
        "education_years": np.random.randint(10, 20, 100),
        "work_years": np.random.randint(0, 30, 100),
    })
    
    alice_path = os.path.join(TEST_DATA_DIR, "alice_stats.csv")
    bob_path = os.path.join(TEST_DATA_DIR, "bob_stats.csv")
    
    alice_data.to_csv(alice_path, index=False)
    bob_data.to_csv(bob_path, index=False)
    
    return {
        "alice": alice_path,
        "bob": bob_path,
    }


def test_table_statistics(setup_devices, prepare_test_data):
    """测试表统计任务"""
    devices = setup_devices
    data_paths = prepare_test_data
    
    task_config = {
        "input_data": data_paths,
        "output_report": os.path.join(TEST_DATA_DIR, "table_stats_report.json"),
        "columns": ["age", "income", "education_years", "work_years"],
    }
    
    result = TaskDispatcher.dispatch("table_statistics", devices, task_config)
    
    assert result is not None
    assert "output_report" in result
    assert "num_columns" in result
    assert result["num_columns"] == 4
    assert os.path.exists(task_config["output_report"])
    
    print(f"\n表统计结果: {result}")
