#!/usr/bin/env python3
"""
简化版PSI单机测试
专门为SecretFlow单机仿真模式设计
"""

import os
import sys
import pandas as pd
import logging

import secretflow as sf

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_simple_psi():
    """运行简化版PSI测试"""
    
    try:
        logger.info("="*50)
        logger.info("开始简化版PSI单机测试")
        logger.info("="*50)
        
        # 检查版本
        logger.info(f"SecretFlow版本: {sf.__version__}")
        
        # 使用项目data目录而不是临时目录
        data_dir = '/disc/home/beng003/work/secretflow_test/data'
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"测试目录: {data_dir}")
        
        # 关闭之前的实例
        try:
            sf.shutdown()
        except:
            pass
        
        # 初始化SecretFlow - 使用最简单的方式
        logger.info("初始化SecretFlow...")
        sf.init(['alice', 'bob'], address='local', num_cpus=8, log_to_driver=False)
        
        # 创建设备 - 简化配置
        logger.info("创建计算设备...")
        alice = sf.PYU('alice')
        bob = sf.PYU('bob')
        
        # 使用正确的SPU配置方式
        spu_config = sf.utils.testing.cluster_def(['alice', 'bob'])
        spu_config['link_desc'] = {
            'connect_retry_times': 60,
            'connect_retry_interval_ms': 1000,
            'brpc_channel_protocol': 'http',
            'brpc_channel_connection_type': 'pooled',
            'recv_timeout_ms': 120000
        }
        spu = sf.SPU(spu_config)
        
        logger.info("设备创建成功")
        
        # 创建测试数据
        logger.info("准备测试数据...")
        
        # 简单的测试数据集
        alice_data = pd.DataFrame({
            'uid': [1, 2, 3, 4, 5],
            'value': ['a', 'b', 'c', 'd', 'e']
        })
        
        bob_data = pd.DataFrame({
            'uid': [3, 4, 5, 6, 7],
            'score': [30, 40, 50, 60, 70]
        })
        
        # 保存到文件
        alice_path = os.path.join(data_dir, 'alice.csv')
        bob_path = os.path.join(data_dir, 'bob.csv')
        
        alice_data.to_csv(alice_path, index=False)
        bob_data.to_csv(bob_path, index=False)
        
        logger.info(f"Alice数据: {alice_data.to_dict('records')}")
        logger.info(f"Bob数据: {bob_data.to_dict('records')}")
        logger.info(f"预期交集: [3, 4, 5]")
        
        # 配置PSI输入输出
        input_paths = {alice: alice_path, bob: bob_path}
        output_paths = {
            alice: os.path.join(data_dir, 'alice_result.csv'),
            bob: os.path.join(data_dir, 'bob_result.csv')
        }
        
        # 执行PSI - 使用最基础的配置
        logger.info("执行PSI计算...")
        spu.psi_csv(
            key='uid',
            input_path=input_paths,
            output_path=output_paths,
            receiver='alice',
            protocol='KKRT_PSI_2PC',
            curve_type='CURVE_FOURQ'
        )
        logger.info("PSI计算完成")
        
        # 验证结果
        logger.info("验证PSI结果...")
        
        alice_result = pd.read_csv(output_paths[alice])
        bob_result = pd.read_csv(output_paths[bob])
        
        logger.info(f"Alice结果: {alice_result.to_dict('records')}")
        logger.info(f"Bob结果: {bob_result.to_dict('records')}")
        
        # 检查结果
        alice_uids = set(alice_result['uid'])
        bob_uids = set(bob_result['uid'])
        expected_uids = {3, 4, 5}
        
        if alice_uids == expected_uids and bob_uids == expected_uids:
            logger.info("✅ PSI测试成功！结果正确")
            return True
        else:
            logger.error(f"❌ PSI测试失败！预期: {expected_uids}, Alice: {alice_uids}, Bob: {bob_uids}")
            return False
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    finally:
        # 清理
        try:
            sf.shutdown()
        except Exception:
            pass
        
        logger.info("测试数据保存在data目录中")


if __name__ == "__main__":
    success = test_simple_psi()
    if success:
        print("\n🎉 PSI单机测试完全成功！")
    else:
        print("\n❌ PSI单机测试失败")
    sys.exit(0 if success else 1)
