"""
任务注册和发现模块

按照celery_todo.md 3.2.1要求实现任务模块管理：
- 统一的任务导入和注册机制
- 支持模块化的任务加载
- 提供任务列表和元数据查询接口
- 集成健康检查和监控

复用现有的任务基类和配置系统。
"""

import importlib
import inspect
from collections.abc import Callable
from datetime import datetime
from typing import Any

from celery import Task

from utils.log import logger


class TaskMetadata:
    """任务元数据信息"""

    def __init__(
        self,
        name: str,
        module_path: str,
        task_function: Callable,
        description: str = "",
        queue: str = "default",
        is_periodic: bool = False,
        schedule_info: dict[str, Any] | None = None,
    ):
        self.name = name
        self.module_path = module_path
        self.task_function = task_function
        self.description = description
        self.queue = queue
        self.is_periodic = is_periodic
        self.schedule_info = schedule_info or {}
        self.registered_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "module_path": self.module_path,
            "description": self.description,
            "queue": self.queue,
            "is_periodic": self.is_periodic,
            "schedule_info": self.schedule_info,
            "registered_at": self.registered_at.isoformat(),
            "signature": str(inspect.signature(self.task_function))
            if self.task_function
            else "N/A",
        }


class TaskRegistry:
    """任务注册器 - 统一管理所有Celery任务"""

    def __init__(self):
        self.tasks: dict[str, TaskMetadata] = {}
        self.modules: dict[str, dict] = {}
        self.load_errors: list[dict] = []

    def register_task(
        self,
        name: str,
        module_path: str,
        task_function: Callable,
        description: str = "",
        queue: str = "default",
        is_periodic: bool = False,
        schedule_info: dict[str, Any] | None = None,
    ) -> None:
        """
        注册任务到注册器

        参数:
            name: 任务名称
            module_path: 模块路径
            task_function: 任务函数
            description: 任务描述
            queue: 任务队列
            is_periodic: 是否为定时任务
            schedule_info: 调度信息
        """
        metadata = TaskMetadata(
            name=name,
            module_path=module_path,
            task_function=task_function,
            description=description,
            queue=queue,
            is_periodic=is_periodic,
            schedule_info=schedule_info,
        )

        self.tasks[name] = metadata
        logger.debug(f"注册任务: {name} (模块: {module_path})")

    def discover_tasks_in_module(self, module_path: str) -> int:
        """
        发现模块中的所有Celery任务

        参数:
            module_path: 模块路径

        返回:
            发现的任务数量
        """
        try:
            # 动态导入模块
            module = importlib.import_module(module_path)
            self.modules[module_path] = {
                "loaded_at": datetime.now(),
                "status": "success",
                "task_count": 0,
            }

            discovered_count = 0

            # 扫描模块中的所有对象
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # 检查是否为Celery任务
                if (
                    hasattr(attr, "delay")
                    and hasattr(attr, "apply_async")
                    and isinstance(attr, Task)
                ):
                    task_name = getattr(attr, "name", f"{module_path}.{attr_name}")

                    # 提取任务描述
                    description = ""
                    if hasattr(attr, "__doc__") and attr.__doc__:
                        description = attr.__doc__.strip().split("\n")[0]

                    # 确定任务队列
                    queue = "default"
                    if hasattr(attr, "queue"):
                        queue = attr.queue

                    # 注册任务
                    self.register_task(
                        name=task_name,
                        module_path=module_path,
                        task_function=attr,
                        description=description,
                        queue=queue,
                    )

                    discovered_count += 1

            self.modules[module_path]["task_count"] = discovered_count
            logger.info(f"模块 {module_path} 发现 {discovered_count} 个任务")
            return discovered_count

        except ImportError as e:
            error_info = {
                "module_path": module_path,
                "error_type": "ImportError",
                "error_message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            self.load_errors.append(error_info)
            logger.warning("模块 %s 导入失败: %s", module_path, e)
            return 0

        except Exception as e:
            error_info = {
                "module_path": module_path,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            self.load_errors.append(error_info)
            logger.error("模块 %s 任务发现失败: %s", module_path, e)
            return 0

    def load_all_tasks(self) -> dict[str, Any]:
        """
        加载所有已知任务模块

        返回:
            加载统计信息
        """
        known_modules = [
            # note: 未来可添加更多计算任务模块
            "src.secretflow",  # SecretFlow计算任务
        ]

        stats = {
            "total_modules": len(known_modules),
            "loaded_modules": 0,
            "failed_modules": 0,
            "total_tasks": 0,
            "load_errors": [],
        }

        logger.info("开始加载所有任务模块...")

        for module_path in known_modules:
            try:
                task_count = self.discover_tasks_in_module(module_path)
                stats["loaded_modules"] += 1
                stats["total_tasks"] += task_count

            except Exception as e:
                stats["failed_modules"] += 1
                stats["load_errors"].append({"module": module_path, "error": str(e)})
                logger.error("加载模块 %s 失败: %s", module_path, e)

        logger.info(
            f"任务模块加载完成: "
            f"成功 {stats['loaded_modules']}/{stats['total_modules']} 个模块, "
            f"发现 {stats['total_tasks']} 个任务"
        )

        return stats

    def get_task_list(self, queue: str | None = None) -> list[dict[str, Any]]:
        """
        获取任务列表

        参数:
            queue: 可选的队列过滤

        返回:
            任务信息列表
        """
        tasks = []
        for metadata in self.tasks.values():
            if queue is None or metadata.queue == queue:
                tasks.append(metadata.to_dict())

        return sorted(tasks, key=lambda x: x["name"])

    def get_task_by_name(self, name: str) -> TaskMetadata | None:
        """
        根据名称获取任务元数据

        参数:
            name: 任务名称

        返回:
            任务元数据或None
        """
        return self.tasks.get(name)

    def get_periodic_tasks(self) -> list[dict[str, Any]]:
        """
        获取所有定时任务

        返回:
            定时任务列表
        """
        periodic_tasks = []
        for metadata in self.tasks.values():
            if metadata.is_periodic:
                periodic_tasks.append(metadata.to_dict())

        return sorted(periodic_tasks, key=lambda x: x["name"])

    def get_tasks_by_queue(self) -> dict[str, list[dict[str, Any]]]:
        """
        按队列分组获取任务

        返回:
            按队列分组的任务字典
        """
        queue_tasks: dict[str, list[dict[str, Any]]] = {}

        for metadata in self.tasks.values():
            queue = metadata.queue
            if queue not in queue_tasks:
                queue_tasks[queue] = []
            queue_tasks[queue].append(metadata.to_dict())

        # 排序每个队列的任务
        for queue in queue_tasks:
            queue_tasks[queue].sort(key=lambda x: x["name"])

        return queue_tasks

    def get_statistics(self) -> dict[str, Any]:
        """
        获取任务注册统计信息

        返回:
            统计信息字典
        """
        queue_counts: dict[str, int] = {}
        periodic_count = 0

        for metadata in self.tasks.values():
            # 统计队列分布
            queue = metadata.queue
            queue_counts[queue] = queue_counts.get(queue, 0) + 1

            # 统计定时任务
            if metadata.is_periodic:
                periodic_count += 1

        return {
            "total_tasks": len(self.tasks),
            "total_modules": len(self.modules),
            "periodic_tasks": periodic_count,
            "queue_distribution": queue_counts,
            "load_errors": len(self.load_errors),
            "modules_loaded": len(
                [m for m in self.modules.values() if m["status"] == "success"]
            ),
        }

    def health_check(self) -> dict[str, Any]:
        """
        执行健康检查

        返回:
            健康检查结果
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "issues": [],
        }

        try:
            # 1. 检查任务注册状态
            stats = self.get_statistics()
            if stats["total_tasks"] == 0:
                health_status["issues"].append("没有发现任何已注册的任务")
                health_status["status"] = "warning"

            if stats["load_errors"] > 0:
                health_status["issues"].append(
                    f"有 {stats['load_errors']} 个模块加载错误"
                )
                health_status["status"] = "warning"

            health_status["checks"]["task_registration"] = {
                "status": "pass" if stats["total_tasks"] > 0 else "fail",
                "details": stats,
            }

            # 2. 检查关键任务模块 - 仅检查SecretFlow相关任务
            critical_modules = [
                "src.secretflow",
            ]
            missing_modules = []

            for module in critical_modules:
                if (
                    module not in self.modules
                    or self.modules[module]["status"] != "success"
                ):
                    missing_modules.append(module)

            if missing_modules:
                health_status["issues"].append(
                    f"关键SecretFlow模块未加载: {missing_modules}"
                )
                health_status["status"] = "error"

            health_status["checks"]["critical_modules"] = {
                "status": "pass" if not missing_modules else "fail",
                "missing_modules": missing_modules,
            }

            # 3. 检查队列配置 - 仅检查SecretFlow项目相关队列
            expected_queues = ["default", "secretflow_queue"]
            queue_distribution = stats["queue_distribution"]

            health_status["checks"]["queue_configuration"] = {
                "status": "pass",
                "expected_queues": expected_queues,
                "active_queues": list(queue_distribution.keys()),
                "distribution": queue_distribution,
            }

            logger.debug(f"任务注册系统健康检查完成: {health_status['status']}")
        except Exception as e:
            health_status["status"] = "error"
            health_status["issues"].append(f"健康检查执行失败: {str(e)}")
            logger.error("任务注册系统健康检查失败: %s", e)

        return health_status


# 全局任务注册器实例
task_registry = TaskRegistry()


def get_task_registry() -> TaskRegistry:
    """
    获取全局任务注册器实例

    返回:
        TaskRegistry实例
    """
    return task_registry


def discover_all_tasks() -> dict[str, Any]:
    """
    发现并加载所有任务模块的便捷函数

    返回:
        加载统计信息
    """
    return task_registry.load_all_tasks()


def get_all_tasks() -> list[dict[str, Any]]:
    """
    获取所有已注册任务的便捷函数

    返回:
        任务列表
    """
    return task_registry.get_task_list()


def get_task_health_status() -> dict[str, Any]:
    """
    获取任务系统健康状态的便捷函数

    返回:
        健康检查结果
    """
    return task_registry.health_check()


# 模块导入时自动发现任务
logger.info("初始化任务注册系统...")
discover_all_tasks()
logger.info("任务注册系统初始化完成")
