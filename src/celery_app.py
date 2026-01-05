"""
Celery应用配置

按照celery_todo.md 3.1.1要求重构Celery应用实例：
- 集成重构后的配置系统 (config.celery_config)
- 修复任务路由和队列配置
- 移除不存在的任务引用
- 任务发现路径调整为新的目录结构
"""

import os
from celery import Celery

from utils.log import logger
from config.celery_config import get_celery_config

# 获取配置实例
celery_config = get_celery_config()

# 创建Celery实例
celery_app = Celery("privacy_computing")

# 应用完整配置
celery_settings = celery_config.get_celery_settings()
celery_app.config_from_object(celery_settings)

# 日志记录配置信息
current_pid = os.getpid()

logger.info("Celery应用配置加载完成")
logger.debug(f"Redis Broker: {celery_config.broker_url}")
logger.debug(f"任务队列数量: {len(celery_config.task_queues)}")
logger.debug(f"任务模块: {celery_config.include}")
logger.debug(f"定时任务数量: {len(celery_config.beat_schedule)}")
logger.info(
    f"🚀 进程配置: PID:{current_pid} | Worker进程数:{celery_config.settings.celery_worker_concurrency}"
)


# 运行时配置验证
def validate_celery_setup():
    """
    验证Celery应用配置的完整性

    在应用启动时检查：
    - 配置有效性
    - 任务模块可导入性
    - 队列和路由配置正确性
    """
    try:
        # 1. 验证配置
        celery_config.validate_config()
        logger.info("✅ Celery配置验证通过")

        # 2. 验证任务模块可导入性
        for module_path in celery_config.include:
            try:
                __import__(module_path)
                logger.debug(f"✅ 任务模块 {module_path} 导入成功")
            except ImportError as e:
                logger.warning(f"⚠️ 任务模块 {module_path} 导入失败: {e}")

        # 3. 验证队列配置
        queue_names = [q.name for q in celery_config.task_queues]
        logger.info(f"✅ 配置队列: {queue_names}")

        # 4. 验证路由配置
        route_count = len(celery_config.task_routes)
        logger.info(f"✅ 配置路由规则: {route_count} 个")

        # 5. 验证定时任务
        beat_tasks = list(celery_config.beat_schedule.keys())
        logger.info(f"✅ 配置定时任务: {beat_tasks}")

        return True

    except Exception as e:
        logger.error(f"❌ Celery配置验证失败: {e}")
        return False


# 启动时验证配置
if __name__ != "__main__":
    validate_celery_setup()
