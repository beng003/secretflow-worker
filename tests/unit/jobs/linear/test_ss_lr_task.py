"""
SS-LR单元测试

测试使用SPU的dump/load机制保存和加载密文分片，
以及使用to_pyu参数进行安全预测
"""

import pytest
import os
from pathlib import Path
import secretflow as sf

from secretflow_task.jobs.linear.ss_lr_task import load_ss_lr_model
from secretflow_task.task_dispatcher import TaskDispatcher

# 测试数据路径
TEST_DATA_DIR = str(Path(__file__).parent.parent.parent.parent / "data")
TEST_MODELS_DIR = str(Path(__file__).parent.parent.parent.parent / "models")


@pytest.fixture(scope="module")
def setup_secretflow():
    """初始化SecretFlow环境"""
    print(f"\nSecretFlow version: {sf.__version__}")
    sf.init(parties=["alice", "bob"], address="local")
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    os.makedirs(TEST_MODELS_DIR, exist_ok=True)
    yield
    sf.shutdown()
    print("\nSecretFlow shutdown")


@pytest.fixture(scope="module")
def setup_devices(setup_secretflow):
    """创建真实的SecretFlow设备"""
    alice = sf.PYU("alice")
    bob = sf.PYU("bob")
    spu = sf.SPU(sf.utils.testing.cluster_def(["alice", "bob"]))

    devices = {
        "alice": alice,
        "bob": bob,
        "spu": spu,
    }
    return devices


@pytest.fixture(scope="module")
def prepare_test_data(setup_devices):
    """准备测试数据"""
    import pandas as pd
    import numpy as np

    np.random.seed(42)
    n_samples = 1000

    alice_data = pd.DataFrame({
        "age": np.random.randint(20, 60, n_samples),
        "income": np.random.randint(30000, 150000, n_samples),
    })

    bob_data = pd.DataFrame({
        "education_years": np.random.randint(10, 20, n_samples),
        "work_years": np.random.randint(0, 30, n_samples),
        "label": np.random.randint(0, 2, n_samples),
    })

    alice_train_path = os.path.join(TEST_DATA_DIR, "alice_train_lr.csv")
    bob_train_path = os.path.join(TEST_DATA_DIR, "bob_train_lr.csv")
    alice_test_path = os.path.join(TEST_DATA_DIR, "alice_test_lr.csv")
    bob_test_path = os.path.join(TEST_DATA_DIR, "bob_test_lr.csv")

    alice_data.to_csv(alice_train_path, index=False)
    bob_data.to_csv(bob_train_path, index=False)
    alice_data.iloc[:100].to_csv(alice_test_path, index=False)
    bob_data.iloc[:100].to_csv(bob_test_path, index=False)

    return {
        "alice_train": alice_train_path,
        "bob_train": bob_train_path,
        "alice_test": alice_test_path,
        "bob_test": bob_test_path,
    }


def test_ss_lr_train(setup_devices, prepare_test_data):
    """测试SS-LR训练任务"""
    devices = setup_devices
    data_paths = prepare_test_data

    task_config = {
        "train_data": {
            "alice": data_paths["alice_train"],
            "bob": data_paths["bob_train"],
        },
        "model_output": {
            "alice": os.path.join(TEST_MODELS_DIR, "ss_lr_alice.model"),
            "bob": os.path.join(TEST_MODELS_DIR, "ss_lr_bob.model"),
        },
        "features": ["age", "income", "education_years", "work_years"],
        "label": "label",
        "label_party": "bob",
        "epochs": 3,
        "learning_rate": 0.1,
        "batch_size": 128,
        "sig_type": "t1",
        "reg_type": "logistic",
        "penalty": "l2",
        "l2_norm": 0.1,
    }

    result = TaskDispatcher.dispatch("ss_logistic_regression", devices, task_config)

    assert result is not None
    assert "model_paths" in result
    assert result["secure_mode"] is True
    assert os.path.exists(task_config["model_output"]["alice"])
    assert os.path.exists(task_config["model_output"]["bob"])

    print(f"\n训练结果: {result}")


def test_ss_lr_predict(setup_devices, prepare_test_data):
    """测试SS-LR预测任务"""
    devices = setup_devices
    data_paths = prepare_test_data

    task_config = {
        "model_path": {
            "alice": os.path.join(TEST_MODELS_DIR, "ss_lr_alice.model"),
            "bob": os.path.join(TEST_MODELS_DIR, "ss_lr_bob.model"),
        },
        "predict_data": {
            "alice": data_paths["alice_test"],
            "bob": data_paths["bob_test"],
        },
        "output_path": {
            "bob": os.path.join(TEST_DATA_DIR, "ss_lr_predictions.csv"),
        },
        "receiver_party": "bob",
    }

    result = TaskDispatcher.dispatch("ss_lr_predict", devices, task_config)

    assert result is not None
    assert "output_path" in result
    assert result["receiver_party"] == "bob"
    assert result["secure_mode"] is True
    assert os.path.exists(task_config["output_path"]["bob"])

    print(f"\n预测结果: {result}")


def test_load_ss_lr_model(setup_devices):
    """测试加载SS-LR模型"""
    devices = setup_devices

    model_output = {
        "alice": os.path.join(TEST_MODELS_DIR, "ss_lr_alice.model"),
        "bob": os.path.join(TEST_MODELS_DIR, "ss_lr_bob.model"),
    }

    model_info = load_ss_lr_model(
        model_output, devices["spu"], ["alice", "bob"]
    )

    assert model_info is not None
    assert "model" in model_info
    assert "features" in model_info
    assert "label" in model_info
    assert model_info["secure_mode"] is True

    print(f"\n加载的模型信息: {model_info}")
