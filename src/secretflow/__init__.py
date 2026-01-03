"""
SecretFlow任务模块

包含SecretFlow相关的Celery任务定义。
"""

# 导入任务以确保它们被Celery发现和注册
from .hello import hello_task, ping_task, echo_task
from .local_test import local_psi_test

__all__ = [
    "hello_task",
    "ping_task", 
    "echo_task",
    "local_psi_test"
]