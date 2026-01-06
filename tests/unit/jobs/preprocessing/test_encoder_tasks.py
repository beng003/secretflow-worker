"""
Encoder预处理任务测试

测试LabelEncoder和OneHotEncoder任务
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
    
    alice_data = pd.DataFrame({
        "gender": ["M", "F", "M", "F", "M"] * 20,
        "city": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Beijing"] * 20,
    })
    
    bob_data = pd.DataFrame({
        "education": ["Bachelor", "Master", "PhD", "Bachelor", "Master"] * 20,
        "occupation": ["Engineer", "Teacher", "Doctor", "Engineer", "Teacher"] * 20,
    })
    
    alice_path = os.path.join(TEST_DATA_DIR, "alice_encoder.csv")
    bob_path = os.path.join(TEST_DATA_DIR, "bob_encoder.csv")
    
    alice_data.to_csv(alice_path, index=False)
    bob_data.to_csv(bob_path, index=False)
    
    return {
        "alice": alice_path,
        "bob": bob_path,
    }


def test_label_encoder(setup_devices, prepare_test_data):
    """测试LabelEncoder任务"""
    devices = setup_devices
    data_paths = prepare_test_data
    
    task_config = {
        "input_data": data_paths,
        "output_data": {
            "alice": os.path.join(TEST_DATA_DIR, "alice_label_encoded.csv"),
            "bob": os.path.join(TEST_DATA_DIR, "bob_label_encoded.csv"),
        },
        "columns": ["gender", "city", "education", "occupation"],
    }
    
    result = TaskDispatcher.dispatch("label_encoder", devices, task_config)
    
    assert result is not None
    assert "output_paths" in result
    assert os.path.exists(task_config["output_data"]["alice"])
    assert os.path.exists(task_config["output_data"]["bob"])
    
    print(f"\nLabelEncoder结果: {result}")


def test_onehot_encoder(setup_devices, prepare_test_data):
    """测试OneHotEncoder任务"""
    devices = setup_devices
    data_paths = prepare_test_data
    
    task_config = {
        "input_data": data_paths,
        "output_data": {
            "alice": os.path.join(TEST_DATA_DIR, "alice_onehot_encoded.csv"),
            "bob": os.path.join(TEST_DATA_DIR, "bob_onehot_encoded.csv"),
        },
        "columns": ["gender", "education"],
        "drop": "first",
    }
    
    result = TaskDispatcher.dispatch("onehot_encoder", devices, task_config)
    
    assert result is not None
    assert "output_paths" in result
    assert os.path.exists(task_config["output_data"]["alice"])
    assert os.path.exists(task_config["output_data"]["bob"])
    
    print(f"\nOneHotEncoder结果: {result}")
