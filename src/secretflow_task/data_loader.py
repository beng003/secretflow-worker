"""SecretFlow数据加载器

负责参与方数据的加载、预处理和格式化。
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
from utils.log import logger
from utils.exceptions import DataLoadingError, ValidationError
from utils.status_notifier import _publish_status


class DataLoader:
    """数据加载器"""
    
    def __init__(self, task_request_id: str = None):
        """初始化数据加载器
        
        Args:
            task_request_id: 任务请求ID，用于状态通知
        """
        self.task_request_id = task_request_id
    
    def load_party_data(self, party_name: str, data_path: str) -> pd.DataFrame:
        """加载参与方数据
        
        Args:
            party_name: 参与方名称
            data_path: 数据文件路径
            
        Returns:
            pd.DataFrame: 加载的数据
            
        Raises:
            DataLoadingError: 数据加载失败
            ValidationError: 数据验证失败
        """
        logger.info(f"开始加载参与方 {party_name} 的数据: {data_path}")
        
        # 发送开始加载状态
        if self.task_request_id:
            _publish_status(self.task_request_id, "RUNNING", {
                "stage": "load_party_data",
                "party_name": party_name,
                "data_path": data_path,
                "started_at": datetime.now().isoformat()
            })
        
        try:
            # 验证文件存在性
            if not os.path.exists(data_path):
                raise DataLoadingError(f"数据文件不存在: {data_path}")
            
            # 获取文件扩展名
            file_extension = Path(data_path).suffix.lower()
            
            # 根据文件类型加载数据
            if file_extension == '.csv':
                data = self._load_csv_data(data_path)
            elif file_extension == '.json':
                data = self._load_json_data(data_path)
            elif file_extension in ['.xlsx', '.xls']:
                data = self._load_excel_data(data_path)
            else:
                raise DataLoadingError(f"不支持的文件格式: {file_extension}")
            
            # 基础数据验证
            self._validate_basic_data_format(data, party_name)
            
            logger.info(f"成功加载参与方 {party_name} 数据, 形状: {data.shape}")
            
            # 发送加载成功状态
            if self.task_request_id:
                _publish_status(self.task_request_id, "SUCCESS", {
                    "stage": "load_party_data_complete",
                    "party_name": party_name,
                    "data_shape": data.shape,
                    "columns_count": len(data.columns),
                    "completed_at": datetime.now().isoformat()
                })
            
            return data
            
        except Exception as e:
            error_msg = f"加载参与方 {party_name} 数据失败: {str(e)}"
            logger.error(error_msg, extra={"party_name": party_name, "data_path": data_path})
            
            # 发送加载失败状态
            if self.task_request_id:
                _publish_status(self.task_request_id, "FAILURE", {
                    "stage": "load_party_data_failed",
                    "party_name": party_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "failed_at": datetime.now().isoformat()
                })
            
            raise DataLoadingError(error_msg) from e
    
    def create_secretflow_data(self, data_config: Dict[str, str], devices: Dict[str, Any]) -> Any:
        """创建secretflow数据对象
        
        Args:
            data_config: 数据配置 {"parties": {"alice": "path1", "bob": "path2"}, "keys": "uid"}
            devices: 设备字典，包含PYU和SPU设备
            
        Returns:
            VerticalDataFrame: SecretFlow联邦数据对象
        """
        try:
            from secretflow.data.vertical import read_csv as v_read_csv
            
            # 提取配置参数
            party_paths = data_config.get("parties", {})
                     
            # 构建设备路径映射
            device_paths = {}
            for party, path in party_paths.items():
                if party in devices:
                    device_paths[devices[party]] = path
                    
            # 创建联邦数据对象
            vdf = v_read_csv(device_paths)
            
            logger.info(f"成功创建vdf数据对象，参与方: {list(party_paths.keys())}")
            return vdf
            
        except Exception as e:
            logger.error(f"创建vdf数据对象失败: {e}")
            return None
    
    def validate_data_schema(self, data: pd.DataFrame, required_columns: List[str]) -> bool:
        """验证数据模式
        
        Args:
            data: 待验证的数据
            required_columns: 必需的列名列表
            
        Returns:
            bool: 验证是否通过
            
        Raises:
            ValidationError: 数据模式验证失败
        """
        try:
            # 检查数据是否为空
            if data.empty:
                raise ValidationError("数据为空")
            
            # 检查必需列是否存在
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                raise ValidationError(f"缺少必需的列: {missing_columns}")
            
            # 检查数据类型
            for column in required_columns:
                if data[column].dtype == 'object' and data[column].isnull().all():
                    raise ValidationError(f"列 '{column}' 全部为空值")
            
            logger.info(f"数据模式验证通过, 数据形状: {data.shape}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            error_msg = f"数据模式验证异常: {str(e)}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e
    
    def _load_csv_data(self, data_path: str) -> pd.DataFrame:
        """加载CSV数据文件"""
        try:
            # 尝试不同的编码格式
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            
            for encoding in encodings:
                try:
                    data = pd.read_csv(data_path, encoding=encoding)
                    logger.info(f"使用 {encoding} 编码成功加载CSV文件")
                    return data
                except UnicodeDecodeError:
                    continue
            
            raise DataLoadingError(f"无法以任何支持的编码格式读取CSV文件: {data_path}")
            
        except pd.errors.EmptyDataError:
            raise DataLoadingError(f"CSV文件为空: {data_path}")
        except pd.errors.ParserError as e:
            raise DataLoadingError(f"CSV文件格式错误: {str(e)}")
    
    def _load_json_data(self, data_path: str) -> pd.DataFrame:
        """加载JSON数据文件"""
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # 支持不同的JSON结构
            if isinstance(json_data, list):
                # 数组格式：[{"col1": val1, "col2": val2}, ...]
                data = pd.DataFrame(json_data)
            elif isinstance(json_data, dict):
                if "data" in json_data:
                    # 包装格式：{"data": [...], "metadata": {...}}
                    data = pd.DataFrame(json_data["data"])
                else:
                    # 直接字典格式：{"col1": [val1, val2], "col2": [val3, val4]}
                    data = pd.DataFrame(json_data)
            else:
                raise DataLoadingError(f"不支持的JSON数据结构类型: {type(json_data)}")
            
            return data
            
        except json.JSONDecodeError as e:
            raise DataLoadingError(f"JSON文件格式错误: {str(e)}")
        except FileNotFoundError:
            raise DataLoadingError(f"JSON文件不存在: {data_path}")
    
    def _load_excel_data(self, data_path: str) -> pd.DataFrame:
        """加载Excel数据文件"""
        try:
            data = pd.read_excel(data_path)
            return data
        except Exception as e:
            raise DataLoadingError(f"Excel文件读取失败: {str(e)}")
    
    def _validate_basic_data_format(self, data: pd.DataFrame, party_name: str) -> None:
        """验证基础数据格式"""
        if data.empty:
            raise ValidationError(f"参与方 {party_name} 的数据为空")
        
        if data.shape[0] == 0:
            raise ValidationError(f"参与方 {party_name} 没有数据行")
        
        if data.shape[1] == 0:
            raise ValidationError(f"参与方 {party_name} 没有数据列")


class ResultManager:
    """结果管理器"""
    
    def save_results(self, results: Dict[str, Any], output_config: Dict[str, Any]) -> List[str]:
        """保存计算结果
        
        Args:
            results: 计算结果
            output_config: 输出配置
            
        Returns:
            List[str]: 输出文件路径列表
        """
        # TODO: 实现结果保存逻辑
        pass
    
    def create_result_metadata(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """创建结果元数据
        
        Args:
            results: 计算结果
            
        Returns:
            Dict[str, Any]: 结果元数据
        """
        # TODO: 实现元数据创建逻辑
        pass
    
    def verify_output_integrity(self, output_path: str) -> bool:
        """验证输出完整性
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 验证是否通过
        """
        # TODO: 实现输出完整性验证逻辑
        pass
