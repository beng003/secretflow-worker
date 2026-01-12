"""
QuantileBinning等频分箱任务

将连续型特征按分位数进行分箱。
"""

from typing import Dict
import os

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU

from utils.log import logger
from ....task_dispatcher import TaskDispatcher


@TaskDispatcher.register_task("quantile_binning")
def execute_quantile_binning(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行QuantileBinning等频分箱任务

    将连续型特征按分位数进行分箱，每个箱中的样本数量大致相等。

    Args:
        devices: 设备字典
        task_config: 任务配置，包含:
            - input_data: Dict[str, str] - 输入数据路径
            - output_data: Dict[str, str] - 输出数据路径
            - columns: List[str] - 需要分箱的列名列表
            - n_bins: int - 分箱数量，默认5

    Returns:
        Dict: 分箱结果
    """
    logger.info("开始执行QuantileBinning等频分箱任务")

    try:
        input_data = task_config["input_data"]
        output_data = task_config["output_data"]
        columns = task_config["columns"]
        n_bins = task_config.get("n_bins", 5)

        parties = list(input_data.keys())
        logger.info(f"QuantileBinning配置: parties={parties}, columns={columns}, n_bins={n_bins}")

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

        # 等频分箱
        def quantile_binning(data, columns, n_bins):
            """在PYU上执行等频分箱"""
            import pandas as pd

            df = data.copy()
            for col in columns:
                if col in df.columns:
                    df[col] = pd.qcut(df[col], q=n_bins, labels=False, duplicates='drop')
            return df

        # 对每个参与方的数据进行分箱
        for party in parties:
            pyu = devices[party]
            party_columns = [col for col in columns if col in vdf.partitions[pyu].columns]
            if party_columns:
                vdf.partitions[pyu] = pyu(quantile_binning)(
                    vdf.partitions[pyu], party_columns, n_bins
                )

        # 保存结果
        pyu_output_paths = {devices[party]: output_data[party] for party in parties}
        vdf.to_csv(pyu_output_paths, index=False)

        result = {
            "output_paths": output_data,
            "binned_columns": columns,
            "n_bins": n_bins,
            "binning_type": "quantile",
            "parties": parties,
        }

        logger.info("QuantileBinning任务执行成功")
        return result

    except Exception as e:
        logger.error("QuantileBinning任务执行失败", exc_info=True)
        raise RuntimeError(f"QuantileBinning任务执行失败: {str(e)}") from e
