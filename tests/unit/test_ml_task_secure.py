"""
SS-LR安全模式（不解密保存）单元测试

测试使用SPU的dump/load机制保存和加载密文分片
"""

import pytest
import os
from pathlib import Path
import secretflow as sf

from secretflow_task.jobs.ml_task_secure import (
    execute_ss_logistic_regression_secure,
    load_ss_lr_model_secure
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
        
        model_path = f"{TEST_MODELS_DIR}/lr_model_secure"
        
        # 训练并保存模型（安全模式）
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
        
        result = TaskDispatcher.dispatch('ss_lr_secure', devices, task_config)
        
        assert result is not None
        assert result['secure_mode'] is True
        assert result['weights_encrypted'] is True
        
        # 验证文件存在
        assert os.path.exists(f"{model_path}.meta.json")
        assert os.path.exists(f"{model_path}.alice.share")
        assert os.path.exists(f"{model_path}.bob.share")
        assert os.path.exists(f"{model_path}.alice.json")
        assert os.path.exists(f"{model_path}.bob.json")
        
        # 加载模型
        spu_device = devices['spu']
        parties = ['alice', 'bob']
        model_info = load_ss_lr_model_secure(model_path, spu_device, parties)
        
        assert model_info is not None
        assert 'model' in model_info
        assert model_info['secure_mode'] is True
        assert model_info['features'] == task_config['features']
        assert model_info['label'] == 'y'
        
        print("\n✅ 安全模式保存和加载测试通过")
    
    def test_secure_predict(self, setup_devices):
        """测试使用安全保存的模型进行预测"""
        devices, alice_path, bob_path = setup_devices
        
        model_path = f"{TEST_MODELS_DIR}/lr_model_secure_predict"
        predict_output = f"{TEST_MODELS_DIR}/predictions_secure.csv"
        
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
        
        TaskDispatcher.dispatch('ss_lr_secure', devices, train_config)
        
        # 执行预测
        predict_config = {
            "model_path": model_path,
            "predict_data": {"alice": alice_path, "bob": bob_path},
            "output_path": predict_output,
            "receiver_party": "alice"
        }
        
        result = TaskDispatcher.dispatch('ss_lr_predict_secure', devices, predict_config)
        
        assert result is not None
        assert result['secure_mode'] is True
        assert result['output_path'] == predict_output
        assert result['num_predictions'] > 0
        assert 'statistics' in result
        
        # 验证预测文件存在
        assert os.path.exists(predict_output)
        
        # 验证预测结果格式
        import pandas as pd
        pred_df = pd.read_csv(predict_output)
        assert 'prediction' in pred_df.columns
        assert 'probability' in pred_df.columns
        
        print("\n✅ 安全模式预测测试通过")
    
    def test_share_files_are_different(self, setup_devices):
        """测试每个参与方的密文分片文件是不同的"""
        devices, alice_path, bob_path = setup_devices
        
        model_path = f"{TEST_MODELS_DIR}/lr_model_share_test"
        
        # 训练并保存模型
        task_config = {
            "train_data": {"alice": alice_path, "bob": bob_path},
            "features": ["f0", "f1", "f2", "f6", "f7"],
            "label": "y",
            "label_party": "alice",
            "model_output": model_path,
            "params": {"epochs": 2}
        }
        
        TaskDispatcher.dispatch('ss_lr_secure', devices, task_config)
        
        # 读取两个参与方的密文分片
        alice_share_path = f"{model_path}.alice.share"
        bob_share_path = f"{model_path}.bob.share"
        
        with open(alice_share_path, 'rb') as f:
            alice_share = f.read()
        
        with open(bob_share_path, 'rb') as f:
            bob_share = f.read()
        
        # 验证两个分片不同（每个参与方只有自己的密文部分）
        assert alice_share != bob_share, "Alice和Bob的密文分片应该不同"
        
        print(f"\n✅ 密文分片验证通过")
        print(f"   Alice分片大小: {len(alice_share)} bytes")
        print(f"   Bob分片大小: {len(bob_share)} bytes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
