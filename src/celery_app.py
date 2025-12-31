"""
Celery 应用配置
基于 SecretFlow 生产模式的分布式隐私计算任务队列
"""
from celery import Celery
from src.config.settings import celery_config, settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

def create_celery_app() -> Celery:
    """创建 Celery 应用实例"""
    
    app = Celery(
        "secretflow_backend",
        broker=celery_config.broker_url,
        backend=celery_config.result_backend,
        include=[
            'src.tasks.privacy_computing',
            'src.tasks.data_processing', 
            'src.tasks.cluster_management',
            'src.tasks.health_check',
        ]
    )
    
    # 应用配置
    app.conf.update(celery_config.get_celery_config())
    
    # 自定义配置 - 单任务模式，确保每个worker同时只执行一个SecretFlow任务
    app.conf.update(
        # 队列配置
        task_default_queue="default",
        task_create_missing_queues=True,
        
        # 任务优先级
        task_inherit_parent_priority=True,
        task_default_priority=5,
        
        # 工作进程配置 - 单任务模式
        worker_concurrency=1,  # 每个worker只有1个并发
        worker_prefetch_multiplier=1,  # 每次只预取1个任务
        task_acks_late=True,  # 任务完成后再确认
        worker_max_tasks_per_child=10,  # 减少每个子进程的任务数，避免内存泄漏
        worker_max_memory_per_child=2048 * 1024,  # 2GB内存限制
        
        # 任务执行配置
        task_reject_on_worker_lost=True,  # worker丢失时拒绝任务
        task_track_started=True,  # 跟踪任务开始状态
        
        # 安全配置
        worker_disable_rate_limits=False,
        
        # 监控配置
        task_send_sent_event=True,
        worker_send_task_events=True,
        
        # 结果配置
        result_expires=7200,  # 结果保存2小时
        result_persistent=True,  # 持久化结果
    )
    
    logger.info(f"Celery app created for node {settings.node_id}")
    logger.info(f"Broker URL: {celery_config.broker_url}")
    logger.info(f"Result Backend: {celery_config.result_backend}")
    
    return app

# 创建全局 Celery 应用实例
celery_app = create_celery_app()

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """设置周期性任务"""
    from src.tasks.health_check import node_health_check
    
    # 每30秒执行健康检查
    sender.add_periodic_task(
        30.0, 
        node_health_check.s(),
        name="node_health_check",
    )

@celery_app.task(bind=True)
def debug_task(self):
    """调试任务"""
    logger.info(f"Request: {self.request!r}")
    return f"Debug task executed on node {settings.node_id}"
