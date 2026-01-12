"""
TableStatistics表统计任务

使用SecretFlow的table_statistics函数计算表的统计信息。
"""

from typing import Dict
import os
import json

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU
from secretflow.stats import table_statistics

from utils.log import logger
from ...task_dispatcher import TaskDispatcher


@TaskDispatcher.register_task("table_statistics")
def execute_table_statistics(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行表统计分析任务

    计算表的统计信息，包括每列的数据类型、计数、缺失值、最小值、最大值、
    均值、方差、标准差、偏度、峰度、分位数等。

    Args:
        devices: 设备字典
        task_config: 任务配置，包含:
            - input_data: Dict[str, str] - 输入数据路径字典
            - columns: Optional[List[str]] - 需要统计的列名列表，不指定则统计所有列
            - output_report: str - 统计报告输出路径（JSON格式）

    Returns:
        Dict: 统计结果
    """
    logger.info("开始执行表统计分析任务")

    try:
        input_data = task_config["input_data"]
        output_report = task_config["output_report"]
        columns = task_config.get("columns")

        parties = list(input_data.keys())
        logger.info(f"表统计配置: parties={parties}, columns={columns}")

        # 验证设备
        for party in parties:
            if party not in devices:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")

        # 验证输入文件
        for party, path in input_data.items():
            if not os.path.exists(path):
                raise ValueError(f"输入文件不存在: {path}")

        # 创建输出目录
        output_dir = os.path.dirname(output_report)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # 读取垂直分区数据
        logger.info("读取垂直分区数据...")
        pyu_input_paths = {devices[party]: input_data[party] for party in parties}
        vdf: VDataFrame = sf.data.vertical.read_csv(pyu_input_paths)

        # 如果指定了列，则只统计这些列
        if columns:
            vdf = vdf[columns]

        # 计算表统计信息
        logger.info("计算表统计信息...")
        stats_df = table_statistics(vdf)

        # 将统计结果转换为字典格式
        stats_dict = {}
        for col in stats_df.index:
            stats_dict[col] = {}
            for stat_name in stats_df.columns:
                value = stats_df.loc[col, stat_name]
                # 处理NaN和特殊值
                if hasattr(value, 'item'):
                    value = value.item()
                # 转换为JSON可序列化的类型
                if str(value) == 'nan' or value != value:  # 检查NaN
                    value = None
                elif hasattr(value, '__float__'):
                    value = float(value)
                elif hasattr(value, '__int__'):
                    value = int(value)
                else:
                    value = str(value)
                stats_dict[col][stat_name] = value

        # 保存统计报告
        logger.info(f"保存统计报告到: {output_report}")
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(stats_dict, f, indent=2, ensure_ascii=False)

        result = {
            "output_report": output_report,
            "num_columns": len(stats_dict),
            "columns": list(stats_dict.keys()),
            "parties": parties,
        }

        logger.info("表统计分析任务执行成功")
        return result

    except Exception as e:
        logger.error("表统计分析任务执行失败", exc_info=True)
        raise RuntimeError(f"表统计分析任务执行失败: {str(e)}") from e
