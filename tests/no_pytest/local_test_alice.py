#!/usr/bin/env python3
"""
简化版PSI单机测试
专门为SecretFlow单机仿真模式设计
"""

from datetime import datetime
from typing import Any, Dict

# 使用项目统一的日志系统
# from src.utils.log import logger


def local_psi_test() -> Dict[str, Any]:
    """
    Hello World 测试任务

    这是一个简单的测试任务，用于验证Celery任务系统是否正常工作。

    Args:
        name: 问候的名称，默认为"SecretFlow"

    Returns:
        包含问候信息和执行详情的字典
    """
    import secretflow as sf

    # Check the version of your SecretFlow
    print("The version of SecretFlow: {}".format(sf.__version__))

    start_time = datetime.now()

    cluster_config = {
        "parties": {
            "alice": {
                # replace with alice's real address.
                "address": "127.0.0.1:7700",
                "listen_addr": "0.0.0.0:7700",
            },
            "bob": {
                # replace with bob's real address.
                "address": "127.0.0.1:7800",
                "listen_addr": "0.0.0.0:7800",
            },
        },
        "self_party": "alice",
    }

    sf.init(address="127.0.0.1:7701", cluster_config=cluster_config, ray_mode=False)

    print("SecretFlow initialized successfully")

    import numpy as np
    from sklearn.datasets import load_iris

    data, target = load_iris(return_X_y=True, as_frame=True)
    data["uid"] = np.arange(len(data)).astype("str")
    data["month"] = ["Jan"] * 75 + ["Feb"] * 75

    import os
    from pathlib import Path

    test_data_path = str(Path(__file__).parent.parent / "data")

    os.makedirs(test_data_path, exist_ok=True)
    da, db = data.sample(frac=0.9), data.sample(frac=0.8)

    da.to_csv(f"{test_data_path}/alice.csv", index=False)
    db.to_csv(f"{test_data_path}/bob.csv", index=False)

    print("Data prepared")

    alice, bob = sf.PYU("alice"), sf.PYU("bob")

    import spu

    cluster_def = {
        "nodes": [
            {
                "party": "alice",
                # Please choose an unused port.
                "address": "127.0.0.1:7702",
                "listen_addr": "0.0.0.0:7702",
            },
            {
                "party": "bob",
                # Please choose an unused port.
                "address": "127.0.0.1:7802",
                "listen_addr": "0.0.0.0:7802",
            },
        ],
        "runtime_config": {
            "protocol": spu.ProtocolKind.SEMI2K,
            "field": spu.FieldType.FM128,
            "sigmoid_mode": spu.RuntimeConfig.SigmoidMode.SIGMOID_REAL,
        },
    }

    spu = sf.SPU(cluster_def=cluster_def)

    print("About to run PSI")
    # 1. 单键隐私求交
    input_path = {
        alice.party: f"{test_data_path}/alice.csv",
        bob.party: f"{test_data_path}/input.csv",
    }
    output_path = {
        alice.party: f"{test_data_path}/alice_psi.csv",
        bob.party: f"{test_data_path}/output.csv",
    }
    sf.wait(
        spu.psi(
            {alice.party: ["uid"], bob.party: ["id"]},
            input_path,
            output_path,
            "alice",
            {alice.party: True, bob.party: True},
            disable_alignment=True,
        )
    )
    print("spu psi completed")
    sf.shutdown()

    # 4. result
    end_time = datetime.now()
    execution_duration = (end_time - start_time).total_seconds()
    result = {
        "message": "SecretFlow local test success",
        "task_name": "local_test",
        "timestamp": datetime.now().isoformat(),
        "execution_duration": execution_duration,
        "status": "success",
    }

    return result


if __name__ == "__main__":
    local_psi_test()
