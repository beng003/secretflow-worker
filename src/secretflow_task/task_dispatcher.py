"""
任务分发器模块

TaskDispatcher负责根据task_type将任务路由到对应的执行函数。
使用装饰器模式实现任务注册，支持动态扩展新任务类型。
"""

from typing import Dict, Callable, List, Any
import logging

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """
    任务分发器：根据task_type路由到对应的执行函数
    
    使用装饰器模式注册任务执行函数，通过dispatch方法分发任务。
    所有任务执行函数必须遵循统一的函数签名：
        func(devices: Dict, task_config: Dict) -> Dict
    
    示例:
        @TaskDispatcher.register_task('psi')
        def execute_psi(devices: dict, task_config: dict) -> dict:
            # 执行PSI任务
            return {"status": "success", "result": {...}}
        
        # 分发任务
        result = TaskDispatcher.dispatch('psi', devices, task_config)
    """
    
    # 任务注册表：存储task_type到执行函数的映射
    TASK_REGISTRY: Dict[str, Callable] = {}
    
    @classmethod
    def register_task(cls, task_type: str) -> Callable:
        """
        任务注册装饰器
        
        将任务执行函数注册到TASK_REGISTRY中，使其可以通过dispatch方法调用。
        
        Args:
            task_type: 任务类型标识符，必须唯一
            
        Returns:
            装饰器函数
            
        Raises:
            ValueError: 当task_type已存在时抛出异常
            
        示例:
            @TaskDispatcher.register_task('psi')
            def execute_psi(devices: dict, task_config: dict) -> dict:
                return {"status": "success"}
        """
        def decorator(func: Callable) -> Callable:
            if task_type in cls.TASK_REGISTRY:
                raise ValueError(
                    f"任务类型 '{task_type}' 已注册。"
                    f"已注册函数: {cls.TASK_REGISTRY[task_type].__name__}, "
                    f"尝试注册函数: {func.__name__}"
                )
            
            cls.TASK_REGISTRY[task_type] = func
            logger.info(f"成功注册任务类型: '{task_type}' -> {func.__name__}")
            return func
        
        return decorator
    
    @classmethod
    def dispatch(cls, task_type: str, devices: Dict[str, Any], task_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        任务分发方法
        
        根据task_type查找并调用对应的任务执行函数。
        
        Args:
            task_type: 任务类型标识符
            devices: 设备字典，包含SPU、PYU等设备对象
            task_config: 任务配置字典，包含任务执行所需的所有参数
            
        Returns:
            任务执行结果字典
            
        Raises:
            ValueError: 当task_type不存在时抛出异常
            Exception: 任务执行过程中的其他异常会被捕获并重新抛出
            
        示例:
            devices = {"spu": spu, "alice": alice, "bob": bob}
            task_config = {"keys": ["uid"], "input_paths": {...}}
            result = TaskDispatcher.dispatch('psi', devices, task_config)
        """
        if task_type not in cls.TASK_REGISTRY:
            supported_tasks = cls.list_supported_tasks()
            raise ValueError(
                f"不支持的任务类型: '{task_type}'。"
                f"支持的任务类型: {supported_tasks}"
            )
        
        task_func = cls.TASK_REGISTRY[task_type]
        logger.info(f"开始执行任务: task_type='{task_type}', func={task_func.__name__}")
        
        try:
            result = task_func(devices, task_config)
            logger.info(f"任务执行成功: task_type='{task_type}'")
            return result
        except Exception as e:
            logger.error(
                f"任务执行失败: task_type='{task_type}', "
                f"error_type={type(e).__name__}, error_msg={str(e)}"
            )
            raise
    
    @classmethod
    def list_supported_tasks(cls) -> List[str]:
        """
        查询所有已注册的任务类型
        
        Returns:
            已注册的任务类型列表，按字母顺序排序
            
        示例:
            tasks = TaskDispatcher.list_supported_tasks()
            print(f"支持的任务: {tasks}")
            # 输出: 支持的任务: ['psi', 'ss_lr', 'ss_xgb', 'standard_scaler', ...]
        """
        return sorted(cls.TASK_REGISTRY.keys())
    
    @classmethod
    def get_task_info(cls, task_type: str) -> Dict[str, Any]:
        """
        获取指定任务的详细信息
        
        Args:
            task_type: 任务类型标识符
            
        Returns:
            任务信息字典，包含函数名、文档字符串等
            
        Raises:
            ValueError: 当task_type不存在时抛出异常
        """
        if task_type not in cls.TASK_REGISTRY:
            raise ValueError(f"任务类型 '{task_type}' 不存在")
        
        func = cls.TASK_REGISTRY[task_type]
        return {
            "task_type": task_type,
            "function_name": func.__name__,
            "module": func.__module__,
            "doc": func.__doc__,
        }
    
    @classmethod
    def clear_registry(cls) -> None:
        """
        清空任务注册表
        
        主要用于测试场景，生产环境不应调用此方法。
        """
        logger.warning("清空任务注册表")
        cls.TASK_REGISTRY.clear()
