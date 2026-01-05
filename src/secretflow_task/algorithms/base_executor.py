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
        required_fields = ["task_type"]
        for field in required_fields:
            if field not in self.task_config:
                return False

        # 验证task_type不为空
        if not self.task_config["task_type"]:
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
        # 验证进度值范围
        progress = max(0.0, min(1.0, progress))

        try:
            from utils.status_notifier import _publish_status

            _publish_status(
                self.task_request_id,
                "RUNNING",
                {
                    "stage": "progress_update",
                    "progress": progress,
                    "progress_percent": f"{progress * 100:.1f}%",
                    "message": message,
                    "task_type": self.task_config.get("task_type", "unknown"),
                    "algorithm_step": message
                    if message
                    else f"进度 {progress * 100:.1f}%",
                },
            )
        except Exception:
            # 静默失败，确保进度发布不影响主算法执行
            pass
