"""
Boosting模型任务模块
"""

from .ss_xgb_task import (
    execute_ss_xgboost,
    execute_ss_xgb_predict,
)

__all__ = [
    'execute_ss_xgboost',
    'execute_ss_xgb_predict',
]
