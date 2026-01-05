"""
VIF方差膨胀因子任务

使用SecretFlow的SSVertVIF计算方差膨胀因子，用于检测多重共线性。
"""

from typing import Dict
import os
import json

import secretflow as sf
from secretflow.data.vertical import VDataFrame
from secretflow.device import PYU, SPU
from secretflow.stats import SSVertVIF

from utils.log import logger
from ...task_dispatcher import TaskDispatcher


@TaskDispatcher.register_task("vif")
def execute_vif(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行VIF方差膨胀因子计算任务

    计算垂直分区数据的方差膨胀因子，用于检测特征之间的多重共线性。
    VIF值越大，说明该特征与其他特征的共线性越强。
    通常VIF > 10表示存在严重的多重共线性问题。

    Args:
        devices: 设备字典，必须包含SPU设备
        task_config: 任务配置，包含:
            - input_data: Dict[str, str] - 输入数据路径字典
            - columns: List[str] - 需要计算VIF的列名列表
            - output_report: str - VIF结果输出路径（JSON格式）

    Returns:
        Dict: VIF计算结果
    """
    logger.info("开始执行VIF方差膨胀因子计算任务")

    try:
        input_data = task_config["input_data"]
        columns = task_config["columns"]
        output_report = task_config["output_report"]

        parties = list(input_data.keys())
        logger.info(f"VIF配置: parties={parties}, columns={columns}")

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

        # 选择需要计算VIF的列
        vdf_selected = vdf[columns]

        # 创建VIF计算器
        logger.info("计算VIF方差膨胀因子...")
        vif_calculator = SSVertVIF(spu_device)
        
        # 计算VIF值
        vif_values = vif_calculator.vif(vdf_selected)

        # 将VIF结果转换为字典格式
        vif_dict = {}
        for i, col in enumerate(columns):
            value = vif_values[i]
            # 处理特殊值
            if hasattr(value, 'item'):
                value = value.item()
            if str(value) == 'nan' or value != value:
                value = None
            else:
                value = float(value)
            vif_dict[col] = value

        # 添加多重共线性诊断
        diagnosis = {}
        for col, vif_value in vif_dict.items():
            if vif_value is None:
                diagnosis[col] = "无法计算"
            elif vif_value > 10:
                diagnosis[col] = "严重共线性"
            elif vif_value > 5:
                diagnosis[col] = "中度共线性"
            else:
                diagnosis[col] = "无共线性问题"

        # 保存VIF结果
        result_data = {
            "vif_values": vif_dict,
            "diagnosis": diagnosis,
            "columns": columns,
            "parties": parties,
        }

        logger.info(f"保存VIF结果到: {output_report}")
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        result = {
            "output_report": output_report,
            "vif_values": vif_dict,
            "diagnosis": diagnosis,
            "num_columns": len(columns),
            "columns": columns,
            "parties": parties,
        }

        logger.info("VIF方差膨胀因子计算任务执行成功")
        return result

    except Exception as e:
        logger.error(f"VIF方差膨胀因子计算任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"VIF方差膨胀因子计算任务执行失败: {str(e)}") from e
