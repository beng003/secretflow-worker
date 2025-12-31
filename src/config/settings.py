"""
环境变量配置管理模块
支持 Celery worker 的配置参数管理
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseSettings, Field, validator


class NodeSettings(BaseSettings):
    """节点配置类"""
    
    # 节点基本信息
    node_id: str = Field(..., env="NODE_ID", description="节点唯一标识")
    node_ip: str = Field(..., env="NODE_IP", description="节点IP地址")
    node_port: int = Field(9394, env="NODE_PORT", description="节点端口")
    node_type: str = Field("worker", env="NODE_TYPE", description="节点类型")
    
    # Redis 配置
    redis_host: str = Field("localhost", env="REDIS_HOST", description="Redis主机地址")
    redis_port: int = Field(6379, env="REDIS_PORT", description="Redis端口")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD", description="Redis密码")
    redis_db: int = Field(0, env="REDIS_DB", description="Redis数据库编号")
    
    # Celery 配置
    celery_broker_url: str = Field(..., env="CELERY_BROKER_URL", description="Celery消息队列URL")
    celery_result_backend: str = Field(..., env="CELERY_RESULT_BACKEND", description="Celery结果存储后端")
    celery_task_serializer: str = Field("json", env="CELERY_TASK_SERIALIZER", description="任务序列化格式")
    celery_result_serializer: str = Field("json", env="CELERY_RESULT_SERIALIZER", description="结果序列化格式")
    celery_accept_content: List[str] = Field(["json"], env="CELERY_ACCEPT_CONTENT", description="接受的内容类型")
    celery_timezone: str = Field("Asia/Shanghai", env="CELERY_TIMEZONE", description="时区设置")
    celery_enable_utc: bool = Field(True, env="CELERY_ENABLE_UTC", description="启用UTC时间")
    
    # SecretFlow 集群配置
    cluster_config: str = Field(..., env="CLUSTER_CONFIG", description="集群配置JSON字符串")
    cluster_nodes: List[str] = Field(..., env="CLUSTER_NODES", description="集群节点列表")
    
    # Ray 配置（SecretFlow 生产模式）
    ray_head_ip: Optional[str] = Field(None, env="RAY_HEAD_IP", description="Ray集群头节点IP")
    ray_head_port: int = Field(10001, env="RAY_HEAD_PORT", description="Ray集群头节点端口")
    
    # 安全配置
    security_token: str = Field(..., env="SECURITY_TOKEN", description="安全认证令牌")
    ssl_cert_path: Optional[str] = Field(None, env="SSL_CERT_PATH", description="SSL证书路径")
    ssl_key_path: Optional[str] = Field(None, env="SSL_KEY_PATH", description="SSL私钥路径")
    
    # 数据配置
    data_path: str = Field("/app/data", env="DATA_PATH", description="数据存储路径")
    temp_path: str = Field("/tmp", env="TEMP_PATH", description="临时文件路径")
    log_level: str = Field("INFO", env="LOG_LEVEL", description="日志级别")
    
    # 计算配置 - 每个worker同时只执行一个任务，确保SecretFlow正确运行
    max_concurrent_tasks: int = Field(1, env="MAX_CONCURRENT_TASKS", description="最大并发任务数（单任务模式）")
    task_timeout: int = Field(3600, env="TASK_TIMEOUT", description="任务超时时间（秒）")
    memory_limit: str = Field("4GB", env="MEMORY_LIMIT", description="内存限制")
    
    @validator("celery_broker_url", pre=True, always=True)
    def generate_broker_url(cls, v, values):
        """生成 Celery broker URL"""
        if v and v.startswith(("redis://", "amqp://")):
            return v
        
        redis_host = values.get("redis_host", "localhost")
        redis_port = values.get("redis_port", 6379)
        redis_password = values.get("redis_password")
        redis_db = values.get("redis_db", 0)
        
        if redis_password:
            return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            return f"redis://{redis_host}:{redis_port}/{redis_db}"
    
    @validator("celery_result_backend", pre=True, always=True)
    def generate_result_backend(cls, v, values):
        """生成 Celery result backend URL"""
        if v and v.startswith(("redis://", "rpc://", "db+", "cache+")):
            return v
        
        redis_host = values.get("redis_host", "localhost")
        redis_port = values.get("redis_port", 6379)
        redis_password = values.get("redis_password")
        redis_db = values.get("redis_db", 0)
        
        if redis_password:
            return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            return f"redis://{redis_host}:{redis_port}/{redis_db}"
    
    @validator("cluster_nodes", pre=True, always=True)
    def parse_cluster_nodes(cls, v):
        """解析集群节点列表"""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # 支持逗号分隔的字符串
            return [node.strip() for node in v.split(",") if node.strip()]
        return []
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class CeleryConfig:
    """Celery 配置类"""
    
    def __init__(self, settings: NodeSettings):
        self.settings = settings
    
    @property
    def broker_url(self) -> str:
        return self.settings.celery_broker_url
    
    @property
    def result_backend(self) -> str:
        return self.settings.celery_result_backend
    
    @property
    def task_serializer(self) -> str:
        return self.settings.celery_task_serializer
    
    @property
    def result_serializer(self) -> str:
        return self.settings.celery_result_serializer
    
    @property
    def accept_content(self) -> List[str]:
        return self.settings.celery_accept_content
    
    @property
    def timezone(self) -> str:
        return self.settings.celery_timezone
    
    @property
    def enable_utc(self) -> bool:
        return self.settings.celery_enable_utc
    
    @property
    def worker_concurrency(self) -> int:
        return self.settings.max_concurrent_tasks
    
    @property
    def task_routes(self) -> Dict[str, Any]:
        """任务路由配置"""
        return {
            "tasks.privacy_computing.*": {"queue": "privacy_computing"},
            "tasks.data_processing.*": {"queue": "data_processing"},
            "tasks.cluster_management.*": {"queue": "cluster_management"},
            "tasks.health_check.*": {"queue": "health_check"},
        }
    
    @property
    def task_annotations(self) -> Dict[str, Any]:
        """任务注释配置"""
        return {
            "*": {
                "rate_limit": "10/s",
                "time_limit": self.settings.task_timeout,
                "soft_time_limit": self.settings.task_timeout - 60,
            }
        }
    
    def get_celery_config(self) -> Dict[str, Any]:
        """获取完整的 Celery 配置"""
        return {
            "broker_url": self.broker_url,
            "result_backend": self.result_backend,
            "task_serializer": self.task_serializer,
            "result_serializer": self.result_serializer,
            "accept_content": self.accept_content,
            "timezone": self.timezone,
            "enable_utc": self.enable_utc,
            "worker_concurrency": self.worker_concurrency,
            "task_routes": self.task_routes,
            "task_annotations": self.task_annotations,
            "worker_hijack_root_logger": False,
            "worker_log_format": "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
            "worker_task_log_format": "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
            "result_expires": 3600,
            "task_track_started": True,
            "task_reject_on_worker_lost": True,
            "worker_disable_rate_limits": False,
        }


# 全局设置实例
settings = NodeSettings()
celery_config = CeleryConfig(settings)
