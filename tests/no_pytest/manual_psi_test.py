import sys
import os
import pandas as pd
from datetime import datetime

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from secretflow_task.task_executor import execute_secretflow_task
from secretflow_task.celery_tasks import submit_secretflow_task


def prepare_test_data():
    """准备测试数据"""
    if not os.path.exists("tests/data"):
        os.makedirs("tests/data")

    # Alice数据 (id: 1-7)
    df_alice = pd.DataFrame(
        {
            "uid": [f"user_{i}" for i in range(1, 8)],
            "age": [20 + i for i in range(1, 8)],
        }
    )
    df_alice.to_csv("tests/data/alice.csv", index=False)

    # Bob数据 (id: 4-10) - 交集应该是 4,5,6,7
    df_bob = pd.DataFrame(
        {
            "uid": [f"user_{i}" for i in range(4, 11)],
            "score": [80 + i for i in range(4, 11)],
        }
    )
    df_bob.to_csv("tests/data/bob.csv", index=False)

    print("✅ 测试数据已生成: tests/data/alice.csv, tests/data/bob.csv")
    return os.path.abspath("tests/data/alice.csv"), os.path.abspath(
        "tests/data/bob.csv"
    )


def run_sync_psi():
    """方式1: 直接同步执行 (调试用)"""
    print("\n" + "=" * 50)
    print("🚀 开始同步执行 PSI 任务...")
    print("=" * 50)

    alice_path, bob_path = prepare_test_data()

    # 1. 任务请求ID
    task_id = f"psi-sync-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # 2. SecretFlow 初始化配置
    # 注意: 本地模拟模式使用 local 地址
    sf_init_config = {
        "parties": ["alice", "bob"],
        "address": "local",
    }

    # 3. SPU 配置
    # 本地模拟不需要真实的IP端口，SecretFlow会自动处理
    spu_config = {
        "cluster_def": {
            "nodes": [
                {"party": "alice", "address": "127.0.0.1:12345"},
                {"party": "bob", "address": "127.0.0.1:12346"},
            ],
            "runtime_config": {
                "protocol": "SEMI2K",  # SPU运行时协议，用于MPC计算
                "field": "FM128",
            },
        }
    }

    # 4. 任务配置
    task_config = {
        "task_type": "psi",
        "keys": "uid",
        "input_paths": {"alice": alice_path, "bob": bob_path},
        "output_paths": {
            "alice": os.path.abspath("tests/data/alice_psi_out.csv"),
            "bob": os.path.abspath("tests/data/bob_psi_out.csv"),
        },
        "receiver_party": "alice",
        "protocol": "KKRT_PSI_2PC",  # PSI具体协议
        "sort": True,
    }

    try:
        # 直接调用执行器
        result = execute_secretflow_task(
            task_request_id=task_id,
            sf_init_config=sf_init_config,
            spu_config=spu_config,
            heu_config=None,
            task_config=task_config,
        )

        print("\n✅ 任务执行成功!")
        print(f"交集数量: {result['result']['intersection_count']}")
        print(f"总耗时: {result['performance_metrics']['total_execution_time']}s")

    except Exception as e:
        print(f"\n❌ 任务执行失败: {e}")
        import traceback

        traceback.print_exc()


def run_async_celery():
    """方式2: 提交到 Celery (生产用)"""
    print("\n" + "=" * 50)
    print("📨 提交 PSI 任务到 Celery...")
    print("=" * 50)

    alice_path, bob_path = prepare_test_data()

    # 配置同上...
    task_id = f"psi-async-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # ... (为了演示简洁，配置略，实际使用时传入完整的配置字典)
    # 这里仅演示 API 调用方式，因为没有启动 Celery Worker，实际不会执行

    print("提示: 确保 Celery Worker 已启动 (celery -A src.celery_app worker ...)")

    # 模拟参数
    sf_init_config = {"parties": ["alice", "bob"], "address": "local"}
    spu_config = {
        "cluster_def": {
            "nodes": [
                {"party": "alice", "address": "127.0.0.1:12345"},
                {"party": "bob", "address": "127.0.0.1:12346"},
            ],
            "runtime_config": {
                "protocol": "SEMI2K",  # SPU运行时协议，用于MPC计算
                "field": "FM128",
            },
        }
    }
    task_config = {
        "task_type": "psi",
        "keys": "uid",
        "input_paths": {"alice": alice_path, "bob": bob_path},
        "output_paths": {
            "alice": os.path.abspath("tests/data/alice_psi_out.csv"),
            "bob": os.path.abspath("tests/data/bob_psi_out.csv"),
        },
        "receiver_party": "alice",
        "protocol": "KKRT_PSI_2PC",  # PSI具体协议
        "sort": True,
    }

    try:
        celery_id = submit_secretflow_task(
            task_request_id=task_id,
            sf_init_config=sf_init_config,
            spu_config=spu_config,
            heu_config=None,
            task_config=task_config,
        )
        print(f"✅ 任务已提交! Celery ID: {celery_id}")

    except Exception as e:
        print(f"❌ 提交失败: {e}")


if __name__ == "__main__":
    # 默认运行同步模式进行测试
    # run_sync_psi()

    # 如果环境准备好，可以取消注释测试 Celery
    run_async_celery()
