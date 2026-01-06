"""
SecretFlow Celery任务集成

将SecretFlow任务执行器集成到Celery任务队列系统中，
提供异步任务执行、超时控制、重试机制和执行监控功能。
"""

import time
import json
from typing import Dict, Any, Optional
from datetime import datetime
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from celery_app import celery_app
from .task_executor import execute_secretflow_task
from utils.log import logger
from utils.status_notifier import _publish_status
from utils.exceptions import ClusterInitError, DeviceConfigError


class SecretFlowTask(Task):
    """SecretFlow任务基类

    提供SecretFlow任务的通用功能：
    - 任务状态追踪
    - 执行监控
    - 错误处理
    - 资源管理
    """

    # 任务重试配置
    autoretry_for = (ClusterInitError, DeviceConfigError)
    retry_kwargs = {"max_retries": 3, "countdown": 60}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    # 任务时间限制（秒）
    soft_time_limit = 3600  # 1小时软限制
    time_limit = 3900  # 1小时15分钟硬限制

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试时的回调

        Args:
            exc: 触发重试的异常
            task_id: 任务ID
            args: 任务位置参数
            kwargs: 任务关键字参数
            einfo: 异常信息
        """
        task_request_id = args[0] if args else kwargs.get("task_request_id", "unknown")

        logger.warning(
            f"SecretFlow任务重试: task_id={task_id}, "
            f"request_id={task_request_id}, "
            f"retry_count={self.request.retries}, "
            f"reason={str(exc)}"
        )

        # 发送重试状态通知
        try:
            _publish_status(
                task_request_id,
                "RETRY",
                {
                    "stage": "task_retrying",
                    "retry_count": self.request.retries,
                    "max_retries": self.max_retries,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "next_retry_at": datetime.now().isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"发送重试状态失败: {e}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的回调

        Args:
            exc: 导致失败的异常
            task_id: 任务ID
            args: 任务位置参数
            kwargs: 任务关键字参数
            einfo: 异常信息
        """
        task_request_id = args[0] if args else kwargs.get("task_request_id", "unknown")

        logger.error(
            f"SecretFlow任务失败: task_id={task_id}, "
            f"request_id={task_request_id}, "
            f"error={str(exc)}",
            exc_info=True,
        )

        # 发送失败状态通知（额外保障）
        try:
            _publish_status(
                task_request_id,
                "FAILURE",
                {
                    "stage": "task_failed_final",
                    "celery_task_id": task_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "retries_exhausted": self.request.retries >= self.max_retries,
                    "failed_at": datetime.now().isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"发送失败状态失败: {e}")

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的回调

        Args:
            retval: 任务返回值
            task_id: 任务ID
            args: 任务位置参数
            kwargs: 任务关键字参数
        """
        task_request_id = args[0] if args else kwargs.get("task_request_id", "unknown")

        logger.info(
            f"SecretFlow任务成功: task_id={task_id}, request_id={task_request_id}"
        )


def _serialize_task_params(task_params: Dict[str, Any]) -> str:
    """序列化任务参数

    将任务参数转换为JSON字符串，便于传输和存储。

    Args:
        task_params: 任务参数字典

    Returns:
        str: JSON序列化后的字符串

    Raises:
        ValueError: 参数无法序列化
    """
    try:
        return json.dumps(task_params, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        error_msg = f"任务参数序列化失败: {e}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e


def _deserialize_task_params(serialized_params: str) -> Dict[str, Any]:
    """反序列化任务参数

    将JSON字符串转换回任务参数字典。

    Args:
        serialized_params: JSON序列化的参数字符串

    Returns:
        Dict[str, Any]: 任务参数字典

    Raises:
        ValueError: 参数无法反序列化
    """
    try:
        return json.loads(serialized_params)
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        error_msg = f"任务参数反序列化失败: {e}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e


def _validate_task_params(task_params: Dict[str, Any]) -> None:
    """验证任务参数完整性

    Args:
        task_params: 任务参数字典

    Raises:
        ValueError: 参数验证失败
    """
    required_keys = ["sf_init_config", "spu_config", "task_config"]

    for key in required_keys:
        if key not in task_params:
            raise ValueError(f"缺少必需参数: {key}")

    # 验证task_config中的task_type
    task_config = task_params.get("task_config", {})
    if not task_config.get("task_type"):
        raise ValueError("task_config中缺少task_type字段")


@celery_app.task(
    bind=True,
    base=SecretFlowTask,
    name="tasks.secretflow.execute_task",
    queue="secretflow_queue",
    acks_late=True,
    reject_on_worker_lost=True,
    track_started=True,
)
def execute_secretflow_celery_task(
    self, task_request_id: str, task_params: Dict[str, Any]
) -> Dict[str, Any]:
    """SecretFlow任务的Celery包装器

    将SecretFlow任务执行器封装为Celery异步任务，提供：
    - 异步执行
    - 超时控制
    - 自动重试
    - 执行监控
    - 状态追踪
    # note: 任务执行参数

    Args:
        self: Celery任务实例（bind=True时自动传入）
        task_request_id: 任务请求唯一标识符
        task_params: 任务参数字典，包含：
            - sf_init_config: SecretFlow集群初始化配置
            - spu_config: SPU设备配置
            - heu_config: HEU设备配置（可选）
            - task_config: 任务特定执行配置

    Returns:
        Dict[str, Any]: 任务执行结果，包含：
            - status: 执行状态
            - result: 算法执行结果
            - performance_metrics: 性能指标
            - task_metadata: 任务元数据
            - celery_metadata: Celery任务元数据

    Raises:
        SoftTimeLimitExceeded: 任务执行超时
        Exception: 任务执行失败
    """
    execution_start = time.time()
    celery_task_id = self.request.id

    try:
        logger.info(
            "=" * 80 + "\n"
            "Celery SecretFlow任务开始\n"
            f"  Celery任务ID: {celery_task_id}\n"
            f"  请求ID: {task_request_id}\n"
            f"  任务类型: {task_params.get('task_config', {}).get('task_type', 'unknown')}\n"
            f"  队列: {self.request.delivery_info.get('routing_key', 'unknown')}\n"
            f"  重试次数: {self.request.retries}\n" + "=" * 80
        )

        # 发送Celery任务开始状态
        _publish_status(
            task_request_id,
            "RUNNING",
            {
                "stage": "celery_task_started",
                "celery_task_id": celery_task_id,
                "task_type": task_params.get("task_config", {}).get("task_type"),
                "retry_count": self.request.retries,
                "started_at": datetime.now().isoformat(),
            },
        )

        # 1. 验证任务参数
        logger.info("验证任务参数...")
        _validate_task_params(task_params)

        # 2. 提取参数
        sf_init_config = task_params["sf_init_config"]
        spu_config = task_params["spu_config"]
        heu_config = task_params.get("heu_config", None)
        task_config = task_params["task_config"]

        # 3. 更新任务状态为STARTED
        self.update_state(
            state="STARTED",
            meta={
                "task_request_id": task_request_id,
                "task_type": task_config.get("task_type"),
                "started_at": datetime.now().isoformat(),
            },
        )

        # 4. 执行SecretFlow任务
        logger.info("调用SecretFlow任务执行器...")

        try:
            result = execute_secretflow_task(
                task_request_id=task_request_id,
                sf_init_config=sf_init_config,
                spu_config=spu_config,
                heu_config=heu_config,
                task_config=task_config,
            )
        except SoftTimeLimitExceeded:
            # 任务超时
            execution_time = time.time() - execution_start
            error_msg = (
                f"任务执行超时: {execution_time:.2f}秒 > {self.soft_time_limit}秒"
            )

            logger.error(error_msg)

            _publish_status(
                task_request_id,
                "FAILURE",
                {
                    "stage": "task_timeout",
                    "celery_task_id": celery_task_id,
                    "error": error_msg,
                    "error_type": "SoftTimeLimitExceeded",
                    "execution_time": execution_time,
                    "time_limit": self.soft_time_limit,
                    "failed_at": datetime.now().isoformat(),
                },
            )

            # 重新抛出异常
            raise

        # 5. 收集Celery元数据
        celery_execution_time = time.time() - execution_start

        celery_metadata = {
            "celery_task_id": celery_task_id,
            "celery_queue": self.request.delivery_info.get("routing_key", "unknown"),
            "celery_exchange": self.request.delivery_info.get("exchange", "unknown"),
            "retry_count": self.request.retries,
            "celery_execution_time": round(celery_execution_time, 2),
            "worker_hostname": self.request.hostname,
            "task_eta": str(self.request.eta) if self.request.eta else None,
        }

        # 6. 构建完整结果
        final_result = {**result, "celery_metadata": celery_metadata}

        # 7. 更新任务状态为SUCCESS
        self.update_state(
            state="SUCCESS",
            meta={
                "task_request_id": task_request_id,
                "result": final_result,
                "completed_at": datetime.now().isoformat(),
            },
        )

        logger.info(
            "=" * 80 + "\n"
            "Celery SecretFlow任务完成\n"
            f"  Celery任务ID: {celery_task_id}\n"
            f"  请求ID: {task_request_id}\n"
            f"  总耗时: {celery_execution_time:.2f}秒\n" + "=" * 80
        )

        return final_result

    except SoftTimeLimitExceeded:
        # 超时异常，不重试，直接失败
        raise

    except (ClusterInitError, DeviceConfigError) as e:
        # 可重试的错误
        execution_time = time.time() - execution_start

        logger.warning(
            f"SecretFlow任务遇到可重试错误: {type(e).__name__}: {str(e)}, "
            f"将在 {self.retry_kwargs.get('countdown', 60)} 秒后重试"
        )

        # 抛出重试异常
        raise self.retry(exc=e, countdown=self.retry_kwargs.get("countdown", 60))

    except Exception as e:
        # 其他错误，不重试，直接失败
        execution_time = time.time() - execution_start
        error_type = type(e).__name__
        error_msg = str(e)

        logger.error(
            f"Celery SecretFlow任务失败: celery_id={celery_task_id}, "
            f"request_id={task_request_id}, "
            f"error={error_type}: {error_msg}, "
            f"execution_time={execution_time:.2f}秒",
            exc_info=True,
        )

        # 更新任务状态为FAILURE
        self.update_state(
            state="FAILURE",
            meta={
                "task_request_id": task_request_id,
                "error": error_msg,
                "error_type": error_type,
                "execution_time": execution_time,
                "failed_at": datetime.now().isoformat(),
            },
        )

        # 重新抛出异常
        raise


# 便捷函数：提交SecretFlow任务
def submit_secretflow_task(
    task_request_id: str,
    sf_init_config: Dict[str, Any],
    spu_config: Dict[str, Any],
    heu_config: Optional[Dict[str, Any]],
    task_config: Dict[str, Any],
    countdown: int = 0,
    eta: Optional[datetime] = None,
) -> str:
    """提交SecretFlow任务到Celery队列

    Args:
        task_request_id: 任务请求ID
        sf_init_config: SecretFlow集群配置
        spu_config: SPU设备配置
        heu_config: HEU设备配置（可选）
        task_config: 任务配置
        countdown: 延迟执行秒数（可选）
        eta: 指定执行时间（可选）

    Returns:
        str: Celery任务ID
    """
    task_params = {
        "sf_init_config": sf_init_config,
        "spu_config": spu_config,
        "heu_config": heu_config,
        "task_config": task_config,
    }

    # 提交任务
    async_result = execute_secretflow_celery_task.apply_async(
        args=[task_request_id, task_params],
        countdown=countdown,
        eta=eta,
        queue="secretflow_queue",
    )

    logger.info(
        f"SecretFlow任务已提交: "
        f"celery_id={async_result.id}, "
        f"request_id={task_request_id}, "
        f"task_type={task_config.get('task_type')}"
    )

    return async_result.id


# 便捷函数：查询任务状态
def get_task_status(celery_task_id: str) -> Dict[str, Any]:
    """查询Celery任务状态

    Args:
        celery_task_id: Celery任务ID

    Returns:
        Dict[str, Any]: 任务状态信息
    """
    from celery.result import AsyncResult

    async_result = AsyncResult(celery_task_id, app=celery_app)

    return {
        "celery_task_id": celery_task_id,
        "state": async_result.state,
        "ready": async_result.ready(),
        "successful": async_result.successful() if async_result.ready() else None,
        "failed": async_result.failed() if async_result.ready() else None,
        "result": async_result.result if async_result.ready() else None,
        "info": async_result.info,
    }
