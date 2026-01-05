"""
机器学习工作流集成测试

测试完整的机器学习工作流：
PSI → Preprocessing → Training → Prediction → Evaluation
"""

import pytest
import os
from pathlib import Path
import secretflow as sf

from secretflow_task.task_dispatcher import TaskDispatcher

# 测试数据路径
TEST_DATA_DIR = str(Path(__file__).parent.parent / "data" / "integration")
TEST_MODELS_DIR = str(Path(__file__).parent.parent / "models" / "integration")


@pytest.fixture(scope="module")
def setup_secretflow():
    """初始化SecretFlow环境"""
    sf.init(parties=["alice", "bob"], address="local")
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    os.makedirs(TEST_MODELS_DIR, exist_ok=True)
    yield
    sf.shutdown()


@pytest.fixture(scope="module")
def setup_devices(setup_secretflow):
    """创建SecretFlow设备"""
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
def prepare_raw_data():
    """准备原始数据"""
    import pandas as pd
    import numpy as np
    
    np.random.seed(42)
    n_samples = 1000
    
    # Alice的原始数据
    alice_data = pd.DataFrame({
        "id": range(n_samples),
        "age": np.random.randint(20, 60, n_samples),
        "income": np.random.randint(30000, 150000, n_samples),
    })
    
    # Bob的原始数据
    bob_data = pd.DataFrame({
        "id": range(n_samples),
        "education_years": np.random.randint(10, 20, n_samples),
        "work_years": np.random.randint(0, 30, n_samples),
        "label": np.random.randint(0, 2, n_samples),
    })
    
    alice_raw_path = os.path.join(TEST_DATA_DIR, "alice_raw.csv")
    bob_raw_path = os.path.join(TEST_DATA_DIR, "bob_raw.csv")
    
    alice_data.to_csv(alice_raw_path, index=False)
    bob_data.to_csv(bob_raw_path, index=False)
    
    return {
        "alice": alice_raw_path,
        "bob": bob_raw_path,
    }


def test_complete_ml_workflow(setup_devices, prepare_raw_data):
    """测试完整的机器学习工作流"""
    devices = setup_devices
    raw_data = prepare_raw_data
    
    # Step 1: PSI求交
    print("\n=== Step 1: PSI求交 ===")
    psi_output = {
        "alice": os.path.join(TEST_DATA_DIR, "alice_psi.csv"),
        "bob": os.path.join(TEST_DATA_DIR, "bob_psi.csv"),
    }
    
    psi_config = {
        "input_data": raw_data,
        "output_data": psi_output,
        "keys": ["id"],
        "protocol": "ECDH_PSI_2PC",
    }
    
    psi_result = TaskDispatcher.dispatch("psi", devices, psi_config)
    assert psi_result["intersection_count"] > 0
    print(f"PSI完成，交集数量: {psi_result['intersection_count']}")
    
    # Step 2: 数据预处理（标准化）
    print("\n=== Step 2: 数据标准化 ===")
    scaled_output = {
        "alice": os.path.join(TEST_DATA_DIR, "alice_scaled.csv"),
        "bob": os.path.join(TEST_DATA_DIR, "bob_scaled.csv"),
    }
    
    scaler_config = {
        "input_data": psi_output,
        "output_data": scaled_output,
        "columns": ["age", "income", "education_years", "work_years"],
        "with_mean": True,
        "with_std": True,
    }
    
    scaler_result = TaskDispatcher.dispatch("standard_scaler", devices, scaler_config)
    assert "output_paths" in scaler_result
    print("数据标准化完成")
    
    # Step 3: 表统计分析
    print("\n=== Step 3: 表统计分析 ===")
    stats_report = os.path.join(TEST_DATA_DIR, "table_stats.json")
    
    stats_config = {
        "input_data": scaled_output,
        "output_report": stats_report,
        "columns": ["age", "income", "education_years", "work_years"],
    }
    
    stats_result = TaskDispatcher.dispatch("table_statistics", devices, stats_config)
    assert stats_result["num_columns"] == 4
    print(f"表统计完成，分析了{stats_result['num_columns']}列")
    
    # Step 4: 模型训练（SS-LR）
    print("\n=== Step 4: SS-LR模型训练 ===")
    model_output = {
        "alice": os.path.join(TEST_MODELS_DIR, "workflow_lr_alice.model"),
        "bob": os.path.join(TEST_MODELS_DIR, "workflow_lr_bob.model"),
    }
    
    train_config = {
        "train_data": scaled_output,
        "model_output": model_output,
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
    
    train_result = TaskDispatcher.dispatch("ss_logistic_regression", devices, train_config)
    assert train_result["secure_mode"] is True
    print("模型训练完成")
    
    # Step 5: 模型预测
    print("\n=== Step 5: 模型预测 ===")
    predict_output = {
        "bob": os.path.join(TEST_DATA_DIR, "workflow_predictions.csv"),
    }
    
    predict_config = {
        "model_path": model_output,
        "predict_data": scaled_output,
        "output_path": predict_output,
        "receiver_party": "bob",
    }
    
    predict_result = TaskDispatcher.dispatch("ss_lr_predict", devices, predict_config)
    assert predict_result["num_predictions"] > 0
    print(f"预测完成，预测样本数: {predict_result['num_predictions']}")
    
    # Step 6: 模型评估
    print("\n=== Step 6: 模型评估 ===")
    eval_report = os.path.join(TEST_DATA_DIR, "workflow_eval.json")
    
    eval_config = {
        "prediction_data": predict_output,
        "label_column": "label",
        "prediction_column": "probability",
        "bucket_size": 10,
        "output_report": eval_report,
    }
    
    eval_result = TaskDispatcher.dispatch("biclassification_eval", devices, eval_config)
    assert "auc" in eval_result["metrics"]
    print(f"评估完成，AUC: {eval_result['metrics']['auc']:.4f}")
    
    print("\n=== 完整工作流测试通过 ===")
    print(f"最终AUC: {eval_result['metrics']['auc']:.4f}")
    print(f"最终Accuracy: {eval_result['metrics']['accuracy']:.4f}")
