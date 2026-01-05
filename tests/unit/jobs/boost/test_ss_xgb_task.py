"""
SS-XGBoost单元测试

测试SS-XGBoost模型的训练和预测功能
"""

import pytest
import os
from pathlib import Path
import secretflow as sf

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
        "f0": np.random.rand(n_samples),
        "f1": np.random.rand(n_samples),
        "f2": np.random.rand(n_samples),
        "y": np.random.randint(0, 2, n_samples),
    })

    bob_data = pd.DataFrame({
        "f6": np.random.rand(n_samples),
        "f7": np.random.rand(n_samples),
    })

    alice_train_path = os.path.join(TEST_DATA_DIR, "alice_train_xgb.csv")
    bob_train_path = os.path.join(TEST_DATA_DIR, "bob_train_xgb.csv")
    alice_test_path = os.path.join(TEST_DATA_DIR, "alice_test_xgb.csv")
    bob_test_path = os.path.join(TEST_DATA_DIR, "bob_test_xgb.csv")

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


def test_ss_xgb_train(setup_devices, prepare_test_data):
    """测试SS-XGBoost训练任务"""
    devices = setup_devices
    data_paths = prepare_test_data

    model_output = {
        "alice": os.path.join(TEST_MODELS_DIR, "ss_xgb_alice.model"),
        "bob": os.path.join(TEST_MODELS_DIR, "ss_xgb_bob.model"),
    }

    task_config = {
        "train_data": {
            "alice": data_paths["alice_train"],
            "bob": data_paths["bob_train"],
        },
        "model_output": model_output,
        "features": ["f0", "f1", "f2", "f6", "f7"],
        "label": "y",
        "label_party": "alice",
        "params": {
            "num_boost_round": 3,
            "max_depth": 3,
            "learning_rate": 0.3,
            "objective": "logistic",
            "reg_lambda": 0.1,
        },
    }

    result = TaskDispatcher.dispatch("ss_xgboost", devices, task_config)

    assert result is not None
    assert "model_paths" in result
    assert result["secure_mode"] is True
    assert result["num_trees"] == 3
    assert os.path.exists(f"{model_output['alice']}.meta.json")
    assert os.path.exists(f"{model_output['bob']}.meta.json")

    print(f"\n训练结果: {result}")


def test_ss_xgb_predict(setup_devices, prepare_test_data):
    """测试SS-XGBoost预测任务"""
    devices = setup_devices
    data_paths = prepare_test_data

    task_config = {
        "model_path": {
            "alice": os.path.join(TEST_MODELS_DIR, "ss_xgb_alice.model"),
            "bob": os.path.join(TEST_MODELS_DIR, "ss_xgb_bob.model"),
        },
        "predict_data": {
            "alice": data_paths["alice_test"],
            "bob": data_paths["bob_test"],
        },
        "output_path": {
            "alice": os.path.join(TEST_DATA_DIR, "ss_xgb_predictions.csv"),
        },
        "receiver_party": "alice",
    }

    result = TaskDispatcher.dispatch("ss_xgb_predict", devices, task_config)

    assert result is not None
    assert "output_path" in result
    assert result["receiver_party"] == "alice"
    assert result["secure_mode"] is True
    assert result["num_predictions"] > 0
    assert os.path.exists(task_config["output_path"]["alice"])

    # 验证预测结果格式
    import pandas as pd
    pred_df = pd.read_csv(task_config["output_path"]["alice"])
    assert "prediction" in pred_df.columns
    assert "probability" in pred_df.columns

    print(f"\n预测结果: {result}")
