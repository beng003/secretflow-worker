#!/usr/bin/env python3
"""
发送Celery任务到指定队列的脚本 - 使用轻量级Celery实例
"""
import sys
import json
import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

# 获取项目根目录
project_root = Path(__file__).parent.parent

# 加载环境变量
env_file = project_root / ".env.production"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✅ 已加载环境配置: {env_file}")

# 从环境变量获取Redis URL
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
print(f"📋 REDIS_URL: {redis_url}")

# 创建轻量级Celery实例，只用于发送任务
# 避免导入整个应用和所有任务注册模块，大幅提升启动速度
app = Celery('secretflow_sender', broker=redis_url, backend=redis_url)

def send_task(task_name: str, args: list, queue: str = "secretflow_queue"):
    """
    发送任务到指定队列
    
    Args:
        task_name: 任务名称，如 "tasks.secretflow.execute_task"
        args: 任务参数列表
        queue: 目标队列名称
    """
    print(f"📤 发送任务到队列: {queue}")
    print(f"📋 任务名称: {task_name}")
    print(f"📦 任务参数: {json.dumps(args, indent=2, ensure_ascii=False)}")
    
    # 使用 apply_async 异步发送任务到队列
    result = app.send_task(
        task_name,
        args=args,
        queue=queue,
        routing_key=queue.replace('_queue', '')  # secretflow_queue -> secretflow
    )
    
    print(f"✅ 任务已发送")
    print(f"📋 任务ID: {result.id}")
    print(f"📊 任务状态: {result.state}")
    print(f"\n💡 查看任务结果:")
    print(f"   result = app.AsyncResult('{result.id}')")
    print(f"   result.get(timeout=300)")
    
    return result


if __name__ == "__main__":
    # 示例：发送 hello_task
    if len(sys.argv) > 1 and sys.argv[1] == "hello":
        result = send_task(
            "tasks.secretflow.hello.hello_task",
            args=[],
            queue="secretflow_queue"
        )
    
    # 示例：发送 health_check_task
    elif len(sys.argv) > 1 and sys.argv[1] == "health":
        result = send_task(
            "tasks.secretflow.health_check.health_check_task",
            args=[],
            queue="secretflow_queue"
        )
    
    # 示例：发送 PSI 任务（使用新的API结构）
    elif len(sys.argv) > 1 and sys.argv[1] == "psi":
        task_params = {
            # 新的三个ID字段
            "task_id": "psi-dag-12345",
            "subtask_id": "psi-node-67890", 
            "execution_id": "psi-exec-11111",
            
            # 原有配置保持不变
            "sf_init_config": {
                "parties": ["alice", "bob"],
                "address": "local"
            },
            "spu_config": {
                "cluster_def": {
                    "nodes": [
                        {"party": "alice", "address": "127.0.0.1:12345"},
                        {"party": "bob", "address": "127.0.0.1:12346"}
                    ],
                    "runtime_config": {
                        "protocol": "SEMI2K",
                        "field": "FM128"
                    }
                }
            },
            "task_config": {
                "task_type": "psi",
                "keys": {
                    "alice": ["uid"],
                    "bob": ["uid"]
                },
                "input_paths": {
                    "alice": "/app/data/alice.csv",
                    "bob": "/app/data/bob.csv"
                },
                "output_paths": {
                    "alice": "/app/data/alice_psi_cli_out.csv",
                    "bob": "/app/data/bob_psi_cli_out.csv"
                },
                "receiver": "alice",
                "protocol": "KKRT_PSI_2PC",
                "sort": True
            }
        }
        
        result = send_task(
            "tasks.secretflow.execute_task",
            args=[task_params],  # 现在只发送一个参数
            queue="secretflow_queue"
        )
    
    else:
        print("使用方法:")
        print("  python scripts/send_task.py hello   # 发送hello任务")
        print("  python scripts/send_task.py health  # 发送健康检查任务")
        print("  python scripts/send_task.py psi     # 发送PSI任务")
