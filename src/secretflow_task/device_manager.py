"""
SecretFlow设备管理器

负责PYU、SPU、HEU等计算设备的初始化、配置和生命周期管理。
"""

import time
from typing import Any, Union
from utils.log import logger
from secretflow.device import PYU, SPU, HEU


class DeviceManager:
    """SecretFlow设备管理器 - 单例模式"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._devices: dict[str, Union[PYU, SPU, HEU]] = {}
            self._device_init_times: dict[str, float] = {}
            DeviceManager._initialized = True

    @classmethod
    def get_instance(cls) -> "DeviceManager":
        """获取DeviceManager单例实例

        Returns:
            DeviceManager: 设备管理器单例实例
        """
        return cls()

    def initialize_devices(
        self,
        pyu_config: dict | None = None,
        spu_config: dict | None = None,
        heu_config: dict | None = None,
    ) -> dict:
        """初始化计算设备

        按需初始化PYU、SPU和HEU设备，支持条件启用

        Args:
            pyu_config: PYU设备配置，支持多个参与方
            spu_config: SPU设备配置
            heu_config: HEU设备配置

        Returns:
            dict: 初始化的设备实例
        """
        devices = {}

        # 从SPU配置中提取参与方信息
        parties = []
        if spu_config and "cluster_def" in spu_config:
            cluster_def = spu_config["cluster_def"]
            # 处理 cluster_def 可能是字典或对象的情况
            if isinstance(cluster_def, dict):
                nodes = cluster_def.get("nodes", [])
            else:
                # 尝试作为对象访问（如果是 protobuf 对象）
                nodes = getattr(cluster_def, "nodes", [])

            parties = [node["party"] for node in nodes if "party" in node]

        logger.info(f"检测到参与方: {parties}")

        # 按需初始化PYU设备
        if pyu_config and parties:
            pyu_devices = self.create_pyu_devices(parties)
            if pyu_devices:
                devices.update(pyu_devices)
                self._devices.update(pyu_devices)

        # 按需初始化SPU设备
        if spu_config:
            spu_device = self.create_spu_device(spu_config)
            if spu_device:
                devices["spu"] = spu_device
                self._devices["spu"] = spu_device

        # 按需初始化HEU设备
        if heu_config:
            heu_device = self.create_heu_device(heu_config)
            if heu_device:
                devices["heu"] = heu_device
                self._devices["heu"] = heu_device

        return devices

    def create_pyu_devices(self, parties: list) -> dict[str, PYU]:
        """创建PYU设备

        Args:
            "parties": ["alice", "bob"],  # 参与方列表
        Returns:
            dict[str, PYU]: PYU设备字典，键为参与方名称
        """
        start_time = time.time()
        pyu_devices = {}

        try:
            # 为每个参与方创建PYU设备
            for party in parties:
                try:
                    pyu_device = PYU(party)
                    pyu_devices[party] = pyu_device
                    logger.info(f"成功创建PYU设备: {party}")

                except Exception as e:
                    logger.error("创建PYU设备 %s 失败: %s", party, e)
                    continue

            # 记录初始化时间
            init_time = time.time() - start_time
            self._device_init_times["pyu"] = init_time

            logger.info(f"成功创建 {len(pyu_devices)} 个PYU设备")
            return pyu_devices

        except Exception as e:
            logger.error("Failed to create PYU devices: %s", e)
            # 记录初始化失败
            init_time = time.time() - start_time
            self._device_init_times["pyu_failed"] = init_time
            return {}

    def create_spu_device(self, config: dict) -> Any:
        """创建SPU设备

        Args:
            config: SPU配置参数，应包含cluster_def字段

        Returns:
            SPU设备实例 (sf.SPU类型)
        """
        start_time = time.time()

        try:
            device_type = "spu"

            # 提取cluster_def参数
            cluster_def = config.get("cluster_def")
            if not cluster_def:
                logger.error("SPU配置中缺少cluster_def字段")
                return None

            logger.info(f"创建SPU设备，cluster_def: {cluster_def}")

            # 创建SPU设备
            spu_device = SPU(cluster_def=cluster_def)

            # 记录初始化时间
            init_time = time.time() - start_time
            self._device_init_times[device_type] = init_time

            logger.info(f"SPU设备创建成功，耗时: {init_time:.2f}秒")

            return spu_device

        except Exception as e:
            logger.error("创建SPU设备失败", exc_info=True)
            # 记录初始化失败
            init_time = time.time() - start_time
            self._device_init_times[f"{device_type}_failed"] = init_time
            return None

    def create_heu_device(self, config: dict) -> Any:
        """创建HEU设备

        Args:
            config: HEU配置参数

        Returns:
            HEU设备实例 (sf.HEU类型)
        """
        start_time = time.time()

        try:
            # 记录初始化开始时间
            device_type = "heu"
            heu_device = HEU(**config)

            # 记录初始化时间
            init_time = time.time() - start_time
            self._device_init_times[device_type] = init_time

            return heu_device

        except Exception as e:
            logger.error("Failed to create HEU device: %s", e)
            # 记录初始化失败
            init_time = time.time() - start_time
            self._device_init_times[f"{device_type}_failed"] = init_time
            return None

    def cleanup_devices(self):
        """清理所有设备资源"""
        for device_name, device in self._devices.items():
            try:
                # PYU设备通常不需要显式关闭，SPU/HEU需要
                if hasattr(device, "shutdown"):
                    device.shutdown()
                    logger.info(f"成功关闭设备: {device_name}")
            except Exception as e:
                # 记录清理错误但不抛出异常
                logger.error("Failed to cleanup device %s: %s", device_name, e)

        # 清空设备字典
        self._devices.clear()
        self._device_init_times.clear()
        logger.info("所有设备已清理完成")

    def get_device_init_times(self) -> dict:
        """获取设备初始化时间记录

        Returns:
            dict: 设备初始化时间字典
        """
        return self._device_init_times.copy()

    def get_initialized_devices(self) -> dict:
        """获取已初始化的设备

        Returns:
            dict: 已初始化设备字典
        """
        return self._devices.copy()

    def get_pyu_devices(self) -> dict[str, PYU]:
        """获取所有PYU设备

        Returns:
            dict[str, PYU]: PYU设备字典，键为参与方名称
        """
        return {
            name: device
            for name, device in self._devices.items()
            if isinstance(device, PYU)
        }

    def get_device(self, device_name: str) -> Union[PYU, SPU, HEU, None]:
        """根据名称获取设备

        Args:
            device_name: 设备名称

        Returns:
            设备实例或None
        """
        return self._devices.get(device_name)
