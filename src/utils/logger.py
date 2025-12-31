"""
结构化日志工具
支持分布式环境下的日志记录和监控
"""
import logging
import structlog
from typing import Any
from src.config.settings import settings


def configure_logging() -> None:
    """配置结构化日志"""
    
    # 配置 structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # 配置标准 logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper()),
    )


def get_logger(name: str, **context: Any) -> structlog.stdlib.BoundLogger:
    """获取结构化日志器"""
    logger = structlog.get_logger(name)
    
    # 添加节点信息到上下文
    default_context = {
        "node_id": settings.node_id,
        "node_ip": settings.node_ip,
        "node_type": settings.node_type,
    }
    
    # 合并默认上下文和传入的上下文
    default_context.update(context)
    
    return logger.bind(**default_context)


class TaskLogger:
    """任务日志器"""
    
    def __init__(self, task_name: str, task_id: str, **context: Any):
        self.task_name = task_name
        self.task_id = task_id
        self.logger = get_logger(
            f"task.{task_name}",
            task_id=task_id,
            task_name=task_name,
            **context
        )
    
    def info(self, msg: str, **kwargs: Any) -> None:
        """记录信息日志"""
        self.logger.info(msg, **kwargs)
    
    def error(self, msg: str, **kwargs: Any) -> None:
        """记录错误日志"""
        self.logger.error(msg, **kwargs)
    
    def warning(self, msg: str, **kwargs: Any) -> None:
        """记录警告日志"""
        self.logger.warning(msg, **kwargs)
    
    def debug(self, msg: str, **kwargs: Any) -> None:
        """记录调试日志"""
        self.logger.debug(msg, **kwargs)
    
    def exception(self, msg: str, **kwargs: Any) -> None:
        """记录异常日志"""
        self.logger.exception(msg, **kwargs)


# 初始化日志配置
configure_logging()
