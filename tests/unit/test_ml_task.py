"""
SS-LR逻辑回归任务单元测试

测试SS-LR任务的配置验证、执行逻辑和错误处理。
使用真实的SecretFlow设备进行测试。
"""

import pytest
import os
from pathlib import Path
import secretflow as sf
import pandas as pd
import numpy as np
from sklearn.datasets import make_classification

from secretflow_task.jobs.ml_task import (
    execute_ss_logistic_regression,
    _validate_ss_lr_config
)
from secretflow_task.task_dispatcher import TaskDispatcher

# 测试数据路径
TEST_DATA_DIR = str(Path(__file__).parent.parent / "data")
TEST_MODELS_DIR = str(Path(__file__).parent.parent / "models")


@pytest.fixture(scope="module")
def setup_secretflow():
    """初始化SecretFlow环境并准备测试数据"""
    print(f'\nSecretFlow version: {sf.__version__}')
    
    # 初始化SecretFlow - 本地模式
    sf.init(parties=['alice', 'bob'], address="local")
    
    # 准备测试数据目录
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    os.makedirs(TEST_MODELS_DIR, exist_ok=True)
    
    # 生成二分类数据集
    np.random.seed(42)
    n_samples = 1000
    n_features = 10
    
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=8,
        n_redundant=2,
        n_classes=2,
        random_state=42
    )
    
    # 分割特征给不同参与方
    n_alice_features = 6
    X_alice = X[:, :n_alice_features]
    X_bob = X[:, n_alice_features:]
    
    # Alice的数据（包含标签）
    alice_data = pd.DataFrame(
        X_alice,
        columns=[f'f{i}' for i in range(n_alice_features)]
    )
    alice_data['y'] = y
    
    # Bob的数据
    bob_data = pd.DataFrame(
        X_bob,
        columns=[f'f{i}' for i in range(n_alice_features, n_features)]
    )
    
    # 保存测试数据
    alice_data.to_csv(f'{TEST_DATA_DIR}/alice_train.csv', index=False)
    bob_data.to_csv(f'{TEST_DATA_DIR}/bob_train.csv', index=False)
    
    print(f"Test data prepared in {TEST_DATA_DIR}")
    print(f"Alice features: {list(alice_data.columns[:-1])}")
    print(f"Bob features: {list(bob_data.columns)}")
    print(f"Label: y (in alice)")
    
    yield
    
    # 清理
    sf.shutdown()
    print("\nSecretFlow shutdown")


@pytest.fixture(scope="module")
def real_devices(setup_secretflow):
    """创建真实的SecretFlow设备"""
    alice = sf.PYU('alice')
    bob = sf.PYU('bob')
    spu = sf.SPU(sf.utils.testing.cluster_def(['alice', 'bob']))
    
    devices = {
        'alice': alice,
        'bob': bob,
        'spu': spu,
    }
    
    return devices


@pytest.fixture(scope="module")
def setup_devices(setup_secretflow):
    """创建真实的SecretFlow设备和测试数据路径"""
    alice = sf.PYU('alice')
    bob = sf.PYU('bob')
    spu = sf.SPU(sf.utils.testing.cluster_def(['alice', 'bob']))
    
    devices = {
        'alice': alice,
        'bob': bob,
        'spu': spu,
    }
    
    alice_path = f'{TEST_DATA_DIR}/alice_train.csv'
    bob_path = f'{TEST_DATA_DIR}/bob_train.csv'
    
    return devices, alice_path, bob_path


@pytest.fixture(scope="module")
def test_data_paths():
    """返回测试数据路径"""
    alice_path = f'{TEST_DATA_DIR}/alice_train.csv'
    bob_path = f'{TEST_DATA_DIR}/bob_train.csv'
    return alice_path, bob_path


class TestSSLRConfigValidation:
    """SS-LR配置验证测试"""
    
    def test_validate_config_success(self):
        """测试有效的配置"""
        config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/alice_train.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": ["f0", "f1", "f2"],
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model",
            "params": {
                "epochs": 5,
                "learning_rate": 0.3
            }
        }
        
        _validate_ss_lr_config(config)
    
    def test_validate_config_missing_field(self):
        """测试缺少必需字段"""
        config = {
            "train_data": {"alice": "alice.csv"}
        }
        
        with pytest.raises(ValueError) as exc_info:
            _validate_ss_lr_config(config)
        
        assert "缺少必需字段" in str(exc_info.value)
    
    def test_validate_config_invalid_train_data_type(self):
        """测试train_data类型错误"""
        config = {
            "train_data": ["alice.csv"],
            "features": ["f1"],
            "label": "y",
            "label_party": "alice",
            "model_output": "/models/lr"
        }
        
        with pytest.raises(ValueError) as exc_info:
            _validate_ss_lr_config(config)
        
        assert "train_data必须是字典类型" in str(exc_info.value)
    
    def test_validate_config_empty_train_data(self):
        """测试空train_data"""
        config = {
            "train_data": {},
            "features": ["f1"],
            "label": "y",
            "label_party": "alice",
            "model_output": "/models/lr"
        }
        
        with pytest.raises(ValueError) as exc_info:
            _validate_ss_lr_config(config)
        
        assert "train_data不能为空" in str(exc_info.value)
    
    def test_validate_config_invalid_features_type(self):
        """测试features类型错误"""
        config = {
            "train_data": {"alice": "alice.csv"},
            "features": "f1",
            "label": "y",
            "label_party": "alice",
            "model_output": "/models/lr"
        }
        
        with pytest.raises(ValueError) as exc_info:
            _validate_ss_lr_config(config)
        
        assert "features必须是列表类型" in str(exc_info.value)
    
    def test_validate_config_empty_features(self):
        """测试空features列表"""
        config = {
            "train_data": {"alice": "alice.csv"},
            "features": [],
            "label": "y",
            "label_party": "alice",
            "model_output": "/models/lr"
        }
        
        with pytest.raises(ValueError) as exc_info:
            _validate_ss_lr_config(config)
        
        assert "features不能为空列表" in str(exc_info.value)
    
    def test_validate_config_invalid_label_party(self):
        """测试label_party不在参与方中"""
        config = {
            "train_data": {"alice": "alice.csv", "bob": "bob.csv"},
            "features": ["f1"],
            "label": "y",
            "label_party": "charlie",
            "model_output": "/models/lr"
        }
        
        with pytest.raises(ValueError) as exc_info:
            _validate_ss_lr_config(config)
        
        assert "不在train_data的参与方中" in str(exc_info.value)
    
    def test_validate_config_invalid_params(self):
        """测试无效的参数"""
        config = {
            "train_data": {"alice": "alice.csv"},
            "features": ["f1"],
            "label": "y",
            "label_party": "alice",
            "model_output": "/models/lr",
            "params": {
                "invalid_param": 123
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            _validate_ss_lr_config(config)
        
        assert "无效的参数" in str(exc_info.value)


class TestExecuteSSLR:
    """SS-LR任务执行测试 - 使用真实设备"""
    
    def test_ss_lr_task_registered(self):
        """测试SS-LR任务已注册"""
        assert 'ss_lr' in TaskDispatcher.TASK_REGISTRY
    
    def test_execute_ss_lr_missing_spu_device(self, real_devices):
        """测试缺少SPU设备"""
        devices = {
            "alice": real_devices['alice'],
            "bob": real_devices['bob']
        }
        
        task_config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/alice_train.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": ["f0", "f1", "f2"],
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_test1"
        }
        
        with pytest.raises(ValueError) as exc_info:
            execute_ss_logistic_regression(devices, task_config)
        
        assert "缺少'spu'设备" in str(exc_info.value)
    
    def test_execute_ss_lr_missing_pyu_device(self, real_devices):
        """测试缺少PYU设备"""
        devices = {
            "alice": real_devices['alice'],
            "spu": real_devices['spu']
        }
        
        task_config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/alice_train.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": ["f0", "f1", "f2"],
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_test2"
        }
        
        with pytest.raises(ValueError) as exc_info:
            execute_ss_logistic_regression(devices, task_config)
        
        assert "缺少参与方'bob'的PYU设备" in str(exc_info.value)
    
    def test_execute_ss_lr_file_not_exist(self, real_devices):
        """测试训练数据文件不存在"""
        task_config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/nonexistent.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": ["f0", "f1", "f2"],
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_test3"
        }
        
        with pytest.raises(ValueError) as exc_info:
            execute_ss_logistic_regression(real_devices, task_config)
        
        assert "训练数据文件不存在" in str(exc_info.value)
    
    def test_execute_ss_lr_feature_not_exist(self, real_devices):
        """测试特征列不存在"""
        task_config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/alice_train.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": ["nonexistent_feature"],
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_test4"
        }
        
        with pytest.raises(ValueError) as exc_info:
            execute_ss_logistic_regression(real_devices, task_config)
        
        assert "不存在于数据中" in str(exc_info.value)
    
    def test_execute_ss_lr_label_not_exist(self, real_devices):
        """测试标签列不存在"""
        task_config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/alice_train.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": ["f0", "f1"],
            "label": "nonexistent_label",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_test5"
        }
        
        with pytest.raises(ValueError) as exc_info:
            execute_ss_logistic_regression(real_devices, task_config)
        
        assert "不存在于数据中" in str(exc_info.value)
    
    def test_execute_ss_lr_basic(self, real_devices):
        """测试基本SS-LR训练"""
        task_config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/alice_train.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_basic",
            "params": {
                "epochs": 3,
                "learning_rate": 0.1,
                "batch_size": 64
            }
        }
        
        result = execute_ss_logistic_regression(real_devices, task_config)
        
        assert "model_path" in result
        assert result["model_path"] == f"{TEST_MODELS_DIR}/lr_model_basic"
        assert result["parties"] == ["alice", "bob"]
        assert result["features"] == ["f0", "f1", "f2", "f6", "f7"]
        assert result["label"] == "y"
        assert result["params"]["epochs"] == 3
        assert result["params"]["learning_rate"] == 0.1
        assert result["params"]["batch_size"] == 64
        
        # 验证模型文件已保存
        assert os.path.exists(f"{TEST_MODELS_DIR}/lr_model_basic")
        
        print(f"\nSS-LR Result (basic): {result}")
    
    def test_execute_ss_lr_with_all_features(self, real_devices):
        """测试使用所有特征训练"""
        all_features = [f'f{i}' for i in range(10)]
        
        task_config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/alice_train.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": all_features,
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_all_features",
            "params": {
                "epochs": 2,
                "learning_rate": 0.05
            }
        }
        
        result = execute_ss_logistic_regression(real_devices, task_config)
        
        assert result["features"] == all_features
        assert os.path.exists(f"{TEST_MODELS_DIR}/lr_model_all_features")
        
        print(f"\nSS-LR Result (all features): {result}")
    
    def test_execute_ss_lr_default_params(self, real_devices):
        """测试使用默认参数"""
        task_config = {
            "train_data": {"alice": f"{TEST_DATA_DIR}/alice_train.csv", "bob": f"{TEST_DATA_DIR}/bob_train.csv"},
            "features": ["f0", "f1", "f2"],
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_default"
        }
        
        result = execute_ss_logistic_regression(real_devices, task_config)
        
        # 验证默认参数
        assert result["params"]["epochs"] == 5
        assert result["params"]["learning_rate"] == 0.3
        assert result["params"]["batch_size"] == 32
        assert result["params"]["sig_type"] == 't1'
        assert result["params"]["reg_type"] == 'logistic'
        assert result["params"]["penalty"] == 'l2'
        assert result["params"]["l2_norm"] == 0.1
        
        print(f"\nSS-LR Result (default params): {result}")


class TestSSLRIntegration:
    """SS-LR集成测试"""
    
    def test_ss_lr_via_dispatcher(self, setup_devices, test_data_paths):
        """测试通过TaskDispatcher调用SS-LR任务"""
        devices, alice_path, bob_path = setup_devices
        
        task_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": f"{TEST_MODELS_DIR}/lr_model_dispatcher",
            "params": {
                "epochs": 3,
                "learning_rate": 0.1,
                "batch_size": 64
            }
        }
        
        # 通过TaskDispatcher调用
        result = TaskDispatcher.dispatch('ss_lr', devices, task_config)
        
        assert result is not None
        assert result['model_path'] == task_config['model_output']
        assert result['parties'] == ['alice', 'bob']
        assert result['features'] == task_config['features']
        assert result['label'] == 'y'
        
        # 验证模型文件存在
        assert os.path.exists(result['model_path'])


class TestModelSaveLoad:
    """模型保存和加载测试"""
    
    def test_model_save_and_load(self, setup_devices, test_data_paths):
        """测试模型保存和加载"""
        from secretflow_task.jobs.ml_task import load_ss_lr_model
        
        devices, alice_path, bob_path = setup_devices
        
        model_path = f"{TEST_MODELS_DIR}/lr_model_save_load"
        
        # 训练并保存模型
        task_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": model_path,
            "params": {
                "epochs": 3,
                "learning_rate": 0.1,
                "batch_size": 64
            }
        }
        
        result = TaskDispatcher.dispatch('ss_lr', devices, task_config)
        assert os.path.exists(model_path)
        
        # 加载模型
        spu_device = devices['spu']
        model_info = load_ss_lr_model(model_path, spu_device)
        
        assert model_info is not None
        assert 'model' in model_info
        assert model_info['features'] == task_config['features']
        assert model_info['label'] == 'y'
        assert model_info['label_party'] == 'alice'
        assert model_info['parties'] == ['alice', 'bob']
        
        # 验证参与方引用文件
        assert os.path.exists(f"{model_path}.alice")
        assert os.path.exists(f"{model_path}.bob")
    
    def test_model_predict(self, setup_devices, test_data_paths):
        """测试模型预测"""
        devices, alice_path, bob_path = setup_devices
        
        model_path = f"{TEST_MODELS_DIR}/lr_model_predict"
        predict_output = f"{TEST_MODELS_DIR}/predictions.csv"
        
        # 训练模型
        train_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": model_path,
            "params": {
                "epochs": 3,
                "learning_rate": 0.1,
                "batch_size": 64
            }
        }
        
        TaskDispatcher.dispatch('ss_lr', devices, train_config)
        
        # 执行预测
        predict_config = {
            "model_path": model_path,
            "predict_data": {"alice": alice_path, "bob": bob_path},
            "output_path": predict_output,
            "receiver_party": "alice"
        }
        
        result = TaskDispatcher.dispatch('ss_lr_predict', devices, predict_config)
        
        assert result is not None
        assert result['output_path'] == predict_output
        assert result['receiver_party'] == 'alice'
        assert result['num_predictions'] > 0
        assert 'statistics' in result
        
        # 验证预测文件存在
        assert os.path.exists(predict_output)
        
        # 验证预测结果格式
        import pandas as pd
        pred_df = pd.read_csv(predict_output)
        assert 'prediction' in pred_df.columns
        assert 'probability' in pred_df.columns
        assert len(pred_df) == result['num_predictions']
    
    def test_load_nonexistent_model(self, setup_devices):
        """测试加载不存在的模型"""
        from secretflow_task.jobs.ml_task import load_ss_lr_model
        
        devices, _, _ = setup_devices
        spu_device = devices['spu']
        
        with pytest.raises(FileNotFoundError):
            load_ss_lr_model("/nonexistent/model.json", spu_device)
    
    def test_predict_missing_model(self, setup_devices, test_data_paths):
        """测试使用不存在的模型进行预测"""
        devices, alice_path, bob_path = setup_devices
        
        predict_config = {
            "model_path": "/nonexistent/model.json",
            "predict_data": {"alice": alice_path, "bob": bob_path},
            "output_path": f"{TEST_MODELS_DIR}/predictions_fail.csv"
        }
        
        with pytest.raises(Exception):
            TaskDispatcher.dispatch('ss_lr_predict', devices, predict_config)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
