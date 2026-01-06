"""
统计分析任务模块

提供垂直联邦学习场景下的统计分析功能，包括：
- 表统计分析
- 相关性分析（Pearson相关系数）
- 方差膨胀因子（VIF）
- 模型评估（二分类、回归）
"""

from .table_statistics_task import execute_table_statistics
from .pearson_correlation_task import execute_pearson_correlation
from .vif_task import execute_vif

__all__ = [
    "execute_table_statistics",
    "execute_pearson_correlation",
    "execute_vif",
]
