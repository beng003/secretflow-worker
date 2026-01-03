"""
Celery配置模块

集成现有的settings.config.Settings配置系统，提供统一的Celery任务配置管理。
复用Redis、数据库、日志等现有配置，避免重复定义。
"""

from kombu import Exchange, Queue

from src.config.settings import settings


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
        """Redis broker URL，直接使用settings.REDIS_URL"""
        return self.settings.REDIS_URL

    @property
    def result_backend(self) -> str:
        """Redis结果后端URL，直接使用settings.REDIS_URL"""
        return self.settings.REDIS_URL

    @property
    def task_serializer(self) -> str:
        """任务序列化格式"""
        return "json"

    @property
    def result_serializer(self) -> str:
        """结果序列化格式"""
        return "json"

    @property
    def accept_content(self) -> list[str]:
        """接受的内容类型"""
        return ["json"]

    @property
    def timezone(self) -> str:
        """时区配置，独立于数据库配置"""
        # 从环境变量或默认值获取时区，不再依赖TORTOISE_ORM
        return getattr(self.settings, 'TIMEZONE', 'Asia/Shanghai')

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
    def task_default_queue(self) -> str:
        """默认任务队列"""
        return "default"

    @property
    def task_default_exchange(self) -> str:
        """默认任务交换器"""
        return "default"

    @property
    def task_default_routing_key(self) -> str:
        """默认路由键"""
        return "default"

    @property
    def task_acks_late(self) -> bool:
        """延迟确认，确保任务执行完成才确认"""
        return True

    @property
    def task_reject_on_worker_lost(self) -> bool:
        """Worker中断时任务重新排队"""
        return True

    @property
    def task_soft_time_limit(self) -> int:
        """软超时时间（秒）"""
        return 3600  # 1小时

    @property
    def task_time_limit(self) -> int:
        """硬超时时间（秒）"""
        return 7200  # 2小时

    @property
    def result_expires(self) -> int:
        """结果过期时间（秒）"""
        return 86400  # 24小时

    @property
    def task_track_started(self) -> bool:
        """跟踪任务开始状态"""
        return True

    @property
    def worker_log_level(self) -> str:
        """Worker日志级别"""
        return "INFO"

    @property
    def worker_disable_rate_limits(self) -> bool:
        """禁用速率限制"""
        return True

    @property
    def worker_send_task_events(self) -> bool:
        """发送任务事件"""
        return False

    @property
    def worker_hijack_root_logger(self) -> bool:
        """不劫持根日志器，保持与现有loguru日志系统兼容"""
        return False

    @property
    def worker_log_format(self) -> str:
        """Worker日志格式，与现有日志系统保持一致"""
        return "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"

    @property
    def worker_concurrency(self) -> int:
        """Worker并发度，从settings读取"""
        return self.settings.CELERY_WORKER_CONCURRENCY

    @property
    def worker_pool(self) -> str:
        """Worker进程池类型，从settings读取"""
        return self.settings.CELERY_WORKER_POOL

    @property
    def worker_autoscaler(self) -> str:
        """Worker自动扩展配置，格式: max_concurrency,min_concurrency"""
        max_workers = self.settings.CELERY_WORKER_AUTOSCALE_MAX
        min_workers = self.settings.CELERY_WORKER_AUTOSCALE_MIN
        return f"{max_workers},{min_workers}"

    @property
    def worker_prefetch_multiplier(self) -> int:
        """Worker预取倍数，控制每个worker进程预取的任务数量"""
        return 1  # 设置为1以获得更好的负载均衡

    @property
    def worker_max_tasks_per_child(self) -> int:
        """每个worker子进程处理的最大任务数，超过后重启进程防止内存泄漏"""
        return 1000

    @property
    def worker_max_memory_per_child(self) -> int:
        """每个worker子进程的最大内存使用量(KB)，超过后重启进程"""
        return 200000  # 200MB

    @property
    def beat_schedule(self) -> dict[str, dict]:
        """定时任务调度配置"""
        # 暂时返回空的定时任务配置，避免引用不存在的任务
        # TODO: 当实际任务模块创建后，重新启用相应的定时任务
        return {}

    @property
    def include(self) -> list[str]:
        """任务模块包含路径"""
        return [
            # SecretFlow任务模块 
            "src.secretflow",
            # todo: 其他任务模块当需要时添加
            # "tasks.web.certificate",
            # "tasks.web.diagnostics", 
            # "tasks.web.system",
        ]

    # database_config已移除 - Celery任务层不再需要数据库配置

    @property
    def redis_config(self) -> dict:
        """Redis配置信息"""
        return {
            "url": self.settings.REDIS_URL,
            "cache_ttl": self.settings.CACHE_TTL,
        }

    @property
    def log_config(self) -> dict:
        """日志配置信息"""
        return {
            "level": self.worker_log_level,
            "format": self.worker_log_format,
            "hijack_root_logger": self.worker_hijack_root_logger,
            "logs_root": self.settings.LOGS_ROOT,
        }

    def get_celery_settings(self) -> dict:
        """
        获取完整的Celery配置字典

        Returns:
            dict: 完整的Celery配置参数
        """
        return {
            "broker_url": self.broker_url,
            "result_backend": self.result_backend,
            "task_serializer": self.task_serializer,
            "result_serializer": self.result_serializer,
            "accept_content": self.accept_content,
            "timezone": self.timezone,
            "task_queues": self.task_queues,
            "task_routes": self.task_routes,
            "task_default_queue": self.task_default_queue,
            "task_default_exchange": self.task_default_exchange,
            "task_default_routing_key": self.task_default_routing_key,
            "task_acks_late": self.task_acks_late,
            "task_reject_on_worker_lost": self.task_reject_on_worker_lost,
            "task_soft_time_limit": self.task_soft_time_limit,
            "task_time_limit": self.task_time_limit,
            "result_expires": self.result_expires,
            "task_track_started": self.task_track_started,
            "worker_log_level": self.worker_log_level,
            "worker_hijack_root_logger": self.worker_hijack_root_logger,
            "worker_log_format": self.worker_log_format,
            # Worker 并发度和性能配置
            "worker_concurrency": self.worker_concurrency,
            "worker_pool": self.worker_pool,
            "worker_prefetch_multiplier": self.worker_prefetch_multiplier,
            "worker_max_tasks_per_child": self.worker_max_tasks_per_child,
            "worker_max_memory_per_child": self.worker_max_memory_per_child,
            "beat_schedule": self.beat_schedule,
            "include": self.include,
            "broker_connection_retry_on_startup": True,
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
        if self.settings.APP_ENV == "production":
            if self.settings.DEBUG:
                raise ValueError("生产环境不能启用DEBUG模式")

            if "localhost" in self.broker_url:
                raise ValueError("生产环境不应使用localhost的Redis连接")

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
