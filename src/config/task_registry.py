"""
任务注册表

管理所有可用的SecretFlow任务类型和对应的执行器。
"""

from typing import Dict, Type
from secretflow.algorithms.base_executor import BaseTaskExecutor
from secretflow.algorithms.psi_executor import PSIExecutor
from secretflow.algorithms.lr_executor import LogisticRegressionExecutor


# 算法执行器注册表
ALGORITHM_REGISTRY: Dict[str, Type[BaseTaskExecutor]] = {
    "psi": PSIExecutor,
    "lr": LogisticRegressionExecutor,
    "logistic_regression": LogisticRegressionExecutor,
}


class AlgorithmFactory:
    """算法执行器工厂"""
    
    @staticmethod
    def create_executor(task_type: str, task_request_id: str, task_config: Dict) -> BaseTaskExecutor:
        """创建算法执行器实例
        
        Args:
            task_type: 任务类型
            task_request_id: 任务请求ID
            task_config: 任务配置
            
        Returns:
            BaseTaskExecutor: 对应的执行器实例
            
        Raises:
            ValueError: 不支持的任务类型
        """
        if task_type not in ALGORITHM_REGISTRY:
            raise ValueError(f"不支持的任务类型: {task_type}")
        
        executor_class = ALGORITHM_REGISTRY[task_type]
        return executor_class(task_request_id, task_config)
    
    @staticmethod
    def get_supported_algorithms() -> list:
        """获取支持的算法列表
        
        Returns:
            list: 支持的算法类型列表
        """
        return list(ALGORITHM_REGISTRY.keys())
