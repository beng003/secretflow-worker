"""
BiClassificationEval二分类评估任务

使用SecretFlow的BiClassificationEval计算二分类模型的评估指标。
"""

from typing import Dict
import os
import json

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU
from secretflow.stats import BiClassificationEval

from utils.log import logger
from ...task_dispatcher import TaskDispatcher


@TaskDispatcher.register_task("biclassification_eval")
def execute_biclassification_eval(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行二分类模型评估任务

    计算二分类模型的评估指标，包括AUC、KS、F1、Precision、Recall、Accuracy等。

    Args:
        devices: 设备字典
        task_config: 任务配置，包含:
            - prediction_data: Dict[str, str] - 预测结果数据路径字典
            - label_column: str - 真实标签列名
            - prediction_column: str - 预测概率列名
            - bucket_size: Optional[int] - 分桶数量，默认10
            - output_report: str - 评估报告输出路径（JSON格式）

    Returns:
        Dict: 评估结果
    """
    logger.info("开始执行二分类模型评估任务")

    try:
        prediction_data = task_config["prediction_data"]
        label_column = task_config["label_column"]
        prediction_column = task_config["prediction_column"]
        bucket_size = task_config.get("bucket_size", 10)
        output_report = task_config["output_report"]

        parties = list(prediction_data.keys())
        logger.info(f"二分类评估配置: parties={parties}, label={label_column}, pred={prediction_column}")

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

        # 创建二分类评估器
        logger.info("计算二分类评估指标...")
        evaluator = BiClassificationEval(
            vdf,
            label=label_column,
            prediction=prediction_column,
            bucket_size=bucket_size
        )

        # 计算各项指标
        metrics = {}
        
        # AUC
        auc_value = evaluator.auc()
        metrics["auc"] = float(auc_value) if auc_value is not None else None
        
        # KS
        ks_value = evaluator.ks()
        metrics["ks"] = float(ks_value) if ks_value is not None else None
        
        # F1 Score
        f1_value = evaluator.f1_score()
        metrics["f1_score"] = float(f1_value) if f1_value is not None else None
        
        # Precision
        precision_value = evaluator.precision()
        metrics["precision"] = float(precision_value) if precision_value is not None else None
        
        # Recall
        recall_value = evaluator.recall()
        metrics["recall"] = float(recall_value) if recall_value is not None else None
        
        # Accuracy
        accuracy_value = evaluator.accuracy()
        metrics["accuracy"] = float(accuracy_value) if accuracy_value is not None else None

        # 获取混淆矩阵
        try:
            confusion_matrix = evaluator.confusion_matrix()
            metrics["confusion_matrix"] = {
                "true_positive": int(confusion_matrix[0]),
                "false_positive": int(confusion_matrix[1]),
                "true_negative": int(confusion_matrix[2]),
                "false_negative": int(confusion_matrix[3]),
            }
        except Exception as e:
            logger.warning(f"无法获取混淆矩阵: {e}")
            metrics["confusion_matrix"] = None

        # 保存评估报告
        result_data = {
            "metrics": metrics,
            "config": {
                "label_column": label_column,
                "prediction_column": prediction_column,
                "bucket_size": bucket_size,
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

        logger.info(f"二分类模型评估任务执行成功: AUC={metrics.get('auc'):.4f}")
        return result

    except Exception as e:
        logger.error(f"二分类模型评估任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"二分类模型评估任务执行失败: {str(e)}") from e
