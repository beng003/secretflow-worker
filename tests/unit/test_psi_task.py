"""
PSI任务单元测试

测试PSI任务的配置验证、执行逻辑和错误处理。
使用真实的SecretFlow设备进行测试。
"""

import pytest
import os
import tempfile
from pathlib import Path
import secretflow as sf
import numpy as np
from sklearn.datasets import load_iris

from secretflow_task.jobs.psi_task import (
    execute_psi,
    _validate_psi_config,
    _count_csv_lines,
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

    # 准备测试数据
    data, target = load_iris(return_X_y=True, as_frame=True)
    data["uid"] = np.arange(len(data)).astype("str")
    data["month"] = ["Jan"] * 75 + ["Feb"] * 75

    # 创建测试数据文件
    da, db = (
        data.sample(frac=0.9, random_state=42),
        data.sample(frac=0.8, random_state=42),
    )
    da.to_csv(f"{TEST_DATA_DIR}/alice.csv", index=False)
    db.to_csv(f"{TEST_DATA_DIR}/bob.csv", index=False)

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
    spu = sf.SPU(sf.utils.testing.cluster_def(["alice", "bob"]))

    devices = {"alice": alice, "bob": bob, "spu": spu}

    return devices


class TestPSIConfigValidation:
    """PSI配置验证测试"""

    def test_validate_psi_config_success(self):
        """测试有效的PSI配置"""
        config = {
            "keys": {"alice": ["uid"], "bob": ["uid"]},
            "input_paths": {
                "alice": f"{TEST_DATA_DIR}/alice.csv",
                "bob": f"{TEST_DATA_DIR}/bob.csv",
            },
            "output_paths": {
                "alice": f"{TEST_DATA_DIR}/alice_psi.csv",
                "bob": f"{TEST_DATA_DIR}/bob_psi.csv",
            },
            "receiver": "alice",
        }

        _validate_psi_config(config)

    def test_validate_psi_config_missing_field(self):
        """测试缺少必需字段"""
        config = {
            "keys": {"alice": ["uid"]},
            "input_paths": {"alice": "/data/alice.csv"},
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_psi_config(config)

        assert "缺少必需字段" in str(exc_info.value)

    def test_validate_psi_config_invalid_keys_type(self):
        """测试keys类型错误"""
        config = {
            "keys": ["uid"],
            "input_paths": {"alice": "/data/alice.csv"},
            "output_paths": {"alice": "/data/alice_psi.csv"},
            "receiver": "alice",
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_psi_config(config)

        assert "keys必须是字典类型" in str(exc_info.value)

    def test_validate_psi_config_empty_keys(self):
        """测试空keys"""
        config = {
            "keys": {},
            "input_paths": {},
            "output_paths": {},
            "receiver": "alice",
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_psi_config(config)

        assert "keys不能为空" in str(exc_info.value)

    def test_validate_psi_config_parties_mismatch(self):
        """测试参与方不一致"""
        config = {
            "keys": {"alice": ["uid"], "bob": ["uid"]},
            "input_paths": {"alice": "/data/alice.csv"},
            "output_paths": {
                "alice": "/data/alice_psi.csv",
                "bob": "/data/bob_psi.csv",
            },
            "receiver": "alice",
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_psi_config(config)

        assert "参与方不一致" in str(exc_info.value)

    def test_validate_psi_config_invalid_receiver(self):
        """测试无效的receiver"""
        config = {
            "keys": {"alice": ["uid"], "bob": ["uid"]},
            "input_paths": {"alice": "/data/alice.csv", "bob": "/data/bob.csv"},
            "output_paths": {
                "alice": "/data/alice_psi.csv",
                "bob": "/data/bob_psi.csv",
            },
            "receiver": "charlie",
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_psi_config(config)

        assert "不在参与方列表中" in str(exc_info.value)

    def test_validate_psi_config_invalid_key_list_type(self):
        """测试key列表类型错误"""
        config = {
            "keys": {"alice": "uid", "bob": ["uid"]},
            "input_paths": {"alice": "/data/alice.csv", "bob": "/data/bob.csv"},
            "output_paths": {
                "alice": "/data/alice_psi.csv",
                "bob": "/data/bob_psi.csv",
            },
            "receiver": "alice",
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_psi_config(config)

        assert "keys必须是列表类型" in str(exc_info.value)

    def test_validate_psi_config_empty_key_list(self):
        """测试空key列表"""
        config = {
            "keys": {"alice": [], "bob": ["uid"]},
            "input_paths": {"alice": "/data/alice.csv", "bob": "/data/bob.csv"},
            "output_paths": {
                "alice": "/data/alice_psi.csv",
                "bob": "/data/bob_psi.csv",
            },
            "receiver": "alice",
        }

        with pytest.raises(ValueError) as exc_info:
            _validate_psi_config(config)

        assert "keys不能为空" in str(exc_info.value)

    def test_validate_psi_config_multi_column(self):
        """测试多列PSI配置"""
        config = {
            "keys": {"alice": ["uid", "month"], "bob": ["uid", "month"]},
            "input_paths": {
                "alice": f"{TEST_DATA_DIR}/alice.csv",
                "bob": f"{TEST_DATA_DIR}/bob.csv",
            },
            "output_paths": {
                "alice": f"{TEST_DATA_DIR}/alice_psi.csv",
                "bob": f"{TEST_DATA_DIR}/bob_psi.csv",
            },
            "receiver": "alice",
        }

        _validate_psi_config(config)


class TestCountCSVLines:
    """CSV行数统计测试"""

    def test_count_csv_lines_success(self, setup_secretflow):
        """测试正常统计CSV行数"""
        count = _count_csv_lines(f"{TEST_DATA_DIR}/alice.csv")
        assert count > 0

    def test_count_csv_lines_empty_file(self):
        """测试空文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            count = _count_csv_lines(temp_path)
            assert count == 0
        finally:
            os.unlink(temp_path)

    def test_count_csv_lines_only_header(self):
        """测试只有表头的文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("uid,name,age\n")
            temp_path = f.name

        try:
            count = _count_csv_lines(temp_path)
            assert count == 0
        finally:
            os.unlink(temp_path)

    def test_count_csv_lines_nonexistent_file(self):
        """测试不存在的文件"""
        count = _count_csv_lines("/nonexistent/path/file.csv")
        assert count == 0


class TestExecutePSI:
    """PSI任务执行测试 - 使用真实设备"""

    def test_psi_task_registered(self):
        """测试PSI任务已注册"""
        assert "psi" in TaskDispatcher.TASK_REGISTRY

    def test_execute_psi_missing_spu_device(self, real_devices):
        """测试缺少SPU设备"""
        devices = {"alice": real_devices["alice"], "bob": real_devices["bob"]}

        task_config = {
            "keys": {"alice": ["uid"], "bob": ["uid"]},
            "input_paths": {
                "alice": f"{TEST_DATA_DIR}/alice.csv",
                "bob": f"{TEST_DATA_DIR}/bob.csv",
            },
            "output_paths": {
                "alice": f"{TEST_DATA_DIR}/alice_psi.csv",
                "bob": f"{TEST_DATA_DIR}/bob_psi.csv",
            },
            "receiver": "alice",
        }

        with pytest.raises(ValueError) as exc_info:
            execute_psi(devices, task_config)

        assert "缺少'spu'设备" in str(exc_info.value)

    def test_execute_psi_missing_pyu_device(self, real_devices):
        """测试缺少PYU设备"""
        devices = {"spu": real_devices["spu"], "alice": real_devices["alice"]}

        task_config = {
            "keys": {"alice": ["uid"], "bob": ["uid"]},
            "input_paths": {
                "alice": f"{TEST_DATA_DIR}/alice.csv",
                "bob": f"{TEST_DATA_DIR}/bob.csv",
            },
            "output_paths": {
                "alice": f"{TEST_DATA_DIR}/alice_psi.csv",
                "bob": f"{TEST_DATA_DIR}/bob_psi.csv",
            },
            "receiver": "alice",
        }

        with pytest.raises(ValueError) as exc_info:
            execute_psi(devices, task_config)

        assert "缺少参与方'bob'的PYU设备" in str(exc_info.value)

    def test_execute_psi_success(self, real_devices):
        """测试PSI执行成功"""
        task_config = {
            "keys": {"alice": ["uid"], "bob": ["uid"]},
            "input_paths": {
                "alice": f"{TEST_DATA_DIR}/alice.csv",
                "bob": f"{TEST_DATA_DIR}/bob.csv",
            },
            "output_paths": {
                "alice": f"{TEST_DATA_DIR}/alice_psi_test1.csv",
                "bob": f"{TEST_DATA_DIR}/bob_psi_test1.csv",
            },
            "receiver": "alice",
            "protocol": "KKRT_PSI_2PC",
        }

        result = execute_psi(real_devices, task_config)

        assert result["intersection_count"] > 0
        assert result["psi_protocol"] == "KKRT_PSI_2PC"
        assert result["receiver"] == "alice"
        assert result["parties"] == ["alice", "bob"]
        assert os.path.exists(f"{TEST_DATA_DIR}/alice_psi_test1.csv")

        print(f"\nPSI Result: {result}")

    def test_execute_psi_multi_column(self, real_devices):
        """测试多列PSI"""
        task_config = {
            "keys": {"alice": ["uid", "month"], "bob": ["uid", "month"]},
            "input_paths": {
                "alice": f"{TEST_DATA_DIR}/alice.csv",
                "bob": f"{TEST_DATA_DIR}/bob.csv",
            },
            "output_paths": {
                "alice": f"{TEST_DATA_DIR}/alice_psi_test2.csv",
                "bob": f"{TEST_DATA_DIR}/bob_psi_test2.csv",
            },
            "receiver": "alice",
        }

        result = execute_psi(real_devices, task_config)

        assert result["intersection_count"] > 0
        assert os.path.exists(f"{TEST_DATA_DIR}/alice_psi_test2.csv")

        print(f"\nMulti-column PSI Result: {result}")


class TestPSITaskIntegration:
    """PSI任务集成测试"""

    def test_psi_task_via_dispatcher(self, real_devices):
        """测试通过TaskDispatcher调用PSI任务"""
        task_config = {
            "keys": {"alice": ["uid"], "bob": ["uid"]},
            "input_paths": {
                "alice": f"{TEST_DATA_DIR}/alice.csv",
                "bob": f"{TEST_DATA_DIR}/bob.csv",
            },
            "output_paths": {
                "alice": f"{TEST_DATA_DIR}/alice_psi_test3.csv",
                "bob": f"{TEST_DATA_DIR}/bob_psi_test3.csv",
            },
            "receiver": "alice",
        }

        result = TaskDispatcher.dispatch("psi", real_devices, task_config)

        assert "intersection_count" in result
        assert "psi_protocol" in result
        assert result["receiver"] == "alice"
        assert result["intersection_count"] > 0

        print(f"\nDispatcher PSI Result: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
