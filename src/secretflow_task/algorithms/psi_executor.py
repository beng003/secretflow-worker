"""PSI算法执行器

实现隐私集合求交（Private Set Intersection）算法的执行逻辑。
"""

import time
from typing import Dict, Any
from datetime import datetime
from .base_executor import BaseTaskExecutor
from utils.log import logger
from utils.exceptions import ParameterValidationError, AlgorithmError
from utils.status_notifier import _publish_status


class PSIExecutor(BaseTaskExecutor):
    """PSI算法执行器

    支持SecretFlow的PSI计算，包括：
    - 2方和3方PSI
    - 单列和多列主键
    - 多种PSI协议（KKRT、ECDH等）
    """

    def validate_params(self) -> bool:
        """验证PSI任务参数

        必需参数：
        - task_type: 'psi'
        - keys: 主键列名（字符串或列表）
        - input_paths: 输入文件路径字典 {party: path}
        - output_paths: 输出文件路径字典 {party: path}
        - receiver_party: 接收方参与方名称

        可选参数：
        - protocol: PSI协议，默认'KKRT_PSI_2PC'
        - precheck_input: 是否预检查输入，默认False
        - sort: 是否排序输出，默认False
        - broadcast_result: 是否广播结果到所有方，默认False

        Returns:
            bool: 参数验证是否通过

        Raises:
            ParameterValidationError: 参数验证失败
        """
        logger.info(f"开始验证PSI任务参数，任务ID: {self.task_request_id}")

        try:
            # 调用基类验证
            if not super().validate_params():
                raise ParameterValidationError("基础参数验证失败")

            # 验证任务类型
            if self.task_config.get("task_type") != "psi":
                raise ParameterValidationError(
                    f"任务类型错误: 期望'psi'，实际'{self.task_config.get('task_type')}'"
                )

            # 验证必需参数
            required_params = ["keys", "input_paths", "output_paths", "receiver_party"]
            for param in required_params:
                if param not in self.task_config:
                    raise ParameterValidationError(f"缺少必需参数: {param}")

            # 验证keys参数
            keys = self.task_config["keys"]
            if not isinstance(keys, (str, list, dict)):
                raise ParameterValidationError(
                    f"keys参数类型错误: 期望str/list/dict，实际{type(keys).__name__}"
                )

            if isinstance(keys, list) and len(keys) == 0:
                raise ParameterValidationError("keys列表不能为空")

            if isinstance(keys, str) and not keys.strip():
                raise ParameterValidationError("keys字符串不能为空")

            # 验证input_paths参数
            input_paths = self.task_config["input_paths"]
            if not isinstance(input_paths, dict) or len(input_paths) == 0:
                raise ParameterValidationError("input_paths必须是非空字典")

            # 验证参与方数量（支持2方或3方PSI）
            num_parties = len(input_paths)
            if num_parties < 2 or num_parties > 3:
                raise ParameterValidationError(
                    f"参与方数量必须是2或3，当前为{num_parties}"
                )

            # 验证output_paths参数
            output_paths = self.task_config["output_paths"]
            if not isinstance(output_paths, dict) or len(output_paths) == 0:
                raise ParameterValidationError("output_paths必须是非空字典")

            # 验证输入输出路径的参与方一致性
            input_parties = set(input_paths.keys())
            output_parties = set(output_paths.keys())
            if input_parties != output_parties:
                raise ParameterValidationError(
                    f"输入输出参与方不一致: 输入{input_parties}, 输出{output_parties}"
                )

            # 验证receiver_party
            receiver_party = self.task_config["receiver_party"]
            if not isinstance(receiver_party, str) or not receiver_party.strip():
                raise ParameterValidationError("receiver_party必须是非空字符串")

            if receiver_party not in input_parties:
                raise ParameterValidationError(
                    f"receiver_party '{receiver_party}' 不在参与方列表中: {input_parties}"
                )

            # 验证协议参数（可选）
            protocol = self.task_config.get("protocol", "KKRT_PSI_2PC")
            valid_protocols = [
                "KKRT_PSI_2PC",
                "ECDH_PSI_2PC",
                "BC22_PSI_2PC",
                "ECDH_PSI_3PC",
            ]

            if protocol not in valid_protocols:
                logger.warning(
                    f"协议 '{protocol}' 可能不被支持，有效协议: {valid_protocols}"
                )

            # 验证3方PSI必须使用3PC协议
            if num_parties == 3 and not protocol.endswith("3PC"):
                raise ParameterValidationError(
                    f"3方PSI必须使用3PC协议，当前协议: {protocol}"
                )

            # 验证2方PSI不能使用3PC协议
            if num_parties == 2 and protocol.endswith("3PC"):
                raise ParameterValidationError(
                    f"2方PSI不能使用3PC协议，当前协议: {protocol}"
                )

            logger.info(
                f"PSI任务参数验证通过，参与方: {list(input_parties)}, 协议: {protocol}"
            )
            self._validated = True
            return True

        except ParameterValidationError:
            raise
        except Exception as e:
            error_msg = f"PSI参数验证异常: {str(e)}"
            logger.error(error_msg)
            raise ParameterValidationError(error_msg) from e

    def execute(self) -> Dict[str, Any]:
        """执行PSI计算

        完整的PSI计算流程：
        1. 参数验证
        2. 准备数据和设备
        3. 执行PSI计算
        4. 处理计算结果
        5. 返回执行报告

        Returns:
            Dict[str, Any]: PSI计算结果，包含：
                - intersection_count: 交集数量
                - execution_time: 执行时间（秒）
                - output_paths: 输出文件路径
                - protocol: 使用的协议
                - parties: 参与方列表
                - reports: SecretFlow PSI报告

        Raises:
            AlgorithmError: PSI计算执行失败
        """
        start_time = time.time()

        try:
            # 发送任务开始状态
            _publish_status(
                self.task_request_id,
                "RUNNING",
                {
                    "stage": "psi_started",
                    "task_type": "psi",
                    "started_at": datetime.now().isoformat(),
                    "parties": list(self.task_config["input_paths"].keys()),
                },
            )

            logger.info(f"开始执行PSI计算，任务ID: {self.task_request_id}")

            # 1. 验证参数
            if not self._validated:
                self.validate_params()

            # 发送进度：准备数据
            self._publish_progress(0.1, "准备PSI数据")

            # 2. 准备数据
            psi_data = self._prepare_psi_data()

            # 发送进度：执行计算
            self._publish_progress(0.3, "执行PSI计算")

            # 3. 执行PSI计算
            psi_result = self._execute_psi_computation(psi_data)

            # 发送进度：处理结果
            self._publish_progress(0.8, "处理PSI结果")

            # 4. 处理结果
            final_result = self._process_psi_results(psi_result, start_time)

            # 发送进度：完成
            self._publish_progress(1.0, "PSI计算完成")

            # 发送任务成功状态
            _publish_status(
                self.task_request_id,
                "SUCCESS",
                {
                    "stage": "psi_completed",
                    "result": final_result,
                    "completed_at": datetime.now().isoformat(),
                },
            )

            logger.info(
                f"PSI计算完成，任务ID: {self.task_request_id}, "
                f"交集数量: {final_result.get('intersection_count', 'N/A')}, "
                f"耗时: {final_result['execution_time']:.2f}秒"
            )

            return final_result

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"PSI计算失败: {str(e)}"

            logger.error(
                f"{error_msg}, 任务ID: {self.task_request_id}, 耗时: {execution_time:.2f}秒",
                exc_info=True,
            )

            # 发送任务失败状态
            _publish_status(
                self.task_request_id,
                "FAILURE",
                {
                    "stage": "psi_failed",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "execution_time": execution_time,
                    "failed_at": datetime.now().isoformat(),
                },
            )

            raise AlgorithmError(error_msg) from e

    def _prepare_psi_data(self) -> Dict[str, Any]:
        """准备PSI计算数据

        准备PSI计算所需的所有参数，包括：
        - PYU设备映射
        - 输入输出路径映射
        - 主键配置
        - 协议和其他配置

        Returns:
            Dict[str, Any]: 准备好的PSI数据配置

        Raises:
            AlgorithmError: 数据准备失败
        """
        try:
            logger.info("开始准备PSI计算数据")

            # 获取设备管理器
            from secretflow_task.device_manager import DeviceManager

            device_manager = DeviceManager.get_instance()
            pyu_devices = device_manager.get_pyu_devices()

            if not pyu_devices:
                raise AlgorithmError("未找到PYU设备，请确保设备已正确初始化")

            # 提取配置参数
            input_paths = self.task_config["input_paths"]
            output_paths = self.task_config["output_paths"]
            keys = self.task_config["keys"]
            receiver_party = self.task_config["receiver_party"]

            # 构建PYU设备到路径的映射
            pyu_input_paths = {}
            pyu_output_paths = {}
            pyu_keys = {}

            for party_name in input_paths.keys():
                if party_name not in pyu_devices:
                    raise AlgorithmError(f"参与方 '{party_name}' 的PYU设备未初始化")

                pyu_device = pyu_devices[party_name]
                pyu_input_paths[pyu_device] = input_paths[party_name]
                pyu_output_paths[pyu_device] = output_paths[party_name]

                # 处理keys配置
                if isinstance(keys, dict):
                    # keys是字典，每个参与方有自己的key
                    if party_name not in keys:
                        raise AlgorithmError(f"参与方 '{party_name}' 的keys配置缺失")
                    pyu_keys[pyu_device] = keys[party_name]

            # 如果keys不是字典，说明所有参与方使用相同的key
            if not isinstance(keys, dict):
                final_keys = keys
            else:
                final_keys = pyu_keys

            # 获取其他配置参数
            protocol = self.task_config.get("protocol", "KKRT_PSI_2PC")
            precheck_input = self.task_config.get("precheck_input", False)
            sort_output = self.task_config.get("sort", False)
            broadcast_result = self.task_config.get("broadcast_result", False)

            psi_data = {
                "keys": final_keys,
                "input_paths": pyu_input_paths,
                "output_paths": pyu_output_paths,
                "receiver_party": receiver_party,
                "protocol": protocol,
                "precheck_input": precheck_input,
                "sort": sort_output,
                "broadcast_result": broadcast_result,
                "pyu_devices": pyu_devices,
            }

            logger.info(
                f"PSI数据准备完成，参与方: {list(input_paths.keys())}, "
                f"协议: {protocol}, keys: {keys if not isinstance(keys, dict) else 'per-party'}"
            )

            return psi_data

        except AlgorithmError:
            raise
        except Exception as e:
            error_msg = f"PSI数据准备失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AlgorithmError(error_msg) from e

    def _execute_psi_computation(self, psi_data: Dict[str, Any]) -> Any:
        """执行PSI核心计算

        调用SecretFlow的SPU设备执行PSI计算

        Args:
            psi_data: 准备好的PSI数据配置

        Returns:
            PSI计算报告

        Raises:
            AlgorithmError: PSI计算执行失败
        """
        try:
            logger.info("开始执行PSI核心计算")

            # 获取SPU设备
            from secretflow_task.device_manager import DeviceManager

            device_manager = DeviceManager.get_instance()
            spu_device = device_manager.get_device("spu")

            if spu_device is None:
                raise AlgorithmError("SPU设备未初始化，PSI计算需要SPU设备")

            # 执行PSI计算
            logger.info(
                f"调用SPU.psi_csv，协议: {psi_data['protocol']}, "
                f"接收方: {psi_data['receiver_party']}"
            )

            psi_reports = spu_device.psi_csv(
                key=psi_data["keys"],
                input_path=psi_data["input_paths"],
                output_path=psi_data["output_paths"],
                receiver=psi_data["receiver_party"],
                protocol=psi_data["protocol"],
                precheck_input=psi_data["precheck_input"],
                sort=psi_data["sort"],
                broadcast_result=psi_data["broadcast_result"],
            )

            logger.info(f"PSI核心计算完成，报告: {psi_reports}")

            return psi_reports

        except Exception as e:
            error_msg = f"PSI核心计算失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AlgorithmError(error_msg) from e

    def _process_psi_results(
        self, psi_reports: Any, start_time: float
    ) -> Dict[str, Any]:
        """处理PSI计算结果

        解析SecretFlow PSI报告，提取关键信息并格式化输出

        Args:
            psi_reports: SecretFlow PSI计算报告
            start_time: 计算开始时间

        Returns:
            Dict[str, Any]: 格式化的PSI结果，包含：
                - intersection_count: 交集数量
                - execution_time: 执行时间
                - output_paths: 输出文件路径
                - protocol: 使用的协议
                - parties: 参与方列表
                - reports: 原始报告
                - metadata: 元数据
        """
        try:
            logger.info("开始处理PSI计算结果")

            execution_time = time.time() - start_time

            # 提取交集数量（如果报告中有）
            intersection_count = None

            logger.info(f"PSI报告类型: {type(psi_reports)}")
            logger.debug(f"PSI报告内容: {psi_reports}")

            # 处理列表类型的报告（通常spu.psi_csv返回每个参与方的报告列表）
            if isinstance(psi_reports, list):
                for report in psi_reports:
                    if (
                        hasattr(report, "intersection_count")
                        and report.intersection_count >= 0
                    ):
                        intersection_count = report.intersection_count
                        break
                    elif isinstance(report, dict) and "intersection_count" in report:
                        intersection_count = report["intersection_count"]
                        break
            # 处理单个对象类型的报告
            elif psi_reports:
                if hasattr(psi_reports, "intersection_count"):
                    intersection_count = psi_reports.intersection_count
                elif (
                    isinstance(psi_reports, dict)
                    and "intersection_count" in psi_reports
                ):
                    intersection_count = psi_reports["intersection_count"]

            # 构建结果字典
            result = {
                "status": "success",
                "intersection_count": intersection_count,
                "execution_time": round(execution_time, 2),
                "output_paths": self.task_config["output_paths"],
                "protocol": self.task_config.get("protocol", "KKRT_PSI_2PC"),
                "parties": list(self.task_config["input_paths"].keys()),
                "receiver_party": self.task_config["receiver_party"],
                "reports": str(psi_reports) if psi_reports else None,
                "metadata": {
                    "task_request_id": self.task_request_id,
                    "task_type": "psi",
                    "completed_at": datetime.now().isoformat(),
                    "keys": self.task_config["keys"],
                    "precheck_input": self.task_config.get("precheck_input", False),
                    "sort_output": self.task_config.get("sort", False),
                    "broadcast_result": self.task_config.get("broadcast_result", False),
                },
            }

            logger.info(
                f"PSI结果处理完成，交集数量: {intersection_count if intersection_count is not None else 'N/A'}"
            )

            return result

        except Exception as e:
            error_msg = f"PSI结果处理失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 即使处理失败，也返回基础结果
            return {
                "status": "partial_success",
                "execution_time": round(time.time() - start_time, 2),
                "output_paths": self.task_config["output_paths"],
                "protocol": self.task_config.get("protocol", "KKRT_PSI_2PC"),
                "parties": list(self.task_config["input_paths"].keys()),
                "error": str(e),
                "error_type": "result_processing_error",
            }
