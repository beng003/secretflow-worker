from datetime import datetime
from typing import Any, Dict

# 使用项目统一的日志系统
from utils.log import logger

# 使用任务基类
from base import BaseTask
from celery_app import celery_app


@celery_app.task(base=BaseTask, name="tasks.secretflow.hello.hello_task")
def hello_task(name: str = "SecretFlow") -> Dict[str, Any]:
    """
    Hello World 测试任务

    这是一个简单的测试任务，用于验证Celery任务系统是否正常工作。

    Args:
        name: 问候的名称，默认为"SecretFlow"

    Returns:
        包含问候信息和执行详情的字典
    """

    start_time = datetime.now()

    logger.info(f"[HELLO-TASK] 开始执行Hello任务，问候对象: {name}")

    # 模拟一些简单的计算工作
    import time

    time.sleep(1)  # 模拟1秒的工作时间

    end_time = datetime.now()
    execution_duration = (end_time - start_time).total_seconds()

    result = {
        "message": f"Hello, {name}! 欢迎使用SecretFlow测试系统",
        "task_name": "hello_task",
        "execution_time": execution_duration,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "status": "success",
        "greeting_target": name,
        "system_info": {
            "python_version": "3.10+",
            "task_queue": "secretflow_queue",
            "worker_type": "secretflow",
        },
    }

    logger.info(
        f"[HELLO-TASK] Hello任务执行完成，耗时 {execution_duration:.2f} 秒",
        extra={"result": result},
    )

    return result


@celery_app.task(base=BaseTask, name="tasks.secretflow.hello.ping_task")
def ping_task() -> Dict[str, Any]:
    """
    Ping 测试任务

    简单的连通性测试任务，用于验证任务队列和worker状态。

    Returns:
        包含ping响应信息的字典
    """

    timestamp = datetime.now()

    logger.info("[PING-TASK] 执行Ping测试")

    result = {
        "message": "Pong! SecretFlow任务系统正常运行",
        "task_name": "ping_task",
        "timestamp": timestamp.isoformat(),
        "status": "healthy",
        "response_time_ms": 1,  # 模拟响应时间
    }

    logger.info("[PING-TASK] Ping测试完成", extra={"result": result})

    return result


@celery_app.task(base=BaseTask, name="tasks.secretflow.hello.echo_task")
def echo_task(data: Any) -> Dict[str, Any]:
    """
    Echo 回显任务

    接收任意数据并原样返回，用于测试数据传输和序列化。

    Args:
        data: 要回显的数据（任意类型）

    Returns:
        包含回显数据和元信息的字典
    """

    timestamp = datetime.now()
    data_type = type(data).__name__

    logger.info(
        f"[ECHO-TASK] 执行Echo任务，数据类型: {data_type}", extra={"input_data": data}
    )

    result = {
        "message": "数据回显成功",
        "task_name": "echo_task",
        "timestamp": timestamp.isoformat(),
        "echoed_data": data,
        "data_type": data_type,
        "data_length": len(str(data)) if data is not None else 0,
        "status": "success",
    }

    logger.info(
        f"[ECHO-TASK] Echo任务完成，回显数据类型: {data_type}", extra={"result": result}
    )

    return result


# 任务注册信息
__all__ = ["hello_task", "ping_task", "echo_task"]
