"""
StandardScaler任务单元测试

测试StandardScaler任务的配置验证、执行逻辑和错误处理。
使用真实的SecretFlow设备进行测试。
"""

import pytest
import os
from pathlib import Path
import secretflow as sf
import pandas as pd
import numpy as np

from secretflow_task.jobs.preprocessing_task import (
    execute_standard_scaler,
    _validate_standard_scaler_config,
)
from secretflow_task.task_dispatcher import TaskDispatcher

# 测试数据路径
TEST_DATA_DIR = str(Path(__file__).parent.parent / "data")


@pytest.fixture(scope="module")
def setup_secretflow():
    """初始化SecretFlow环境并准备测试数据"""
    print(f"\nSecretFlow version: {sf.__version__}")

    # 初始化SecretFlow - 本地模式
    sf.init(parties=["alice", "bob"], address="local")

    # 准备测试数据目录
    os.makedirs(TEST_DATA_DIR, exist_ok=True)

    # 准备测试数据 - 包含需要标准化的数值列
    # 注意：垂直分区场景下，不同参与方的列名不能重复
    np.random.seed(42)
    n_samples = 100

    # Alice的数据
    alice_data = pd.DataFrame(
        {
            "age": np.random.randint(20, 60, n_samples),
            "income": np.random.randint(30000, 150000, n_samples),
        }
    )

    # Bob的数据
    bob_data = pd.DataFrame(
        {
            "score": np.random.uniform(0, 100, n_samples),
            "experience": np.random.randint(0, 30, n_samples),
        }
    )

    # 保存测试数据
    alice_data.to_csv(f"{TEST_DATA_DIR}/alice_raw.csv", index=False)
    bob_data.to_csv(f"{TEST_DATA_DIR}/bob_raw.csv", index=False)

    print(f"Test data prepared in {TEST_DATA_DIR}")

    yield

    # 清理
    sf.shutdown()
    print("\nSecretFlow shutdown")


@pytest.fixture(scope="module")
def real_devices(setup_secretflow):
    """创建真实的SecretFlow设备"""
    alice = sf.PYU("alice")
    bob = sf.PYU("bob")

    devices = {
        "alice": alice,
        "bob": bob,
    }

    return devices


class TestStandardScalerConfigValidation:
    """StandardScaler配置验证测试"""

    def test_validate_config_success(self):
        """测试有效的配置"""
        config = {
            "input_data": {
                "alice": f"{TEST_DATA_DIR}/alice_raw.csv",
                "bob": f"{TEST_DATA_DIR}/bob_raw.csv",
            },
            "output_data": {
                "alice": f"{TEST_DATA_DIR}/alice_scaled.csv",
                "bob": f"{TEST_DATA_DIR}/bob_scaled.csv",
            },
            "columns": ["age", "income"],
            "with_mean": True,
            "with_std": True,
        }

        _validate_standard_scaler_config(config)

    def test_validate_config_missing_field(self):
        """测试缺少必需字段"""
        config = {"input_data": {"alice": "alice.csv"}}

        with pytest.raises(ValueError) as exc_info:
            _validate_standard_scaler_config(config)

        assert "缺少必需字段" in str(exc_info.value)

    def test_validate_config_invalid_input_data_type(self):
        """测试input_data类型错误"""
        config = {
            "input_data": ["alice.csv"],
            "output_data": {"alice": "alice_scaled.csv"},
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_standard_scaler_config(config)

        assert "input_data必须是字典类型" in str(exc_info.value)

    def test_validate_config_empty_input_data(self):
        """测试空input_data"""
        config = {"input_data": {}, "output_data": {}}

        with pytest.raises(ValueError) as exc_info:
            _validate_standard_scaler_config(config)

        assert "input_data不能为空" in str(exc_info.value)

    def test_validate_config_parties_mismatch(self):
        """测试参与方不一致"""
        config = {
            "input_data": {"alice": "alice.csv", "bob": "bob.csv"},
            "output_data": {"alice": "alice_scaled.csv"},
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_standard_scaler_config(config)

        assert "参与方不一致" in str(exc_info.value)

    def test_validate_config_invalid_path(self):
        """测试无效的路径"""
        config = {
            "input_data": {"alice": "", "bob": "bob.csv"},
            "output_data": {"alice": "alice_scaled.csv", "bob": "bob_scaled.csv"},
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_standard_scaler_config(config)

        assert "路径必须是非空字符串" in str(exc_info.value)

    def test_validate_config_invalid_columns_type(self):
        """测试columns类型错误"""
        config = {
            "input_data": {"alice": "alice.csv"},
            "output_data": {"alice": "alice_scaled.csv"},
            "columns": "age",
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_standard_scaler_config(config)

        assert "columns必须是列表类型" in str(exc_info.value)

    def test_validate_config_empty_columns(self):
        """测试空columns列表"""
        config = {
            "input_data": {"alice": "alice.csv"},
            "output_data": {"alice": "alice_scaled.csv"},
            "columns": [],
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_standard_scaler_config(config)

        assert "columns不能为空列表" in str(exc_info.value)


class TestExecuteStandardScaler:
    """StandardScaler任务执行测试 - 使用真实设备"""

    def test_standard_scaler_task_registered(self):
        """测试StandardScaler任务已注册"""
        assert "standard_scaler" in TaskDispatcher.TASK_REGISTRY

    def test_execute_standard_scaler_missing_device(self, real_devices):
        """测试缺少设备"""
        devices = {"alice": real_devices["alice"]}

        task_config = {
            "input_data": {
                "alice": f"{TEST_DATA_DIR}/alice_raw.csv",
                "bob": f"{TEST_DATA_DIR}/bob_raw.csv",
            },
            "output_data": {
                "alice": f"{TEST_DATA_DIR}/alice_scaled.csv",
                "bob": f"{TEST_DATA_DIR}/bob_scaled.csv",
            },
        }

        with pytest.raises(ValueError) as exc_info:
            execute_standard_scaler(devices, task_config)

        assert "缺少参与方'bob'的PYU设备" in str(exc_info.value)

    def test_execute_standard_scaler_file_not_exist(self, real_devices):
        """测试输入文件不存在"""
        task_config = {
            "input_data": {
                "alice": f"{TEST_DATA_DIR}/nonexistent.csv",
                "bob": f"{TEST_DATA_DIR}/bob_raw.csv",
            },
            "output_data": {
                "alice": f"{TEST_DATA_DIR}/alice_scaled.csv",
                "bob": f"{TEST_DATA_DIR}/bob_scaled.csv",
            },
        }

        with pytest.raises(ValueError) as exc_info:
            execute_standard_scaler(real_devices, task_config)

        assert "输入文件不存在" in str(exc_info.value)

    def test_execute_standard_scaler_all_columns(self, real_devices):
        """测试标准化所有列"""
        task_config = {
            "input_data": {
                "alice": f"{TEST_DATA_DIR}/alice_raw.csv",
                "bob": f"{TEST_DATA_DIR}/bob_raw.csv",
            },
            "output_data": {
                "alice": f"{TEST_DATA_DIR}/alice_scaled_all.csv",
                "bob": f"{TEST_DATA_DIR}/bob_scaled_all.csv",
            },
            "with_mean": True,
            "with_std": True,
        }

        result = execute_standard_scaler(real_devices, task_config)

        assert "output_paths" in result
        assert result["with_mean"] is True
        assert result["with_std"] is True
        assert result["parties"] == ["alice", "bob"]
        assert os.path.exists(f"{TEST_DATA_DIR}/alice_scaled_all.csv")
        assert os.path.exists(f"{TEST_DATA_DIR}/bob_scaled_all.csv")

        print(f"\nStandardScaler Result (all columns): {result}")

    def test_execute_standard_scaler_specific_columns(self, real_devices):
        """测试标准化指定列"""
        task_config = {
            "input_data": {
                "alice": f"{TEST_DATA_DIR}/alice_raw.csv",
                "bob": f"{TEST_DATA_DIR}/bob_raw.csv",
            },
            "output_data": {
                "alice": f"{TEST_DATA_DIR}/alice_scaled_specific.csv",
                "bob": f"{TEST_DATA_DIR}/bob_scaled_specific.csv",
            },
            "columns": ["age", "income"],
            "with_mean": True,
            "with_std": True,
        }

        result = execute_standard_scaler(real_devices, task_config)

        assert "scaled_columns" in result
        assert result["scaled_columns"] == ["age", "income"]
        assert os.path.exists(f"{TEST_DATA_DIR}/alice_scaled_specific.csv")

        print(f"\nStandardScaler Result (specific columns): {result}")

    def test_execute_standard_scaler_without_mean(self, real_devices):
        """测试不使用均值中心化"""
        task_config = {
            "input_data": {
                "alice": f"{TEST_DATA_DIR}/alice_raw.csv",
                "bob": f"{TEST_DATA_DIR}/bob_raw.csv",
            },
            "output_data": {
                "alice": f"{TEST_DATA_DIR}/alice_scaled_nomean.csv",
                "bob": f"{TEST_DATA_DIR}/bob_scaled_nomean.csv",
            },
            "with_mean": False,
            "with_std": True,
        }

        result = execute_standard_scaler(real_devices, task_config)

        assert result["with_mean"] is False
        assert result["with_std"] is True

        print(f"\nStandardScaler Result (without mean): {result}")

    def test_execute_standard_scaler_column_not_exist(self, real_devices):
        """测试列不存在"""
        task_config = {
            "input_data": {
                "alice": f"{TEST_DATA_DIR}/alice_raw.csv",
                "bob": f"{TEST_DATA_DIR}/bob_raw.csv",
            },
            "output_data": {
                "alice": f"{TEST_DATA_DIR}/alice_scaled.csv",
                "bob": f"{TEST_DATA_DIR}/bob_scaled.csv",
            },
            "columns": ["nonexistent_column"],
        }

        with pytest.raises(ValueError) as exc_info:
            execute_standard_scaler(real_devices, task_config)

        assert "不存在于数据中" in str(exc_info.value)


class TestStandardScalerIntegration:
    """StandardScaler任务集成测试"""

    def test_standard_scaler_via_dispatcher(self, real_devices):
        """测试通过TaskDispatcher调用StandardScaler任务"""
        task_config = {
            "input_data": {
                "alice": f"{TEST_DATA_DIR}/alice_raw.csv",
                "bob": f"{TEST_DATA_DIR}/bob_raw.csv",
            },
            "output_data": {
                "alice": f"{TEST_DATA_DIR}/alice_scaled_dispatcher.csv",
                "bob": f"{TEST_DATA_DIR}/bob_scaled_dispatcher.csv",
            },
            "columns": ["age", "income"],
            "with_mean": True,
            "with_std": True,
        }

        result = TaskDispatcher.dispatch("standard_scaler", real_devices, task_config)

        assert "output_paths" in result
        assert "scaled_columns" in result
        assert result["scaled_columns"] == ["age", "income"]
        assert result["parties"] == ["alice", "bob"]

        print(f"\nDispatcher StandardScaler Result: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
