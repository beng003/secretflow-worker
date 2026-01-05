"""
RegressionEval回归评估任务测试
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
    """准备测试数据（包含真实值和预测值）"""
    import pandas as pd
    import numpy as np
    
    np.random.seed(42)
    
    # 模拟回归预测结果数据
    actual_values = np.random.rand(100) * 100
    predicted_values = actual_values + np.random.randn(100) * 10
    
    prediction_data = pd.DataFrame({
        "actual_value": actual_values,
        "predicted_value": predicted_values,
    })
    
    prediction_path = os.path.join(TEST_DATA_DIR, "alice_regression_predictions.csv")
    prediction_data.to_csv(prediction_path, index=False)
    
    return {
        "alice": prediction_path,
    }


def test_regression_eval(setup_devices, prepare_test_data):
    """测试回归评估任务"""
    devices = setup_devices
    data_paths = prepare_test_data
    
    task_config = {
        "prediction_data": data_paths,
        "label_column": "actual_value",
        "prediction_column": "predicted_value",
        "output_report": os.path.join(TEST_DATA_DIR, "regression_eval_report.json"),
    }
    
    result = TaskDispatcher.dispatch("regression_eval", devices, task_config)
    
    assert result is not None
    assert "output_report" in result
    assert "metrics" in result
    assert "mse" in result["metrics"]
    assert "rmse" in result["metrics"]
    assert "mae" in result["metrics"]
    assert "r2_score" in result["metrics"]
    assert os.path.exists(task_config["output_report"])
    
    # 验证评估报告格式
    import json
    with open(task_config["output_report"], 'r') as f:
        eval_data = json.load(f)
    
    assert "metrics" in eval_data
    assert "config" in eval_data
    
    print(f"\n回归评估结果: {result}")
