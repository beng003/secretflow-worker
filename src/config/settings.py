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
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.APP_ENV = os.getenv("APP_ENV", "development")
        
        # Redis配置
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
        
        # 日志配置
        self.LOGS_ROOT = PROJECT_ROOT / "logs"
        self.LOGS_ROOT.mkdir(exist_ok=True)
        
        # Celery Worker配置
        self.CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))
        self.CELERY_WORKER_POOL = os.getenv("CELERY_WORKER_POOL", "prefork")
        self.CELERY_WORKER_AUTOSCALE_MAX = int(os.getenv("CELERY_WORKER_AUTOSCALE_MAX", "8"))
        self.CELERY_WORKER_AUTOSCALE_MIN = int(os.getenv("CELERY_WORKER_AUTOSCALE_MIN", "2"))
        
        # 确保数据目录存在
        (PROJECT_ROOT / "data").mkdir(exist_ok=True)

# 全局配置实例
settings = Settings()

__all__ = ["settings", "Settings"]
