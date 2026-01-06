"""
FillNA缺失值填充任务

使用指定策略填充缺失值。
"""

from typing import Dict
import os

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU

from utils.log import logger
from ....task_dispatcher import TaskDispatcher


@TaskDispatcher.register_task("fillna")
def execute_fillna(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行FillNA缺失值填充任务

    使用指定策略填充缺失值：均值、中位数、众数或常数。

    Args:
        devices: 设备字典
        task_config: 任务配置，包含:
            - input_data: Dict[str, str] - 输入数据路径
            - output_data: Dict[str, str] - 输出数据路径
            - columns: List[str] - 需要填充的列名列表
            - strategy: str - 填充策略：'mean'/'median'/'mode'/'constant'
            - fill_value: Optional[Any] - 当strategy='constant'时的填充值

    Returns:
        Dict: 填充结果
    """
    logger.info("开始执行FillNA缺失值填充任务")

    try:
        input_data = task_config["input_data"]
        output_data = task_config["output_data"]
        columns = task_config["columns"]
        strategy = task_config.get("strategy", "mean")
        fill_value = task_config.get("fill_value")

        parties = list(input_data.keys())
        logger.info(f"FillNA配置: parties={parties}, columns={columns}, strategy={strategy}")

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

        # 缺失值填充
        def fillna(data, columns, strategy, fill_value):
            """在PYU上执行缺失值填充"""
            import pandas as pd

            df = data.copy()
            for col in columns:
                if col in df.columns:
                    if strategy == "mean":
                        df[col].fillna(df[col].mean(), inplace=True)
                    elif strategy == "median":
                        df[col].fillna(df[col].median(), inplace=True)
                    elif strategy == "mode":
                        mode_val = df[col].mode()
                        if len(mode_val) > 0:
                            df[col].fillna(mode_val[0], inplace=True)
                    elif strategy == "constant":
                        df[col].fillna(fill_value, inplace=True)
                    else:
                        raise ValueError(f"不支持的填充策略: {strategy}")
            return df

        # 对每个参与方的数据进行填充
        for party in parties:
            pyu = devices[party]
            party_columns = [col for col in columns if col in vdf.partitions[pyu].columns]
            if party_columns:
                vdf.partitions[pyu] = pyu(fillna)(
                    vdf.partitions[pyu], party_columns, strategy, fill_value
                )

        # 保存结果
        pyu_output_paths = {devices[party]: output_data[party] for party in parties}
        vdf.to_csv(pyu_output_paths, index=False)

        result = {
            "output_paths": output_data,
            "filled_columns": columns,
            "strategy": strategy,
            "parties": parties,
        }

        logger.info("FillNA任务执行成功")
        return result

    except Exception as e:
        logger.error(f"FillNA任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"FillNA任务执行失败: {str(e)}") from e
