"""
SecretFlow异常定义模块

定义了SecretFlow任务执行过程中可能出现的各种异常类型。
"""


class SecretFlowTaskError(Exception):
    """SecretFlow任务执行异常基类"""

    pass


class ClusterInitError(SecretFlowTaskError):
    """集群初始化失败异常"""

    pass


class DeviceConfigError(SecretFlowTaskError):
    """设备配置错误异常"""

    pass


class NetworkError(SecretFlowTaskError):
    """网络通信错误异常，可重试"""

    pass


class AlgorithmError(SecretFlowTaskError):
    """算法执行错误异常"""

    pass


class ParameterValidationError(SecretFlowTaskError):
    """参数验证错误异常"""

    pass


class DataLoadError(SecretFlowTaskError):
    """数据加载错误异常"""

    pass


class ResultSaveError(SecretFlowTaskError):
    """结果保存错误异常"""

    pass


class SPUInitError(DeviceConfigError):
    """SPU设备初始化错误"""

    pass


class HEUInitError(DeviceConfigError):
    """HEU设备初始化错误"""

    pass
