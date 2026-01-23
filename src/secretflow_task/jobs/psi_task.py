"""
PSI (Private Set Intersection) 隐私集合求交任务模块

提供基于SecretFlow的隐私集合求交功能，支持单列和多列PSI。
"""

import os
from typing import Dict, Any

from utils.log import logger
from secretflow_task.task_dispatcher import TaskDispatcher
from secretflow.device import SPU, PYU
from secretflow import reveal


def _validate_psi_config(task_config: Dict[str, Any]) -> None:
    """
    验证PSI任务配置参数

    Args:
        task_config: 任务配置字典

    Raises:
        ValueError: 配置参数不合法时抛出异常
    """
    required_fields = ["keys", "input_paths", "output_paths"]

    for field in required_fields:
        if field not in task_config:
            raise ValueError(f"PSI任务配置缺少必需字段: {field}")

    keys = task_config["keys"]
    input_paths = task_config["input_paths"]
    output_paths = task_config["output_paths"]
    receiver = task_config.get("receiver")

    if not isinstance(keys, dict):
        raise ValueError(f"keys必须是字典类型，当前类型: {type(keys)}")

    if not isinstance(input_paths, dict):
        raise ValueError(f"input_paths必须是字典类型，当前类型: {type(input_paths)}")

    if not isinstance(output_paths, dict):
        raise ValueError(f"output_paths必须是字典类型，当前类型: {type(output_paths)}")

    if not keys:
        raise ValueError("keys不能为空")

    if not input_paths:
        raise ValueError("input_paths不能为空")

    if not output_paths:
        raise ValueError("output_paths不能为空")

    parties = set(keys.keys())
    if parties != set(input_paths.keys()):
        raise ValueError(
            f"keys和input_paths的参与方不一致: {parties} vs {set(input_paths.keys())}"
        )

    if parties != set(output_paths.keys()):
        raise ValueError(
            f"keys和output_paths的参与方不一致: {parties} vs {set(output_paths.keys())}"
        )

    if receiver and receiver not in parties:
        raise ValueError(f"receiver '{receiver}' 不在参与方列表中: {parties}")

    for party, key_list in keys.items():
        if not isinstance(key_list, list):
            raise ValueError(
                f"参与方 '{party}' 的keys必须是列表类型，当前类型: {type(key_list)}"
            )
        if not key_list:
            raise ValueError(f"参与方 '{party}' 的keys不能为空")

    for party, path in input_paths.items():
        if not isinstance(path, str):
            raise ValueError(f"参与方 '{party}' 的input_path必须是字符串类型")
        if not path:
            raise ValueError(f"参与方 '{party}' 的input_path不能为空")


def _count_csv_lines(file_path: str) -> int:
    """
    统计CSV文件的行数（不包含表头）

    Args:
        file_path: CSV文件路径

    Returns:
        int: 数据行数（不包含表头）
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return 0

        with open(file_path, "r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
            return max(0, line_count - 1)
    except Exception as e:
        logger.error("统计文件行数失败: %s, 错误: %s", file_path, e)
        return 0


@TaskDispatcher.register_task("psi")
def execute_psi(
    devices: Dict[str, SPU | PYU], task_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    执行PSI隐私集合求交任务

    使用SecretFlow的SPU设备执行隐私集合求交，支持单列和多列PSI。

    Args:
        devices: 设备字典，必须包含'spu'设备和各参与方的PYU设备
        task_config: 任务配置字典，包含以下字段：
            - keys: Dict[str, List[str]] - 各参与方的求交列名
            - input_paths: Dict[str, str] - 各参与方的输入文件路径
            - output_paths: Dict[str, str] - 各参与方的输出文件路径
            - receiver: str - 接收结果的参与方名称
            - protocol: str (可选) - PSI协议，默认'KKRT_PSI_2PC'
            - precheck_input: bool (可选) - 是否预检查输入，默认False
            - sort: bool (可选) - 是否排序结果，默认False
            - broadcast_result: bool (可选) - 是否广播结果给所有方，默认False

    Returns:
        Dict[str, Any]: 执行结果，包含：
            - intersection_count: int - 交集数量
            - output_paths: Dict[str, str] - 输出文件路径
            - psi_protocol: str - 使用的PSI协议
            - reports: Any - PSI执行报告

    Raises:
        ValueError: 配置参数不合法
        RuntimeError: PSI执行失败

    Example:
        >>> task_config = {
        ...     "keys": {"alice": ["uid"], "bob": ["uid"]},
        ...     "input_paths": {"alice": "/data/alice.csv", "bob": "/data/bob.csv"},
        ...     "output_paths": {"alice": "/data/alice_psi.csv", "bob": "/data/bob_psi.csv"},
        ...     "receiver": "alice",
        ...     "protocol": "KKRT_PSI_2PC"
        ... }
        >>> result = execute_psi(devices, task_config)
    """
    logger.info("开始执行PSI任务")

    try:
        _validate_psi_config(task_config)

        spu = devices.get("spu")
        if spu is None:
            raise ValueError("devices中缺少'spu'设备")

        keys = task_config["keys"]
        input_paths = task_config["input_paths"]
        output_paths = task_config["output_paths"]
        
        # 处理可选的 receiver
        receiver = task_config.get("receiver")
        broadcast_result = task_config.get("broadcast_result", False)
        
        if not receiver:
            # 如果未指定 receiver，默认为广播模式
            broadcast_result = True
            # 选择第一个参与方作为名义上的 receiver (SPU 接口可能需要)
            receiver = list(keys.keys())[0]
            logger.info(f"未指定receiver，启用广播模式，主接收方: {receiver}")
            
        protocol = task_config.get("protocol", "KKRT_PSI_2PC")
        precheck_input = task_config.get("precheck_input", False)
        sort_result = task_config.get("sort", False)

        logger.info(
            f"PSI配置: protocol={protocol}, receiver={receiver}, parties={list(keys.keys())}"
        )

        # 验证所有参与方的PYU设备存在
        for party in keys.keys():
            pyu_device = devices.get(party)
            if pyu_device is None:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")

        # 构建PSI参数 - 使用PYU设备对象作为键
        psi_keys = {}
        psi_input_paths = {}
        psi_output_paths = {}

        for party in keys.keys():
            pyu_device = devices.get(party)
            # 使用PYU设备对象作为键
            psi_keys[pyu_device] = keys[party]
            psi_input_paths[pyu_device] = input_paths[party]
            psi_output_paths[pyu_device] = output_paths[party]

        logger.info(f"输入文件: {input_paths}")
        logger.info(f"输出文件: {output_paths}")

        for party, path in output_paths.items():
            output_dir = os.path.dirname(path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"创建输出目录: {output_dir}")

        logger.info("调用spu.psi_csv执行PSI...")
        reports = spu.psi_csv(
            key=psi_keys,
            input_path=psi_input_paths,
            output_path=psi_output_paths,
            receiver=receiver,
            protocol=protocol,
            precheck_input=precheck_input,
            sort=sort_result,
            broadcast_result=broadcast_result,
        )

        logger.info(f"PSI执行完成，报告: {reports}")

        intersection_count = 0
        receiver_output_path = output_paths.get(receiver)
        if receiver_output_path:
            # 直接在接收方设备上执行检查，避免非接收方节点的本地检查误报
            # _count_csv_lines 内部会检查文件是否存在
            intersection_count = reveal(
                devices[receiver](_count_csv_lines)(receiver_output_path)
            )
            logger.info(f"交集数量: {intersection_count}")

        result = {
            "intersection_count": intersection_count,
            "output_paths": output_paths,
            "psi_protocol": protocol,
            "reports": str(reports) if reports else None,
            "receiver": receiver,
            "parties": list(keys.keys()),
        }

        logger.info("PSI任务执行成功")
        return result

    except ValueError as e:
        logger.error("PSI任务配置错误: %s", e)
        raise
    except Exception as e:
        logger.error("PSI任务执行失败", exc_info=True)
        raise RuntimeError(f"PSI任务执行失败: {str(e)}") from e
