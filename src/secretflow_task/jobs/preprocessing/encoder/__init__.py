"""
Encoder子模块

提供数据编码功能：
- LabelEncoder: 标签编码（将类别转换为数值）
- OneHotEncoder: 独热编码（将类别转换为二进制向量）
"""

from .label_encoder_task import execute_label_encoder
from .onehot_encoder_task import execute_onehot_encoder

__all__ = [
    "execute_label_encoder",
    "execute_onehot_encoder",
]
