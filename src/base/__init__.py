"""
任务基类模块

提供统一的Celery任务基类，集成项目的日志系统、数据库管理和异常处理机制。
包含异步执行助手，解决事件循环冲突和线程安全问题。
"""

from .async_helpers import (
    AsyncExecutionError,
    AsyncTimeoutError,
    get_async_execution_stats,
    run_async_safely,
)

# 数据库上下文管理已移除，仅保留任务相关功能
from .task_base import BaseTask, SecretFlowTask, WebTask

__all__ = [
    # 任务基类
    "BaseTask",
    "WebTask",
    "SecretFlowTask",
    # 异步执行助手（仅保留纯计算相关）
    "run_async_safely",
    # 异常类
    "AsyncExecutionError",
    "AsyncTimeoutError",
    # 统计功能
    "get_async_execution_stats",
]
