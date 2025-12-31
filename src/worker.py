"""
Celery Worker 主入口
基于 SecretFlow 的隐私计算 Worker 节点
"""
import os
import signal
import sys
from typing import Optional
from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from src.celery_app import celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SecretFlowWorker:
    """SecretFlow Celery Worker 管理器"""
    
    def __init__(self):
        self.celery_app: Celery = celery_app
        self.worker_process: Optional[object] = None
        
    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"接收到信号 {signum}，开始优雅关闭")
            self.shutdown()
            sys.exit(0)
            
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def validate_environment(self):
        """验证环境配置"""
        logger.info("验证环境配置")
        
        # 检查必需的环境变量
        required_vars = [
            "NODE_ID", "NODE_IP", "REDIS_HOST", 
            "CLUSTER_CONFIG", "SECURITY_TOKEN"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise EnvironmentError(f"缺少必需的环境变量: {', '.join(missing_vars)}")
        
        # 检查数据目录
        if not os.path.exists(settings.data_path):
            logger.info(f"创建数据目录: {settings.data_path}")
            os.makedirs(settings.data_path, exist_ok=True)
        
        # 检查 Redis 连接
        try:
            import redis
            r = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                socket_timeout=5
            )
            r.ping()
            logger.info("Redis 连接正常")
        except Exception as e:
            raise ConnectionError(f"Redis 连接失败: {str(e)}")
        
        logger.info("环境验证完成")
    
    def start_worker(self):
        """启动 Celery Worker - 单任务模式"""
        logger.info(f"启动 SecretFlow Worker 节点: {settings.node_id}")
        logger.info(f"节点IP: {settings.node_ip}:{settings.node_port}")
        logger.info(f"Redis: {settings.redis_host}:{settings.redis_port}")
        logger.info(f"运行模式: 单任务模式 (并发数={settings.max_concurrent_tasks})")
        
        # 验证单任务模式配置
        if settings.max_concurrent_tasks != 1:
            logger.warning(f"检测到并发数为 {settings.max_concurrent_tasks}，但推荐设置为 1 以确保 SecretFlow 正确运行")
        
        # 配置 worker 参数 - 强制单任务模式
        worker_kwargs = {
            'app': self.celery_app,
            'hostname': f"{settings.node_id}@{settings.node_ip}",
            'concurrency': 1,  # 强制设置为1，确保单任务执行
            'loglevel': settings.log_level,
            'queues': ['default', 'privacy_computing', 'data_processing', 'health_check'],
            'pool': 'solo',  # 使用 solo 池，更适合单任务模式
        }
        
        try:
            # 创建并启动 worker
            from celery.bin.worker import worker
            worker_instance = worker(app=self.celery_app)
            self.worker_process = worker_instance
            
            # 启动 worker（这会阻塞）
            worker_instance.run(
                hostname=worker_kwargs['hostname'],
                concurrency=worker_kwargs['concurrency'],
                loglevel=worker_kwargs['loglevel'],
                queues=worker_kwargs['queues'],
                pool=worker_kwargs['pool']
            )
            
        except KeyboardInterrupt:
            logger.info("收到中断信号，停止 worker")
        except Exception as e:
            logger.exception(f"Worker 启动失败: {str(e)}")
            raise
    
    def shutdown(self):
        """关闭 Worker"""
        logger.info("开始关闭 SecretFlow Worker")
        
        if self.worker_process:
            try:
                # 优雅关闭 worker
                self.worker_process.terminate()
                logger.info("Worker 进程已终止")
            except Exception as e:
                logger.error(f"关闭 worker 时出错: {str(e)}")
        
        logger.info("SecretFlow Worker 已关闭")


@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Worker 就绪事件处理"""
    logger.info(f"Worker {settings.node_id} 已就绪，开始接收任务")
    
    # 执行健康检查
    try:
        from src.tasks.health_check import node_health_check
        node_health_check.delay()
        logger.info("初始健康检查任务已提交")
    except Exception as e:
        logger.warning(f"提交健康检查任务失败: {str(e)}")


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Worker 关闭事件处理"""
    logger.info(f"Worker {settings.node_id} 正在关闭")


def main():
    """主函数"""
    try:
        # 创建 worker 实例
        worker = SecretFlowWorker()
        
        # 设置信号处理器
        worker.setup_signal_handlers()
        
        # 验证环境
        worker.validate_environment()
        
        # 启动 worker
        worker.start_worker()
        
    except Exception as e:
        logger.exception(f"启动 Worker 失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
