"""
任务注册表

管理所有可用的SecretFlow任务类型和对应的执行器。
支持动态注册、版本管理、算法发现和兼容性检查。
"""

import inspect
import threading
from typing import Dict, Type, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from secretflow_task.algorithms.base_executor import BaseTaskExecutor
from secretflow_task.algorithms.psi_executor import PSIExecutor
from secretflow_task.algorithms.lr_executor import LogisticRegressionExecutor
from utils.log import logger
from utils.exceptions import ParameterValidationError


@dataclass
class AlgorithmMetadata:
    """算法元数据
    
    记录算法的版本、能力、依赖等信息
    """
    name: str
    executor_class: Type[BaseTaskExecutor]
    version: str = "1.0.0"
    description: str = ""
    required_devices: List[str] = field(default_factory=list)  # ['spu', 'heu', 'pyu']
    min_parties: int = 2
    max_parties: int = 3
    supported_protocols: List[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=datetime.now)
    deprecated: bool = False
    deprecation_message: str = ""
    
    def is_compatible(self, required_version: str = None) -> bool:
        """检查版本兼容性
        
        Args:
            required_version: 需要的最低版本
            
        Returns:
            bool: 是否兼容
        """
        if not required_version:
            return True
        
        # 简单的版本比较 (major.minor.patch)
        try:
            current = tuple(map(int, self.version.split('.')))
            required = tuple(map(int, required_version.split('.')))
            return current >= required
        except (ValueError, AttributeError):
            logger.warning(f"无法解析版本号: current={self.version}, required={required_version}")
            return True


class AlgorithmRegistry:
    """算法注册中心
    
    提供算法的注册、发现、版本管理和兼容性检查功能。
    使用单例模式确保全局唯一。
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._registry: Dict[str, AlgorithmMetadata] = {}
            self._aliases: Dict[str, str] = {}  # 别名映射到主名称
            self._initialized = True
            self._register_builtin_algorithms()
    
    def _register_builtin_algorithms(self):
        """注册内置算法"""
        # 注册PSI算法
        self.register(
            name="psi",
            executor_class=PSIExecutor,
            version="1.0.0",
            description="隐私集合求交算法，支持2方和3方PSI",
            required_devices=['pyu', 'spu'],
            min_parties=2,
            max_parties=3,
            supported_protocols=['KKRT_PSI_2PC', 'ECDH_PSI_2PC', 'BC22_PSI_2PC', 'ECDH_PSI_3PC']
        )
        
        # 注册逻辑回归算法
        self.register(
            name="lr",
            executor_class=LogisticRegressionExecutor,
            version="1.0.0",
            description="联邦逻辑回归算法",
            required_devices=['pyu', 'spu'],
            min_parties=2,
            max_parties=3,
            supported_protocols=['SEMI2K', 'ABY3']
        )
        
        # 注册别名
        self.register_alias("logistic_regression", "lr")
        
        logger.info(f"已注册 {len(self._registry)} 个内置算法")
    
    def register(
        self,
        name: str,
        executor_class: Type[BaseTaskExecutor],
        version: str = "1.0.0",
        description: str = "",
        required_devices: List[str] = None,
        min_parties: int = 2,
        max_parties: int = 3,
        supported_protocols: List[str] = None,
        force: bool = False
    ) -> bool:
        """注册算法执行器
        
        Args:
            name: 算法名称（唯一标识）
            executor_class: 执行器类
            version: 算法版本
            description: 算法描述
            required_devices: 需要的设备类型
            min_parties: 最少参与方数量
            max_parties: 最多参与方数量
            supported_protocols: 支持的协议列表
            force: 是否强制覆盖已存在的注册
            
        Returns:
            bool: 注册是否成功
        """
        try:
            # 验证执行器类
            if not inspect.isclass(executor_class):
                raise ValueError(f"executor_class必须是类，而不是 {type(executor_class)}")
            
            if not issubclass(executor_class, BaseTaskExecutor):
                raise ValueError("executor_class必须继承自BaseTaskExecutor")
            
            # 检查是否已存在
            if name in self._registry and not force:
                logger.warning(f"算法 '{name}' 已存在，使用force=True强制覆盖")
                return False
            
            # 创建元数据
            metadata = AlgorithmMetadata(
                name=name,
                executor_class=executor_class,
                version=version,
                description=description,
                required_devices=required_devices or ['pyu'],
                min_parties=min_parties,
                max_parties=max_parties,
                supported_protocols=supported_protocols or []
            )
            
            # 注册到注册表
            self._registry[name] = metadata
            
            logger.info(
                f"成功注册算法: name={name}, version={version}, "
                f"executor={executor_class.__name__}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"注册算法失败: {e}", exc_info=True)
            return False
    
    def register_alias(self, alias: str, target: str) -> bool:
        """注册算法别名
        
        Args:
            alias: 别名
            target: 目标算法名称
            
        Returns:
            bool: 注册是否成功
        """
        if target not in self._registry:
            logger.warning(f"目标算法 '{target}' 不存在，无法注册别名 '{alias}'")
            return False
        
        self._aliases[alias] = target
        logger.info(f"注册别名: {alias} -> {target}")
        return True
    
    def unregister(self, name: str) -> bool:
        """注销算法
        
        Args:
            name: 算法名称
            
        Returns:
            bool: 注销是否成功
        """
        if name in self._registry:
            del self._registry[name]
            logger.info(f"注销算法: {name}")
            return True
        return False
    
    def get_metadata(self, name: str) -> Optional[AlgorithmMetadata]:
        """获取算法元数据
        
        Args:
            name: 算法名称或别名
            
        Returns:
            AlgorithmMetadata: 算法元数据，如果不存在返回None
        """
        # 解析别名
        actual_name = self._aliases.get(name, name)
        return self._registry.get(actual_name)
    
    def get_executor_class(self, name: str) -> Optional[Type[BaseTaskExecutor]]:
        """获取算法执行器类
        
        Args:
            name: 算法名称或别名
            
        Returns:
            Type[BaseTaskExecutor]: 执行器类，如果不存在返回None
        """
        metadata = self.get_metadata(name)
        return metadata.executor_class if metadata else None
    
    def is_registered(self, name: str) -> bool:
        """检查算法是否已注册
        
        Args:
            name: 算法名称或别名
            
        Returns:
            bool: 是否已注册
        """
        actual_name = self._aliases.get(name, name)
        return actual_name in self._registry
    
    def list_algorithms(self, include_deprecated: bool = False) -> List[str]:
        """列出所有已注册的算法
        
        Args:
            include_deprecated: 是否包含已弃用的算法
            
        Returns:
            List[str]: 算法名称列表
        """
        if include_deprecated:
            return list(self._registry.keys())
        else:
            return [name for name, meta in self._registry.items() if not meta.deprecated]
    
    def list_aliases(self) -> Dict[str, str]:
        """列出所有别名
        
        Returns:
            Dict[str, str]: 别名映射字典
        """
        return self._aliases.copy()
    
    def check_compatibility(
        self, 
        name: str, 
        required_version: str = None,
        available_devices: List[str] = None,
        num_parties: int = None
    ) -> Dict[str, Any]:
        """检查算法兼容性
        
        Args:
            name: 算法名称
            required_version: 需要的最低版本
            available_devices: 可用的设备列表
            num_parties: 参与方数量
            
        Returns:
            Dict[str, Any]: 兼容性检查结果
        """
        metadata = self.get_metadata(name)
        
        if not metadata:
            return {
                'compatible': False,
                'reason': f"算法 '{name}' 不存在"
            }
        
        issues = []
        
        # 检查版本兼容性
        if required_version and not metadata.is_compatible(required_version):
            issues.append(f"版本不兼容: 需要 >= {required_version}, 当前 {metadata.version}")
        
        # 检查设备要求
        if available_devices:
            missing_devices = set(metadata.required_devices) - set(available_devices)
            if missing_devices:
                issues.append(f"缺少必需设备: {missing_devices}")
        
        # 检查参与方数量
        if num_parties is not None:
            if num_parties < metadata.min_parties:
                issues.append(f"参与方数量不足: 最少需要 {metadata.min_parties}, 当前 {num_parties}")
            if num_parties > metadata.max_parties:
                issues.append(f"参与方数量超限: 最多支持 {metadata.max_parties}, 当前 {num_parties}")
        
        # 检查是否已弃用
        if metadata.deprecated:
            issues.append(f"算法已弃用: {metadata.deprecation_message}")
        
        return {
            'compatible': len(issues) == 0,
            'issues': issues,
            'metadata': metadata
        }
    
    def deprecate_algorithm(self, name: str, message: str = "") -> bool:
        """标记算法为已弃用
        
        Args:
            name: 算法名称
            message: 弃用说明
            
        Returns:
            bool: 操作是否成功
        """
        metadata = self.get_metadata(name)
        if metadata:
            metadata.deprecated = True
            metadata.deprecation_message = message
            logger.info(f"算法 '{name}' 已标记为弃用: {message}")
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取注册表统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            'total_algorithms': len(self._registry),
            'active_algorithms': len([m for m in self._registry.values() if not m.deprecated]),
            'deprecated_algorithms': len([m for m in self._registry.values() if m.deprecated]),
            'total_aliases': len(self._aliases),
            'algorithms': {
                name: {
                    'version': meta.version,
                    'deprecated': meta.deprecated,
                    'required_devices': meta.required_devices
                }
                for name, meta in self._registry.items()
            }
        }


# 全局注册中心实例
_registry = AlgorithmRegistry()

# 向后兼容的全局注册表
ALGORITHM_REGISTRY: Dict[str, Type[BaseTaskExecutor]] = {
    name: _registry.get_executor_class(name)
    for name in _registry.list_algorithms(include_deprecated=True)
}


class AlgorithmFactory:
    """算法执行器工厂
    
    提供算法执行器的创建、验证和管理功能。
    使用缓存机制优化性能。
    """
    
    def __init__(self):
        self._registry = _registry
        self._executor_cache: Dict[str, Type[BaseTaskExecutor]] = {}
        self._cache_lock = threading.Lock()
    
    def create_executor(
        self, 
        task_type: str, 
        task_request_id: str, 
        task_config: Dict,
        validate_compatibility: bool = True
    ) -> BaseTaskExecutor:
        """创建算法执行器实例
        
        Args:
            task_type: 任务类型
            task_request_id: 任务请求ID
            task_config: 任务配置
            validate_compatibility: 是否验证兼容性
            
        Returns:
            BaseTaskExecutor: 对应的执行器实例
            
        Raises:
            ValueError: 不支持的任务类型
            ParameterValidationError: 兼容性验证失败
        """
        try:
            # 检查算法是否已注册
            if not self._registry.is_registered(task_type):
                available = ', '.join(self._registry.list_algorithms())
                raise ValueError(
                    f"不支持的任务类型: '{task_type}'。"
                    f"可用算法: {available}"
                )
            
            # 获取算法元数据
            metadata = self._registry.get_metadata(task_type)
            
            # 兼容性检查
            if validate_compatibility:
                compatibility = self._validate_compatibility(task_type, task_config)
                if not compatibility['compatible']:
                    raise ParameterValidationError(
                        f"算法 '{task_type}' 兼容性检查失败: {', '.join(compatibility['issues'])}"
                    )
            
            # 从缓存获取或加载执行器类
            executor_class = self._get_executor_class_cached(task_type)
            
            # 创建执行器实例
            executor = executor_class(task_request_id, task_config)
            
            logger.info(
                f"成功创建执行器: task_type={task_type}, "
                f"version={metadata.version}, task_id={task_request_id}"
            )
            
            return executor
            
        except (ValueError, ParameterValidationError):
            raise
        except Exception as e:
            error_msg = f"创建执行器失败: task_type={task_type}, error={str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg) from e
    
    def _get_executor_class_cached(self, task_type: str) -> Type[BaseTaskExecutor]:
        """从缓存获取执行器类（性能优化）
        
        Args:
            task_type: 任务类型
            
        Returns:
            Type[BaseTaskExecutor]: 执行器类
        """
        # 快速路径：从缓存获取
        if task_type in self._executor_cache:
            return self._executor_cache[task_type]
        
        # 慢速路径：从注册表获取并缓存
        with self._cache_lock:
            # 双重检查
            if task_type in self._executor_cache:
                return self._executor_cache[task_type]
            
            executor_class = self._registry.get_executor_class(task_type)
            if executor_class:
                self._executor_cache[task_type] = executor_class
            return executor_class
    
    def _validate_compatibility(
        self, 
        task_type: str, 
        task_config: Dict
    ) -> Dict[str, Any]:
        """验证算法兼容性
        
        Args:
            task_type: 任务类型
            task_config: 任务配置
            
        Returns:
            Dict[str, Any]: 兼容性检查结果
        """
        # 提取配置中的兼容性相关参数
        required_version = task_config.get('algorithm_version')
        num_parties = None
        
        # 尝试从不同的配置字段提取参与方数量
        if 'input_paths' in task_config and isinstance(task_config['input_paths'], dict):
            num_parties = len(task_config['input_paths'])
        elif 'parties' in task_config:
            if isinstance(task_config['parties'], list):
                num_parties = len(task_config['parties'])
            elif isinstance(task_config['parties'], dict):
                num_parties = len(task_config['parties'])
        
        # 执行兼容性检查
        return self._registry.check_compatibility(
            name=task_type,
            required_version=required_version,
            num_parties=num_parties
        )
    
    def get_supported_algorithms(self, include_deprecated: bool = False) -> List[str]:
        """获取支持的算法列表
        
        Args:
            include_deprecated: 是否包含已弃用的算法
            
        Returns:
            List[str]: 支持的算法类型列表
        """
        return self._registry.list_algorithms(include_deprecated=include_deprecated)
    
    def get_algorithm_info(self, task_type: str) -> Optional[Dict[str, Any]]:
        """获取算法信息
        
        Args:
            task_type: 任务类型
            
        Returns:
            Optional[Dict[str, Any]]: 算法信息，如果不存在返回None
        """
        metadata = self._registry.get_metadata(task_type)
        if not metadata:
            return None
        
        return {
            'name': metadata.name,
            'version': metadata.version,
            'description': metadata.description,
            'required_devices': metadata.required_devices,
            'min_parties': metadata.min_parties,
            'max_parties': metadata.max_parties,
            'supported_protocols': metadata.supported_protocols,
            'deprecated': metadata.deprecated,
            'deprecation_message': metadata.deprecation_message
        }
    
    def clear_cache(self):
        """清除执行器类缓存"""
        with self._cache_lock:
            self._executor_cache.clear()
            logger.info("执行器缓存已清除")
    
    def get_registry_statistics(self) -> Dict[str, Any]:
        """获取注册表统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return self._registry.get_statistics()


# 全局工厂实例（单例）
_factory = AlgorithmFactory()


# 便捷函数
def register_algorithm(
    name: str,
    executor_class: Type[BaseTaskExecutor],
    **kwargs
) -> bool:
    """注册算法的便捷函数
    
    Args:
        name: 算法名称
        executor_class: 执行器类
        **kwargs: 其他元数据参数
        
    Returns:
        bool: 注册是否成功
    """
    return _registry.register(name, executor_class, **kwargs)


def get_algorithm_factory() -> AlgorithmFactory:
    """获取全局算法工厂实例
    
    Returns:
        AlgorithmFactory: 工厂实例
    """
    return _factory
