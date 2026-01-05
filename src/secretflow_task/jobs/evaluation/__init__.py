"""
模型评估任务模块

提供垂直联邦学习场景下的模型评估功能，包括：
- 二分类评估（AUC、Accuracy、Precision、Recall、F1等）
- 回归评估（MSE、RMSE、MAE、R²等）
"""

from .biclassification_eval_task import execute_biclassification_eval
from .regression_eval_task import execute_regression_eval

__all__ = [
    "execute_biclassification_eval",
    "execute_regression_eval",
]
