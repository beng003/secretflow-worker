"""
SecretFlow任务执行器主模块

该模块提供SecretFlow任务的统一执行入口，负责协调各个子模块完成任务执行。
包括集群初始化、设备管理、算法执行、性能监控和资源自动清理。
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime

from secretflow_task.cluster_initializer import SecretFlowClusterInitializer
from secretflow_task.device_manager import DeviceManager
from secretflow_task.task_dispatcher import TaskDispatcher
from utils.log import logger
from utils.status_notifier import _publish_status
from utils.exceptions import ClusterInitError, DeviceConfigError, AlgorithmError


def _collect_performance_metrics(
    start_time: float,
    cluster_init_time: Optional[float],
    device_init_time: Optional[float],
    algorithm_exec_time: Optional[float],
) -> Dict[str, Any]:
    """收集性能指标

    Args:
        start_time: 任务开始时间
        cluster_init_time: 集群初始化耗时
        device_init_time: 设备初始化耗时
        algorithm_exec_time: 算法执行耗时

    Returns:
        Dict[str, Any]: 性能指标
    """
    total_time = time.time() - start_time

    metrics = {
        "total_execution_time": round(total_time, 2),
        "cluster_init_time": round(cluster_init_time, 2) if cluster_init_time else None,
        "device_init_time": round(device_init_time, 2) if device_init_time else None,
        "algorithm_exec_time": round(algorithm_exec_time, 2)
        if algorithm_exec_time
        else None,
        "overhead_time": round(
            total_time
            - (cluster_init_time or 0)
            - (device_init_time or 0)
            - (algorithm_exec_time or 0),
            2,
        ),
    }

    # 计算占比
    if total_time > 0:
        metrics["cluster_init_percentage"] = round(
            (cluster_init_time or 0) / total_time * 100, 1
        )
        metrics["device_init_percentage"] = round(
            (device_init_time or 0) / total_time * 100, 1
        )
        metrics["algorithm_exec_percentage"] = round(
            (algorithm_exec_time or 0) / total_time * 100, 1
        )

    return metrics


def execute_secretflow_task(
    task_request_id: str,
    sf_init_config: Dict[str, Any],
    spu_config: Dict[str, Any],
    heu_config: Dict[str, Any],
    task_config: Dict[str, Any],
) -> Dict[str, Any]:
    """SecretFlow任务执行主函数

    统一的SecretFlow任务执行入口，协调所有子模块完成任务执行。

    执行流程：
    1. 初始化SecretFlow集群
    2. 初始化计算设备（PYU/SPU/HEU）
    3. 创建并执行算法执行器
    4. 收集性能指标
    5. 清理资源（自动）

    Args:
        task_request_id: 任务请求唯一标识符
        sf_init_config: SecretFlow集群初始化配置
            - parties: 参与方列表 ['alice', 'bob']
            - address: Ray集群地址或'local'
        spu_config: SPU设备配置
            - cluster_def: SPU集群定义
        heu_config: HEU设备配置（可选）
        task_config: 任务特定执行配置
            - task_type: 任务类型（'psi', 'lr'等）
            - 其他算法特定参数

    Returns:
        Dict[str, Any]: 任务执行结果，包含：
            - status: 执行状态 ('success' or 'failed')
            - result: 算法执行结果
            - performance_metrics: 性能指标
            - task_metadata: 任务元数据

    Raises:
        SecretFlowTaskError: 任务执行失败
    """
    start_time = time.time()
    cluster_initializer = None
    device_manager = None

    # 性能指标
    cluster_init_time = None
    device_init_time = None
    algorithm_exec_time = None

    try:
        logger.info(
            "=" * 80 + "\n"
            "SecretFlow任务开始执行\n"
            f"  任务ID: {task_request_id}\n"
            f"  任务类型: {task_config.get('task_type', 'unknown')}\n"
            f"  开始时间: {datetime.now().isoformat()}\n" + "=" * 80
        )

        # 发送任务开始状态
        _publish_status(
            task_request_id,
            "RUNNING",
            {
                "stage": "task_started",
                "task_type": task_config.get("task_type"),
                "started_at": datetime.now().isoformat(),
                "progress": 0.0,
            },
        )

        # ========================================
        # 第1步：初始化SecretFlow集群
        # ========================================
        logger.info("\n[1/4] 初始化SecretFlow集群...")
        cluster_init_start = time.time()

        _publish_status(
            task_request_id, "RUNNING", {"stage": "cluster_init", "progress": 0.1}
        )

        cluster_initializer = SecretFlowClusterInitializer()
        if not cluster_initializer.initialize_cluster(sf_init_config):
            raise ClusterInitError("集群初始化失败")

        cluster_init_time = time.time() - cluster_init_start
        logger.info(f"  ✓ 集群初始化完成，耗时: {cluster_init_time:.2f}秒")

        _publish_status(
            task_request_id,
            "RUNNING",
            {
                "stage": "cluster_initialized",
                "cluster_init_time": cluster_init_time,
                "progress": 0.2,
            },
        )

        # ========================================
        # 第2步：初始化计算设备
        # ========================================
        logger.info("\n[2/4] 初始化计算设备...")
        device_init_start = time.time()

        _publish_status(
            task_request_id, "RUNNING", {"stage": "device_creation", "progress": 0.3}
        )

        device_manager = DeviceManager.get_instance()

        # 根据配置决定初始化哪些设备
        devices = device_manager.initialize_devices(
            pyu_config={"enabled": True},  # PYU总是需要的
            spu_config=spu_config if spu_config else None,
            heu_config=heu_config if heu_config else None,
        )

        if not devices:
            raise DeviceConfigError("设备初始化失败，未创建任何设备")

        device_init_time = time.time() - device_init_start
        logger.info(
            f"  ✓ 设备初始化完成，耗时: {device_init_time:.2f}秒\n"
            f"    初始化设备: {list(devices.keys())}"
        )

        _publish_status(
            task_request_id,
            "RUNNING",
            {
                "stage": "devices_initialized",
                "device_init_time": device_init_time,
                "initialized_devices": list(devices.keys()),
                "progress": 0.4,
            },
        )

        # ========================================
        # 第3步：执行算法任务
        # ========================================
        logger.info("\n[3/4] 执行算法任务...")
        algorithm_exec_start = time.time()

        task_type = task_config.get("task_type")

        if not task_type:
            raise AlgorithmError("任务配置中缺少task_type字段")

        logger.info(f"  任务类型: {task_type}")

        _publish_status(
            task_request_id,
            "RUNNING",
            {"stage": "task_execution", "task_type": task_type, "progress": 0.5},
        )

        # 使用TaskDispatcher分发任务
        logger.info(f"  开始执行任务: {task_type}")
        algorithm_result = TaskDispatcher.dispatch(task_type, devices, task_config)

        algorithm_exec_time = time.time() - algorithm_exec_start
        logger.info(f"  ✓ 任务执行完成，耗时: {algorithm_exec_time:.2f}秒")

        # ========================================
        # 第4步：收集性能指标
        # ========================================
        logger.info("\n[4/4] 收集性能指标...")

        performance_metrics = _collect_performance_metrics(
            start_time=start_time,
            cluster_init_time=cluster_init_time,
            device_init_time=device_init_time,
            algorithm_exec_time=algorithm_exec_time,
        )

        logger.info(
            f"  性能指标:\n"
            f"    - 总耗时: {performance_metrics['total_execution_time']}秒\n"
            f"    - 集群初始化: {performance_metrics['cluster_init_time']}秒 "
            f"({performance_metrics.get('cluster_init_percentage', 0):.1f}%)\n"
            f"    - 设备初始化: {performance_metrics['device_init_time']}秒 "
            f"({performance_metrics.get('device_init_percentage', 0):.1f}%)\n"
            f"    - 算法执行: {performance_metrics['algorithm_exec_time']}秒 "
            f"({performance_metrics.get('algorithm_exec_percentage', 0):.1f}%)\n"
            f"    - 其他开销: {performance_metrics['overhead_time']}秒"
        )

        # 构建最终结果
        final_result = {
            "status": "success",
            "result": algorithm_result,
            "performance_metrics": performance_metrics,
            "task_metadata": {
                "task_request_id": task_request_id,
                "task_type": task_type,
                "started_at": datetime.fromtimestamp(start_time).isoformat(),
                "completed_at": datetime.now().isoformat(),
                "devices_used": list(devices.keys()),
            },
        }

        # 发送任务成功状态
        _publish_status(
            task_request_id,
            "SUCCESS",
            {
                "stage": "task_completed",
                "result": algorithm_result,
                "performance_metrics": performance_metrics,
                "completed_at": datetime.now().isoformat(),
                "progress": 1.0,
            },
        )

        logger.info(
            "\n" + "=" * 80 + "\n"
            "SecretFlow任务执行成功\n"
            f"  任务ID: {task_request_id}\n"
            f"  总耗时: {performance_metrics['total_execution_time']}秒\n"
            f"  完成时间: {datetime.now().isoformat()}\n" + "=" * 80
        )

        return final_result

    except Exception as e:
        # 计算当前执行时间
        execution_time = time.time() - start_time
        error_type = type(e).__name__
        error_msg = str(e)

        logger.error(
            "\n" + "=" * 80 + "\n"
            "SecretFlow任务执行失败\n"
            f"  任务ID: {task_request_id}\n"
            f"  错误类型: {error_type}\n"
            f"  错误信息: {error_msg}\n"
            f"  已执行时间: {execution_time:.2f}秒\n" + "=" * 80,
            exc_info=True,
        )

        # 发送任务失败状态
        _publish_status(
            task_request_id,
            "FAILURE",
            {
                "stage": "task_failed",
                "error": error_msg,
                "error_type": error_type,
                "execution_time": execution_time,
                "failed_at": datetime.now().isoformat(),
            },
        )

        # 重新抛出异常，但先清理资源
        raise

    finally:
        # 资源清理
        try:
            logger.info(f"开始清理任务资源，task_id={task_request_id}")

            # 清理设备
            if device_manager:
                device_manager.cleanup_devices()
                logger.info("设备资源清理完成")

            # 关闭集群
            if cluster_initializer:
                cluster_initializer.shutdown_cluster()
                logger.info("集群关闭完成")

            logger.info(f"任务资源清理完成，task_id={task_request_id}")

        except Exception as e:
            # 资源清理失败不影响主流程，但需记录
            logger.error(f"资源清理失败: {e}", exc_info=True)
