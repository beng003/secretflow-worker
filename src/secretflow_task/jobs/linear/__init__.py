"""
线性模型任务模块
"""

from .ss_lr_task import (
    execute_ss_logistic_regression,
    execute_ss_lr_predict,
)

__all__ = [
    'execute_ss_logistic_regression',
    'execute_ss_lr_predict',
]
