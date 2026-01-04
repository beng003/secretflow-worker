"""
状态通知模块

集成现有的Redis状态监听系统，提供统一的状态上报接口。
"""


def _publish_status(task_request_id: str, status: str, data: dict = None) -> None:
    """SecretFlow任务的统一状态上报接口
    
    简单的状态上报，失败不影响主任务
    
    Args:
        task_request_id: 任务请求ID
        status: 任务状态 (如: RUNNING, SUCCESS, FAILURE)
        data: 状态相关数据，可选
    """
    try:
        # 构造状态事件数据
        event_data = {
            "task_request_id": task_request_id,
            "status": status,
            "timestamp": _get_timestamp(),
            "data": data or {},
            "worker_container": _get_worker_id(),
            "task_name": "task.secretflow"
        }
        
        # 发布到Redis
        _publish_to_redis(event_data)
        
    except Exception:
        # 静默失败，不影响主任务执行
        pass


def _get_timestamp() -> str:
    """获取ISO格式时间戳"""
    from datetime import datetime
    return datetime.now().isoformat()


def _get_worker_id() -> str:
    """获取Worker容器ID"""
    from config.settings import settings
    return settings.node_id


def _publish_to_redis(event_data: dict) -> None:
    """发布事件到Redis"""
    import json
    
    try:
        # 尝试使用redis库
        import redis
        
        # 获取Redis连接配置
        redis_url = _get_redis_url()
        redis_client = redis.Redis.from_url(redis_url)
        
        # 序列化事件数据
        event_json = json.dumps(event_data)
        
        # 双重保障：发布订阅 + 队列
        redis_client.publish("task_status_events", event_json)
        redis_client.lpush("task_status_queue", event_json)
        
    except ImportError:
        # Redis库不可用时静默失败
        pass
    except Exception:
        # 其他Redis错误也静默失败
        pass


def _get_redis_url() -> str:
    """获取Redis连接URL"""
    from config.settings import settings
    return settings.redis_url
