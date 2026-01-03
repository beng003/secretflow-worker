# SecretFlow 任务参数分析
# 基于实际PSI任务参数的结构化分析

secretflow_task_config:
  # 任务类型: PSI (Private Set Intersection) - 隐私集合求交
  task_type: "psi"
  domain: "data_prep"
  version: "1.0.0"
  
  # 数据源配置
  sf_datasource_config:
    description: "各参与方的数据源配置"
    parties:
      alice:
        id: "default-data-source"
        description: "Alice方数据源标识"
      bob:
        id: "default-data-source" 
        description: "Bob方数据源标识"
    
  # 集群描述配置
  sf_cluster_desc:
    description: "SecretFlow集群的完整配置描述"
    
    parties:
      - "alice"
      - "bob"
      description: "参与计算的所有参与方列表"
    
    # 设备配置
    devices:
      # SPU设备 (Secure Processing Unit)
      spu:
        name: "spu"
        type: "spu"
        parties: ["alice", "bob"]
        config:
          runtime_config:
            protocol: "SEMI2K"
            description: "半诚实安全协议，适用于两方计算"
            field: "FM128"
            description: "128位有限域，平衡安全性和性能"
          link_desc:
            connect_retry_times: 60
            connect_retry_interval_ms: 1000
            brpc_channel_protocol: "http"
            brpc_channel_connection_type: "pooled"
            recv_timeout_ms: 1200000  # 20分钟
            http_timeout_ms: 1200000   # 20分钟
            description: "网络连接配置，支持长时间计算任务"
      
      # HEU设备 (Homomorphic Encryption Unit)  
      heu:
        name: "heu"
        type: "heu"
        parties: ["alice", "bob"]
        config:
          mode: "PHEU"
          description: "部分同态加密模式"
          schema: "paillier"
          description: "Paillier同态加密方案"
          key_size: 2048
          description: "2048位密钥长度，提供强安全保障"
    
    # Ray联邦学习配置
    ray_fed_config:
      cross_silo_comm_backend: "brpc_link"
      description: "跨数据孤岛通信后端，使用BRPC协议"

  # 节点评估参数
  sf_node_eval_param:
    description: "PSI算法节点的具体执行参数"
    domain: "data_prep"
    name: "psi"
    version: "1.0.0"
    
    # 属性路径配置
    attr_paths:
      - "input/input_ds1/keys"      # Alice方输入数据的关键字段
      - "input/input_ds2/keys"      # Bob方输入数据的关键字段
      - "protocol"                  # PSI协议选择
      - "sort_result"              # 结果排序选项
      - "receiver_parties"         # 接收结果的参与方
      - "allow_empty_result"       # 是否允许空结果
      - "join_type"               # 连接类型
      - "input_ds1_keys_duplicated" # Alice方数据是否有重复键
      - "input_ds2_keys_duplicated" # Bob方数据是否有重复键
    
    # 属性值配置
    attrs:
      - is_na: false
        ss: ["id1"]
        description: "Alice方关键字段名称"
      
      - is_na: false  
        ss: ["id2"]
        description: "Bob方关键字段名称"
        
      - is_na: false
        s: "PROTOCOL_RR22"
        description: "使用RR22协议进行PSI计算"
        
      - b: true
        is_na: false
        description: "启用结果排序"
        
      - is_na: false
        ss: ["alice", "bob"]
        description: "Alice和Bob都接收计算结果"
        
      - is_na: true
        description: "允许空结果配置"
        
      - is_na: false
        s: "inner_join"
        description: "内连接方式，只保留交集"
        
      - b: true
        is_na: false
        description: "Alice方数据允许重复键"
        
      - b: true
        is_na: false  
        description: "Bob方数据允许重复键"

  # 输入输出配置
  sf_input_ids:
    - "alice-table"
    - "bob-table"
    description: "输入数据表的标识符"
    
  sf_output_ids:
    - "psi-output-0"
    - "psi-output-1"  
    description: "输出结果的标识符"
    
  sf_output_uris:
    - "psi-output-0"
    - "psi-output-1"
    description: "输出结果的URI路径"

# 任务执行分析
task_execution_analysis:
  security_level: "半诚实安全"
  computational_complexity: "中等"
  network_requirements: "稳定的参与方间通信"
  expected_duration: "取决于数据规模和网络延迟"
  
  # 关键技术点
  key_technologies:
    - "SEMI2K多方安全计算协议"
    - "Paillier同态加密"
    - "RR22 PSI协议"
    - "BRPC高性能RPC通信"
    - "Ray联邦学习框架"

# Worker端开发要点
worker_development_notes:
  task_integration:
    - "需要实现PSI任务的完整执行逻辑"
    - "支持多方数据源配置和验证"
    - "实现SPU和HEU设备的初始化和管理"
    - "处理网络通信和重试机制"
    
  status_reporting:
    - "集成任务状态监听系统"
    - "支持实时状态更新到Redis"
    - "处理计算进度和错误报告"
    - "记录详细的执行日志"
    
  security_considerations:
    - "确保密钥安全管理"
    - "验证参与方身份"
    - "保护中间计算结果"
    - "实现安全的数据传输"

# 与现有系统集成
integration_with_existing_system:
  redis_integration:
    - "使用task_status_events频道发布状态"
    - "支持task_status_queue队列机制"
    - "集成_publish_task_event通知器"
    
  container_coordination:
    - "Worker容器执行PSI计算"
    - "Web容器接收状态更新"
    - "数据库记录任务执行历史"
    
  error_handling:
    - "网络连接异常处理"
    - "计算错误恢复机制"  
    - "资源不足时的降级策略"