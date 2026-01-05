"""
SS-LR单元测试

测试使用SPU的dump/load机制保存和加载密文分片，
以及使用to_pyu参数进行安全预测
"""

import pytest
import os
from pathlib import Path
import secretflow as sf

from secretflow_task.jobs.linear.ss_lr_task import (
    execute_ss_logistic_regression,
    load_ss_lr_model,
)
from secretflow_task.task_dispatcher import TaskDispatcher

# 测试数据路径
TEST_DATA_DIR = str(Path(__file__).parent.parent / "data")
TEST_MODELS_DIR = str(Path(__file__).parent.parent / "models")


@pytest.fixture(scope="module")
def setup_secretflow():
    """初始化SecretFlow环境"""
    print(f'\nSecretFlow version: {sf.__version__}')
    
    # 初始化SecretFlow - 本地模式
    sf.init(parties=['alice', 'bob'], address="local")
    
    # 创建测试数据目录
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    os.makedirs(TEST_MODELS_DIR, exist_ok=True)
    
    yield
    
    # 清理
    sf.shutdown()
    print("\nSecretFlow shutdown")


@pytest.fixture(scope="module")
def setup_devices(setup_secretflow):
    """创建真实的SecretFlow设备"""
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


class TestSecureModelSaveLoad:
    """安全模式模型保存和加载测试"""
    
    def test_secure_save_and_load(self, setup_devices):
        """测试安全模式保存和加载（不解密）"""
        devices, alice_path, bob_path = setup_devices
        
        # 使用字典格式的模型路径
        model_output = {
            "alice": f"{TEST_MODELS_DIR}/alice/lr_model_secure.share",
            "bob": f"{TEST_MODELS_DIR}/bob/lr_model_secure.share"
        }
        
        # 训练并保存模型（安全模式）
        task_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": model_output,
            "params": {
                "epochs": 3,
                "learning_rate": 0.1,
                "batch_size": 64
            }
        }
        
        result = TaskDispatcher.dispatch('ss_lr', devices, task_config)
        
        assert result is not None
        assert result['secure_mode'] is True
        assert result['weights_encrypted'] is True
        
        # 验证文件存在
        assert os.path.exists(f"{model_output['alice']}.meta.json")
        assert os.path.exists(model_output['alice'])
        assert os.path.exists(f"{model_output['bob']}.meta.json")
        assert os.path.exists(model_output['bob'])
        
        # 加载模型
        spu_device = devices['spu']
        parties = ['alice', 'bob']
        model_info = load_ss_lr_model(model_output, spu_device, parties)
        
        assert model_info is not None
        assert 'model' in model_info
        assert model_info['secure_mode'] is True
        assert model_info['features'] == task_config['features']
        assert model_info['label'] == 'y'
        
        print("\n✅ 安全模式保存和加载测试通过")
    
    def test_secure_predict(self, setup_devices):
        """测试使用安全保存的模型进行预测"""
        devices, alice_path, bob_path = setup_devices
        
        # 使用字典格式的模型路径
        model_output = {
            "alice": f"{TEST_MODELS_DIR}/alice/lr_model_predict.share",
            "bob": f"{TEST_MODELS_DIR}/bob/lr_model_predict.share"
        }
        
        # 使用字典格式的预测输出路径
        predict_output = {
            "alice": f"{TEST_MODELS_DIR}/alice/predictions.csv",
            "bob": f"{TEST_MODELS_DIR}/bob/predictions.csv"
        }
        
        # 训练模型
        train_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": model_output,
            "params": {
                "epochs": 3,
                "learning_rate": 0.1,
                "batch_size": 64
            }
        }
        
        TaskDispatcher.dispatch('ss_lr', devices, train_config)
        
        # 执行预测
        predict_config = {
            "model_path": model_output,
            "predict_data": {"alice": alice_path, "bob": bob_path},
            "output_path": predict_output,
            "receiver_party": "alice"
        }
        
        result = TaskDispatcher.dispatch('ss_lr_predict', devices, predict_config)
        
        assert result is not None
        assert result['secure_mode'] is True
        assert result['output_path'] == predict_output
        assert result['num_predictions'] > 0
        assert 'statistics' not in result  # 不应该返回统计信息（避免泄露数据）
        
        # 验证预测文件存在（只有接收方alice有预测结果）
        assert os.path.exists(predict_output['alice'])
        
        # 验证预测结果格式
        import pandas as pd
        pred_df = pd.read_csv(predict_output['alice'])
        assert 'prediction' in pred_df.columns
        assert 'probability' in pred_df.columns
        
        print("\n✅ 安全模式预测测试通过")
    
    def test_share_files_are_different(self, setup_devices):
        """测试每个参与方的密文分片文件是不同的"""
        devices, alice_path, bob_path = setup_devices
        
        # 使用字典格式的模型路径
        model_output = {
            "alice": f"{TEST_MODELS_DIR}/alice/lr_model_share_test.share",
            "bob": f"{TEST_MODELS_DIR}/bob/lr_model_share_test.share"
        }
        
        # 训练并保存模型
        task_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": model_output,
            "params": {"epochs": 2}
        }
        
        TaskDispatcher.dispatch('ss_lr', devices, task_config)
        
        # 读取两个参与方的密文分片
        alice_share_path = model_output['alice']
        bob_share_path = model_output['bob']
        
        with open(alice_share_path, 'rb') as f:
            alice_share = f.read()
        
        with open(bob_share_path, 'rb') as f:
            bob_share = f.read()
        
        # 验证两个分片不同（每个参与方只有自己的密文部分）
        assert alice_share != bob_share, "Alice和Bob的密文分片应该不同"
        
        print(f"\n✅ 密文分片验证通过")
        print(f"   Alice分片大小: {len(alice_share)} bytes")
        print(f"   Bob分片大小: {len(bob_share)} bytes")


class TestSSXGBoost:
    """SS-XGBoost模型训练和预测测试"""
    
    def test_ss_xgb_train(self, setup_devices):
        """测试SS-XGBoost训练"""
        devices, alice_path, bob_path = setup_devices
        
        # 使用字典格式的模型路径
        model_output = {
            "alice": f"{TEST_MODELS_DIR}/alice/xgb_model.model",
            "bob": f"{TEST_MODELS_DIR}/bob/xgb_model.model"
        }
        
        # 训练配置
        task_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": model_output,
            "params": {
                "num_boost_round": 3,
                "max_depth": 3,
                "learning_rate": 0.3,
                "objective": "logistic",
                "reg_lambda": 0.1
            }
        }
        
        result = TaskDispatcher.dispatch('ss_xgb', devices, task_config)
        
        assert result is not None
        assert result['secure_mode'] is True
        assert result['num_trees'] == 3
        
        # 验证文件存在
        assert os.path.exists(f"{model_output['alice']}.meta.json")
        assert os.path.exists(f"{model_output['bob']}.meta.json")
        
        print("\n✅ SS-XGBoost训练测试通过")
    
    def test_ss_xgb_predict(self, setup_devices):
        """测试SS-XGBoost预测"""
        devices, alice_path, bob_path = setup_devices
        
        # 使用字典格式的模型路径
        model_output = {
            "alice": f"{TEST_MODELS_DIR}/alice/xgb_model_pred.model",
            "bob": f"{TEST_MODELS_DIR}/bob/xgb_model_pred.model"
        }
        
        # 使用字典格式的预测输出路径
        predict_output = {
            "alice": f"{TEST_MODELS_DIR}/alice/xgb_predictions.csv",
            "bob": f"{TEST_MODELS_DIR}/bob/xgb_predictions.csv"
        }
        
        # 训练模型
        train_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": model_output,
            "params": {
                "num_boost_round": 3,
                "max_depth": 3
            }
        }
        
        TaskDispatcher.dispatch('ss_xgb', devices, train_config)
        
        # 执行预测
        predict_config = {
            "model_path": model_output,
            "predict_data": {"alice": alice_path, "bob": bob_path},
            "output_path": predict_output,
            "receiver_party": "alice"
        }
        
        result = TaskDispatcher.dispatch('ss_xgb_predict', devices, predict_config)
        
        assert result is not None
        assert result['secure_mode'] is True
        assert result['output_path'] == predict_output
        assert result['num_predictions'] > 0
        assert 'statistics' not in result
        
        # 验证预测文件存在（只有接收方alice有预测结果）
        assert os.path.exists(predict_output['alice'])
        
        # 验证预测结果格式
        import pandas as pd
        pred_df = pd.read_csv(predict_output['alice'])
        assert 'prediction' in pred_df.columns
        assert 'probability' in pred_df.columns
        
        print("\n✅ SS-XGBoost预测测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
