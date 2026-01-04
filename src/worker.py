#!/usr/bin/env python3
"""
SecretFlow Worker 启动脚本
启动Celery worker进程来处理SecretFlow任务
"""

import os
import sys
import signal

from src.utils.log import logger
from src.celery_app import celery_app
from src.config.settings import settings



def setup_signal_handlers():
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，正在优雅关闭Worker...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def validate_environment():
    """验证环境配置"""
    logger.info("验证环境配置")
    
    # 检查数据目录
    if not os.path.exists(settings.data_path):
        logger.info(f"创建数据目录: {settings.data_path}")
        os.makedirs(settings.data_path, exist_ok=True)
    
    # 检查Redis连接
    try:
        import redis
        
        r = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        r.ping()
        r.close()
        r.connection_pool.disconnect()
        
        logger.info("Redis连接正常")
    except Exception as e:
        logger.warning(f"Redis连接检查失败: {e}")
        # 不抛出异常，因为启动时可能Redis还未完全就绪
    
    logger.info("环境验证完成")


def main():
    """启动Celery Worker主函数"""
    logger.info("🚀 启动SecretFlow Celery Worker...")
    
    try:
        # 设置环境变量
        os.environ.setdefault('CELERY_APP', 'src.celery_app:celery_app')
        
        # 验证环境
        validate_environment()
        
        # 设置信号处理
        setup_signal_handlers()
        
        # 显示启动信息
        logger.info("📋 Worker配置:")
        logger.info(f"   节点ID: {settings.node_id}")
        logger.info(f"   并发数: {settings.worker_concurrency}")
        logger.info(f"   队列: {settings.worker_queues}")
        logger.info(f"   主机名: {settings.worker_hostname}")
        logger.info(f"   日志级别: {settings.worker_loglevel}")
        logger.info(f"   任务软超时: {settings.worker_task_soft_time_limit}秒")
        
        # 创建并启动Worker
        # 使用最简单可靠的启动方式，直接从settings导入参数
        import sys
        sys.argv = [
            'worker',
            f'--loglevel={settings.worker_loglevel}',
            f'--concurrency={settings.worker_concurrency}',
            f'--queues={",".join(settings.worker_queues)}',
            f'--hostname={settings.worker_hostname}',
            f'--pool={settings.worker_pool}',
            f'--prefetch-multiplier={settings.worker_prefetch_multiplier}',  # 每个进程最多1个任务
            f'--max-tasks-per-child={settings.worker_max_tasks_per_child}',
            '--without-gossip',
            '--without-mingle',
            '--without-heartbeat'  # 禁用心跳，加速关闭
        ]
        
        # 直接启动worker
        celery_app.start()
        
    except KeyboardInterrupt:
        logger.info("📋 Worker被用户中断")
    except Exception as e:
        logger.error(f"❌ Worker启动失败: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 SecretFlow Worker已停止")


if __name__ == '__main__':
    main()