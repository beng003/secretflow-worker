"""
基础任务执行器

定义了所有SecretFlow算法执行器的基础接口和通用方法。
"""

from abc import ABC, abstractmethod


class BaseTaskExecutor(ABC):
    """基础任务执行器抽象类"""
    
    def __init__(self, task_request_id: str, task_config: dict):
        """初始化执行器
        
        Args:
            task_request_id: 任务请求ID
            task_config: 任务配置参数
        """
        self.task_request_id = task_request_id
        self.task_config = task_config
        self._validated = False
    
    def validate_params(self) -> bool:
        """验证任务参数
        
        验证基础参数结构和必需字段的存在性
        
        Returns:
            bool: 参数验证是否通过
        """
        if not isinstance(self.task_config, dict):
            return False
        
        # 验证必需的基础字段
        required_fields = ['task_type']
        for field in required_fields:
            if field not in self.task_config:
                return False
        
        # 验证task_type不为空
        if not self.task_config['task_type']:
            return False
        
        self._validated = True
        return True
    
    @abstractmethod
    def execute(self) -> dict:
        """执行任务
        
        Returns:
            dict: 任务执行结果
        """
        pass
    
    def _publish_progress(self, progress: float, message: str = "") -> None:
        """发布任务进度
        
        Args:
            progress: 进度百分比 (0.0-1.0)
            message: 进度描述消息
        """
        # TODO: 实现进度发布逻辑
        pass
