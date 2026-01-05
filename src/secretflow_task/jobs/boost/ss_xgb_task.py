"""
SS-XGBoost (Secret Sharing XGBoost) 任务模块

使用SPU进行密态计算，模型分片保存到各参与方。
预测结果使用to_pyu参数只发送给指定接收方。
"""

import os
import json
import logging
from typing import Dict, List
from datetime import datetime

import secretflow as sf
from secretflow.device import SPU, PYU
from secretflow.ml.boost.ss_xgb_v import Xgb, XgbModel

from ...task_dispatcher import TaskDispatcher

logger = logging.getLogger(__name__)
def _save_ss_xgb_model(
    model: XgbModel,
    features: List[str],
    label: str,
    label_party: str,
    parties: List[str],
    params: Dict,
    model_output: Dict[str, str],
    spu_device: SPU
) -> None:
    """
    保存SS-XGBoost模型
    
    Args:
        model: 训练好的XgbModel模型
        features: 特征列名列表
        label: 标签列名
        label_party: 标签所属参与方
        parties: 参与方列表
        params: 训练参数
        model_output: 模型输出路径字典 {party: path}
        spu_device: SPU设备对象
    """
    logger.info("开始保存SS-XGBoost模型...")
    
    # 构建模型元数据
    model_meta = {
        "model_type": "ss_xgb",
        "version": "1.0.0",
        "objective": str(model.objective),
        "base_score": float(model.base),
        "features": features,
        "label": label,
        "label_party": label_party,
        "parties": parties,
        "num_trees": len(model.trees),
        "training_params": params,
        "created_at": datetime.now().isoformat(),
        "secure_mode": True
    }
    
    # 为每个参与方保存模型
    for party in parties:
        if party not in model_output:
            raise ValueError(f"model_output中缺少参与方'{party}'的路径")
        
        party_path = model_output[party]
        
        # 确保目录存在
        party_dir = os.path.dirname(party_path)
        if party_dir:
            os.makedirs(party_dir, exist_ok=True)
        
        # 保存元数据
        meta_path = f"{party_path}.meta.json"
        with open(meta_path, 'w') as f:
            json.dump(model_meta, f, indent=2)
        logger.info(f"参与方 {party} 的元数据已保存到: {meta_path}")
    
    # 保存树结构和权重（每个参与方的树分片）
    for tree_idx, (tree, weight) in enumerate(zip(model.trees, model.weights)):
        # 为每个参与方保存树的分片
        tree_paths = []
        for party in parties:
            party_path = model_output[party]
            tree_path = f"{party_path}.tree_{tree_idx}.pkl"
            tree_paths.append(tree_path)
        
        # 保存树结构（每个参与方只保存自己的部分）
        for party, pyu in zip(parties, tree.keys()):
            party_path = model_output[party]
            tree_path = f"{party_path}.tree_{tree_idx}.pkl"
            tree_obj = tree[pyu]
            
            # 使用pickle保存PYUObject
            import pickle
            pyu(lambda obj, path: pickle.dump(obj, open(path, 'wb')))(tree_obj, tree_path)
        
        # 保存权重（SPUObject，需要dump到各参与方）
        weight_paths = [f"{model_output[party]}.weight_{tree_idx}.share" for party in parties]
        spu_device.dump(weight, weight_paths)
        
        logger.info(f"树 {tree_idx} 已保存")
    
    logger.info("SS-XGBoost模型保存成功")


def load_ss_xgb_model(
    model_output: Dict[str, str],
    spu_device: SPU,
    parties: List[str],
    devices: Dict[str, PYU]
) -> Dict:
    """
    加载SS-XGBoost模型
    
    Args:
        model_output: 模型输出路径字典 {party: path}
        spu_device: SPU设备对象
        parties: 参与方列表
        devices: 设备字典
        
    Returns:
        包含模型和元数据的字典
    """
    logger.info("开始加载SS-XGBoost模型...")
    
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
    
    # 读取模型元数据
    with open(meta_path, 'r') as f:
        model_meta = json.load(f)
    
    # 验证模型类型
    if model_meta.get('model_type') != 'ss_xgb':
        raise ValueError(f"不支持的模型类型: {model_meta.get('model_type')}")
    
    # 解析objective
    from secretflow.ml.boost.ss_xgb_v.core.node_split import RegType
    objective_str = model_meta['objective']
    if 'Logistic' in objective_str:
        objective = RegType.Logistic
    else:
        objective = RegType.Linear
    
    # 创建XgbModel
    base_score = model_meta['base_score']
    model = XgbModel(spu_device, objective, base_score)
    
    # 加载树和权重
    num_trees = model_meta['num_trees']
    for tree_idx in range(num_trees):
        # 加载树结构
        tree = {}
        for party in parties:
            pyu = devices[party]
            party_path = model_output[party]
            tree_path = f"{party_path}.tree_{tree_idx}.pkl"
            
            if not os.path.exists(tree_path):
                raise FileNotFoundError(f"树文件不存在: {tree_path}")
            
            # 加载PYUObject
            import pickle
            tree_obj = pyu(lambda path: pickle.load(open(path, 'rb')))(tree_path)
            tree[pyu] = tree_obj
        
        # 加载权重
        weight_paths = [f"{model_output[party]}.weight_{tree_idx}.share" for party in parties]
        for weight_path in weight_paths:
            if not os.path.exists(weight_path):
                raise FileNotFoundError(f"权重文件不存在: {weight_path}")
        
        weight = spu_device.load(weight_paths)
        
        model.trees.append(tree)
        model.weights.append(weight)
    
    logger.info(f"SS-XGBoost模型加载成功，共 {num_trees} 棵树")
    
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


@TaskDispatcher.register_task('ss_xgb')
def execute_ss_xgboost(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行SS-XGBoost训练任务
    
    Args:
        devices: 设备字典
        task_config: 任务配置，包含以下字段：
            - train_data: Dict[str, str] - 训练数据路径字典
            - features: List[str] - 特征列名列表
            - label: str - 标签列名
            - label_party: str - 标签所属参与方
            - model_output: Dict[str, str] - 模型输出路径字典 {party: path}
            - params: Dict - 训练参数
                - num_boost_round: int - 树的数量（默认10）
                - max_depth: int - 树的最大深度（默认5）
                - learning_rate: float - 学习率（默认0.3）
                - objective: str - 目标函数 'logistic'或'linear'（默认'logistic'）
                - reg_lambda: float - L2正则化系数（默认0.1）
                - subsample: float - 样本采样比例（默认1.0）
                - colsample_by_tree: float - 特征采样比例（默认1.0）
                - base_score: float - 初始预测分数（默认0.0）
                
    Returns:
        包含训练结果的字典
    """
    try:
        logger.info("开始执行SS-XGBoost训练任务")
        
        # 验证配置
        required_fields = ['train_data', 'features', 'label', 'label_party', 'model_output']
        for field in required_fields:
            if field not in task_config:
                raise ValueError(f"缺少必需字段: {field}")
        
        train_data = task_config['train_data']
        features = task_config['features']
        label = task_config['label']
        label_party = task_config['label_party']
        model_output = task_config['model_output']
        params = task_config.get('params', {})
        
        # 验证model_output格式
        if not isinstance(model_output, dict):
            raise ValueError("model_output必须是字典格式 {party: path}")
        
        parties = list(train_data.keys())
        
        # 获取SPU设备
        spu_device = devices.get('spu')
        if spu_device is None:
            raise ValueError("devices中缺少'spu'设备")
        
        # 读取训练数据
        logger.info("读取垂直分区训练数据...")
        pyu_input_paths = {}
        for party in train_data.keys():
            pyu_device = devices.get(party)
            if pyu_device is None:
                raise ValueError(f"devices中缺少参与方'{party}'的PYU设备")
            pyu_input_paths[pyu_device] = train_data[party]
        
        vdf = sf.data.vertical.read_csv(pyu_input_paths)
        
        # 分离特征和标签
        x_vdf = vdf[features]
        y_vdf = vdf[label]
        
        # 设置训练参数
        xgb_params = {
            'num_boost_round': params.get('num_boost_round', 10),
            'max_depth': params.get('max_depth', 5),
            'learning_rate': params.get('learning_rate', 0.3),
            'objective': params.get('objective', 'logistic'),
            'reg_lambda': params.get('reg_lambda', 0.1),
            'subsample': params.get('subsample', 1.0),
            'colsample_by_tree': params.get('colsample_by_tree', 1.0),
            'base_score': params.get('base_score', 0.0),
            'seed': params.get('seed', 42)
        }
        
        logger.info(f"训练参数: {xgb_params}")
        
        # 创建并训练模型
        logger.info("开始训练SS-XGBoost模型...")
        xgb = Xgb(spu_device)
        model = xgb.train(xgb_params, x_vdf, y_vdf)
        
        logger.info(f"训练完成，共 {len(model.trees)} 棵树")
        
        # 保存模型
        _save_ss_xgb_model(
            model=model,
            features=features,
            label=label,
            label_party=label_party,
            parties=parties,
            params=xgb_params,
            model_output=model_output,
            spu_device=spu_device
        )
        
        result = {
            "model_output": model_output,
            "num_trees": len(model.trees),
            "secure_mode": True,
            "training_params": xgb_params
        }
        
        logger.info("SS-XGBoost训练任务执行成功")
        return result
        
    except Exception as e:
        logger.error(f"SS-XGBoost训练任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"SS-XGBoost训练任务执行失败: {str(e)}") from e


@TaskDispatcher.register_task('ss_xgb_predict')
def execute_ss_xgb_predict(devices: Dict[str, PYU], task_config: Dict) -> Dict:
    """
    执行SS-XGBoost模型预测任务
    
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
        logger.info("开始执行SS-XGBoost预测任务")
        
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
        
        # 加载模型
        logger.info(f"加载模型: {model_path}")
        model_info = load_ss_xgb_model(model_path, spu_device, parties, devices)
        
        model: XgbModel = model_info['model']
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
        
        # 使用to_pyu参数，预测结果只发送给指定参与方
        predictions_fed = model.predict(x_vdf, to_pyu=receiver_pyu)
        
        # FedNdarray只包含接收方的partition，获取PYUObject
        predictions_pyu = predictions_fed.partitions[receiver_pyu]
        
        # 验证接收方在output_path中有对应路径
        if receiver_party not in output_path:
            raise ValueError(f"output_path中缺少接收方'{receiver_party}'的路径")
        
        receiver_output_path = output_path[receiver_party]
        
        # 在接收方PYU上保存预测结果
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
            
            # pred_flat是概率值（对于logistic）或预测值（对于linear）
            # 对于二分类，添加prediction列
            pred_df = pd.DataFrame({
                'probability': pred_flat,
                'prediction': (pred_flat >= 0.5).astype(int)
            })
            
            pred_df.to_csv(output_file, index=False)
            
            # 只返回预测数量
            return len(pred_flat)
        
        # 在接收方PYU上执行保存操作
        num_predictions_pyu = receiver_pyu(save_predictions)(predictions_pyu, receiver_output_path)
        
        # 只获取预测数量
        from secretflow.device import reveal
        num_predictions = reveal(num_predictions_pyu)
        
        logger.info("预测结果保存成功（仅在接收方）")
        
        result = {
            "output_path": output_path,
            "receiver_party": receiver_party,
            "num_predictions": num_predictions,
            "secure_mode": True
        }
        
        logger.info("SS-XGBoost预测任务执行成功")
        return result
        
    except Exception as e:
        logger.error(f"SS-XGBoost预测任务执行失败: {e}", exc_info=True)
        raise RuntimeError(f"SS-XGBoost预测任务执行失败: {str(e)}") from e
