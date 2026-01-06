"""
任务路由配置模块

基于现有任务结构和队列分离设计，提供任务到队列的路由映射配置。
支持Web任务和Worker任务的队列分配，以及基于任务类型的优先级配置。
"""

from enum import Enum
from typing import Any


class TaskQueue(str, Enum):
    """任务队列枚举"""

    DEFAULT = "default"
    WEB_QUEUE = "web_queue"
    SECRETFLOW_QUEUE = "secretflow_queue"


class TaskPriority(int, Enum):
    """任务优先级枚举"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskRouteConfig:
    """
    任务路由配置类

    基于现有任务结构提供路由配置，支持队列分离和优先级管理。
    根据实际存在的任务名称模式进行精确配置。
    """

    def __init__(self):
        """初始化任务路由配置"""
        pass

    @property
    def web_task_routes(self) -> dict[str, dict[str, Any]]:
        """
        Web应用任务路由配置

        统一的tasks.web.*任务路由配置
        """
        return {
            # note: new task任务路由配置
            # 所有Web应用任务统一路由到web_queue
            "tasks.web.*": {
                "queue": TaskQueue.WEB_QUEUE,
                "priority": TaskPriority.NORMAL,
                "soft_time_limit": 300,  # 5分钟软超时
                "time_limit": 600,  # 10分钟硬超时
            },
        }

    @property
    def secretflow_task_routes(self) -> dict[str, dict[str, Any]]:
        """
        SecretFlow任务路由配置

        隐私计算任务的独立队列配置，支持长时间运行
        """
        return {
            # SecretFlow计算任务
            "tasks.secretflow.*": {
                "queue": TaskQueue.SECRETFLOW_QUEUE,
                "priority": TaskPriority.HIGH,
                "soft_time_limit": 3600,  # 1小时软超时
                "time_limit": 7200,  # 2小时硬超时
            },
            # SecretFlow健康检查
            "tasks.secretflow.health_check": {
                "queue": TaskQueue.SECRETFLOW_QUEUE,
                "priority": TaskPriority.NORMAL,
                "soft_time_limit": 60,  # 1分钟软超时
                "time_limit": 120,  # 2分钟硬超时
            },
        }

    def get_all_routes(self) -> dict[str, dict[str, Any]]:
        """
        获取完整的任务路由配置字典

        合并Web任务和SecretFlow任务路由配置
        """
        all_routes = {}

        # 合并路由配置
        # note: new task任务路由配置的优先级是后配置的覆盖先配置的
        all_routes.update(self.web_task_routes)  # Web应用任务路由
        all_routes.update(self.secretflow_task_routes)  # SecretFlow任务路由

        return all_routes

    def get_celery_task_routes(self) -> dict[str, dict[str, str]]:
        """
        获取Celery兼容的任务路由配置

        只返回Celery需要的queue配置，过滤其他配置项
        """
        all_routes = self.get_all_routes()
        celery_routes = {}

        for pattern, config in all_routes.items():
            celery_routes[pattern] = {"queue": config["queue"]}

        return celery_routes

    def get_task_config(self, task_name: str) -> dict[str, Any] | None:
        """
        根据任务名称获取匹配的配置

        Args:
            task_name: 完整的任务名称

        Returns:
            匹配的任务配置字典，未找到返回None
        """
        all_routes = self.get_all_routes()

        for pattern, config in all_routes.items():
            if self._match_pattern(task_name, pattern):
                return config.copy()

        return None

    def _match_pattern(self, task_name: str, pattern: str) -> bool:
        """
        匹配任务名称和路由模式

        支持通配符匹配 (*)
        """
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return task_name.startswith(prefix)
        elif pattern == "*":
            return True
        else:
            return task_name == pattern

    def get_queue_statistics(self) -> dict[str, dict[str, int]]:
        """
        获取队列统计信息

        返回每个队列的任务类型数量和优先级分布
        """
        all_routes = self.get_all_routes()
        stats = {}

        for config in all_routes.values():
            queue_name = config["queue"]
            priority = config.get("priority", TaskPriority.NORMAL)

            if queue_name not in stats:
                stats[queue_name] = {
                    "total_patterns": 0,
                    "priority_distribution": {
                        "LOW": 0,
                        "NORMAL": 0,
                        "HIGH": 0,
                        "CRITICAL": 0,
                    },
                }

            stats[queue_name]["total_patterns"] += 1
            priority_name = TaskPriority(priority).name
            stats[queue_name]["priority_distribution"][priority_name] += 1

        return stats


# 全局配置实例
_task_route_config_instance = None


def get_task_route_config() -> TaskRouteConfig:
    """
    获取任务路由配置单例实例

    Returns:
        TaskRouteConfig: 任务路由配置实例
    """
    global _task_route_config_instance

    if _task_route_config_instance is None:
        _task_route_config_instance = TaskRouteConfig()

    return _task_route_config_instance


def get_celery_task_routes() -> dict[str, dict[str, str]]:
    """
    获取Celery兼容的任务路由配置的便捷函数

    Returns:
        dict: Celery格式的任务路由配置
    """
    config = get_task_route_config()
    return config.get_celery_task_routes()


def get_all_task_routes() -> dict[str, dict[str, Any]]:
    """
    获取完整任务路由配置的便捷函数

    Returns:
        dict: 完整的任务路由配置
    """
    config = get_task_route_config()
    return config.get_all_routes()
