from datetime import datetime
from typing import Any, Dict

# 使用项目统一的日志系统

# 使用任务基类
from base import BaseTask
from celery_app import celery_app


@celery_app.task(base=BaseTask, name="tasks.secretflow.local_test.local_psi_test")
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
    sf.init(parties=["alice", "bob"], address="local")

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
    spu = sf.SPU(sf.utils.testing.cluster_def(["alice", "bob"]))

    print("About to run PSI")
    # 1. 单键隐私求交
    input_path = {
        alice.party: f"{test_data_path}/alice.csv",
        bob.party: f"{test_data_path}/bob.csv",
    }
    output_path = {
        alice.party: f"{test_data_path}/alice_psi.csv",
        bob.party: f"{test_data_path}/bob_psi.csv",
    }
    spu.psi(
        {alice.party: ["uid"], bob.party: ["uid"]},
        input_path,
        output_path,
        "alice",
        {alice.party: True, bob.party: True},
        disable_alignment=True,
    )

    print("spu psi completed")

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
