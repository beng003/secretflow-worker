"""
Celery配置模块

集成现有的settings.config.Settings配置系统，提供统一的Celery任务配置管理。
复用Redis、数据库、日志等现有配置，避免重复定义。
"""

from kombu import Exchange, Queue

from config.settings import settings


class CeleryConfig:
    """
    Celery配置类

    直接复用settings.config.Settings的配置，确保与主应用配置一致性。
    支持开发/生产环境配置切换，集成现有的日志和数据库配置。
    """

    def __init__(self):
        """初始化Celery配置，复用现有settings配置"""
        self.settings = settings

    @property
    def broker_url(self) -> str:
        """Redis broker URL，直接使用settings.redis_url"""
        return self.settings.redis_url

    @property
    def result_backend(self) -> str:
        """Redis结果后端URL，直接使用settings.redis_url"""
        return self.settings.redis_url

    # 序列化和时区配置已移至get_celery_settings方法中直接使用

    @property
    def task_queues(self) -> tuple[Queue, ...]:
        """任务队列定义，支持进程隔离"""
        default_exchange = Exchange("default", type="direct")
        secretflow_exchange = Exchange("secretflow", type="direct")
        web_exchange = Exchange("web", type="direct")

        return (
            Queue("default", default_exchange, routing_key="default"),
            Queue("secretflow_queue", secretflow_exchange, routing_key="secretflow"),
            Queue("web_queue", web_exchange, routing_key="web"),
        )

    @property
    def task_routes(self) -> dict[str, dict[str, str]]:
        """任务路由规则配置"""
        return {
            # SecretFlow任务 -> secretflow_queue（进程隔离）
            "tasks.secretflow.*": {"queue": "secretflow_queue"},
        }

    @property
    def beat_schedule(self) -> dict[str, dict]:
        """定时任务调度配置"""
        return {}  # 暂时为空

    @property
    def include(self) -> list[str]:
        """任务模块包含路径"""
        return [
            "secretflow_task.celery_tasks",
            "secretflow_task.hello",
            "secretflow_task.local_test",
            "secretflow_task.health_check",
        ]

    @property
    def redis_config(self) -> dict:
        """Redis配置信息"""
        return {
            "url": self.settings.redis_url,
            "cache_ttl": self.settings.cache_ttl,
        }

    def get_celery_settings(self) -> dict:
        """
        获取完整的Celery配置字典

        Returns:
            dict: 完整的Celery配置参数
        """
        from kombu import Exchange, Queue

        # 任务队列定义
        default_exchange = Exchange("default", type="direct")
        secretflow_exchange = Exchange("secretflow", type="direct")
        web_exchange = Exchange("web", type="direct")

        task_queues = (
            Queue("default", default_exchange, routing_key="default"),
            Queue("secretflow_queue", secretflow_exchange, routing_key="secretflow"),
            Queue("web_queue", web_exchange, routing_key="web"),
        )

        # 任务路由规则
        task_routes = {
            "tasks.secretflow.*": {"queue": "secretflow_queue"},
        }

        # 任务模块包含路径
        include_modules = self.include

        return {
            # Redis连接配置
            "broker_url": self.settings.redis_url,
            "result_backend": self.settings.redis_url,
            # 序列化配置
            "task_serializer": self.settings.task_serializer,
            "result_serializer": self.settings.result_serializer,
            "accept_content": self.settings.accept_content,
            # 时区配置
            "timezone": self.settings.timezone,
            # 队列和路由配置
            "task_queues": task_queues,
            "task_routes": task_routes,
            "task_default_queue": self.settings.task_default_queue,
            "task_default_exchange": self.settings.task_default_exchange,
            "task_default_routing_key": self.settings.task_default_routing_key,
            # 任务行为配置
            "task_acks_late": self.settings.task_acks_late,
            "task_reject_on_worker_lost": self.settings.task_reject_on_worker_lost,
            "task_soft_time_limit": self.settings.task_soft_time_limit,
            "task_time_limit": self.settings.task_time_limit,
            "result_expires": self.settings.result_expires,
            "task_track_started": self.settings.task_track_started,
            # Worker配置
            "worker_log_level": self.settings.worker_loglevel,
            "worker_hijack_root_logger": self.settings.worker_hijack_root_logger,
            "worker_log_format": self.settings.worker_log_format,
            "worker_concurrency": self.settings.celery_worker_concurrency,
            "worker_pool": self.settings.celery_worker_pool,
            "worker_prefetch_multiplier": self.settings.worker_prefetch_multiplier,
            "worker_max_tasks_per_child": self.settings.worker_max_tasks_per_child,
            "worker_max_memory_per_child": self.settings.worker_max_memory_per_child,
            "worker_disable_rate_limits": self.settings.worker_disable_rate_limits,
            "worker_send_task_events": self.settings.worker_send_task_events,
            "worker_redirect_stdouts": False,
            # 定时任务和模块包含
            "beat_schedule": {},  # 暂时为空
            "include": include_modules,
        }

    def validate_config(self) -> bool:
        """
        验证配置有效性

        Returns:
            bool: 配置是否有效

        Raises:
            ValueError: 配置无效时抛出异常
        """
        # 验证Redis URL
        if not self.broker_url:
            raise ValueError("Redis URL未配置")

        # 数据库配置验证已移除 - 任务层不再依赖数据库连接

        # 验证生产环境配置
        if self.settings.app_env == "production":
            if self.settings.debug:
                raise ValueError("生产环境不能启用DEBUG模式")

            # Host网络模式下允许使用127.0.0.1连接本地Redis
            # 检查是否使用了不推荐的配置
            if "localhost" in self.broker_url and "127.0.0.1" not in self.broker_url:
                raise ValueError("生产环境请使用127.0.0.1而非localhost")

        return True


# 全局配置实例
_celery_config_instance = None


def get_celery_config() -> CeleryConfig:
    """
    获取Celery配置单例实例

    Returns:
        CeleryConfig: Celery配置实例
    """
    global _celery_config_instance

    if _celery_config_instance is None:
        _celery_config_instance = CeleryConfig()
        # 验证配置
        _celery_config_instance.validate_config()

    return _celery_config_instance


def get_celery_settings() -> dict:
    """
    获取完整的Celery配置字典的便捷函数

    Returns:
        dict: 完整的Celery配置参数
    """
    config = get_celery_config()
    return config.get_celery_settings()
