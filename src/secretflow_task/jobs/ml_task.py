"""
机器学习任务模块

包含各种机器学习算法的任务实现
"""

import os
import json
import logging
from typing import Dict, List
import secretflow as sf
from secretflow.device import SPU, PYU, reveal
from secretflow.ml.linear.ss_sgd import SSRegression
from secretflow.data.vertical import VDataFrame
from secretflow.data.ndarray import FedNdarray, PartitionWay

from ..task_dispatcher import TaskDispatcher

logger = logging.getLogger(__name__)


def _validate_ss_lr_config(task_config: Dict) -> None:
    """
    验证SS-LR任务配置
    
    Args:
        task_config: 任务配置字典
        
    Raises:
        ValueError: 配置验证失败
    """
    required_fields = ['train_data', 'features', 'label', 'label_party', 'model_output']
    
    for field in required_fields:
        if field not in task_config:
            raise ValueError(f"缺少必需字段: {field}")
    
    train_data = task_config['train_data']
    if not isinstance(train_data, dict):
        raise ValueError("train_data必须是字典类型")
    
    if not train_data:
        raise ValueError("train_data不能为空")
    
    for party, path in train_data.items():
        if not isinstance(path, str) or not path:
            raise ValueError(f"参与方'{party}'的路径必须是非空字符串")
    
    features = task_config['features']
    if not isinstance(features, list):
        raise ValueError("features必须是列表类型")
    
    if not features:
        raise ValueError("features不能为空列表")
    
    label = task_config['label']
    if not isinstance(label, str) or not label:
        raise ValueError("label必须是非空字符串")
    
    label_party = task_config['label_party']
    if not isinstance(label_party, str) or not label_party:
        raise ValueError("label_party必须是非空字符串")
    
    if label_party not in train_data:
        raise ValueError(f"label_party '{label_party}' 不在train_data的参与方中")
    
    model_output = task_config['model_output']
    if not isinstance(model_output, str) or not model_output:
        raise ValueError("model_output必须是非空字符串")
    
    params = task_config.get('params', {})
    if not isinstance(params, dict):
        raise ValueError("params必须是字典类型")
    
    valid_param_keys = ['epochs', 'learning_rate', 'batch_size', 'sig_type', 'reg_type', 'penalty', 'l2_norm']
    for key in params.keys():
        if key not in valid_param_keys:
            raise ValueError(f"无效的参数: {key}")


def _save_ss_lr_model(
    model: SSRegression,
    features: List[str],
    label: str,
    label_party: str,
    parties: List[str],
    epochs: int,
    learning_rate: float,
    batch_size: int,
    sig_type: str,
    reg_type: str,
    penalty: str,
    l2_norm: float,
    model_output: str
) -> None:
    """
    保存SS-LR模型
    
    保存模型元数据和权重。权重通过reveal解密后保存为明文。
    
    Args:
        model: 训练好的SSRegression模型
        features: 特征列名列表
        label: 标签列名
        label_party: 标签所属参与方
        parties: 参与方列表
        epochs: 训练轮数
        learning_rate: 学习率
        batch_size: 批次大小
        sig_type: 签名类型
        reg_type: 回归类型
        penalty: 正则化类型
        l2_norm: L2正则化系数
        model_output: 模型输出路径
    """
    from datetime import datetime
    
    # 获取LinearModel对象
    linear_model = model.save_model()
    
    # 解密权重（将SPUObject转换为明文）
    logger.info("解密模型权重...")
    weights_plain = reveal(linear_model.weights)
    
    # 转换为可序列化的格式
    import numpy as np
    if isinstance(weights_plain, np.ndarray):
        weights_list = weights_plain.tolist()
    else:
        weights_list = weights_plain
    
    # 构建模型元数据
    model_meta = {
        "model_type": "ss_sgd",
        "version": "1.0.0",
        "reg_type": str(linear_model.reg_type),
        "sig_type": str(linear_model.sig_type),
        "features": features,
        "label": label,
        "label_party": label_party,
        "parties": parties,
        "weights": weights_list,
        "training_params": {
            "epochs": epochs,
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "penalty": penalty,
            "l2_norm": l2_norm
        },
        "created_at": datetime.now().isoformat()
    }
    
    # 保存主模型文件
    with open(model_output, 'w') as f:
        json.dump(model_meta, f, indent=2)
    
    logger.info(f"模型元数据已保存到: {model_output}")
    
    # 为每个参与方创建引用文件
    for party in parties:
        party_model_path = f"{model_output}.{party}"
        party_meta = {
            "party": party,
            "model_reference": model_output,
            "model_type": "ss_sgd",
            "created_at": datetime.now().isoformat()
        }
        with open(party_model_path, 'w') as f:
            json.dump(party_meta, f, indent=2)
        logger.info(f"参与方 {party} 的模型引用已保存到: {party_model_path}")


def load_ss_lr_model(model_path: str, spu_device: SPU) -> Dict:
    """
    加载SS-LR模型
    
    从文件加载模型元数据和权重，并重新创建SSRegression模型。
    
    Args:
        model_path: 模型文件路径
        spu_device: SPU设备对象
        
    Returns:
        包含模型和元数据的字典
        
    Raises:
        FileNotFoundError: 模型文件不存在
        ValueError: 模型文件格式错误
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    
    logger.info(f"加载模型: {model_path}")
    
    # 读取模型元数据
    with open(model_path, 'r') as f:
        model_meta = json.load(f)
    
    # 验证模型类型
    if model_meta.get('model_type') != 'ss_sgd':
        raise ValueError(f"不支持的模型类型: {model_meta.get('model_type')}")
    
    # 创建新的SSRegression模型
    model = SSRegression(spu_device)
    
    # 加载权重
    import numpy as np
    weights = np.array(model_meta['weights'])
    
    # 将权重转换为SPUObject
    from secretflow.ml.linear.ss_sgd.model import LinearModel, RegType
    from secretflow.ml.linear.linear_model import SigType
    
    # 将明文权重转换为SPU密文
    spu_weights = spu_device(lambda w: w)(weights)
    
    # 解析reg_type
    reg_type_str = model_meta['reg_type']
    if 'logistic' in reg_type_str.lower():
        reg_type = RegType.Logistic
    else:
        reg_type = RegType.Linear
    
    # 解析sig_type
    sig_type_str = model_meta['sig_type'].lower()
    if 't1' in sig_type_str:
        sig_type = SigType.T1
    elif 't3' in sig_type_str:
        sig_type = SigType.T3
    elif 't5' in sig_type_str:
        sig_type = SigType.T5
    elif 'real' in sig_type_str:
        sig_type = SigType.REAL
    else:
        sig_type = SigType.T1  # 默认值
    
    # 创建LinearModel并加载到模型中
    linear_model = LinearModel(
        weights=spu_weights,
        reg_type=reg_type,
        sig_type=sig_type
    )
    
    model.load_model(linear_model)
    
    logger.info("模型加载成功")
    
    return {
        "model": model,
        "features": model_meta['features'],
        "label": model_meta['label'],
        "label_party": model_meta['label_party'],
        "parties": model_meta['parties'],
        "training_params": model_meta['training_params'],
        "created_at": model_meta.get('created_at')
    }


@TaskDispatcher.register_task('ss_lr')
def execute_ss_logistic_regression(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行SS-LR（安全逻辑回归）训练任务
    
    使用SecretFlow的SS-SGD算法在垂直分区数据上训练逻辑回归模型。
    
    Args:
        devices: 设备字典，键为参与方名称，值为PYU设备对象
                 必须包含'spu'键对应SPU设备
        task_config: 任务配置，包含以下字段：
            - train_data: Dict[str, str] - 训练数据路径字典
            - features: List[str] - 特征列名列表
            - label: str - 标签列名
            - label_party: str - 标签所属参与方
            - model_output: str - 模型输出路径
            - params: Dict - 可选训练参数
                - epochs: int - 训练轮数，默认5
                - learning_rate: float - 学习率，默认0.3
                - batch_size: int - 批次大小，默认32
                - sig_type: str - 签名类型，默认't1'
                - reg_type: str - 回归类型，默认'logistic'
                - penalty: str - 正则化类型，默认'l2'
                - l2_norm: float - L2正则化系数，默认0.1
    
    Returns:
        Dict: 包含以下字段的结果字典
            - model_path: str - 模型保存路径
            - parties: List[str] - 参与方列表
            - features: List[str] - 特征列表
            - label: str - 标签列名
            - params: Dict - 实际使用的训练参数
    
    Raises:
        ValueError: 配置验证失败或参数错误
        RuntimeError: 训练执行失败
    
    Example:
        >>> devices = {
        ...     'alice': sf.PYU('alice'),
        ...     'bob': sf.PYU('bob'),
        ...     'spu': sf.SPU(...)
        ... }
        >>> task_config = {
        ...     "train_data": {"alice": "alice_train.csv", "bob": "bob_train.csv"},
        ...     "features": ["f1", "f2", "f3"],
        ...     "label": "y",
        ...     "label_party": "alice",
        ...     "model_output": "/models/lr_model",
        ...     "params": {
        ...         "epochs": 10,
        ...         "learning_rate": 0.01,
        ...         "batch_size": 128
        ...     }
        ... }
        >>> result = execute_ss_logistic_regression(devices, task_config)
    """
    try:
        logger.info("开始执行SS-LR逻辑回归训练任务")
        
        _validate_ss_lr_config(task_config)
        
        train_data = task_config['train_data']
        features = task_config['features']
        label = task_config['label']
        label_party = task_config['label_party']
        model_output = task_config['model_output']
        
        params = task_config.get('params', {})
        epochs = params.get('epochs', 5)
        learning_rate = params.get('learning_rate', 0.3)
        batch_size = params.get('batch_size', 32)
        sig_type = params.get('sig_type', 't1')
        reg_type = params.get('reg_type', 'logistic')
        penalty = params.get('penalty', 'l2')
        l2_norm = params.get('l2_norm', 0.1)
        
        parties = list(train_data.keys())
        logger.info(f"SS-LR配置: parties={parties}, features={features}, label={label}, label_party={label_party}")
        logger.info(f"训练参数: epochs={epochs}, lr={learning_rate}, batch_size={batch_size}, penalty={penalty}")
        
        spu_device = devices.get('spu')
        if spu_device is None:
            raise ValueError("devices中缺少'spu'设备")
        
        if not isinstance(spu_device, SPU):
            raise ValueError("'spu'设备必须是SPU类型")
        
        for party in parties:
            pyu_device = devices.get(party)
            if pyu_device is None:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")
        
        logger.info("检查训练数据文件...")
        for party, path in train_data.items():
            if not os.path.exists(path):
                raise ValueError(f"训练数据文件不存在: {path}")
        
        model_dir = os.path.dirname(model_output)
        if model_dir and not os.path.exists(model_dir):
            os.makedirs(model_dir, exist_ok=True)
            logger.info(f"创建模型输出目录: {model_dir}")
        
        logger.info("读取垂直分区训练数据...")
        pyu_input_paths = {}
        for party in parties:
            pyu_device = devices.get(party)
            pyu_input_paths[pyu_device] = train_data[party]
        
        vdf = sf.data.vertical.read_csv(pyu_input_paths)
        logger.info(f"数据读取完成，列: {vdf.columns}")
        
        for feature in features:
            if feature not in vdf.columns:
                raise ValueError(f"特征列'{feature}'不存在于数据中")
        
        if label not in vdf.columns:
            raise ValueError(f"标签列'{label}'不存在于数据中")
        
        logger.info("准备特征数据...")
        x_vdf = vdf[features]
        
        logger.info("准备标签数据...")
        label_pyu = devices.get(label_party)
        y_data = FedNdarray(
            partitions={label_pyu: label_pyu(lambda df: df[label].values)(vdf.partitions[label_pyu].data)},
            partition_way=PartitionWay.VERTICAL,
        )
        
        logger.info("创建SS-LR模型实例...")
        model = SSRegression(spu_device)
        
        logger.info("开始训练模型...")
        model.fit(
            x_vdf,
            y_data,
            epochs,
            learning_rate,
            batch_size,
            sig_type,
            reg_type,
            penalty,
            l2_norm
        )
        logger.info("模型训练完成")
        
        # 保存模型
        logger.info(f"保存模型到: {model_output}")
        _save_ss_lr_model(model, features, label, label_party, parties, 
                         epochs, learning_rate, batch_size, sig_type, 
                         reg_type, penalty, l2_norm, model_output)
        logger.info("模型保存成功")
        
        result = {
            "model_path": model_output,
            "parties": parties,
            "features": features,
            "label": label,
            "params": {
                "epochs": epochs,
                "learning_rate": learning_rate,
                "batch_size": batch_size,
                "sig_type": sig_type,
                "reg_type": reg_type,
                "penalty": penalty,
                "l2_norm": l2_norm
            }
        }
        
        logger.info("SS-LR训练任务执行成功")
        return result
        
    except ValueError as e:
        logger.error(f"SS-LR任务配置错误: {e}")
        raise
    except Exception as e:
        logger.error(f"SS-LR任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"SS-LR任务执行失败: {str(e)}") from e


@TaskDispatcher.register_task('ss_lr_predict')
def execute_ss_lr_predict(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行SS-LR模型预测任务
    
    使用已训练的SS-LR模型对新数据进行预测。
    
    Args:
        devices: 设备字典，键为参与方名称，值为PYU设备对象
                 必须包含'spu'键对应SPU设备
        task_config: 任务配置，包含以下字段：
            - model_path: str - 模型文件路径
            - predict_data: Dict[str, str] - 预测数据路径字典
            - output_path: str - 预测结果输出路径
            - receiver_party: str - 接收预测结果的参与方（可选，默认为label_party）
            
    Returns:
        包含预测结果路径和统计信息的字典
        
    Example:
        >>> devices = {
        ...     'alice': sf.PYU('alice'),
        ...     'bob': sf.PYU('bob'),
        ...     'spu': sf.SPU(...)
        ... }
        >>> task_config = {
        ...     "model_path": "/models/lr_model",
        ...     "predict_data": {"alice": "alice_test.csv", "bob": "bob_test.csv"},
        ...     "output_path": "/results/predictions.csv",
        ...     "receiver_party": "alice"
        ... }
        >>> result = execute_ss_lr_predict(devices, task_config)
    """
    try:
        logger.info("开始执行SS-LR预测任务")
        
        # 验证配置
        required_fields = ['model_path', 'predict_data', 'output_path']
        for field in required_fields:
            if field not in task_config:
                raise ValueError(f"缺少必需字段: {field}")
        
        model_path = task_config['model_path']
        predict_data = task_config['predict_data']
        output_path = task_config['output_path']
        
        if not isinstance(predict_data, dict) or not predict_data:
            raise ValueError("predict_data必须是非空字典")
        
        # 获取SPU设备
        spu_device = devices.get('spu')
        if spu_device is None:
            raise ValueError("devices中缺少'spu'设备")
        
        if not isinstance(spu_device, SPU):
            raise ValueError("'spu'设备必须是SPU类型")
        
        # 加载模型
        logger.info(f"加载模型: {model_path}")
        model_info = load_ss_lr_model(model_path, spu_device)
        
        model = model_info['model']
        features = model_info['features']
        label_party = model_info['label_party']
        
        # 确定接收方
        receiver_party = task_config.get('receiver_party', label_party)
        if receiver_party not in devices:
            raise ValueError(f"接收方'{receiver_party}'不在devices中")
        
        logger.info(f"预测配置: features={features}, receiver={receiver_party}")
        
        # 检查预测数据文件
        logger.info("检查预测数据文件...")
        for party, path in predict_data.items():
            if not os.path.exists(path):
                raise ValueError(f"预测数据文件不存在: {path}")
        
        # 读取垂直分区预测数据
        logger.info("读取垂直分区预测数据...")
        pyu_input_paths = {}
        for party in predict_data.keys():
            pyu_device = devices.get(party)
            if pyu_device is None:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")
            pyu_input_paths[pyu_device] = predict_data[party]
        
        vdf = sf.data.vertical.read_csv(pyu_input_paths)
        logger.info(f"数据读取完成，列: {vdf.columns}")
        
        # 验证特征列
        for feature in features:
            if feature not in vdf.columns:
                raise ValueError(f"特征列'{feature}'不存在于预测数据中")
        
        # 准备特征数据
        logger.info("准备特征数据...")
        x_vdf = vdf[features]
        
        # 执行预测
        logger.info("开始预测...")
        spu_predictions = model.predict(x_vdf)
        
        # 解密预测结果到接收方
        logger.info(f"解密预测结果到接收方: {receiver_party}")
        receiver_pyu = devices[receiver_party]
        predictions = reveal(spu_predictions)
        
        # 保存预测结果
        logger.info(f"保存预测结果到: {output_path}")
        
        # 创建输出目录
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 保存预测结果到CSV
        import pandas as pd
        import numpy as np
        
        if isinstance(predictions, np.ndarray):
            pred_df = pd.DataFrame({
                'prediction': predictions.flatten(),
                'probability': predictions.flatten()  # 对于逻辑回归，这是概率
            })
        else:
            pred_df = pd.DataFrame({
                'prediction': predictions,
                'probability': predictions
            })
        
        pred_df.to_csv(output_path, index=False)
        logger.info("预测结果保存成功")
        
        # 统计信息
        pred_array = pred_df['prediction'].values
        result = {
            "output_path": output_path,
            "receiver_party": receiver_party,
            "num_predictions": len(pred_array),
            "statistics": {
                "mean": float(np.mean(pred_array)),
                "std": float(np.std(pred_array)),
                "min": float(np.min(pred_array)),
                "max": float(np.max(pred_array))
            }
        }
        
        logger.info("SS-LR预测任务执行成功")
        return result
        
    except ValueError as e:
        logger.error(f"SS-LR预测任务配置错误: {e}")
        raise
    except Exception as e:
        logger.error(f"SS-LR预测任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"SS-LR预测任务执行失败: {str(e)}") from e
