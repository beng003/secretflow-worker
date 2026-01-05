"""
BiClassificationEval二分类评估任务测试
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
    sf.init(parties=["alice"], address="local")
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    yield
    sf.shutdown()


@pytest.fixture(scope="module")
def setup_devices(setup_secretflow):
    """创建SecretFlow设备"""
    alice = sf.PYU("alice")
    
    devices = {
        "alice": alice,
    }
    return devices


@pytest.fixture(scope="module")
def prepare_test_data():
    """准备测试数据（包含真实标签和预测概率）"""
    import pandas as pd
    import numpy as np
    
    np.random.seed(42)
    
    # 模拟预测结果数据
    prediction_data = pd.DataFrame({
        "label": np.random.randint(0, 2, 100),
        "probability": np.random.random(100),
    })
    
    prediction_path = os.path.join(TEST_DATA_DIR, "alice_predictions.csv")
    prediction_data.to_csv(prediction_path, index=False)
    
    return {
        "alice": prediction_path,
    }


def test_biclassification_eval(setup_devices, prepare_test_data):
    """测试二分类评估任务"""
    devices = setup_devices
    data_paths = prepare_test_data
    
    task_config = {
        "prediction_data": data_paths,
        "label_column": "label",
        "prediction_column": "probability",
        "bucket_size": 10,
        "output_report": os.path.join(TEST_DATA_DIR, "biclass_eval_report.json"),
    }
    
    result = TaskDispatcher.dispatch("biclassification_eval", devices, task_config)
    
    assert result is not None
    assert "output_report" in result
    assert "metrics" in result
    assert "auc" in result["metrics"]
    assert os.path.exists(task_config["output_report"])
    
    print(f"\n二分类评估结果: {result}")
