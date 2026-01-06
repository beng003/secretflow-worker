"""
LabelEncoder标签编码任务

将类别型特征转换为数值型标签。
"""

from typing import Dict
import os

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU

from utils.log import logger
from ....task_dispatcher import TaskDispatcher


def _validate_label_encoder_config(task_config: Dict) -> None:
    """验证LabelEncoder任务配置"""
    required_fields = ["input_data", "output_data", "columns"]
    for field in required_fields:
        if field not in task_config:
            raise ValueError(f"缺少必需字段: {field}")

    input_data = task_config["input_data"]
    output_data = task_config["output_data"]
    columns = task_config["columns"]

    if not isinstance(input_data, dict):
        raise ValueError("input_data必须是字典类型")

    if not isinstance(output_data, dict):
        raise ValueError("output_data必须是字典类型")

    if not isinstance(columns, list) or not columns:
        raise ValueError("columns必须是非空列表")

    if set(input_data.keys()) != set(output_data.keys()):
        raise ValueError("input_data和output_data的参与方不一致")


@TaskDispatcher.register_task("label_encoder")
def execute_label_encoder(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行LabelEncoder标签编码任务

    将类别型特征转换为数值型标签（0, 1, 2, ...）。

    Args:
        devices: 设备字典
        task_config: 任务配置，包含:
            - input_data: Dict[str, str] - 输入数据路径
            - output_data: Dict[str, str] - 输出数据路径
            - columns: List[str] - 需要编码的列名列表

    Returns:
        Dict: 编码结果，包含编码映射信息
    """
    logger.info("开始执行LabelEncoder标签编码任务")

    try:
        _validate_label_encoder_config(task_config)

        input_data = task_config["input_data"]
        output_data = task_config["output_data"]
        columns = task_config["columns"]

        parties = list(input_data.keys())
        logger.info(f"LabelEncoder配置: parties={parties}, columns={columns}")

        # 验证设备
        for party in parties:
            if party not in devices:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")

        # 读取数据
        pyu_input_paths = {devices[party]: input_data[party] for party in parties}

        for party, path in input_data.items():
            if not os.path.exists(path):
                raise ValueError(f"输入文件不存在: {path}")

        for party, path in output_data.items():
            output_dir = os.path.dirname(path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

        logger.info("读取垂直分区数据...")
        vdf: VDataFrame = sf.data.vertical.read_csv(pyu_input_paths)

        # LabelEncoder编码
        logger.info("执行LabelEncoder编码...")

        def label_encode(data, columns):
            """在PYU上执行LabelEncoder"""
            from sklearn.preprocessing import LabelEncoder
            import pandas as pd

            df = data.copy()
            encoders = {}

            for col in columns:
                if col in df.columns:
                    le = LabelEncoder()
                    df[col] = le.fit_transform(df[col].astype(str))
                    encoders[col] = {
                        "classes": le.classes_.tolist(),
                        "n_classes": len(le.classes_),
                    }

            return df, encoders

        encoded_columns = []
        for col in columns:
            if col not in vdf.columns:
                raise ValueError(f"列'{col}'不存在于数据中")
            encoded_columns.append(col)

        # 对每个参与方的数据进行编码
        for party in parties:
            pyu = devices[party]
            party_columns = [
                col for col in columns if col in vdf.partitions[pyu].columns
            ]
            if party_columns:
                vdf.partitions[pyu], _ = pyu(label_encode)(
                    vdf.partitions[pyu], party_columns
                )

        # 保存结果
        pyu_output_paths = {devices[party]: output_data[party] for party in parties}
        vdf.to_csv(pyu_output_paths, index=False)

        result = {
            "output_paths": output_data,
            "encoded_columns": encoded_columns,
            "parties": parties,
        }

        logger.info("LabelEncoder任务执行成功")
        return result

    except ValueError as e:
        logger.error(f"LabelEncoder任务配置错误: {e}")
        raise
    except Exception as e:
        logger.error(f"LabelEncoder任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"LabelEncoder任务执行失败: {str(e)}") from e
