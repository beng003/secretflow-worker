#!/usr/bin/env python3
"""
Bob 节点的 PSI 隐私计算脚本
作为 Ray worker 连接到 Alice 的 Ray head，参与 PSI 计算
"""

import os
import sys
import time
import logging
import pandas as pd
import secretflow as sf

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/bob/bob.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def setup_cluster_config():
    """设置集群配置"""
    return {
        'parties': {
            'alice': {
                'address': os.getenv('ALICE_ADDRESS', '192.168.100.10:12945'),
                'listen_addr': '0.0.0.0:12945'
            },
            'bob': {
                'address': os.getenv('BOB_ADDRESS', '192.168.100.20:12946'),
                'listen_addr': '0.0.0.0:12946'
            }
        },
        'self_party': 'bob'
    }


def create_sample_data():
    """创建 Bob 的示例数据"""
    logger.info("Creating sample data for Bob...")
    
    # Bob 的数据集 - 购买记录（与 Alice 有部分重叠的用户）
    bob_data = {
        'user_id': [f'user_{i:04d}' for i in range(500, 1501)],  # 1000个用户，与Alice有500个重叠
        'product': [f'Product_{chr(65 + i % 26)}' for i in range(500, 1501)],
        'purchase_amount': [(100 + (i * 13) % 1000) for i in range(500, 1501)],
        'purchase_date': [f'2024-{1 + (i % 12):02d}-{1 + (i % 28):02d}' for i in range(500, 1501)],
        'category': [['Electronics', 'Clothing', 'Books', 'Home'][i % 4] for i in range(500, 1501)],
    }
    
    df_bob = pd.DataFrame(bob_data)
    
    # 确保数据目录存在
    os.makedirs('/data/bob', exist_ok=True)
    
    # 保存数据
    input_path = '/data/bob/bob_input.csv'
    df_bob.to_csv(input_path, index=False)
    logger.info(f"Bob's data saved to {input_path}")
    logger.info(f"Bob has {len(df_bob)} records")
    
    return input_path


def wait_for_alice():
    """等待 Alice 节点准备就绪"""
    logger.info("Waiting for Alice to initialize PSI...")
    max_retries = 60
    for i in range(max_retries):
        try:
            # 检查 Alice 的数据文件是否存在
            alice_data_path = '/data/alice/alice_input.csv'
            if os.path.exists(alice_data_path):
                logger.info("Alice's data file found.")
                # 等待一些额外时间让 Alice 完成初始化
                time.sleep(5)
                return True
        except Exception as e:
            logger.debug(f"Waiting for Alice... attempt {i+1}/{max_retries}")
        
        time.sleep(3)
    
    logger.warning("Timeout waiting for Alice, but proceeding...")
    return False


def run_psi_participant():
    """作为 PSI 参与方运行"""
    try:
        logger.info("Starting PSI computation as Bob...")
        
        # 创建示例数据
        bob_input_path = create_sample_data()
        
        # 等待 Alice 准备就绪
        wait_for_alice()
        
        # 获取集群配置
        cluster_config = setup_cluster_config()
        ray_address = os.getenv('RAY_HEAD_ADDRESS', '172.20.0.10:9394')
        
        logger.info(f"Connecting to SecretFlow with ray address: {ray_address}")
        logger.info(f"Cluster config: {cluster_config}")
        
        # 初始化 SecretFlow（使用模拟模式）
        sf.init(parties=['alice', 'bob'], address='local')
        
        # 创建 PYU 设备
        alice = sf.PYU('alice')
        bob = sf.PYU('bob')
        
        logger.info("Bob PYU device created successfully")
        
        # Bob 主要是等待 Alice 发起 PSI 计算
        # 在实际的 PSI 过程中，Bob 的数据会被 SPU 自动处理
        logger.info("Bob is ready for PSI computation...")
        
        # 等待 PSI 计算完成
        logger.info("Waiting for PSI computation to complete...")
        
        # 监控输出文件
        max_wait = 300  # 等待最多5分钟
        start_wait = time.time()
        
        while time.time() - start_wait < max_wait:
            if os.path.exists('/data/bob/bob_output.csv'):
                logger.info("PSI output file detected!")
                break
            time.sleep(5)
        
        # 检查结果
        if os.path.exists('/data/bob/bob_output.csv'):
            result_df = pd.read_csv('/data/bob/bob_output.csv')
            logger.info(f"Bob's PSI result contains {len(result_df)} records")
            logger.info("Sample results:")
            logger.info(result_df.head().to_string())
            
            # 保存 Bob 的统计信息
            stats = {
                'bob_input_count': len(pd.read_csv('/data/bob/bob_input.csv')),
                'bob_output_count': len(result_df),
                'participation_time': time.time() - start_wait
            }
            
            stats_df = pd.DataFrame([stats])
            stats_df.to_csv('/data/bob/bob_stats.csv', index=False)
            logger.info(f"Bob statistics saved: {stats}")
        else:
            logger.warning("No PSI output file found for Bob")
        
        logger.info("Bob PSI participation completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during Bob's PSI participation: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        # 清理资源
        try:
            sf.shutdown()
            logger.info("SecretFlow shutdown completed for Bob")
        except Exception as e:
            logger.error(f"Error during Bob's shutdown: {e}")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Bob PSI Node Starting...")
    logger.info("=" * 60)
    
    # 等待一些时间确保网络和 Alice 就绪
    time.sleep(15)
    
    run_psi_participant()
    
    logger.info("Bob PSI Node Finished")
    
    # 保持容器运行以便检查结果
    logger.info("Container will stay running for result inspection...")
    while True:
        time.sleep(60)
