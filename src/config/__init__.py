"""
任务配置模块

提供Celery任务系统的统一配置管理，集成现有的settings.config系统。
包括Celery配置和任务路由配置的统一管理。
"""

from .celery_config import CeleryConfig, get_celery_config, get_celery_settings
from .task_routes import (
    TaskPriority,
    TaskQueue,
    TaskRouteConfig,
    get_all_task_routes,
    get_celery_task_routes,
    get_task_route_config,
)

from .settings import settings

__all__ = [
    # Celery配置
    "CeleryConfig",
    "get_celery_config",
    "get_celery_settings",
    # 任务路由配置
    "TaskQueue",
    "TaskPriority",
    "TaskRouteConfig",
    # 任务路由配置
    "get_task_route_config",
    "get_celery_task_routes",
    "get_all_task_routes",
    "settings",
]
