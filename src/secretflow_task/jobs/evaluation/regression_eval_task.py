"""
RegressionEval回归评估任务

使用SecretFlow的RegressionEval计算回归模型的评估指标。
"""

from typing import Dict
import os
import json

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU
from secretflow.stats import RegressionEval

from utils.log import logger
from ...task_dispatcher import TaskDispatcher


@TaskDispatcher.register_task("regression_eval")
def execute_regression_eval(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行回归模型评估任务

    计算回归模型的评估指标，包括MSE、RMSE、MAE、R²等。

    Args:
        devices: 设备字典
        task_config: 任务配置，包含:
            - prediction_data: Dict[str, str] - 预测结果数据路径字典
            - label_column: str - 真实标签列名
            - prediction_column: str - 预测值列名
            - output_report: str - 评估报告输出路径（JSON格式）

    Returns:
        Dict: 评估结果
    """
    logger.info("开始执行回归模型评估任务")

    try:
        prediction_data = task_config["prediction_data"]
        label_column = task_config["label_column"]
        prediction_column = task_config["prediction_column"]
        output_report = task_config["output_report"]

        parties = list(prediction_data.keys())
        logger.info(f"回归评估配置: parties={parties}, label={label_column}, pred={prediction_column}")

        # 验证设备
        for party in parties:
            if party not in devices:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")

        # 验证输入文件
        for party, path in prediction_data.items():
            if not os.path.exists(path):
                raise ValueError(f"预测数据文件不存在: {path}")

        # 创建输出目录
        output_dir = os.path.dirname(output_report)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # 读取预测数据
        logger.info("读取预测数据...")
        pyu_input_paths = {devices[party]: prediction_data[party] for party in parties}
        vdf: VDataFrame = sf.data.vertical.read_csv(pyu_input_paths)

        # 创建回归评估器
        logger.info("计算回归评估指标...")
        evaluator = RegressionEval(
            vdf,
            label=label_column,
            prediction=prediction_column
        )

        # 计算各项指标
        metrics = {}
        
        # Mean Squared Error (MSE)
        mse_value = evaluator.mean_squared_error()
        metrics["mse"] = float(mse_value) if mse_value is not None else None
        
        # Root Mean Squared Error (RMSE)
        rmse_value = evaluator.root_mean_squared_error()
        metrics["rmse"] = float(rmse_value) if rmse_value is not None else None
        
        # Mean Absolute Error (MAE)
        mae_value = evaluator.mean_abs_error()
        metrics["mae"] = float(mae_value) if mae_value is not None else None
        
        # Mean Absolute Percentage Error (MAPE)
        try:
            mape_value = evaluator.mean_abs_percent_error()
            metrics["mape"] = float(mape_value) if mape_value is not None else None
        except Exception as e:
            logger.warning(f"无法计算MAPE: {e}")
            metrics["mape"] = None
        
        # R² Score
        r2_value = evaluator.r2_score()
        metrics["r2_score"] = float(r2_value) if r2_value is not None else None
        
        # Explained Variance Score
        try:
            explained_var = evaluator.explained_variance_score()
            metrics["explained_variance"] = float(explained_var) if explained_var is not None else None
        except Exception as e:
            logger.warning(f"无法计算explained_variance: {e}")
            metrics["explained_variance"] = None

        # 保存评估报告
        result_data = {
            "metrics": metrics,
            "config": {
                "label_column": label_column,
                "prediction_column": prediction_column,
            },
            "parties": parties,
        }

        logger.info(f"保存评估报告到: {output_report}")
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        result = {
            "output_report": output_report,
            "metrics": metrics,
            "parties": parties,
        }

        logger.info(f"回归模型评估任务执行成功: RMSE={metrics.get('rmse'):.4f}, R²={metrics.get('r2_score'):.4f}")
        return result

    except Exception as e:
        logger.error(f"回归模型评估任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"回归模型评估任务执行失败: {str(e)}") from e
