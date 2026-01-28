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
        logger.info(f"[调试] 广播结果模式: {broadcast_result}")
        logger.info(f"[调试] 预检查输入: {precheck_input}")
        logger.info(f"[调试] 排序结果: {sort_result}")

        # 验证所有参与方的PYU设备存在
        logger.info(f"[调试] 开始验证参与方设备，总数: {len(keys)}")
        for party in keys.keys():
            pyu_device = devices.get(party)
            if pyu_device is None:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")
            logger.info(f"[调试] 参与方 {party} 的 PYU 设备: {pyu_device}, 类型: {type(pyu_device)}")

        # 构建PSI参数 - 使用PYU设备对象作为键
        psi_keys = {}
        psi_input_paths = {}
        psi_output_paths = {}

        logger.info(f"[调试] 输入文件路径映射: {input_paths}")
        logger.info(f"[调试] 输出文件路径映射: {output_paths}")
        
        # 检查输入文件是否存在，对于不存在的远程占位符文件创建空文件
        for party, path in input_paths.items():
            exists = os.path.exists(path)
            logger.info(f"[调试] 输入文件 {party}: {path}, 存在: {exists}")
            if exists:
                file_size = os.path.getsize(path)
                logger.info(f"[调试] 文件大小: {file_size} bytes")
            else:
                # 如果是远程占位符文件（/tmp/remote_party_*.dat），创建空占位符
                if path.startswith("/tmp/remote_party_") and path.endswith(".dat"):
                    try:
                        # 创建空文件作为占位符（SecretFlow 可能会检查文件存在性）
                        with open(path, 'w') as f:
                            f.write("")
                        logger.info(f"[调试] 创建远程占位符文件: {path}")
                    except Exception as e:
                        logger.warning(f"[调试] 创建占位符文件失败: {path}, 错误: {e}")

        # 确保输出路径为绝对路径，避免SPU底层创建目录失败 (Invalid argument [])
        for party, path in output_paths.items():
            if not os.path.isabs(path):
                abs_path = os.path.abspath(path)
                logger.info(f"[调试] 将输出路径转换为绝对路径: {path} -> {abs_path}")
                output_paths[party] = abs_path
                path = abs_path

            output_dir = os.path.dirname(path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"创建输出目录: {output_dir}")
        
        # 使用更新后的绝对路径重新构建 psi_*_paths（使用PYU设备对象作为键）
        for party in keys.keys():
            pyu_device = devices.get(party)
            psi_keys[pyu_device] = keys[party]
            psi_input_paths[pyu_device] = input_paths[party]
            psi_output_paths[pyu_device] = output_paths[party]  # 使用更新后的绝对路径
                
        from secretflow import wait

        logger.info(f"[调试] SPU 设备信息: {spu}, 类型: {type(spu)}")
        logger.info(f"[调试] 准备调用 spu.psi_csv，参数如下:")
        logger.info(f"[调试]   - key: {psi_keys}")
        logger.info(f"[调试]   - input_path: {psi_input_paths}")
        logger.info(f"[调试]   - output_path: {psi_output_paths}")
        logger.info(f"[调试]   - receiver: {receiver}")
        logger.info(f"[调试]   - protocol: {protocol}")
        logger.info(f"[调试]   - broadcast_result: {broadcast_result}")
        
        logger.info("[调试] 开始调用 spu.psi_csv 执行 PSI...")
        try:
            reports = wait(spu.psi_csv(
            key=psi_keys,
            input_path=psi_input_paths,
            output_path=psi_output_paths,
            receiver=receiver,
            protocol=protocol,
            precheck_input=precheck_input,
            sort=sort_result,
            broadcast_result=broadcast_result,
        ))
            logger.info(f"[调试] spu.psi_csv 调用成功，wait 完成")
        except Exception as psi_error:
            logger.error(f"[调试] spu.psi_csv 调用失败，异常类型: {type(psi_error).__name__}")
            logger.error(f"[调试] 异常信息: {str(psi_error)}")
            raise

        logger.info(f"[调试] PSI执行完成，报告类型: {type(reports)}")
        logger.info(f"[调试] PSI执行报告: {reports}")

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
