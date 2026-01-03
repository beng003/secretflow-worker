"""
统一任务基类模块

提供各种Celery任务基类，集成项目统一的日志系统、数据库连接管理和异常处理机制。
按照celery_todo.md重构要求，移除事件循环手动管理，复用现有系统配置。
"""

import time
from abc import ABC
from typing import Any

from celery import Task

# 使用项目统一的loguru日志系统，替代celery日志
from src.log import logger


class BaseTask(Task, ABC):
    """
    统一任务基类 - 提供通用任务功能

    关键改进：
    - 集成现有的log.log.logger统一日志格式
    - 统一的异常处理和错误报告
    """

    def __init__(self):
        super().__init__()
        self._start_time = None
        self._task_context = {}


    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        """任务开始前的钩子"""
        self._start_time = time.time()
        self._task_context = {
            "task_id": task_id,
            "args": args,
            "kwargs": kwargs,
            "start_time": self._start_time,
        }

        queue_name = getattr(self.request, "delivery_info", {}).get(
            "routing_key", "default"
        )

        # 使用项目统一的loguru日志系统
        logger.info(
            f"[CELERY] 任务 {task_id} 开始执行",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args_count": len(args),
                "kwargs_count": len(kwargs),
                "queue_name": queue_name,
            },
        )

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """任务成功完成的钩子"""
        execution_time = time.time() - self._start_time if self._start_time else 0

        logger.info(
            f"[CELERY] 任务 {task_id} 执行成功，耗时 {execution_time:.2f} 秒",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "execution_time": execution_time,
                "status": "SUCCESS",
                "result_type": type(retval).__name__,
            },
        )

        # 记录任务执行统计
        self._record_task_statistics(task_id, "SUCCESS", execution_time, None)

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo
    ) -> None:
        """任务失败的钩子"""
        execution_time = time.time() - self._start_time if self._start_time else 0
        error_msg = str(exc)
        error_type = type(exc).__name__
        retry_count = getattr(self.request, "retries", 0)

        logger.error(
            f"[CELERY] 任务 {task_id} 执行失败，耗时 {execution_time:.2f} 秒",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "execution_time": execution_time,
                "status": "FAILURE",
                "error_type": error_type,
                "error_message": error_msg,
                "retry_count": retry_count,
            },
        )

        # 记录详细错误信息用于调试
        logger.debug(
            f"[CELERY] 任务 {task_id} 失败详情",
            extra={
                "task_id": task_id,
                "error_traceback": str(einfo),
            },
        )

        # 记录任务执行统计
        self._record_task_statistics(task_id, "FAILURE", execution_time, error_msg)

    def on_retry(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo
    ) -> None:
        """任务重试的钩子"""
        retry_count = self.request.retries if hasattr(self.request, "retries") else 0

        logger.warning(
            f"[CELERY] 任务 {task_id} 正在重试 (第{retry_count + 1}次)",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "retry_count": retry_count,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )

        # 更新重试统计
        self._record_task_retry(task_id, str(exc))

    def _record_task_statistics(
        self, task_id: str, status: str, execution_time: float, error_msg: str | None
    ) -> None:
        """
        记录任务执行统计

        集成现有的异常处理机制，统一错误报告格式
        """
        try:
            # 这里可以记录到数据库或监控系统
            stats = {
                "task_id": task_id,
                "task_name": self.name,
                "status": status,
                "execution_time": execution_time,
                "error_message": error_msg,
                "timestamp": time.time(),
                "queue": getattr(self.request, "delivery_info", {}).get(
                    "routing_key", "unknown"
                ),
            }

            # 使用debug级别记录统计信息，避免日志噪音
            logger.debug(
                "[CELERY] 任务统计记录",
                extra={
                    "task_statistics": stats,
                },
            )

        except Exception as e:
            # 集成现有异常处理机制
            logger.error(
                "[CELERY] 记录任务统计失败",
                extra={
                    "task_id": task_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

    def _record_task_retry(self, task_id: str, error_msg: str) -> None:
        """记录任务重试信息"""
        try:
            retry_count = getattr(self.request, "retries", 0)
            retry_info = {
                "task_id": task_id,
                "task_name": self.name,
                "retry_count": retry_count,
                "error_message": error_msg,
                "timestamp": time.time(),
            }

            logger.debug(
                "[CELERY] 任务重试记录",
                extra={
                    "task_retry_info": retry_info,
                },
            )

        except Exception as e:
            logger.error(
                "[CELERY] 记录任务重试信息失败",
                extra={
                    "task_id": task_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

class WebTask(BaseTask):
    """
    Web应用任务基类

    专用于Web相关任务（证书检查、诊断等），提供Web任务特有的功能
    """

    # Web任务默认配置
    abstract = True
    default_retry_delay = 60  # 60秒重试延迟
    max_retries = 3  # 最大重试次数

    def __init__(self):
        super().__init__()

    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        """Web任务开始前的钩子"""
        super().before_start(task_id, args, kwargs)
        logger.info(
            f"[WEB-TASK] Web任务 {task_id} 开始执行",
            extra={
                "task_category": "web",
                "task_id": task_id,
            },
        )


class SecretFlowTask(BaseTask):
    """
    SecretFlow任务基类

    专用于SecretFlow隐私计算任务，提供进程隔离和长时间运行支持
    """

    # SecretFlow任务默认配置
    abstract = True
    default_retry_delay = 300  # 5分钟重试延迟
    max_retries = 2  # 最大重试次数
    time_limit = 7200  # 2小时硬超时
    soft_time_limit = 6600  # 1小时50分钟软超时

    def __init__(self):
        super().__init__()

    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        """SecretFlow任务开始前的钩子"""
        super().before_start(task_id, args, kwargs)
        logger.info(
            f"[SECRETFLOW-TASK] SecretFlow任务 {task_id} 开始执行",
            extra={
                "task_category": "secretflow",
                "task_id": task_id,
                "time_limit": self.time_limit,
                "soft_time_limit": self.soft_time_limit,
            },
        )

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo
    ) -> None:
        """SecretFlow任务失败处理"""
        super().on_failure(exc, task_id, args, kwargs, einfo)

        # SecretFlow任务失败时的特殊处理
        logger.critical(
            f"[SECRETFLOW-TASK] 关键任务失败 {task_id}",
            extra={
                "task_category": "secretflow",
                "task_id": task_id,
                "critical_failure": True,
            },
        )
