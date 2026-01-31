"""
LabelEncoder标签编码任务

使用SecretFlow官方LabelEncoder进行安全的标签编码。
各参与方的数据在本地编码，结果不会泄露给其他方。
"""

from typing import Dict
import os

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow_fl.preprocessing.encoder_fl import LabelEncoder
from secretflow.device import PYU

from utils.log import logger
from ....task_dispatcher import TaskDispatcher


def _ensure_output_dir(path):
    """确保输出目录存在（模块级函数，在PYU上执行）"""
    import os
    output_dir = os.path.dirname(path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)


def _get_columns_exclude(path, exclude_cols):
    """获取CSV列名并排除指定列（模块级函数，在PYU上执行）"""
    import pandas as pd
    df = pd.read_csv(path, nrows=0)
    return [c for c in df.columns if c not in exclude_cols]


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

    # 注意：不再要求 input_data 和 output_data 的参与方完全一致
    # 这允许从联邦数据集（如 PSI 结果）读取，但写入到单方输出


@TaskDispatcher.register_task("label_encoder")
def execute_label_encoder(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行LabelEncoder标签编码任务（使用SecretFlow官方LabelEncoder）

    将类别型特征转换为数值型标签（0, 1, 2, ...）。
    使用SecretFlow的LabelEncoder确保数据安全，各方数据不会泄露。

    Args:
        devices: 设备字典
        task_config: 任务配置，包含:
            - input_data: Dict[str, str] - 输入数据路径
            - output_data: Dict[str, str] - 输出数据路径
            - columns: List[str] - 需要编码的列名列表
            - drop_keys: List[str] - 可选，读取时要排除的列（如join key）

    Returns:
        Dict: 编码结果
    """
    logger.info("开始执行LabelEncoder标签编码任务（SecretFlow官方实现）")

    try:
        _validate_label_encoder_config(task_config)

        input_data = task_config["input_data"]
        output_data = task_config["output_data"]
        columns = task_config["columns"]
        drop_keys = task_config.get("drop_keys", None)

        parties = list(input_data.keys())
        logger.info(f"LabelEncoder配置: parties={parties}, columns={columns}, drop_keys={drop_keys}")

        # 验证设备
        for party in parties:
            if party not in devices:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")

        # 确保输出目录存在
        for party, path in output_data.items():
            if party in devices:
                devices[party](_ensure_output_dir)(path)

        # 构建输入路径映射
        pyu_input_paths = {devices[party]: input_data[party] for party in parties}

        # 读取垂直分区数据
        logger.info("读取垂直分区数据...")
        if drop_keys:
            logger.info(f"排除重复列: {drop_keys}")
            # 为每个参与方构建 usecols（排除 drop_keys）
            pyu_usecols = {}
            for party in parties:
                pyu = devices[party]
                party_cols_pyu = pyu(_get_columns_exclude)(input_data[party], drop_keys)
                party_cols = sf.reveal(party_cols_pyu)
                pyu_usecols[pyu] = party_cols
                logger.info(f"参与方 {party} 读取列: {party_cols}")
            vdf: VDataFrame = sf.data.vertical.read_csv(pyu_input_paths, usecols=pyu_usecols)
        else:
            vdf: VDataFrame = sf.data.vertical.read_csv(pyu_input_paths)

        # 使用SecretFlow官方LabelEncoder进行编码
        logger.info("使用SecretFlow LabelEncoder进行安全编码...")
        encoder = LabelEncoder()
        
        encoded_columns = []
        for col in columns:
            if col in vdf.columns:
                logger.info(f"编码列: {col}")
                vdf[col] = encoder.fit_transform(vdf[col])
                encoded_columns.append(col)
            else:
                logger.warning(f"列 '{col}' 不存在于数据中，跳过")

        # 保存编码后的数据（各方数据保存在各自本地，不泄露）
        logger.info("保存编码结果到各参与方...")
        pyu_output_paths = {devices[party]: output_data[party] for party in parties}
        vdf.to_csv(pyu_output_paths, index=False)

        result = {
            "output_paths": output_data,
            "encoded_columns": encoded_columns,
            "parties": parties,
        }

        logger.info(f"LabelEncoder任务执行成功，编码列: {encoded_columns}")
        return result

    except ValueError as e:
        logger.error("LabelEncoder任务配置错误: %s", e)
        raise
    except Exception as e:
        logger.error("LabelEncoder任务执行失败", exc_info=True)
        raise RuntimeError(f"LabelEncoder任务执行失败: {str(e)}") from e
