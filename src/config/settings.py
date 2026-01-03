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
            load_dotenv(env_file)
        
        # 环境配置
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.app_env = os.getenv("APP_ENV", "development")
        
        # Redis配置
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:16379/0")
        self.redis_host = os.getenv("REDIS_HOST", "localhost") 
        self.redis_port = int(os.getenv("REDIS_PORT", "16379"))
        self.redis_password = os.getenv("REDIS_PASSWORD")
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
        
        # 节点配置
        self.node_id = os.getenv("NODE_ID", "secretflow-worker-001")
        self.node_ip = os.getenv("NODE_IP", "127.0.0.1")
        self.node_port = int(os.getenv("NODE_PORT", "8080"))
        
        # 数据目录配置
        self.data_path = PROJECT_ROOT / "data"
        self.data_path.mkdir(exist_ok=True)
        
        # 日志配置
        self.LOGS_ROOT = PROJECT_ROOT / "logs"
        self.LOGS_ROOT.mkdir(exist_ok=True)
        
        # Celery Worker配置
        self.CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "2"))
        self.CELERY_WORKER_POOL = os.getenv("CELERY_WORKER_POOL", "prefork")
        self.CELERY_WORKER_AUTOSCALE_MAX = int(os.getenv("CELERY_WORKER_AUTOSCALE_MAX", "4"))
        self.CELERY_WORKER_AUTOSCALE_MIN = int(os.getenv("CELERY_WORKER_AUTOSCALE_MIN", "2"))
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

# 全局配置实例
settings = Settings()

__all__ = ["settings", "Settings"]
