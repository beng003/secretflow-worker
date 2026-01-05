"""
机器学习任务模块

使用SPU的dump/load机制保存密文分片，每个参与方只保存自己的部分。
预测结果使用to_pyu参数只发送给指定接收方，不公开reveal。
"""

import os
import json
import logging
from typing import Dict, List
from datetime import datetime

import secretflow as sf
from secretflow.device import SPU, PYU
from secretflow.ml.linear.ss_sgd import SSRegression
from secretflow.data.vertical import VDataFrame

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
    if not isinstance(model_output, dict):
        raise ValueError("model_output必须是字典类型 {party: path}")
    
    if not model_output:
        raise ValueError("model_output不能为空")
    
    for party, path in model_output.items():
        if not isinstance(path, str) or not path:
            raise ValueError(f"参与方'{party}'的model_output路径必须是非空字符串")
    
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
    model_output: Dict[str, str],
    spu_device: SPU
) -> None:
    """
    安全保存SS-LR模型（不解密）
    
    使用SPU的dump机制保存密文分片，每个参与方只保存自己的密文部分。
    
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
        model_output: 模型输出路径字典 {party: path}
        spu_device: SPU设备对象
    """
    logger.info("开始保存模型（安全模式：不解密）...")
    
    # 获取LinearModel对象
    linear_model = model.save_model()
    
    # 构建模型元数据（不包含权重明文）
    model_meta = {
        "model_type": "ss_sgd_secure",
        "version": "1.0.0",
        "reg_type": str(linear_model.reg_type),
        "sig_type": str(linear_model.sig_type),
        "features": features,
        "label": label,
        "label_party": label_party,
        "parties": parties,
        "model_output_paths": model_output,
        "training_params": {
            "epochs": epochs,
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "penalty": penalty,
            "l2_norm": l2_norm
        },
        "created_at": datetime.now().isoformat(),
        "secure_mode": True,
        "weights_encrypted": True
    }
    
    # 为每个参与方保存密文分片和元数据
    share_paths = []
    for party in parties:
        if party not in model_output:
            raise ValueError(f"model_output中缺少参与方'{party}'的路径")
        
        party_path = model_output[party]
        
        # 确保目录存在
        party_dir = os.path.dirname(party_path)
        if party_dir:
            os.makedirs(party_dir, exist_ok=True)
        
        # 密文分片路径
        share_path = party_path
        share_paths.append(share_path)
        
        # 为每个参与方保存元数据文件
        party_meta = {
            "party": party,
            "model_type": "ss_sgd_secure",
            "share_path": share_path,
            "parties": parties,
            "features": features,
            "label": label,
            "label_party": label_party,
            "reg_type": str(linear_model.reg_type),
            "sig_type": str(linear_model.sig_type),
            "training_params": model_meta["training_params"],
            "secure_mode": True,
            "created_at": datetime.now().isoformat()
        }
        
        meta_path = f"{party_path}.meta.json"
        with open(meta_path, 'w') as f:
            json.dump(party_meta, f, indent=2)
        logger.info(f"参与方 {party} 的元数据已保存到: {meta_path}")
    
    # 使用SPU.dump保存密文分片
    logger.info(f"保存密文分片到: {share_paths}")
    spu_device.dump(linear_model.weights, share_paths)
    
    logger.info("密文分片保存成功（每个参与方只有自己的密文部分）")


def load_ss_lr_model(model_output: Dict[str, str], spu_device: SPU, parties: List[str]) -> Dict:
    """
    安全加载SS-LR模型（从密文分片）
    
    使用SPU的load机制从密文分片重建模型，不需要解密。
    
    Args:
        model_output: 模型输出路径字典 {party: path}
        spu_device: SPU设备对象
        parties: 参与方列表
        
    Returns:
        包含模型和元数据的字典
        
    Raises:
        FileNotFoundError: 模型文件不存在
        ValueError: 模型文件格式错误
    """
    logger.info("开始加载模型（安全模式）...")
    
    # 验证所有参与方的路径都存在
    for party in parties:
        if party not in model_output:
            raise ValueError(f"model_output中缺少参与方'{party}'的路径")
    
    # 从第一个参与方的元数据文件读取模型信息
    first_party = parties[0]
    first_party_path = model_output[first_party]
    meta_path = f"{first_party_path}.meta.json"
    
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"模型元数据文件不存在: {meta_path}")
    
    logger.info(f"加载模型元数据: {meta_path}")
    
    # 读取模型元数据
    with open(meta_path, 'r') as f:
        model_meta = json.load(f)
    
    # 验证模型类型
    if model_meta.get('model_type') != 'ss_sgd_secure':
        raise ValueError(f"不支持的模型类型: {model_meta.get('model_type')}")
    
    if not model_meta.get('secure_mode'):
        raise ValueError("此模型不是安全模式保存的")
    
    # 构建密文分片路径
    share_paths = []
    for party in parties:
        share_path = model_output[party]
        if not os.path.exists(share_path):
            raise FileNotFoundError(f"参与方 {party} 的密文分片不存在: {share_path}")
        share_paths.append(share_path)
    
    logger.info(f"加载密文分片: {share_paths}")
    
    # 使用SPU.load从密文分片重建SPUObject
    spu_weights = spu_device.load(share_paths)
    
    logger.info("密文分片加载成功，重建模型...")
    
    # 创建新的SSRegression模型
    model = SSRegression(spu_device)
    
    # 解析枚举类型
    from secretflow.ml.linear.ss_sgd.model import LinearModel, RegType
    from secretflow.ml.linear.linear_model import SigType
    
    reg_type_str = model_meta['reg_type']
    if 'logistic' in reg_type_str.lower():
        reg_type = RegType.Logistic
    else:
        reg_type = RegType.Linear
    
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
        sig_type = SigType.T1
    
    # 创建LinearModel并加载到模型中
    linear_model = LinearModel(
        weights=spu_weights,
        reg_type=reg_type,
        sig_type=sig_type
    )
    
    model.load_model(linear_model)
    
    logger.info("模型加载成功（安全模式：权重保持加密状态）")
    
    return {
        "model": model,
        "features": model_meta['features'],
        "label": model_meta['label'],
        "label_party": model_meta['label_party'],
        "parties": model_meta['parties'],
        "training_params": model_meta['training_params'],
        "created_at": model_meta.get('created_at'),
        "secure_mode": True
    }


@TaskDispatcher.register_task('ss_lr')
def execute_ss_logistic_regression(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行SS-LR训练任务（安全模式：不解密保存）
    
    使用SPU的dump机制保存密文分片，每个参与方只保存自己的密文部分。
    
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
                
    Returns:
        包含训练结果的字典
    """
    try:
        logger.info("开始执行SS-LR训练任务（安全模式）")
        
        # 验证配置
        _validate_ss_lr_config(task_config)
        
        # 获取配置
        train_data = task_config['train_data']
        features = task_config['features']
        label = task_config['label']
        label_party = task_config['label_party']
        model_output = task_config['model_output']
        parties = list(train_data.keys())
        
        # 获取SPU设备
        spu_device = devices.get('spu')
        if spu_device is None:
            raise ValueError("devices中缺少'spu'设备")
        
        if not isinstance(spu_device, SPU):
            raise ValueError("'spu'设备必须是SPU类型")
        
        # 获取训练参数
        params = task_config.get('params', {})
        epochs = params.get('epochs', 5)
        learning_rate = params.get('learning_rate', 0.3)
        batch_size = params.get('batch_size', 32)
        sig_type = params.get('sig_type', 't1')
        reg_type = params.get('reg_type', 'logistic')
        penalty = params.get('penalty', 'l2')
        l2_norm = params.get('l2_norm', 0.1)
        
        logger.info(f"训练配置: features={features}, label={label}, parties={parties}")
        logger.info(f"训练参数: epochs={epochs}, lr={learning_rate}, batch_size={batch_size}")
        
        # 检查训练数据文件
        logger.info("检查训练数据文件...")
        for party, path in train_data.items():
            if not os.path.exists(path):
                raise ValueError(f"训练数据文件不存在: {path}")
        
        # 读取垂直分区训练数据
        logger.info("读取垂直分区训练数据...")
        pyu_input_paths = {}
        for party in train_data.keys():
            pyu_device = devices.get(party)
            if pyu_device is None:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")
            pyu_input_paths[pyu_device] = train_data[party]
        
        vdf = sf.data.vertical.read_csv(pyu_input_paths)
        logger.info(f"数据读取完成，列: {vdf.columns}")
        
        # 验证特征和标签列
        for feature in features:
            if feature not in vdf.columns:
                raise ValueError(f"特征列'{feature}'不存在于训练数据中")
        
        if label not in vdf.columns:
            raise ValueError(f"标签列'{label}'不存在于训练数据中")
        
        # 准备训练数据
        logger.info("准备训练数据...")
        x_vdf = vdf[features]
        y_data = vdf[label]
        
        # 创建模型
        logger.info("创建SS-LR模型...")
        model = SSRegression(spu_device)
        
        # 训练模型
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
        
        # 安全保存模型（不解密）
        logger.info(f"保存模型到: {model_output}（安全模式：不解密）")
        _save_ss_lr_model(
            model, features, label, label_party, parties,
            epochs, learning_rate, batch_size, sig_type,
            reg_type, penalty, l2_norm, model_output, spu_device
        )
        logger.info("模型保存成功（安全模式）")
        
        result = {
            "model_path": model_output,
            "parties": parties,
            "features": features,
            "label": label,
            "secure_mode": True,
            "weights_encrypted": True,
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
        
        logger.info("SS-LR训练任务执行成功（安全模式）")
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
    执行SS-LR模型预测任务（安全模式）
    
    使用安全保存的模型进行预测，权重保持加密状态。
    
    Args:
        devices: 设备字典
        task_config: 任务配置，包含以下字段：
            - model_path: Dict[str, str] - 模型文件路径字典 {party: path}
            - predict_data: Dict[str, str] - 预测数据路径字典
            - output_path: Dict[str, str] - 预测结果输出路径字典 {party: path}
            - receiver_party: str - 接收预测结果的参与方（可选）
            
    Returns:
        包含预测结果路径的字典
    """
    try:
        logger.info("开始执行SS-LR预测任务（安全模式）")
        
        # 验证配置
        required_fields = ['model_path', 'predict_data', 'output_path']
        for field in required_fields:
            if field not in task_config:
                raise ValueError(f"缺少必需字段: {field}")
        
        model_path = task_config['model_path']
        predict_data = task_config['predict_data']
        output_path = task_config['output_path']
        
        # 验证路径格式
        if not isinstance(model_path, dict):
            raise ValueError("model_path必须是字典格式 {party: path}")
        if not isinstance(output_path, dict):
            raise ValueError("output_path必须是字典格式 {party: path}")
        
        parties = list(predict_data.keys())
        
        # 获取SPU设备
        spu_device = devices.get('spu')
        if spu_device is None:
            raise ValueError("devices中缺少'spu'设备")
        
        # 加载模型（安全模式）
        logger.info(f"加载模型: {model_path}（安全模式）")
        model_info = load_ss_lr_model(model_path, spu_device, parties)
        
        model: SSRegression = model_info['model']
        features = model_info['features']
        label_party = model_info['label_party']
        
        # 确定接收方
        receiver_party = task_config.get('receiver_party', label_party)
        
        logger.info(f"预测配置: features={features}, receiver={receiver_party}")
        
        # 读取预测数据
        logger.info("读取垂直分区预测数据...")
        pyu_input_paths = {}
        for party in predict_data.keys():
            pyu_device = devices.get(party)
            if pyu_device is None:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")
            pyu_input_paths[pyu_device] = predict_data[party]
        
        vdf = sf.data.vertical.read_csv(pyu_input_paths)
        x_vdf = vdf[features]
        
        # 执行预测
        logger.info("开始预测...")
        receiver_pyu = devices[receiver_party]
        
        # 使用to_pyu参数，预测结果只发送给指定参与方（不公开reveal）
        predictions_fed = model.predict(x_vdf, to_pyu=receiver_pyu)
        
        # FedNdarray只包含接收方的partition，获取PYUObject
        predictions_pyu = predictions_fed.partitions[receiver_pyu]
        
        # 验证接收方在output_path中有对应路径
        if receiver_party not in output_path:
            raise ValueError(f"output_path中缺少接收方'{receiver_party}'的路径")
        
        receiver_output_path = output_path[receiver_party]
        
        # 在接收方PYU上保存预测结果（不reveal到driver）
        logger.info(f"在接收方 {receiver_party} 上保存预测结果到: {receiver_output_path}")
        
        def save_predictions(pred_data, output_file):
            """在PYU上执行的保存函数"""
            import pandas as pd
            import numpy as np
            import os
            
            # 创建输出目录
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # 转换为DataFrame并保存
            if isinstance(pred_data, np.ndarray):
                pred_flat = pred_data.flatten()
            else:
                pred_flat = pred_data
            
            # pred_flat是概率值（0到1之间）
            # prediction是根据阈值0.5判断的类别（0或1）
            pred_df = pd.DataFrame({
                'probability': pred_flat,  # 预测概率
                'prediction': (pred_flat >= 0.5).astype(int)  # 预测类别
            })
            
            pred_df.to_csv(output_file, index=False)
            
            # 只返回预测数量（不泄露数据分布信息）
            return len(pred_flat)
        
        # 在接收方PYU上执行保存操作
        num_predictions_pyu = receiver_pyu(save_predictions)(predictions_pyu, receiver_output_path)
        
        # 只获取预测数量（不reveal统计信息）
        from secretflow.device import reveal
        num_predictions = reveal(num_predictions_pyu)
        
        logger.info("预测结果保存成功（仅在接收方）")
        
        result = {
            "output_path": output_path,
            "receiver_party": receiver_party,
            "num_predictions": num_predictions,
            "secure_mode": True
        }
        
        logger.info("SS-LR预测任务执行成功（安全模式）")
        return result
        
    except Exception as e:
        logger.error(f"SS-LR预测任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"SS-LR预测任务执行失败: {str(e)}") from e
