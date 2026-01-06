"""
数据预处理任务模块

提供垂直联邦学习场景下的数据预处理功能，包括：
- Scaler: 数据标准化和归一化
- Encoder: 标签编码和独热编码
- Binning: 数据分箱
- FillNA: 缺失值填充
"""

from .scaler.standard_scaler_task import execute_standard_scaler
from .scaler.minmax_scaler_task import execute_minmax_scaler
from .encoder.label_encoder_task import execute_label_encoder
from .encoder.onehot_encoder_task import execute_onehot_encoder
from .binning.quantile_binning_task import execute_quantile_binning
from .binning.equal_width_binning_task import execute_equal_width_binning
from .fillna.fillna_task import execute_fillna

__all__ = [
    "execute_standard_scaler",
    "execute_minmax_scaler",
    "execute_label_encoder",
    "execute_onehot_encoder",
    "execute_quantile_binning",
    "execute_equal_width_binning",
    "execute_fillna",
]
