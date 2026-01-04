from datetime import datetime
from typing import Any, Dict

# 使用项目统一的日志系统
from src.utils.log import logger

# 使用任务基类
from src.base import BaseTask
from src.celery_app import celery_app
from src.config.settings import settings


@celery_app.task(base=BaseTask, name="tasks.secretflow.health_check.health_check_task")
def health_check_task() -> Dict[str, Any]:
    """
    系统健康检查任务
    
    检查SecretFlow系统的基本运行状态，包括Redis连接和Celery状态。
    
    Returns:
        包含健康检查结果和系统状态的字典
    """
    
    start_time = datetime.now()
    
    logger.info("[HEALTH-CHECK] 开始执行系统健康检查")
    
    # 检查Redis连接
    redis_status = "unknown"
    redis_details = {}
    try:
        import redis
        r = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        ping_result = r.ping()
        if ping_result:
            redis_status = "healthy"
            info = r.info()
            redis_details = {
                "memory_usage": info.get('used_memory_human', 'unknown'),
                "connected_clients": info.get('connected_clients', 0)
            }
        else:
            redis_status = "error"
        r.close()
        r.connection_pool.disconnect()
    except Exception as e:
        redis_status = "error"
        redis_details = {"error": str(e)}
    
    # 检查Celery状态
    celery_status = "unknown"
    celery_details = {}
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        if active_workers:
            celery_status = "healthy"
            worker_count = len(active_workers)
            total_active_tasks = sum(len(tasks) for tasks in active_workers.values())
            celery_details = {
                "worker_count": worker_count,
                "active_tasks": total_active_tasks
            }
        else:
            celery_status = "warning"
            celery_details = {"message": "无活跃Worker"}
    except Exception as e:
        celery_status = "error"
        celery_details = {"error": str(e)}
    
    # 判断总体状态
    overall_status = "healthy"
    if redis_status == "error" or celery_status == "error":
        overall_status = "error"
    elif redis_status == "warning" or celery_status == "warning":
        overall_status = "warning"
    
    end_time = datetime.now()
    execution_duration = (end_time - start_time).total_seconds()
    
    result = {
        "message": f"健康检查完成，系统状态: {overall_status}",
        "task_name": "health_check_task",
        "execution_time": execution_duration,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "status": "success",
        "overall_status": overall_status,
        "components": {
            "redis": {
                "status": redis_status,
                "details": redis_details
            },
            "celery": {
                "status": celery_status,
                "details": celery_details
            }
        },
        "node_info": {
            "node_id": settings.node_id,
            "node_ip": settings.node_ip,
            "app_env": settings.app_env
        }
    }
    
    logger.info(f"[HEALTH-CHECK] 健康检查完成，总体状态: {overall_status}，耗时: {execution_duration:.2f}s")
    
    return result
