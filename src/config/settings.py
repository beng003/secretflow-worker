"""
项目设置配置模块

提供项目的统一配置管理，包括数据库连接、Redis配置、Celery配置等。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

class Settings:
    """项目配置类"""
    
    def __init__(self):
        # 加载SecretFlow专用环境变量文件
        env_file = PROJECT_ROOT / ".env.secretflow"
        if env_file.exists():
            load_dotenv(env_file, override=False)
        
        # 环境配置
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.app_env = os.getenv("APP_ENV", "development")
        
        # Redis配置
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:16379/0")
        self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))
        
        # 节点配置
        self.node_id = os.getenv("NODE_ID", "secretflow-worker")
        self.node_ip = os.getenv("NODE_IP", "127.0.0.1")
        self.node_port = int(os.getenv("NODE_PORT", "8080"))
        
        # 数据目录配置
        self.data_path = PROJECT_ROOT / "data"
        self.data_path.mkdir(exist_ok=True)
        
        # 日志配置
        self.logs_root = PROJECT_ROOT / "logs"
        self.logs_root.mkdir(exist_ok=True)
        
        # Celery Worker配置
        self.celery_worker_concurrency = int(os.getenv("CELERY_WORKER_CONCURRENCY", "2"))
        self.celery_worker_pool = os.getenv("CELERY_WORKER_POOL", "prefork")
        self.celery_worker_autoscale_max = int(os.getenv("CELERY_WORKER_AUTOSCALE_MAX", "4"))
        self.celery_worker_autoscale_min = int(os.getenv("CELERY_WORKER_AUTOSCALE_MIN", "2"))
        self.max_concurrent_tasks = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))
        
        # Worker启动配置参数
        self.worker_loglevel = os.getenv('CELERY_LOG_LEVEL', 'INFO')
        self.worker_concurrency = self.max_concurrent_tasks
        self.worker_queues = ['secretflow_queue']
        self.worker_hostname = f'{self.node_id}@{self.node_ip}'
        self.worker_pool = 'prefork'
        self.worker_max_tasks_per_child = int(os.getenv('WORKER_MAX_TASKS_PER_CHILD', '1'))
        self.worker_task_soft_time_limit = int(os.getenv('WORKER_TASK_SOFT_TIME_LIMIT', '3600'))
        self.worker_task_time_limit = int(os.getenv('WORKER_TASK_TIME_LIMIT', '3900'))
        self.worker_prefetch_multiplier = int(os.getenv('WORKER_PREFETCH_MULTIPLIER', '1'))
        
        # Celery任务配置
        self.task_soft_time_limit = int(os.getenv('TASK_SOFT_TIME_LIMIT', '3600'))
        self.task_time_limit = int(os.getenv('TASK_TIME_LIMIT', '7200'))
        self.result_expires = int(os.getenv('RESULT_EXPIRES', '86400'))
        self.worker_max_memory_per_child = int(os.getenv('WORKER_MAX_MEMORY_PER_CHILD', '200000'))
        self.timezone = os.getenv('TIMEZONE', 'Asia/Shanghai')
        
        # Celery任务序列化和内容类型
        self.task_serializer = os.getenv('TASK_SERIALIZER', 'json')
        self.result_serializer = os.getenv('RESULT_SERIALIZER', 'json')
        self.accept_content = os.getenv('ACCEPT_CONTENT', 'json').split(',')
        
        # Celery任务队列和路由配置
        self.task_default_queue = os.getenv('TASK_DEFAULT_QUEUE', 'secretflow_queue')
        self.task_default_exchange = os.getenv('TASK_DEFAULT_EXCHANGE', 'secretflow')
        self.task_default_routing_key = os.getenv('TASK_DEFAULT_ROUTING_KEY', 'secretflow')
        
        # Celery Worker行为配置
        self.task_acks_late = os.getenv('TASK_ACKS_LATE', 'true').lower() == 'true'
        self.task_reject_on_worker_lost = os.getenv('TASK_REJECT_ON_WORKER_LOST', 'true').lower() == 'true'
        self.task_track_started = os.getenv('TASK_TRACK_STARTED', 'true').lower() == 'true'
        self.worker_disable_rate_limits = os.getenv('WORKER_DISABLE_RATE_LIMITS', 'true').lower() == 'true'
        self.worker_send_task_events = os.getenv('WORKER_SEND_TASK_EVENTS', 'false').lower() == 'true'
        self.worker_hijack_root_logger = os.getenv('WORKER_HIJACK_ROOT_LOGGER', 'false').lower() == 'true'
        self.worker_log_format = os.getenv('WORKER_LOG_FORMAT', '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s')

# 全局配置实例
settings = Settings()

__all__ = ["settings", "Settings"]
