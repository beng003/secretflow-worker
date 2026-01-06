"""
StandardScaler标准化任务

使用SecretFlow的StandardScaler对垂直分区数据进行标准化处理。
"""

from typing import Dict
import os

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.preprocessing import StandardScaler
from secretflow.device import PYU

from utils.log import logger
from ....task_dispatcher import TaskDispatcher


def _validate_standard_scaler_config(task_config: Dict) -> None:
    """
    验证StandardScaler任务配置

    Args:
        task_config: 任务配置字典

    Raises:
        ValueError: 配置验证失败
    """
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

    if not input_data:
        raise ValueError("input_data不能为空")

    if not output_data:
        raise ValueError("output_data不能为空")

    input_parties = set(input_data.keys())
    output_parties = set(output_data.keys())

    if input_parties != output_parties:
        raise ValueError(
            f"input_data和output_data的参与方不一致: {input_parties} vs {output_parties}"
        )

    for party, path in input_data.items():
        if not isinstance(path, str) or not path:
            raise ValueError(f"参与方'{party}'的input_data路径必须是非空字符串")

    for party, path in output_data.items():
        if not isinstance(path, str) or not path:
            raise ValueError(f"参与方'{party}'的output_data路径必须是非空字符串")

    columns = task_config.get("columns")
    if columns is not None:
        if not isinstance(columns, list):
            raise ValueError("columns必须是列表类型")
        if not columns:
            raise ValueError("columns不能为空列表")
        for col in columns:
            if not isinstance(col, str):
                raise ValueError(f"列名必须是字符串类型: {col}")


@TaskDispatcher.register_task("standard_scaler")
def execute_standard_scaler(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行StandardScaler数据标准化任务

    StandardScaler将数据标准化为均值为0、标准差为1的分布。
    支持垂直联邦学习场景下的数据标准化。

    Args:
        devices: 设备字典，键为参与方名称，值为PYU设备对象
        task_config: 任务配置字典，包含:
            - input_data: Dict[str, str] - 输入数据路径
            - output_data: Dict[str, str] - 输出数据路径
            - columns: Optional[List[str]] - 需要标准化的列名列表
            - with_mean: Optional[bool] - 是否减去均值，默认True
            - with_std: Optional[bool] - 是否除以标准差，默认True

    Returns:
        Dict: 标准化结果，包含:
            - output_paths: Dict[str, str] - 输出文件路径
            - scaled_columns: List[str] - 标准化的列名
            - with_mean: bool - 是否使用了均值中心化
            - with_std: bool - 是否使用了标准差缩放
            - parties: List[str] - 参与方列表

    Raises:
        ValueError: 配置验证失败或设备缺失
        RuntimeError: 标准化执行失败
    """
    logger.info("开始执行StandardScaler标准化任务")

    try:
        _validate_standard_scaler_config(task_config)

        input_data = task_config["input_data"]
        output_data = task_config["output_data"]
        columns = task_config.get("columns")
        with_mean = task_config.get("with_mean", True)
        with_std = task_config.get("with_std", True)

        parties = list(input_data.keys())
        logger.info(
            f"StandardScaler配置: parties={parties}, columns={columns}, with_mean={with_mean}, with_std={with_std}"
        )

        for party in parties:
            pyu_device = devices.get(party)
            if pyu_device is None:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")

        pyu_input_paths = {}
        for party in parties:
            pyu_device = devices.get(party)
            pyu_input_paths[pyu_device] = input_data[party]

        logger.info(f"输入文件: {input_data}")

        for party, path in input_data.items():
            if not os.path.exists(path):
                raise ValueError(f"输入文件不存在: {path}")

        for party, path in output_data.items():
            output_dir = os.path.dirname(path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"创建输出目录: {output_dir}")

        logger.info("读取垂直分区数据...")
        vdf: VDataFrame = sf.data.vertical.read_csv(pyu_input_paths)
        logger.info(f"数据读取完成，列: {vdf.columns}")

        logger.info("创建StandardScaler实例...")
        scaler = StandardScaler(with_mean=with_mean, with_std=with_std)

        if columns is None:
            logger.info("标准化所有数值列")
            scaled_vdf = scaler.fit_transform(vdf)
            scaled_columns = list(vdf.columns)
        else:
            logger.info(f"标准化指定列: {columns}")
            for col in columns:
                if col not in vdf.columns:
                    raise ValueError(f"列'{col}'不存在于数据中")

            for col in columns:
                vdf[col] = scaler.fit_transform(vdf[col])
            scaled_vdf = vdf
            scaled_columns = columns

        logger.info("保存标准化后的数据...")
        pyu_output_paths = {}
        for party in parties:
            pyu_device = devices.get(party)
            pyu_output_paths[pyu_device] = output_data[party]

        scaled_vdf.to_csv(pyu_output_paths, index=False)
        logger.info(f"输出文件: {output_data}")

        result = {
            "output_paths": output_data,
            "scaled_columns": scaled_columns,
            "with_mean": with_mean,
            "with_std": with_std,
            "parties": parties,
        }

        logger.info("StandardScaler任务执行成功")
        return result

    except ValueError as e:
        logger.error(f"StandardScaler任务配置错误: {e}")
        raise
    except Exception as e:
        logger.error(f"StandardScaler任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"StandardScaler任务执行失败: {str(e)}") from e
