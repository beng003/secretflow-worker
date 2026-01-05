"""
MinMaxScaler归一化任务

使用SecretFlow对垂直分区数据进行归一化处理，将数据缩放到指定范围。
"""

from typing import Dict, Tuple
import os

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU

from utils.log import logger
from ....task_dispatcher import TaskDispatcher


def _validate_minmax_scaler_config(task_config: Dict) -> None:
    """验证MinMaxScaler任务配置"""
    required_fields = ["input_data", "output_data"]
    for field in required_fields:
        if field not in task_config:
            raise ValueError(f"缺少必需字段: {field}")

    input_data = task_config["input_data"]
    output_data = task_config["output_data"]

    if not isinstance(input_data, dict):
        raise ValueError("input_data必须是字典类型")

    if not isinstance(output_data, dict):
        raise ValueError("output_data必须是字典类型")

    if set(input_data.keys()) != set(output_data.keys()):
        raise ValueError("input_data和output_data的参与方不一致")

    feature_range = task_config.get("feature_range", (0, 1))
    if not isinstance(feature_range, (list, tuple)) or len(feature_range) != 2:
        raise ValueError("feature_range必须是长度为2的列表或元组")

    if feature_range[0] >= feature_range[1]:
        raise ValueError("feature_range的最小值必须小于最大值")


@TaskDispatcher.register_task("minmax_scaler")
def execute_minmax_scaler(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行MinMaxScaler归一化任务

    将数据缩放到指定范围（默认[0, 1]）。

    Args:
        devices: 设备字典
        task_config: 任务配置，包含:
            - input_data: Dict[str, str] - 输入数据路径
            - output_data: Dict[str, str] - 输出数据路径
            - columns: Optional[List[str]] - 需要归一化的列名列表
            - feature_range: Optional[Tuple[float, float]] - 目标范围，默认(0, 1)

    Returns:
        Dict: 归一化结果
    """
    logger.info("开始执行MinMaxScaler归一化任务")

    try:
        _validate_minmax_scaler_config(task_config)

        input_data = task_config["input_data"]
        output_data = task_config["output_data"]
        columns = task_config.get("columns")
        feature_range = tuple(task_config.get("feature_range", (0, 1)))

        parties = list(input_data.keys())
        logger.info(
            f"MinMaxScaler配置: parties={parties}, columns={columns}, feature_range={feature_range}"
        )

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

        # MinMaxScaler归一化
        logger.info("执行MinMaxScaler归一化...")

        def minmax_scale(data, feature_range):
            """在PYU上执行MinMaxScaler"""
            import pandas as pd

            min_val, max_val = feature_range
            data_min = data.min()
            data_max = data.max()

            # 避免除零
            data_range = data_max - data_min
            data_range[data_range == 0] = 1

            scaled = (data - data_min) / data_range
            scaled = scaled * (max_val - min_val) + min_val

            return scaled

        if columns is None:
            # 归一化所有数值列
            scaled_columns = list(vdf.columns)
            for col in scaled_columns:
                for party in parties:
                    pyu = devices[party]
                    if col in vdf.partitions[pyu].columns:
                        vdf.partitions[pyu][col] = pyu(minmax_scale)(
                            vdf.partitions[pyu][col], feature_range
                        )
        else:
            # 归一化指定列
            for col in columns:
                if col not in vdf.columns:
                    raise ValueError(f"列'{col}'不存在于数据中")

            for col in columns:
                for party in parties:
                    pyu = devices[party]
                    if col in vdf.partitions[pyu].columns:
                        vdf.partitions[pyu][col] = pyu(minmax_scale)(
                            vdf.partitions[pyu][col], feature_range
                        )
            scaled_columns = columns

        # 保存结果
        pyu_output_paths = {devices[party]: output_data[party] for party in parties}
        vdf.to_csv(pyu_output_paths, index=False)

        result = {
            "output_paths": output_data,
            "scaled_columns": scaled_columns,
            "feature_range": feature_range,
            "parties": parties,
        }

        logger.info("MinMaxScaler任务执行成功")
        return result

    except ValueError as e:
        logger.error(f"MinMaxScaler任务配置错误: {e}")
        raise
    except Exception as e:
        logger.error(f"MinMaxScaler任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"MinMaxScaler任务执行失败: {str(e)}") from e
