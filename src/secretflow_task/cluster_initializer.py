"""
SecretFlow集群初始化管理器

负责SecretFlow集群的初始化、状态管理和资源清理。
"""

import time
import threading
from utils.log import logger


class SecretFlowClusterInitializer:
    """SecretFlow集群初始化管理器 - 单例模式"""

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._cluster_initialized = False
            self._initialization_time = None
            SecretFlowClusterInitializer._initialized = True

    @classmethod
    def get_instance(cls) -> "SecretFlowClusterInitializer":
        """获取SecretFlowClusterInitializer单例实例"""
        return cls()

    def initialize_cluster(self, sf_init_config: dict) -> bool:
        """初始化SecretFlow集群

        使用sf.init(**sf_init_config)直接初始化，参数验证交给SecretFlow框架处理

        Args:
            sf_init_config: SecretFlow初始化配置

        Returns:
            bool: 初始化是否成功
        """
        if self._cluster_initialized:
            logger.warning("SecretFlow集群已经初始化，跳过重复初始化")
            return True

        start_time = time.time()

        try:
            logger.info("开始初始化SecretFlow集群...")

            # 使用SecretFlow原生API初始化集群
            import secretflow as sf

            sf.init(**sf_init_config)

            self._cluster_initialized = True
            self._initialization_time = time.time() - start_time

            logger.info(
                f"SecretFlow集群初始化成功，耗时: {self._initialization_time:.2f}秒"
            )
            return True

        except Exception as e:
            init_time = time.time() - start_time
            logger.error(
                f"SecretFlow集群初始化失败，耗时: {init_time:.2f}秒，错误: {e}"
            )
            self._cluster_initialized = False
            return False

    def shutdown_cluster(self) -> None:
        """关闭SecretFlow集群"""
        if not self._cluster_initialized:
            logger.warning("SecretFlow集群未初始化，无需关闭")
            return

        try:
            logger.info("开始关闭SecretFlow集群...")

            # 使用SecretFlow原生API关闭集群
            import secretflow as sf

            sf.shutdown()

            self._cluster_initialized = False
            logger.info("SecretFlow集群已关闭")

        except Exception as e:
            logger.error(f"SecretFlow集群关闭时发生错误: {e}")
            # 即使关闭失败也标记为未初始化
            self._cluster_initialized = False

    def is_cluster_ready(self) -> bool:
        """检查集群是否就绪

        Returns:
            bool: 集群是否准备就绪
        """
        return self._cluster_initialized

    def get_initialization_time(self) -> float | None:
        """获取集群初始化时间

        Returns:
            float | None: 初始化耗时（秒），如果未初始化则返回None
        """
        return self._initialization_time
