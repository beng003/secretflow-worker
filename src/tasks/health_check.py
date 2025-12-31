"""
健康检查任务
监控节点状态和系统资源
"""
import psutil
import time
from datetime import datetime
from src.celery_app import celery_app
from src.config.settings import settings
from src.utils.logger import TaskLogger


@celery_app.task(bind=True, name="tasks.health_check.node_health_check")
def node_health_check(self):
    """节点健康检查任务"""
    task_logger = TaskLogger("node_health_check", self.request.id)
    
    try:
        start_time = time.time()
        
        # 收集系统信息
        health_data = {
            "node_id": settings.node_id,
            "node_ip": settings.node_ip,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
        }
        
        # CPU 使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        health_data["cpu_percent"] = cpu_percent
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        health_data["memory"] = {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
            "free": memory.free
        }
        
        # 磁盘使用情况
        disk = psutil.disk_usage(settings.data_path)
        health_data["disk"] = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100
        }
        
        # 网络连接状态
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((settings.redis_host, settings.redis_port))
            health_data["redis_connection"] = result == 0
            sock.close()
        except Exception as e:
            health_data["redis_connection"] = False
            task_logger.warning("Redis连接检查失败", error=str(e))
        
        # 检查资源阈值
        warnings = []
        if cpu_percent > 90:
            warnings.append("CPU使用率过高")
        if memory.percent > 90:
            warnings.append("内存使用率过高")
        if health_data["disk"]["percent"] > 90:
            warnings.append("磁盘使用率过高")
        
        if warnings:
            health_data["status"] = "warning"
            health_data["warnings"] = warnings
            task_logger.warning("系统资源警告", warnings=warnings)
        
        execution_time = time.time() - start_time
        health_data["execution_time"] = execution_time
        
        task_logger.info(
            "健康检查完成",
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=health_data["disk"]["percent"],
            execution_time=execution_time
        )
        
        return health_data
        
    except Exception as e:
        error_msg = f"健康检查失败: {str(e)}"
        task_logger.exception(error_msg)
        
        return {
            "node_id": settings.node_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error",
            "error": error_msg
        }


@celery_app.task(bind=True, name="tasks.health_check.connectivity_test")
def connectivity_test(self, target_nodes: list):
    """节点连通性测试"""
    task_logger = TaskLogger("connectivity_test", self.request.id, target_nodes=target_nodes)
    
    try:
        results = {}
        
        for node in target_nodes:
            try:
                import socket
                host, port = node.split(":")
                port = int(port)
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                start_time = time.time()
                result = sock.connect_ex((host, port))
                latency = time.time() - start_time
                sock.close()
                
                results[node] = {
                    "reachable": result == 0,
                    "latency": latency,
                    "error": None
                }
                
            except Exception as e:
                results[node] = {
                    "reachable": False,
                    "latency": None,
                    "error": str(e)
                }
        
        task_logger.info("连通性测试完成", results=results)
        return results
        
    except Exception as e:
        error_msg = f"连通性测试失败: {str(e)}"
        task_logger.exception(error_msg)
        raise


@celery_app.task(bind=True, name="tasks.health_check.ray_cluster_status")
def ray_cluster_status(self):
    """Ray集群状态检查"""
    task_logger = TaskLogger("ray_cluster_status", self.request.id)
    
    try:
        # 注意：SecretFlow 的 Ray 是内置的，不直接导入 ray
        # 这里只检查相关进程和端口
        import subprocess
        import socket
        
        status = {
            "node_id": settings.node_id,
            "timestamp": datetime.utcnow().isoformat(),
            "ray_processes": [],
            "cluster_connectivity": False
        }
        
        # 检查 Ray 相关进程
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ray"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                ray_pids = result.stdout.strip().split("\n")
                status["ray_processes"] = ray_pids
                task_logger.info(f"发现 {len(ray_pids)} 个 Ray 进程")
            else:
                task_logger.warning("未发现 Ray 进程")
        except Exception as e:
            task_logger.warning("Ray 进程检查失败", error=str(e))
        
        # 检查集群连通性（如果配置了头节点）
        if settings.ray_head_ip:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((settings.ray_head_ip, settings.ray_head_port))
                status["cluster_connectivity"] = result == 0
                sock.close()
                
                if status["cluster_connectivity"]:
                    task_logger.info("Ray集群连接正常")
                else:
                    task_logger.warning("Ray集群连接失败")
                    
            except Exception as e:
                task_logger.warning("Ray集群连通性检查失败", error=str(e))
        
        return status
        
    except Exception as e:
        error_msg = f"Ray集群状态检查失败: {str(e)}"
        task_logger.exception(error_msg)
        return {
            "node_id": settings.node_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_msg
        }
