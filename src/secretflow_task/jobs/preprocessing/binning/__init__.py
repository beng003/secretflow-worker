"""
Binning子模块

提供数据分箱功能：
- QuantileBinning: 等频分箱
- EqualWidthBinning: 等宽分箱
"""

from .quantile_binning_task import execute_quantile_binning
from .equal_width_binning_task import execute_equal_width_binning

__all__ = [
    "execute_quantile_binning",
    "execute_equal_width_binning",
]
