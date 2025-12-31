#!/usr/bin/env python3
"""
Alice 节点的 PSI 隐私计算脚本
负责初始化 SecretFlow 集群、配置 SPU 和执行 PSI 计算
"""

import os
import sys
import time
import logging
import pandas as pd
import secretflow as sf
from secretflow.utils.testing import cluster_def

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/alice/alice.log'),
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
        'self_party': 'alice'
    }


def create_sample_data():
    """创建 Alice 的示例数据"""
    logger.info("Creating sample data for Alice...")
    
    # Alice 的数据集 - 用户信息
    alice_data = {
        'user_id': [f'user_{i:04d}' for i in range(1, 1001)],  # 1000个用户
        'name': [f'Alice_User_{i}' for i in range(1, 1001)],
        'age': [(20 + (i * 7) % 50) for i in range(1, 1001)],
        'city': [['Beijing', 'Shanghai', 'Guangzhou', 'Shenzhen'][i % 4] for i in range(1, 1001)],
        'income': [(30000 + i * 100) for i in range(1, 1001)],
    }
    
    df_alice = pd.DataFrame(alice_data)
    
    # 确保数据目录存在
    os.makedirs('/data/alice', exist_ok=True)
    
    # 保存数据
    input_path = '/data/alice/alice_input.csv'
    df_alice.to_csv(input_path, index=False)
    logger.info(f"Alice's data saved to {input_path}")
    logger.info(f"Alice has {len(df_alice)} records")
    
    return input_path


def wait_for_bob():
    """等待 Bob 节点准备就绪"""
    logger.info("Waiting for Bob to be ready...")
    max_retries = 30
    for i in range(max_retries):
        try:
            # 检查 Bob 的数据文件是否存在
            bob_data_path = '/data/bob/bob_input.csv'
            if os.path.exists(bob_data_path):
                logger.info("Bob's data file found. Ready to proceed.")
                return True
        except Exception as e:
            logger.debug(f"Waiting for Bob... attempt {i+1}/{max_retries}")
        
        time.sleep(2)
    
    logger.warning("Timeout waiting for Bob, proceeding anyway...")
    return False


def run_psi():
    """执行 PSI 隐私计算"""
    try:
        logger.info("Starting PSI computation as Alice...")
        
        # 创建示例数据
        alice_input_path = create_sample_data()
        
        # 启动 Alice 的 Ray head 节点
        import ray
        logger.info("Starting Alice Ray head node...")
        ray.init(
            include_dashboard=False,
            ignore_reinit_error=True
        )
        logger.info("Alice Ray head node started successfully")
        
        # 等待 Bob 准备就绪
        wait_for_bob()
        
        # p2p 模式集群配置
        cluster_config = {
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
            'self_party': 'alice'
        }
        
        # Alice 连接到自己的 Ray head 地址（生产模式）
        alice_ray_address = 'localhost:10001'  # Ray默认端口
        
        logger.info(f"Initializing SecretFlow with Alice Ray address: {alice_ray_address}")
        logger.info(f"Cluster config: {cluster_config}")
        
        # 根据生产模式文档初始化 SecretFlow
        sf.init(address=alice_ray_address, cluster_config=cluster_config)
        
        # 创建 PYU 设备
        alice = sf.PYU('alice')
        bob = sf.PYU('bob')
        
        logger.info("PYU devices created successfully")
        
        # 配置 SPU 集群
        spu_cluster_def = {
            'nodes': [
                {
                    'party': 'alice', 
                    'address': '192.168.100.10:12945',
                    'listen_address': '0.0.0.0:12945'
                },
                {
                    'party': 'bob', 
                    'address': '192.168.100.20:12946',
                    'listen_address': '0.0.0.0:12946'
                },
            ],
            'runtime_config': {
                'protocol': 'REF2K',
                'field': 'FM64',
            },
        }
        
        # 创建 SPU 设备
        spu = sf.SPU(spu_cluster_def)
        logger.info("SPU device created successfully")
        
        # 设置 PSI 参数
        input_paths = {
            alice: '/data/alice/alice_input.csv',
            bob: '/data/bob/bob_input.csv'
        }
        
        output_paths = {
            alice: '/data/alice/alice_output.csv',
            bob: '/data/bob/bob_output.csv'
        }
        
        # 确保输出目录存在
        os.makedirs('/data/alice', exist_ok=True)
        
        logger.info("Starting PSI computation...")
        start_time = time.time()
        
        # 执行 PSI
        reports = spu.psi_csv(
            key='user_id',  # 交集计算的关键字段
            input_path=input_paths,
            output_path=output_paths,
            receiver='alice',  # Alice 接收结果
            protocol='KKRT_PSI_2PC',  # 使用 KKRT 协议
            precheck_input=True,
            sort=True,
            broadcast_result=False
        )
        
        computation_time = time.time() - start_time
        logger.info(f"PSI computation completed in {computation_time:.2f} seconds")
        logger.info(f"PSI reports: {reports}")
        
        # 读取并显示结果
        if os.path.exists('/data/alice/alice_output.csv'):
            result_df = pd.read_csv('/data/alice/alice_output.csv')
            logger.info(f"PSI result contains {len(result_df)} common records")
            logger.info("Sample results:")
            logger.info(result_df.head().to_string())
            
            # 保存统计信息
            stats = {
                'alice_input_count': len(pd.read_csv('/data/alice/alice_input.csv')),
                'intersection_count': len(result_df),
                'computation_time': computation_time,
                'protocol': 'KKRT_PSI_2PC'
            }
            
            stats_df = pd.DataFrame([stats])
            stats_df.to_csv('/data/alice/psi_stats.csv', index=False)
            logger.info(f"Statistics saved: {stats}")
        else:
            logger.error("PSI output file not found!")
        
        logger.info("PSI computation completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during PSI computation: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        # 清理资源
        try:
            sf.shutdown()
            logger.info("SecretFlow shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Alice PSI Node Starting...")
    logger.info("=" * 60)
    
    # 等待一些时间确保网络就绪
    time.sleep(10)
    
    run_psi()
    
    logger.info("Alice PSI Node Finished")
    
    # 保持容器运行以便检查结果
    logger.info("Container will stay running for result inspection...")
    while True:
        time.sleep(60)
