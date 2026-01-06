"""
SecretFlow任务模块

本模块包含各类SecretFlow任务的执行函数:
- PSI任务: 隐私集合求交
- 预处理任务: 数据标准化、归一化、编码等
- 机器学习任务: 逻辑回归、XGBoost等
- 统计分析任务: 表统计、相关性分析等
- 评估任务: 模型评估指标计算
"""

from .psi_task import execute_psi
from .linear import execute_ss_logistic_regression, execute_ss_lr_predict
from .boost import execute_ss_xgboost, execute_ss_xgb_predict
from .preprocessing import (
    execute_standard_scaler,
    execute_minmax_scaler,
    execute_label_encoder,
    execute_onehot_encoder,
    execute_quantile_binning,
    execute_equal_width_binning,
    execute_fillna,
)
from .stats import (
    execute_table_statistics,
    execute_pearson_correlation,
    execute_vif,
)
from .evaluation import (
    execute_biclassification_eval,
    execute_regression_eval,
)

__all__ = [
    "execute_psi",
    "execute_ss_logistic_regression",
    "execute_ss_lr_predict",
    "execute_ss_xgboost",
    "execute_ss_xgb_predict",
    "execute_standard_scaler",
    "execute_minmax_scaler",
    "execute_label_encoder",
    "execute_onehot_encoder",
    "execute_quantile_binning",
    "execute_equal_width_binning",
    "execute_fillna",
    "execute_table_statistics",
    "execute_pearson_correlation",
    "execute_vif",
    "execute_biclassification_eval",
    "execute_regression_eval",
]
