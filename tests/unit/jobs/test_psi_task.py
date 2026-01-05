"""
PSI任务单元测试

从原test_psi_task.py迁移而来
"""

import pytest
import os
from pathlib import Path
import secretflow as sf

from secretflow_task.task_dispatcher import TaskDispatcher

# 测试数据路径
TEST_DATA_DIR = str(Path(__file__).parent.parent.parent / "data")


@pytest.fixture(scope="module")
def setup_secretflow():
    """初始化SecretFlow环境"""
    print(f"\nSecretFlow version: {sf.__version__}")
    sf.init(parties=["alice", "bob"], address="local")
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    yield
    sf.shutdown()
    print("\nSecretFlow shutdown")


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
def prepare_psi_test_data():
    """准备PSI测试数据"""
    import pandas as pd
    
    alice_data = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "age": [25, 30, 35, 40, 45],
    })
    
    bob_data = pd.DataFrame({
        "id": [3, 4, 5, 6, 7],
        "income": [50000, 60000, 70000, 80000, 90000],
    })
    
    alice_path = os.path.join(TEST_DATA_DIR, "alice_psi.csv")
    bob_path = os.path.join(TEST_DATA_DIR, "bob_psi.csv")
    
    alice_data.to_csv(alice_path, index=False)
    bob_data.to_csv(bob_path, index=False)
    
    return {
        "alice": alice_path,
        "bob": bob_path,
    }


def test_psi_task(setup_devices, prepare_psi_test_data):
    """测试PSI任务"""
    devices = setup_devices
    data_paths = prepare_psi_test_data
    
    task_config = {
        "input_data": data_paths,
        "output_data": {
            "alice": os.path.join(TEST_DATA_DIR, "alice_psi_output.csv"),
            "bob": os.path.join(TEST_DATA_DIR, "bob_psi_output.csv"),
        },
        "keys": ["id"],
        "protocol": "ECDH_PSI_2PC",
    }
    
    result = TaskDispatcher.dispatch("psi", devices, task_config)
    
    assert result is not None
    assert "intersection_count" in result
    assert result["intersection_count"] == 3  # id: 3, 4, 5
    assert os.path.exists(task_config["output_data"]["alice"])
    assert os.path.exists(task_config["output_data"]["bob"])
    
    print(f"\nPSI结果: {result}")
