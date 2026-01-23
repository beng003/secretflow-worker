"""
异步执行助手模块

提供安全的异步函数执行工具，解决Celery任务中的事件循环冲突和线程安全问题。
按照celery_todo.md要求，集成超时控制、异常处理和异步事务管理。
"""

import asyncio

import threading
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from utils.log import logger

# 类型定义
T = TypeVar("T")


class AsyncExecutionError(Exception):
    """异步执行错误"""

    pass


class AsyncTimeoutError(AsyncExecutionError):
    """异步执行超时错误"""

    pass


def run_async_safely(
    async_func: Callable[..., Awaitable[T]], *args, timeout: int | None = None, **kwargs
) -> T:
    """
    安全执行异步函数，处理事件循环冲突

    解决现有任务中手动管理事件循环的问题，提供统一的异步执行接口。

    Args:
        async_func: 要执行的异步函数
        *args: 异步函数的位置参数
        timeout: 超时时间（秒），None表示不限制
        **kwargs: 异步函数的关键字参数

    Returns:
        异步函数的执行结果

    Raises:
        AsyncTimeoutError: 执行超时
        AsyncExecutionError: 执行异常
    """

    # 记录执行开始
    start_time = time.time()
    func_name = getattr(async_func, "__name__", "unknown_async_func")

    logger.debug(
        f"[ASYNC-HELPER] 开始安全执行异步函数: {func_name}",
        extra={
            "function_name": func_name,
            "timeout": timeout,
            "args_count": len(args),
            "kwargs_count": len(kwargs),
        },
    )

    try:
        # 检查当前线程是否已有事件循环
        try:
            asyncio.get_running_loop()  # 检查是否已有事件循环
            # 如果当前线程有运行中的事件循环，使用线程池执行
            logger.debug(
                f"[ASYNC-HELPER] 检测到运行中的事件循环，使用线程池执行 {func_name}"
            )
            return _run_in_thread_pool(async_func, args, kwargs, timeout)

        except RuntimeError:
            # 当前线程没有运行中的事件循环，可以安全创建新循环
            logger.debug(f"[ASYNC-HELPER] 创建新事件循环执行 {func_name}")
            return _run_in_new_loop(async_func, args, kwargs, timeout)

    except TimeoutError as e:
        execution_time = time.time() - start_time
        logger.error(
            "[ASYNC-HELPER] 异步函数执行超时: %s",
            func_name,
            extra={
                "function_name": func_name,
                "execution_time": execution_time,
                "timeout": timeout,
            },
        )
        raise AsyncTimeoutError(f"异步函数 {func_name} 执行超时 ({timeout}秒)") from e

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            "[ASYNC-HELPER] 异步函数执行失败: %s",
            func_name,
            extra={
                "function_name": func_name,
                "execution_time": execution_time,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        raise AsyncExecutionError(f"异步函数 {func_name} 执行失败: {str(e)}") from e

    else:
        execution_time = time.time() - start_time
        logger.debug(
            f"[ASYNC-HELPER] 异步函数执行成功: {func_name}",
            extra={
                "function_name": func_name,
                "execution_time": execution_time,
            },
        )


def _run_in_new_loop(
    async_func: Callable[..., Awaitable[T]],
    args: tuple,
    kwargs: dict,
    timeout: int | None,
) -> T:
    """在新事件循环中执行异步函数"""

    async def _execute_with_timeout():
        if timeout is not None:
            return await asyncio.wait_for(async_func(*args, **kwargs), timeout=timeout)
        else:
            return await async_func(*args, **kwargs)

    # 创建新的事件循环并执行
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_execute_with_timeout())
    finally:
        # 确保循环被正确关闭
        try:
            loop.close()
        except Exception as e:
            logger.warning("[ASYNC-HELPER] 关闭事件循环时出现警告: %s", str(e))


def _run_in_thread_pool(
    async_func: Callable[..., Awaitable[T]],
    args: tuple,
    kwargs: dict,
    timeout: int | None,
) -> T:
    """在线程池中执行异步函数"""

    def _thread_worker():
        """线程工作函数"""

        async def _execute_with_timeout():
            if timeout is not None:
                return await asyncio.wait_for(
                    async_func(*args, **kwargs), timeout=timeout
                )
            else:
                return await async_func(*args, **kwargs)

        # 在新线程中创建新的事件循环
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_execute_with_timeout())
        finally:
            try:
                loop.close()
            except Exception as e:
                logger.warning(
                    "[ASYNC-HELPER] 线程池中关闭事件循环时出现警告: %s", str(e)
                )

    # 使用线程池执行
    with ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="AsyncHelper"
    ) as executor:
        future = executor.submit(_thread_worker)
        try:
            # 添加额外的超时保护
            thread_timeout = timeout + 5 if timeout else None
            return future.result(timeout=thread_timeout)
        except Exception as e:
            logger.error("[ASYNC-HELPER] 线程池执行异常: %s", str(e))
            raise


# async_transaction_context 已移除 - 数据库事务操作移至Service层


# run_repository_safely 已移除 - 任务层不再直接调用Repository
# 线程安全的异步执行统计
class AsyncExecutionStats:
    """异步执行统计信息"""

    def __init__(self):
        self._lock = threading.Lock()
        self._stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "timeout_executions": 0,
            "total_execution_time": 0.0,
        }

    def record_execution(
        self, success: bool, execution_time: float, timeout: bool = False
    ):
        """记录执行统计"""
        with self._lock:
            self._stats["total_executions"] += 1
            self._stats["total_execution_time"] += execution_time

            if timeout:
                self._stats["timeout_executions"] += 1
            elif success:
                self._stats["successful_executions"] += 1
            else:
                self._stats["failed_executions"] += 1

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.copy()
            if stats["total_executions"] > 0:
                stats["success_rate"] = (
                    stats["successful_executions"] / stats["total_executions"]
                )
                stats["average_execution_time"] = (
                    stats["total_execution_time"] / stats["total_executions"]
                )
            else:
                stats["success_rate"] = 0.0
                stats["average_execution_time"] = 0.0
            return stats


# 全局统计实例
_execution_stats = AsyncExecutionStats()


def get_async_execution_stats() -> dict[str, Any]:
    """获取异步执行统计信息"""
    return _execution_stats.get_stats()
