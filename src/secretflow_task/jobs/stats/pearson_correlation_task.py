"""
PearsonCorrelation相关性分析任务

使用SecretFlow的SSVertPearsonR计算Pearson相关系数。
"""

from typing import Dict
import os
import json

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU, SPU
from secretflow.stats import SSVertPearsonR

from utils.log import logger
from ...task_dispatcher import TaskDispatcher


@TaskDispatcher.register_task("pearson_correlation")
def execute_pearson_correlation(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行Pearson相关性分析任务

    计算垂直分区数据的Pearson相关系数矩阵。

    Args:
        devices: 设备字典，必须包含SPU设备
        task_config: 任务配置，包含:
            - input_data: Dict[str, str] - 输入数据路径字典
            - columns: List[str] - 需要计算相关性的列名列表
            - output_report: str - 相关性矩阵输出路径（JSON格式）

    Returns:
        Dict: 相关性分析结果
    """
    logger.info("开始执行Pearson相关性分析任务")

    try:
        input_data = task_config["input_data"]
        columns = task_config["columns"]
        output_report = task_config["output_report"]

        parties = list(input_data.keys())
        logger.info(f"Pearson相关性配置: parties={parties}, columns={columns}")

        # 验证设备
        for party in parties:
            if party not in devices:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")

        spu_device = devices.get('spu')
        if spu_device is None:
            raise ValueError("devices中缺少'spu'设备")

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

        # 选择需要计算相关性的列
        vdf_selected = vdf[columns]

        # 创建Pearson相关性分析器
        logger.info("计算Pearson相关系数...")
        pearson = SSVertPearsonR(spu_device)
        
        # 计算相关系数矩阵
        corr_matrix = pearson.pearsonr(vdf_selected)

        # 将相关系数矩阵转换为字典格式
        corr_dict = {}
        for i, col1 in enumerate(columns):
            corr_dict[col1] = {}
            for j, col2 in enumerate(columns):
                value = corr_matrix[i][j]
                # 处理特殊值
                if hasattr(value, 'item'):
                    value = value.item()
                if str(value) == 'nan' or value != value:
                    value = None
                else:
                    value = float(value)
                corr_dict[col1][col2] = value

        # 保存相关性矩阵
        logger.info(f"保存相关性矩阵到: {output_report}")
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(corr_dict, f, indent=2, ensure_ascii=False)

        result = {
            "output_report": output_report,
            "num_columns": len(columns),
            "columns": columns,
            "parties": parties,
        }

        logger.info("Pearson相关性分析任务执行成功")
        return result

    except Exception as e:
        logger.error(f"Pearson相关性分析任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"Pearson相关性分析任务执行失败: {str(e)}") from e
